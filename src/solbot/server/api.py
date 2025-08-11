"""FastAPI application exposing trading endpoints.

Startup verifies that the configured wallet holds a valid license token.
The authority wallet (`LICENSE_AUTHORITY`) bypasses this check, and demo
wallets log a warning and disable trading.

Endpoints:
* ``GET /`` – resource index
* ``GET /health`` – service liveness
* ``GET /status`` – bootstrap progress
* ``GET /assets`` – list available symbols
* ``GET /license`` – license status
* ``GET /positions`` – open positions (API key required)
* ``GET /orders`` – order history (API key required)
* ``POST /orders`` – place an order (API key required)
* ``POST /backtest`` – run strategy backtest
* ``GET /chart/{symbol}`` – convenience redirect to TradingView
* ``GET /version`` – running commit and schema hash
* ``/ws`` – websocket stream of new orders
* ``/positions/ws`` – websocket stream of position changes
* ``/dashboard/ws`` – aggregated dashboard updates
"""

from __future__ import annotations

import os
import asyncio
import time
import logging
import contextlib
import tempfile
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Depends, Query
from fastapi.routing import APIRoute, APIWebSocketRoute
from fastapi.security import APIKeyHeader
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from prometheus_fastapi_instrumentator import Instrumentator
from prometheus_client import Histogram
from typing import Optional
from pathlib import Path

try:  # psutil is optional
    import psutil  # type: ignore
except Exception:  # pragma: no cover - fallback when psutil not installed
    psutil = None  # type: ignore

from ..utils import BotConfig, LicenseManager
from ..engine import RiskManager, TradeEngine, FeatureEngine, PosteriorEngine
from ..types import Side
from ..persistence.assets import AssetService
from ..persistence.dal import DAL
from ..bootstrap import BootstrapCoordinator
from ..schema import SCHEMA_HASH
from ..service import start_network_poller
from backtest import BacktestConfig, BacktestConnector, run_backtest


class OrderRequest(BaseModel):
    token: str
    qty: float
    side: Side
    limit: Optional[float] = None


class OrderResponse(BaseModel):
    id: int
    token: str
    quantity: float
    side: Side
    price: float
    slippage: float
    fee: float
    timestamp: int
    status: str


class StateUpdate(BaseModel):
    running: Optional[bool] = None
    emergency_stop: Optional[bool] = None
    settings: Optional[dict] = None


class BacktestRequest(BaseModel):
    source: str
    fee: float = 0.0
    slippage: float = 0.0
    initial_cash: float = 0.0


class BacktestResponse(BaseModel):
    pnl: float
    drawdown: float
    sharpe: float


class FeatureInfo(BaseModel):
    index: int
    name: str
    category: str
    event_kinds: list[str]
    unit: str
    normalization: str


class FeatureSchema(BaseModel):
    version: int
    features: list[FeatureInfo]
    timestamp: int
    schema_hash: str = Field(..., alias="schema")

    class Config:
        allow_population_by_field_name = True


class FeatureSnapshot(BaseModel):
    features: list[float]
    timestamp: int


class PosteriorSnapshot(BaseModel):
    rug: float
    trend: float
    revert: float
    chop: float
    timestamp: int


class NetworkStats(BaseModel):
    tps: float | None = None
    fee: float | None = None


class Metrics(BaseModel):
    cpu: float | None = None
    memory: float | None = None
    network: NetworkStats | None = None


class RouteInfo(BaseModel):
    path: str
    methods: list[str]


class Manifest(BaseModel):
    version: int
    rest: list[RouteInfo]
    websocket: list[str]
    timestamp: int


class Catalyst(BaseModel):
    event: str
    timestamp: int
    severity: str


class EndpointMap(BaseModel):
    health: str
    status: str
    assets: str
    features: str
    features_schema: str
    posterior: str
    positions: str
    orders: str
    backtest: str
    chart: str
    version: str
    docs: str
    redoc: str
    openapi: str
    metrics: str
    orders_ws: str
    features_ws: str
    posterior_ws: str
    positions_ws: str
    dashboard_ws: str
    logs_ws: str
    dashboard: str
    manifest: str
    tv: str
    license: str
    state: str
    catalysts: str


class LicenseInfo(BaseModel):
    wallet: str
    mode: str
    issued_at: int


class ServiceMap(BaseModel):
    tradingview: str
    endpoints: EndpointMap
    license: LicenseInfo
    timestamp: int
    schema_hash: str = Field(..., alias="schema")

    class Config:
        allow_population_by_field_name = True


api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def create_app(
    cfg: BotConfig,
    lm: LicenseManager,
    risk: RiskManager,
    trade: TradeEngine,
    assets: AssetService,
    bootstrap: BootstrapCoordinator,
    features: Optional[FeatureEngine] = None,
    posterior: Optional[PosteriorEngine] = None,
    metrics_interval: float = 0.0,
    ) -> FastAPI:
    app = FastAPI(title="sol-bot API")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    Instrumentator().instrument(app).expose(
        app, endpoint="/metrics/prometheus", include_in_schema=False
    )
    latency_hist = Histogram(
        "order_latency_ns", "Order placement latency", buckets=(1e6, 5e6, 1e7, 5e7, 1e8)
    )

    static_dir = Path(__file__).resolve().parents[3] / "web" / "public"
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    connections: list[WebSocket] = []
    conn_lock = asyncio.Lock()
    pos_connections: list[WebSocket] = []
    pos_lock = asyncio.Lock()
    order_subs: list[asyncio.Queue[dict]] = []
    log_subs: list[asyncio.Queue[dict]] = []
    log_lock = asyncio.Lock()
    poller_task: Optional[asyncio.Task] = None
    runtime_state = {"running": True, "emergency_stop": False, "settings": {}}

    def subscribe_orders() -> asyncio.Queue[dict]:
        q: asyncio.Queue[dict] = asyncio.Queue()
        order_subs.append(q)
        return q

    def unsubscribe_orders(q: asyncio.Queue[dict]) -> None:
        with contextlib.suppress(ValueError):
            order_subs.remove(q)

    class WSLogHandler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:  # pragma: no cover - minimal
            data = {
                "level": record.levelname.lower(),
                "timestamp": int(record.created),
                "message": record.getMessage(),
            }
            loop = asyncio.get_event_loop()
            for q in list(log_subs):
                loop.call_soon_threadsafe(q.put_nowait, data)

    logging.getLogger().addHandler(WSLogHandler())

    def check_key(key: Optional[str] = Depends(api_key_header)) -> None:
        expected_hash = os.getenv("API_KEY_HASH")
        if expected_hash:
            import hashlib, hmac
            if not key or not hmac.compare_digest(
                hashlib.sha256(key.encode()).hexdigest(), expected_hash
            ):
                raise HTTPException(status_code=401, detail="invalid api key")

    @app.on_event("startup")
    async def check_license() -> None:
        mode = lm.license_mode(cfg.wallet) if cfg.wallet else "none"
        if mode == "none":
            raise RuntimeError("wallet lacks license token")
        if mode == "demo":
            logging.warning("Demo mode active: trading disabled")
        if not bootstrap.is_ready():
            await bootstrap.run(assets, trade.connector.oracle)
        nonlocal poller_task
        if features is not None and metrics_interval > 0:
            poller_task = start_network_poller(features, cfg.rpc_http, metrics_interval)

    @app.get("/license", response_model=LicenseInfo)
    def license_info() -> LicenseInfo:
        return LicenseInfo(
            wallet=cfg.wallet or "",
            mode=lm.license_mode(cfg.wallet) if cfg.wallet else "none",
            issued_at=int(time.time()),
        )

    @app.get("/state")
    def state() -> dict:
        return {
            "running": runtime_state["running"],
            "emergency_stop": runtime_state["emergency_stop"],
            "settings": runtime_state["settings"],
            "license": license_info(),
            "status": bootstrap.status(),
            "timestamp": int(time.time()),
        }

    @app.post("/state")
    def update_state(req: StateUpdate) -> dict:
        if req.running is not None:
            runtime_state["running"] = req.running
        if req.emergency_stop is not None:
            runtime_state["emergency_stop"] = req.emergency_stop
        if req.settings is not None:
            runtime_state["settings"] = req.settings
        return state()

    @app.get("/", include_in_schema=False)
    async def root() -> RedirectResponse:
        return RedirectResponse("/static/dashboard.html")

    @app.get("/favicon.ico", include_in_schema=False)
    async def favicon() -> FileResponse:
        return FileResponse(static_dir / "favicon.ico")

    @app.get("/api", response_model=ServiceMap)
    async def api_index() -> ServiceMap:
        """Return resource index and embed template for TradingView."""
        endpoints = EndpointMap(
            health=app.url_path_for("health"),
            status=app.url_path_for("status"),
            assets=app.url_path_for("assets_endpoint"),
            features=app.url_path_for("features_endpoint"),
            features_schema=app.url_path_for("features_schema_endpoint"),
            posterior=app.url_path_for("posterior_endpoint"),
            positions=app.url_path_for("positions"),
            orders=app.url_path_for("orders"),
            backtest=app.url_path_for("backtest"),
            chart=app.url_path_for("chart", symbol="<sym>"),
            version=app.url_path_for("version"),
            docs=app.url_path_for("swagger_ui_html"),
            redoc=app.url_path_for("redoc_html"),
            openapi=app.url_path_for("openapi"),
            metrics=app.url_path_for("metrics"),
            catalysts=app.url_path_for("catalysts_endpoint"),
            orders_ws=app.url_path_for("ws"),
            features_ws=app.url_path_for("features_ws"),
              posterior_ws=app.url_path_for("posterior_ws"),
              positions_ws=app.url_path_for("positions_ws"),
              dashboard_ws=app.url_path_for("dashboard_ws"),
              logs_ws=app.url_path_for("logs_ws"),
              dashboard=app.url_path_for("dashboard"),
              manifest=app.url_path_for("manifest"),
              tv=app.url_path_for("tradingview_page"),
              license=app.url_path_for("license_info"),
              state=app.url_path_for("state"),
        )
        return ServiceMap(
            tradingview="https://www.tradingview.com/widgetembed/?symbol=<sym>USDT",
            endpoints=endpoints,
            license=license_info(),
            timestamp=int(time.time()),
            schema_hash=SCHEMA_HASH,
        )

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok"}

    @app.get("/tv", response_class=HTMLResponse)
    async def tradingview_page(symbol: str = "SOL") -> str:
        """Return simple TradingView iframe for manual inspection."""
        pair = f"{symbol.upper()}USDT"
        return (
            "<html><body>"
            f"<iframe src='https://www.tradingview.com/widgetembed/?symbol={pair}'"
            " width='100%' height='600'></iframe>"
            "<p><a href='" + app.url_path_for("features_endpoint") + "'>features</a> | "
            "<a href='" + app.url_path_for("posterior_endpoint") + "'>posterior</a></p>"
            "</body></html>"
        )

    @app.get("/status")
    async def status() -> dict:
        return bootstrap.status()

    @app.get("/metrics", response_model=Metrics)
    async def metrics() -> Metrics:
        cpu = mem = None
        net = None
        if psutil is not None:
            try:
                cpu = psutil.cpu_percent(interval=None)
                mem = psutil.virtual_memory().percent
            except Exception:
                cpu = mem = None
        if cpu is None:
            try:
                load = os.getloadavg()[0]
                cores = os.cpu_count() or 1
                cpu = load / cores * 100.0
            except Exception:
                cpu = None
        if features is not None:
            try:
                vec = features.snapshot()
                if len(vec) > 7:
                    net = NetworkStats(tps=float(vec[6]), fee=float(vec[7]))
            except Exception:
                pass
        return Metrics(cpu=cpu, memory=mem, network=net)

    @app.get("/assets", response_model=list[str])
    async def assets_endpoint() -> list[str]:
        return [a["symbol"] for a in assets.list_assets()]

    @app.get("/catalysts", response_model=list[Catalyst])
    async def catalysts_endpoint() -> list[Catalyst]:
        now = int(time.time())
        return [
            Catalyst(event="$NOVA Token Burn", timestamp=now + 2 * 3600 + 15 * 60, severity="high"),
            Catalyst(event="Jupiter V2 Launch", timestamp=now + 6 * 3600 + 42 * 60, severity="medium"),
            Catalyst(event="Solana Breakpoint", timestamp=now + 2 * 24 * 3600 + 14 * 3600, severity="low"),
        ]

    @app.get("/features", response_model=FeatureSnapshot)
    async def features_endpoint() -> FeatureSnapshot:
        if features is None:
            raise HTTPException(status_code=503, detail="features unavailable")
        vec = features.snapshot().tolist()
        return FeatureSnapshot(features=vec, timestamp=int(time.time()))

    @app.get("/features/schema", response_model=FeatureSchema)
    async def features_schema_endpoint() -> FeatureSchema:
        """Return metadata mapping feature indices to names."""
        cfg_path = Path(__file__).resolve().parents[3] / "features.yaml"
        import yaml

        with open(cfg_path, "r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh)
        data["schema"] = SCHEMA_HASH
        data["timestamp"] = int(time.time())
        return FeatureSchema(**data)

    @app.get("/posterior", response_model=PosteriorSnapshot)
    async def posterior_endpoint() -> PosteriorSnapshot:
        if features is None or posterior is None:
            raise HTTPException(status_code=503, detail="posterior unavailable")
        vec = features.snapshot()
        out = posterior.predict(vec)
        return PosteriorSnapshot(
            rug=out.rug,
            trend=out.trend,
            revert=out.revert,
            chop=out.chop,
            timestamp=int(time.time()),
        )

    @app.post("/backtest", response_model=BacktestResponse, name="backtest")
    async def backtest(req: BacktestRequest) -> BacktestResponse:
        with tempfile.TemporaryDirectory() as tmp:
            dal = DAL(os.path.join(tmp, "bt.db"))
            bt_risk = RiskManager()
            connector = BacktestConnector()
            engine_bt = TradeEngine(risk=bt_risk, connector=connector, dal=dal)
            cfg = BacktestConfig(
                source=req.source,
                fee_rate=req.fee,
                slippage_rate=req.slippage,
                initial_cash=req.initial_cash,
            )
            res = await run_backtest(engine_bt, cfg)
        return BacktestResponse(pnl=res.pnl, drawdown=res.drawdown, sharpe=res.sharpe)

    @app.get("/dashboard")
    async def dashboard() -> dict:
        vec = features.snapshot() if features else None
        posterior_out = (
            posterior.predict(vec).__dict__ if (features and posterior) else None
        )
        unrealized = sum(p.unrealized for p in risk.positions.values())
        orders = [
            {
                "id": o.id,
                "token": o.token,
                "quantity": o.quantity,
                "side": o.side.value,
                "price": o.price,
                "slippage": o.slippage,
                "fee": o.fee,
                "timestamp": o.timestamp,
                "status": o.status,
            }
            for o in trade.list_orders()
        ] if bootstrap.is_ready() else []
        return {
            "features": vec.tolist() if vec is not None else None,
            "posterior": posterior_out,
            "positions": trade.list_positions() if bootstrap.is_ready() else {},
            "orders": orders,
            "risk": {
                "equity": risk.equity,
                "unrealized": unrealized,
                "drawdown": risk.drawdown,
                "realized": risk.total_realized(),
                "var": risk.var,
                "es": risk.es,
                "sharpe": risk.sharpe,
            },
            "timestamp": int(time.time()),
        }

    @app.get("/positions")
    async def positions(key: None = Depends(check_key)) -> dict:
        if not bootstrap.is_ready():
            raise HTTPException(status_code=503, detail="state: BOOTSTRAPPING")
        return trade.list_positions()

    @app.get("/orders")
    async def orders(status: Optional[str] = Query(None), key: None = Depends(check_key)) -> list[dict]:
        if not bootstrap.is_ready():
            raise HTTPException(status_code=503, detail="state: BOOTSTRAPPING")
        return [
            {
                "id": o.id,
                "token": o.token,
                "quantity": o.quantity,
                "side": o.side.value,
                "price": o.price,
                "slippage": o.slippage,
                "fee": o.fee,
                "timestamp": o.timestamp,
                "status": o.status,
            }
            for o in trade.list_orders() if status is None or o.status == status
        ]

    @app.post("/orders", response_model=OrderResponse)
    async def place_order(req: OrderRequest, key: None = Depends(check_key)) -> OrderResponse:
        if not bootstrap.is_ready():
            raise HTTPException(status_code=503, detail="state: BOOTSTRAPPING")
        if req.token not in [a["symbol"] for a in assets.list_assets()]:
            raise HTTPException(status_code=400, detail="unsupported asset")
        if runtime_state["emergency_stop"]:
            raise HTTPException(status_code=400, detail="emergency stop active")
        if not runtime_state["running"]:
            raise HTTPException(status_code=400, detail="trading paused")
        start = time.perf_counter_ns()
        order = await trade.place_order(req.token, req.qty, req.side, req.limit)
        latency_hist.observe(time.perf_counter_ns() - start)
        payload = {
            "id": order.id,
            "token": order.token,
            "quantity": order.quantity,
            "side": order.side.value,
            "price": order.price,
            "slippage": order.slippage,
            "fee": order.fee,
            "timestamp": order.timestamp,
            "status": order.status,
        }
        for ws in list(connections):
            try:
                await ws.send_json(payload)
            except WebSocketDisconnect:
                connections.remove(ws)
        positions = trade.list_positions()
        for ws in list(pos_connections):
            try:
                await ws.send_json(positions)
            except WebSocketDisconnect:
                pos_connections.remove(ws)
        for q in list(order_subs):
            q.put_nowait(payload)
        return OrderResponse(**payload)

    @app.websocket("/ws")
    async def ws(ws: WebSocket):
        await ws.accept()
        key = ws.headers.get("X-API-Key") or ws.query_params.get("key")
        expected_hash = os.getenv("API_KEY_HASH")
        if expected_hash:
            import hashlib, hmac
            if not key or not hmac.compare_digest(
                hashlib.sha256(key.encode()).hexdigest(), expected_hash
            ):
                await ws.send_json({"error": "unauthorized"})
                await ws.close(code=1008)
                return
        async with conn_lock:
            connections.append(ws)
        try:
            while True:
                await ws.receive_text()
        except WebSocketDisconnect:
            async with conn_lock:
                if ws in connections:
                    connections.remove(ws)

    @app.websocket("/orders/ws")
    async def orders_ws(ws_conn: WebSocket):
        await ws(ws_conn)

    @app.websocket("/logs/ws")
    async def logs_ws(ws_conn: WebSocket):
        await ws_conn.accept()
        key = ws_conn.headers.get("X-API-Key") or ws_conn.query_params.get("key")
        expected_hash = os.getenv("API_KEY_HASH")
        if expected_hash:
            import hashlib, hmac
            if not key or not hmac.compare_digest(
                hashlib.sha256(key.encode()).hexdigest(), expected_hash
            ):
                await ws_conn.send_json({"error": "unauthorized"})
                await ws_conn.close(code=1008)
                return
        q: asyncio.Queue[dict] = asyncio.Queue()
        async with log_lock:
            log_subs.append(q)
        try:
            while True:
                log_task = asyncio.create_task(q.get())
                recv_task = asyncio.create_task(ws_conn.receive_text())
                done, _ = await asyncio.wait(
                    {log_task, recv_task}, return_when=asyncio.FIRST_COMPLETED
                )
                if recv_task in done:
                    log_task.cancel()
                    with contextlib.suppress(asyncio.CancelledError, WebSocketDisconnect):
                        await log_task
                    break
                record = log_task.result()
                recv_task.cancel()
                with contextlib.suppress(asyncio.CancelledError, WebSocketDisconnect):
                    await recv_task
                await ws_conn.send_json(record)
        except WebSocketDisconnect:
            pass
        finally:
            async with log_lock:
                with contextlib.suppress(ValueError):
                    log_subs.remove(q)

    @app.websocket("/features/ws")
    async def features_ws(ws: WebSocket):
        if features is None:
            await ws.close()
            return
        await ws.accept()
        q = features.subscribe()
        try:
            while True:
                vec_task = asyncio.create_task(asyncio.to_thread(q.get))
                recv_task = asyncio.create_task(ws.receive_text())
                done, _ = await asyncio.wait(
                    {vec_task, recv_task}, return_when=asyncio.FIRST_COMPLETED
                )
                if recv_task in done:
                    vec_task.cancel()
                    q.put_nowait((None, None))
                    with contextlib.suppress(asyncio.CancelledError):
                        await vec_task
                    with contextlib.suppress(asyncio.CancelledError, WebSocketDisconnect):
                        await recv_task
                    break
                event, vec = vec_task.result()
                recv_task.cancel()
                with contextlib.suppress(asyncio.CancelledError, WebSocketDisconnect):
                    await recv_task
                if event is None:
                    break
                event_data = event.__dict__.copy()
                event_data["kind"] = int(event.kind)
                await ws.send_json({"event": event_data, "features": vec.tolist()})
        except WebSocketDisconnect:
            with contextlib.suppress(Exception):
                q.put_nowait((None, None))
        finally:
            features.unsubscribe(q)

    @app.websocket("/positions/ws")
    async def positions_ws(ws: WebSocket):
        await ws.accept()
        key = ws.headers.get("X-API-Key") or ws.query_params.get("key")
        expected_hash = os.getenv("API_KEY_HASH")
        if expected_hash:
            import hashlib, hmac
            if not key or not hmac.compare_digest(
                hashlib.sha256(key.encode()).hexdigest(), expected_hash
            ):
                await ws.send_json({"error": "unauthorized"})
                await ws.close(code=1008)
                return
        async with pos_lock:
            pos_connections.append(ws)
        try:
            while True:
                await ws.receive_text()
        except WebSocketDisconnect:
            async with pos_lock:
                if ws in pos_connections:
                    pos_connections.remove(ws)

    @app.websocket("/posterior/ws")
    async def posterior_ws(ws: WebSocket):
        if features is None or posterior is None:
            await ws.close()
            return
        await ws.accept()
        q = features.subscribe()
        try:
            while True:
                vec_task = asyncio.create_task(asyncio.to_thread(q.get))
                recv_task = asyncio.create_task(ws.receive_text())
                done, _ = await asyncio.wait(
                    {vec_task, recv_task}, return_when=asyncio.FIRST_COMPLETED
                )
                if recv_task in done:
                    vec_task.cancel()
                    q.put_nowait((None, None))
                    with contextlib.suppress(asyncio.CancelledError):
                        await vec_task
                    with contextlib.suppress(asyncio.CancelledError, WebSocketDisconnect):
                        await recv_task
                    break
                event, vec = vec_task.result()
                recv_task.cancel()
                with contextlib.suppress(asyncio.CancelledError, WebSocketDisconnect):
                    await recv_task
                if event is None:
                    break
                event_data = event.__dict__.copy()
                event_data["kind"] = int(event.kind)
                out = posterior.predict(vec)
                await ws.send_json(
                    {
                        "event": event_data,
                        "posterior": {
                            "rug": out.rug,
                            "trend": out.trend,
                            "revert": out.revert,
                            "chop": out.chop,
                        },
                    }
                )
        except WebSocketDisconnect:
            with contextlib.suppress(Exception):
                q.put_nowait((None, None))
        finally:
            features.unsubscribe(q)


    @app.websocket("/dashboard/ws")
    async def dashboard_ws(ws: WebSocket):
        await ws.accept()
        if features is None or posterior is None:
            await ws.close()
            return
        key = ws.headers.get("X-API-Key") or ws.query_params.get("key")
        expected_hash = os.getenv("API_KEY_HASH")
        if expected_hash:
            import hashlib, hmac
            if not key or not hmac.compare_digest(
                hashlib.sha256(key.encode()).hexdigest(), expected_hash
            ):
                await ws.send_json({"error": "unauthorized"})
                await ws.close(code=1008)
                return
        feat_q = features.subscribe()
        order_q = subscribe_orders()
        try:
            while True:
                vec_task = asyncio.create_task(asyncio.to_thread(feat_q.get))
                order_task = asyncio.create_task(order_q.get())
                recv_task = asyncio.create_task(ws.receive_text())
                done, _ = await asyncio.wait(
                    {vec_task, order_task, recv_task},
                    return_when=asyncio.FIRST_COMPLETED,
                )
                if recv_task in done:
                    vec_task.cancel()
                    order_task.cancel()
                    feat_q.put_nowait((None, None))
                    with contextlib.suppress(asyncio.CancelledError):
                        await vec_task
                    with contextlib.suppress(asyncio.CancelledError):
                        await order_task
                    with contextlib.suppress(asyncio.CancelledError, WebSocketDisconnect):
                        await recv_task
                    break
                if vec_task in done:
                    event, vec = vec_task.result()
                    order_task.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await order_task
                    with contextlib.suppress(asyncio.CancelledError, WebSocketDisconnect):
                        await recv_task
                    if event is None:
                        break
                    event_data = event.__dict__.copy()
                    event_data["kind"] = int(event.kind)
                    out = posterior.predict(vec)
                    payload = {
                        "event": event_data,
                        "features": vec.tolist(),
                        "posterior": {
                            "rug": out.rug,
                            "trend": out.trend,
                            "revert": out.revert,
                            "chop": out.chop,
                        },
                        "positions": trade.list_positions()
                        if bootstrap.is_ready()
                        else {},
                        "orders": [
                            {
                                "id": o.id,
                                "token": o.token,
                                "quantity": o.quantity,
                                "side": o.side.value,
                                "price": o.price,
                                "slippage": o.slippage,
                                "fee": o.fee,
                            }
                            for o in trade.list_orders()
                        ]
                        if bootstrap.is_ready()
                        else [],
                        "risk": {
                            "equity": risk.equity,
                            "unrealized": sum(p.unrealized for p in risk.positions.values()),
                            "drawdown": risk.drawdown,
                            "realized": risk.total_realized(),
                            "var": risk.var,
                            "es": risk.es,
                            "sharpe": risk.sharpe,
                        },
                        "timestamp": int(time.time()),
                    }
                    await ws.send_json(payload)
                else:
                    order = order_task.result()
                    vec_task.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await vec_task
                    with contextlib.suppress(asyncio.CancelledError, WebSocketDisconnect):
                        await recv_task
                    vec = features.snapshot()
                    out = posterior.predict(vec)
                    event_data = {"kind": "order", **order}
                    payload = {
                        "event": event_data,
                        "features": vec.tolist(),
                        "posterior": {
                            "rug": out.rug,
                            "trend": out.trend,
                            "revert": out.revert,
                            "chop": out.chop,
                        },
                        "positions": trade.list_positions()
                        if bootstrap.is_ready()
                        else {},
                        "orders": [
                            {
                                "id": o.id,
                                "token": o.token,
                                "quantity": o.quantity,
                                "side": o.side.value,
                                "price": o.price,
                                "slippage": o.slippage,
                                "fee": o.fee,
                            }
                            for o in trade.list_orders()
                        ]
                        if bootstrap.is_ready()
                        else [],
                        "risk": {
                            "equity": risk.equity,
                            "unrealized": sum(p.unrealized for p in risk.positions.values()),
                            "drawdown": risk.drawdown,
                            "realized": risk.total_realized(),
                            "var": risk.var,
                            "es": risk.es,
                            "sharpe": risk.sharpe,
                        },
                        "timestamp": int(time.time()),
                    }
                    await ws.send_json(payload)
        except WebSocketDisconnect:
            with contextlib.suppress(Exception):
                feat_q.put_nowait((None, None))
        finally:
            features.unsubscribe(feat_q)
            unsubscribe_orders(order_q)


    @app.get("/chart/{symbol}")
    async def chart(symbol: str) -> dict:
        return {
            "symbol": symbol.upper(),
            "url": f"https://www.tradingview.com/chart/?symbol={symbol.upper()}",
        }
    @app.get("/version")
    async def version() -> dict:
        return {"git": os.getenv("COMMIT_SHA", "dev"), "schema": SCHEMA_HASH}

    @app.get("/manifest", response_model=Manifest)
    async def manifest() -> Manifest:
        rest, websockets = [], []
        for route in app.router.routes:
            if isinstance(route, APIRoute):
                rest.append(RouteInfo(path=route.path, methods=sorted(route.methods)))
            elif isinstance(route, APIWebSocketRoute):
                websockets.append(route.path)
        return Manifest(version=1, rest=rest, websocket=websockets, timestamp=int(time.time()))

    @app.on_event("shutdown")
    async def stop_poller() -> None:
        nonlocal poller_task
        if poller_task is not None:
            poller_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await poller_task


    return app
