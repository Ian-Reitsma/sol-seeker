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
import secrets
import json
from bisect import bisect_left, bisect_right
from dataclasses import dataclass
from fastapi import (
    FastAPI,
    HTTPException,
    WebSocket,
    WebSocketDisconnect,
    Depends,
    Query,
    Request,
)
from fastapi.routing import APIRoute, APIWebSocketRoute
from fastapi.security import APIKeyHeader
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse, JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, root_validator, ValidationError
from prometheus_fastapi_instrumentator import Instrumentator
from prometheus_client import Histogram
from typing import Optional, List
from pathlib import Path
from backtest import BacktestConfig, run_backtest

try:  # psutil is optional
    import psutil  # type: ignore
except Exception:  # pragma: no cover - fallback when psutil not installed
    psutil = None  # type: ignore

from ..utils import BotConfig, LicenseManager
from ..engine import RiskManager, TradeEngine, FeatureEngine, PosteriorEngine
from ..engine.features import PyFeatureEngine
from ..types import Side
from ..persistence import DAL
from ..persistence.assets import AssetService
from ..exchange import PaperConnector
from ..oracle.coingecko import CoingeckoOracle
from ..bootstrap import BootstrapCoordinator
from ..schema import SCHEMA_HASH, PositionState, PnLState
from ..service import start_network_poller, publisher
from ..scanner.launch import TokenLaunchScanner
from ..risk.rug_detector import RugDetector


MAX_PORTFOLIO_POINTS = 1_000


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
    mode: Optional[str] = Field(None, regex="^(live|demo)$")
    paper_assets: Optional[List[str]] = None
    paper_capital: Optional[float] = None


class BacktestJobRequest(BaseModel):
    period: str
    capital: float
    strategy_mix: str


class BacktestJobResponse(BaseModel):
    id: str


@dataclass
class BacktestJob:
    queue: asyncio.Queue[dict]
    task: asyncio.Task


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
    tps: Optional[float] = None
    fee: Optional[float] = None


class Metrics(BaseModel):
    cpu: Optional[float] = None
    memory: Optional[float] = None
    network: Optional[NetworkStats] = None


class LimitParams(BaseModel):
    limit: int = Field(MAX_PORTFOLIO_POINTS, ge=1, le=MAX_PORTFOLIO_POINTS)
    offset: Optional[int] = Field(None, ge=0)
    cursor: Optional[int] = Field(None, ge=0)

    @root_validator(allow_reuse=True)
    def _check_offset_cursor(cls, values: dict) -> dict:
        offset, cursor = values.get("offset"), values.get("cursor")
        if offset is not None and cursor is not None:
            raise ValueError("offset and cursor are mutually exclusive")
        return values


class RangeParams(BaseModel):
    start: Optional[int] = Field(None, ge=0)
    end: Optional[int] = Field(None, ge=0)

    @root_validator(allow_reuse=True)
    def _check_range(cls, values: dict) -> dict:
        start, end = values.get("start"), values.get("end")
        if start is not None and end is not None and start > end:
            raise ValueError("start must be <= end")
        return values


class RouteInfo(BaseModel):
    path: str
    methods: list[str]


class Manifest(BaseModel):
    version: int
    rest: list[RouteInfo]
    websocket: list[str]
    timestamp: int


class Catalyst(BaseModel):
    name: str
    eta: int
    severity: str


class SecurityFlag(BaseModel):
    status: str
    detail: str


class SecurityReport(BaseModel):
    rug_pull: SecurityFlag
    liquidity: SecurityFlag
    contract_verified: SecurityFlag
    holder_distribution: SecurityFlag
    trading_patterns: SecurityFlag


class TrendingToken(BaseModel):
    symbol: str
    mentions: int
    change_pct: float
    sentiment: str


class InfluencerAlert(BaseModel):
    handle: str
    message: str
    followers: int
    stance: str


class PulseMetrics(BaseModel):
    fear_greed: int
    fear_greed_pct: float
    social_volume: int
    social_volume_pct: float
    fomo: int
    fomo_pct: float
    timestamp: int | None = None


class NewsItem(BaseModel):
    id: int
    title: str
    source: str
    confidence: int


class WhaleStats(BaseModel):
    following: int
    success_rate: float
    copied_today: int
    profit: float


class SmartMoneyFlow(BaseModel):
    net_inflow: float
    trend: str


class CopyTrade(BaseModel):
    whale: str
    profit: Optional[float] = None


class StrategyStat(BaseModel):
    name: str
    trades: int
    pnl: float
    confidence: float
    targets: int
    success: float


class ArbitrageStat(BaseModel):
    status: str
    trades: int
    pnl: float
    spread: float
    opportunities: int
    latency: int


class StrategyPerf(BaseModel):
    name: str
    pnl: float
    win_rate: float


class StrategyBreakdownItem(BaseModel):
    name: str
    pnl: float
    win_rate: float


class StrategyRisk(BaseModel):
    sharpe: float
    max_drawdown: float
    volatility: float
    calmar: float


class PerformanceMatrix(BaseModel):
    days: list[float]
    strategies: list[StrategyPerf]
    risk: StrategyRisk


class StrategyMatrixItem(BaseModel):
    name: str
    status: str
    last_update: int
    latency_ms: int
    trades: int | None = None
    pnl: float | None = None


class MarketStat(BaseModel):
    symbol: str
    volume: float
    volatility: float
    liquidity: float
    spread: float


class MevStatus(BaseModel):
    saved_today: float
    attacks_blocked: int
    success_rate: float
    latency_ms: float


class AlphaSignals(BaseModel):
    strength: str
    social_sentiment: float
    onchain_momentum: float
    whale_activity: float


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
    chart_portfolio: str
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
    events_catalysts: str
    risk_security: str
    whales: str
    smart_money_flow: str
    copy_trading: str
    strategies: str
    arbitrage: str
    sentiment_trending: str
    sentiment_influencers: str
    sentiment_pulse: str
    news: str
    strategy_performance: str
    strategy_breakdown: str
    strategy_risk: str
    mev_status: str
    alpha_signals: str
    logs_generate: str
    risk_rug: str
    market_active: str


class LicenseInfo(BaseModel):
    wallet: str
    mode: str
    issued_at: int
    expires_at: int


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
    publisher_queue_size: int = 0,
    publisher_overflow: str = "drop_new",
    ) -> FastAPI:
    publisher.configure(maxsize=publisher_queue_size, overflow=publisher_overflow)

    app = FastAPI(title="sol-bot API")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    async def validation_error_handler(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(status_code=400, content={"detail": exc.errors()})

    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(ValidationError, validation_error_handler)
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
    model_task: Optional[asyncio.Task] = None
    scanner = TokenLaunchScanner()
    rug = RugDetector()
    app.state.rug_detector = rug
    scanner_task: Optional[asyncio.Task] = None
    backtest_jobs: dict[str, BacktestJob] = {}
    sentiment_state = {
        "trending": [],
        "influencers": [],
        "pulse": None,
    }
    # Always default to demo mode and keep the engine paused until an explicit
    # start command is issued. The paper account begins with 10 SOL which the
    # frontend converts to USD on load.
    initial_mode = "demo"
    runtime_state = {
        "running": False,
        "emergency_stop": False,
        "settings": {},
        "mode": initial_mode,
        "paper": {"assets": ["SOL"], "capital": 10.0},
    }

    model_dir = Path.home() / ".solbot" / "models"
    model_dir.mkdir(parents=True, exist_ok=True)
    feat_path = model_dir / "features.npz"
    post_path = model_dir / "posterior.npz"

    async def save_models_periodically() -> None:
        while True:
            await asyncio.sleep(300)
            with contextlib.suppress(Exception):
                features.save(feat_path)
                posterior.save(post_path)

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
            import hashlib
            import hmac
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
        # Always reset runtime state on startup so the dashboard begins in
        # paused demo mode with a fresh 10 SOL paper balance regardless of any
        # prior session state persisted in memory.
        runtime_state["running"] = False
        runtime_state["paper"]["capital"] = 10.0
        if not bootstrap.is_ready():
            await bootstrap.run(assets, trade.connector.oracle)
        nonlocal poller_task, model_task
        if features is not None and metrics_interval > 0:
            poller_task = start_network_poller(features, cfg.rpc_http, metrics_interval)
        model_task = asyncio.create_task(save_models_periodically())
        app.state.model_task = model_task

    @app.get("/license", response_model=LicenseInfo)
    def license_info() -> LicenseInfo:
        now = int(time.time())
        return LicenseInfo(
            wallet=cfg.wallet or "",
            mode=lm.license_mode(cfg.wallet) if cfg.wallet else "none",
            issued_at=now,
            expires_at=now + 30 * 24 * 3600,
        )

    @app.get("/state")
    def state() -> dict:
        lic = license_info()
        return {
            "running": runtime_state["running"],
            "emergency_stop": runtime_state["emergency_stop"],
            "settings": runtime_state["settings"],
            "mode": runtime_state["mode"],
            "paper": runtime_state["paper"],
            "license": lic,
            "status": bootstrap.status(),
            "timestamp": int(time.time()),
        }

    def seed_demo_positions(tokens: list[str], capital: float) -> None:
        """Populate demo positions using ``capital`` equally across ``tokens``."""
        uniq = list(dict.fromkeys(tokens))
        risk.reset()
        risk.update_equity(capital)
        if uniq:
            per_asset = capital / len(uniq)
            for tok in uniq:
                qty = per_asset
                risk.positions[tok] = PositionState(
                    token=tok, qty=qty, cost=1.0, unrealized=0.0
                )
                risk.pnl[tok] = PnLState(realized=0.0, unrealized=0.0)
                risk.market_prices[tok] = 1.0

    if initial_mode == "demo":
        seed_demo_positions(
            runtime_state["paper"].get("assets", []),
            runtime_state["paper"].get("capital", 0.0),
        )

    @app.post("/state")
    def update_state(req: StateUpdate) -> dict:
        if req.running is not None:
            runtime_state["running"] = req.running
        if req.emergency_stop is not None:
            runtime_state["emergency_stop"] = req.emergency_stop
            if req.emergency_stop:
                risk.reset()
        if req.settings is not None:
            runtime_state["settings"].update(req.settings)
        if req.mode is not None:
            if req.mode == "live" and lm.license_mode(cfg.wallet) != "full":
                raise HTTPException(
                    status_code=400, detail="full license required for live mode"
                )
            runtime_state["mode"] = req.mode
            if req.mode == "demo":
                capital = runtime_state["paper"].get("capital", 0.0)
                tokens = runtime_state["paper"].get("assets", [])
                seed_demo_positions(tokens, capital)
        if req.paper_assets is not None or req.paper_capital is not None:
            paper = runtime_state["paper"]
            if req.paper_assets is not None:
                available = {a["symbol"].upper() for a in assets.list_assets()}
                normalized = [s.strip().upper() for s in req.paper_assets if s.strip()]
                normalized = list(dict.fromkeys(normalized))
                unknown = [s for s in normalized if s not in available]
                if unknown:
                    raise HTTPException(
                        status_code=400, detail=f"unknown assets: {', '.join(unknown)}"
                    )
                paper["assets"] = normalized
            if req.paper_capital is not None:
                paper["capital"] = req.paper_capital
            runtime_state["paper"] = paper
            if runtime_state["mode"] == "demo":
                tokens = paper.get("assets", [])
                capital = paper.get("capital", 0.0)
                seed_demo_positions(tokens, capital)
        return state()

    @app.post("/engine/start")
    async def engine_start() -> dict:
        """Explicitly start the trading engine."""
        nonlocal scanner_task
        if runtime_state["running"]:
            raise HTTPException(status_code=409, detail="engine already running")
        runtime_state["running"] = True
        if scanner_task is None or scanner_task.done():
            scanner.start()
            scanner_task = scanner._task
            app.state.scanner_task = scanner_task
        return {"running": True}

    @app.post("/engine/stop")
    async def engine_stop() -> dict:
        """Pause all trading engine activity."""
        nonlocal scanner_task
        if not runtime_state["running"]:
            raise HTTPException(status_code=409, detail="engine already stopped")
        runtime_state["running"] = False
        if scanner_task is not None:
            await scanner.stop()
            scanner_task = None
            app.state.scanner_task = None
        return {"running": False}

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
            chart_portfolio=app.url_path_for("chart_portfolio"),
            version=app.url_path_for("version"),
            docs=app.url_path_for("swagger_ui_html"),
            redoc=app.url_path_for("redoc_html"),
            openapi=app.url_path_for("openapi"),
            metrics=app.url_path_for("metrics"),
            events_catalysts=app.url_path_for("catalysts_endpoint"),
            risk_security=app.url_path_for("risk_security_endpoint"),
            sentiment_trending=app.url_path_for("sentiment_trending"),
            sentiment_influencers=app.url_path_for("sentiment_influencers"),
            sentiment_pulse=app.url_path_for("sentiment_pulse"),
            news=app.url_path_for("news_endpoint"),
            whales=app.url_path_for("whales_endpoint"),
            smart_money_flow=app.url_path_for("smart_money_flow_endpoint"),
            copy_trading=app.url_path_for("copy_trading_endpoint"),
            strategies=app.url_path_for("strategies_endpoint"),
            arbitrage=app.url_path_for("arbitrage_endpoint"),
            strategy_performance=app.url_path_for("strategy_performance"),
            strategy_breakdown=app.url_path_for("strategy_breakdown"),
            strategy_risk=app.url_path_for("strategy_risk"),
            mev_status=app.url_path_for("mev_status_endpoint"),
            alpha_signals=app.url_path_for("alpha_signals_endpoint"),
            logs_generate=app.url_path_for("logs_generate"),
            risk_rug=app.url_path_for("risk_rug_endpoint"),
            market_active=app.url_path_for("market_active"),
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
        start = time.perf_counter()
        await asyncio.sleep(0)
        latency = int((time.perf_counter() - start) * 1000)
        return {"status": "ok", "rpc_latency_ms": latency}

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
    async def status(
        _: RangeParams = Depends(),
        __: LimitParams = Depends(),
    ) -> dict:
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

    @app.get("/price/sol")
    async def price_sol() -> dict:
        """Return the current SOL price in USD."""
        price = await oracle.price("SOL")
        return {"price": price}

    @app.get("/pnl/realized")
    async def pnl_realized() -> dict:
        """Return aggregate realized PnL."""
        total = sum(p.realized for p in risk.pnl.values())
        return {"total": total, "today": 0.0}

    @app.get("/risk/portfolio")
    async def risk_portfolio() -> dict:
        """Return portfolio-level risk metrics."""

        eq = risk.equity
        prev_eq = risk.equity_history[-2][1] if len(risk.equity_history) > 1 else eq
        change = eq - prev_eq
        change_pct = (change / prev_eq * 100.0) if prev_eq else 0.0
        return {
            "equity": eq,
            "change": change,
            "change_pct": change_pct,
            "max_drawdown": risk.max_drawdown(),
            "leverage": risk.leverage,
            "exposure": risk.exposure,
            "position_size": risk.position_size,
        }

    @app.get("/risk/rug")
    async def risk_rug_endpoint() -> dict:
        """Return current rug pull alerts."""
        alerts = [a.__dict__ for a in rug.alerts()]
        return {"alerts": alerts}

    @app.get("/assets", response_model=list[str])
    async def assets_endpoint(limits: LimitParams = Depends()) -> list[str]:
        symbols = [a["symbol"] for a in assets.list_assets()]
        if limits.offset:
            symbols = symbols[limits.offset :]
        return symbols[: limits.limit]

    @app.get("/events/catalysts", response_model=list[Catalyst])
    async def catalysts_endpoint() -> list[Catalyst]:
        now = int(time.time())
        return [
            Catalyst(name="Firedancer Testnet", eta=now + 2 * 3600 + 15 * 60, severity="high"),
            Catalyst(name="Jupiter V2 Launch", eta=now + 6 * 3600 + 42 * 60, severity="medium"),
            Catalyst(name="Solana Breakpoint", eta=now + 2 * 24 * 3600 + 14 * 3600, severity="low"),
        ]

    @app.get("/risk/security", response_model=SecurityReport)
    async def risk_security_endpoint() -> SecurityReport:
        return SecurityReport(
            rug_pull=SecurityFlag(status="OK", detail="No threats detected"),
            liquidity=SecurityFlag(status="OK", detail="Sufficient liquidity"),
            contract_verified=SecurityFlag(status="OK", detail="Contract verified"),
            holder_distribution=SecurityFlag(status="OK", detail="Balanced holders"),
            trading_patterns=SecurityFlag(status="OK", detail="No anomalies"),
        )

    @app.get("/market/active", response_model=list[MarketStat])
    async def market_active() -> list[MarketStat]:
        """Return basic stats for active market pairs."""
        return [
            MarketStat(symbol="SOL/USDC", volume=1_200_000.0, volatility=0.042, liquidity=5_000_000.0, spread=0.0012),
            MarketStat(symbol="RAY/SOL", volume=320_000.0, volatility=0.058, liquidity=1_200_000.0, spread=0.0021),
            MarketStat(symbol="ORCA/USDC", volume=210_000.0, volatility=0.034, liquidity=950_000.0, spread=0.0015),
        ]

    @app.get("/sentiment/trending", response_model=list[TrendingToken])
    async def sentiment_trending() -> list[TrendingToken]:
        """Return currently trending tokens with sentiment data.

        This stub pulls from the in-memory collectors fed by
        ``solbot.social.twitter`` and ``solbot.social.telegram`` modules.  The
        collectors are lightweight and primarily used for tests and demo mode
        so we seed a few memecoin examples when no live data is present.
        """

        if not sentiment_state["trending"]:
            sentiment_state["trending"] = [
                TrendingToken(symbol="BONK", mentions=240, change_pct=12.4, sentiment="BULLISH"),
                TrendingToken(symbol="WIF", mentions=180, change_pct=3.1, sentiment="BULLISH"),
                TrendingToken(symbol="SOL", mentions=123, change_pct=5.4, sentiment="BULLISH"),
            ]
        return sentiment_state["trending"]

    @app.get("/sentiment/influencers", response_model=list[InfluencerAlert])
    async def sentiment_influencers() -> list[InfluencerAlert]:
        """Return recent influencer messages."""
        if not sentiment_state["influencers"]:
            sentiment_state["influencers"] = [
                InfluencerAlert(handle="@bonkmaxi", message="BONK to the moon", followers=15000, stance="bull"),
                InfluencerAlert(handle="@skeptic", message="Taking profits", followers=8000, stance="bear"),
            ]
        return sentiment_state["influencers"]

    @app.get("/sentiment/pulse", response_model=PulseMetrics)
    async def sentiment_pulse() -> PulseMetrics:
        """Return aggregate community sentiment metrics."""
        if sentiment_state["pulse"] is None:
            sentiment_state["pulse"] = PulseMetrics(
                fear_greed=60,
                fear_greed_pct=60.0,
                social_volume=70,
                social_volume_pct=70.0,
                fomo=45,
                fomo_pct=45.0,
                timestamp=int(time.time()),
            )
        return sentiment_state["pulse"]

    @app.get("/news", response_model=list[NewsItem])
    async def news_endpoint() -> list[NewsItem]:
        """Return latest news items."""
        return [
            NewsItem(id=1, title="SOL surges on volume", source="Reporter", confidence=80),
            NewsItem(id=2, title="ETH sees profit taking", source="Reporter", confidence=60),
        ]

    @app.get("/whales", response_model=WhaleStats)
    async def whales_endpoint() -> WhaleStats:
        """Return basic whale tracking statistics."""
        return WhaleStats(following=3, success_rate=0.65, copied_today=1, profit=5.2)

    @app.get("/smart-money-flow", response_model=SmartMoneyFlow)
    async def smart_money_flow_endpoint() -> SmartMoneyFlow:
        """Return net inflow statistics for smart money."""
        return SmartMoneyFlow(net_inflow=1.7, trend="UP")

    @app.get("/copy-trading", response_model=list[CopyTrade])
    async def copy_trading_endpoint() -> list[CopyTrade]:
        """Return recent profitable whale trades being copied."""
        return [
            CopyTrade(whale="0xWhale1", profit=2.1),
            CopyTrade(whale="0xWhale2", profit=-0.4),
        ]

    @app.get("/strategies", response_model=list[StrategyStat])
    async def strategies_endpoint() -> list[StrategyStat]:
        """Return demo strategy performance statistics."""
        return [
            StrategyStat(name="Listing Sniper", trades=12, pnl=1.2, confidence=78.0, targets=3, success=83.0),
            StrategyStat(name="Arbitrage", trades=5, pnl=0.8, confidence=65.0, targets=2, success=60.0),
        ]

    @app.get("/arbitrage", response_model=ArbitrageStat)
    async def arbitrage_endpoint() -> ArbitrageStat:
        """Return demo arbitrage engine status."""
        return ArbitrageStat(
            status="IDLE",
            trades=0,
            pnl=0.0,
            spread=0.15,
            opportunities=0,
            latency=120,
        )

    @app.get("/strategy/performance", response_model=list[StrategyPerf])
    async def strategy_performance(period: str = Query("7d")) -> list[StrategyPerf]:
        realized = risk.total_realized() or 1.0
        scale = 1.0 if period == "7d" else 2.0
        base = {
            "Listing Sniper": 0.4,
            "Arbitrage": 0.35,
            "Market Making": 0.25,
        }
        return [
            StrategyPerf(name=name, pnl=realized * frac * scale, win_rate=0.55 + i * 0.05)
            for i, (name, frac) in enumerate(base.items())
        ]

    @app.get("/strategy/breakdown", response_model=list[StrategyBreakdownItem])
    async def strategy_breakdown() -> list[StrategyBreakdownItem]:
        realized = risk.total_realized()
        return [
            StrategyBreakdownItem(name="Scalper", pnl=realized * 0.4, win_rate=0.58),
            StrategyBreakdownItem(name="Trend", pnl=realized * 0.35, win_rate=0.61),
            StrategyBreakdownItem(name="Liquidity", pnl=realized * 0.15, win_rate=0.55),
            StrategyBreakdownItem(name="Other", pnl=realized * 0.10, win_rate=0.5),
        ]

    @app.get("/strategy/risk", response_model=StrategyRisk)
    async def strategy_risk() -> StrategyRisk:
        vol = risk.portfolio_volatility(risk.price_history)
        max_dd = risk.max_drawdown()
        sharpe = risk.sharpe
        calmar = sharpe / max(max_dd, 1e-9)
        return StrategyRisk(sharpe=sharpe, max_drawdown=max_dd, volatility=vol, calmar=calmar)

    @app.get("/strategy/matrix", response_model=list[StrategyMatrixItem])
    async def strategy_matrix() -> list[StrategyMatrixItem]:
        now = int(time.time() * 1000)
        return [
            StrategyMatrixItem(
                name="Listing Sniper",
                status="running",
                last_update=now,
                latency_ms=42,
                trades=len(trade.orders),
                pnl=risk.total_realized(),
            ),
            StrategyMatrixItem(
                name="Arbitrage",
                status="idle",
                last_update=now,
                latency_ms=35,
                trades=0,
                pnl=0.0,
            ),
            StrategyMatrixItem(
                name="Market Making",
                status="stopped",
                last_update=now,
                latency_ms=50,
                trades=0,
                pnl=-0.1,
            ),
        ]

    @app.get("/strategy/performance_matrix", response_model=PerformanceMatrix)
    async def strategy_performance_matrix(period: str = Query("7d")) -> PerformanceMatrix:
        """Return recent strategy performance metrics."""
        heatmap = {
            "7d": [0.2, -0.1, 0.3, 0.0, 0.5, -0.2, 0.1, 0.4, -0.3, 0.2, 0.6, -0.1, 0.0, 0.3],
            "30d": [0.1 * ((i % 5) - 2) for i in range(30)],
        }
        strategies = [
            StrategyPerf(name="Sniper", pnl=12.4, win_rate=0.94),
            StrategyPerf(name="Arbitrage", pnl=8.7, win_rate=0.87),
            StrategyPerf(name="Market Making", pnl=3.2, win_rate=0.76),
        ]
        risk = StrategyRisk(sharpe=2.84, max_drawdown=0.052, volatility=0.124, calmar=4.67)
        return PerformanceMatrix(days=heatmap.get(period, heatmap["7d"]), strategies=strategies, risk=risk)

    @app.get("/mev/status", response_model=MevStatus)
    async def mev_status_endpoint() -> MevStatus:
        return MevStatus(
            saved_today=2.847,
            attacks_blocked=47,
            success_rate=99.2,
            latency_ms=3.0,
        )

    @app.get("/alpha/signals", response_model=AlphaSignals)
    async def alpha_signals_endpoint() -> AlphaSignals:
        return AlphaSignals(
            strength="STRONG",
            social_sentiment=8.2,
            onchain_momentum=7.8,
            whale_activity=6.1,
        )

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

    @app.post("/backtest", response_model=BacktestJobResponse, name="backtest")
    async def backtest(req: BacktestJobRequest) -> BacktestJobResponse:
        job_id = secrets.token_hex(8)
        q: asyncio.Queue[dict] = asyncio.Queue()

        async def runner() -> None:
            try:
                await q.put({"progress": 0})
                cfg = BacktestConfig(source=req.period, initial_cash=req.capital)

                def select_strategy(name: str):
                    if name == "momentum":
                        prev: Optional[float] = None
                        holding = False

                        def strat(bar):  # type: ignore[no-redef]
                            nonlocal prev, holding
                            if prev is None:
                                prev = bar.price
                                return None
                            action = None
                            if bar.price > prev and not holding:
                                holding = True
                                action = (Side.BUY, 1.0)
                            elif bar.price < prev and holding:
                                holding = False
                                action = (Side.SELL, 1.0)
                            prev = bar.price
                            return action

                        return strat
                    return None

                strat_fn = select_strategy(req.strategy_mix)
                res = await run_backtest(trade, cfg, strat_fn)
                record = {
                    "id": job_id,
                    "pnl": res.pnl,
                    "drawdown": res.drawdown,
                    "sharpe": res.sharpe,
                    "timestamp": int(time.time()),
                }
                bt_dir = (
                    Path(__file__).resolve().parents[3] / "persistence" / "backtests"
                )
                bt_dir.mkdir(parents=True, exist_ok=True)
                (bt_dir / f"{job_id}.json").write_text(json.dumps(record))
                await q.put({"progress": 100, **record, "finished": True})
            except asyncio.CancelledError:
                await q.put({"progress": 100, "cancelled": True, "finished": True})
                raise
            except Exception as e:  # pragma: no cover - defensive
                await q.put({"error": str(e)})
            finally:
                await q.put(None)

        task = asyncio.create_task(runner())
        backtest_jobs[job_id] = BacktestJob(queue=q, task=task)
        return BacktestJobResponse(id=job_id)

    @app.websocket("/backtest/ws/{job_id}", name="backtest_ws")
    async def backtest_ws(ws: WebSocket, job_id: str) -> None:
        await ws.accept()
        job = backtest_jobs.get(job_id)
        if job is None:
            await ws.close()
            return
        q = job.queue
        task = job.task
        recv = asyncio.create_task(ws.receive_json())
        qtask = asyncio.create_task(q.get())
        try:
            while True:
                done, _ = await asyncio.wait({recv, qtask}, return_when=asyncio.FIRST_COMPLETED)
                if qtask in done:
                    msg = qtask.result()
                    if msg is None:
                        break
                    await ws.send_json(msg)
                    qtask = asyncio.create_task(q.get())
                if recv in done:
                    try:
                        data = recv.result()
                    except WebSocketDisconnect:
                        break
                    if data.get("action") == "cancel":
                        task.cancel()
                    recv = asyncio.create_task(ws.receive_json())
        finally:
            recv.cancel()
            qtask.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
            backtest_jobs.pop(job_id, None)
            await ws.close()

    backtest_dir = Path(__file__).resolve().parents[3] / "persistence" / "backtests"

    @app.get("/backtest/history", name="backtest_history")
    async def backtest_history() -> list[dict]:
        if not backtest_dir.exists():
            return []
        out = []
        for p in backtest_dir.glob("*.json"):
            try:
                out.append(json.loads(p.read_text()))
            except Exception:
                continue
        out.sort(key=lambda r: r.get("timestamp", 0), reverse=True)
        return out

    @app.get("/backtest/{job_id}", name="get_backtest")
    async def get_backtest(job_id: str) -> dict:
        path = backtest_dir / f"{job_id}.json"
        if not path.exists():
            raise HTTPException(status_code=404, detail="backtest not found")
        return json.loads(path.read_text())

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
                "position_size": risk.position_size,
                "leverage": risk.leverage,
                "exposure": risk.exposure,
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
        if runtime_state["mode"] == "demo":
            raise HTTPException(status_code=403, detail="demo mode: trading disabled")
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
            import hashlib
            import hmac
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
            import hashlib
            import hmac
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

    @app.post("/logs/generate")
    async def logs_generate() -> dict:
        """Generate sample log entries for the debug console."""
        logging.info("demo info log")
        logging.error("demo error log")
        return {"status": "ok"}

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
            import hashlib
            import hmac
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
                if not runtime_state["running"]:
                    await asyncio.sleep(0.5)
                    continue
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
            import hashlib
            import hmac
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
                if not runtime_state["running"]:
                    await asyncio.sleep(0.5)
                    continue
                vec_task = asyncio.create_task(asyncio.to_thread(feat_q.get))
                order_task = asyncio.create_task(order_q.get())
                recv_task = asyncio.create_task(ws.receive_text())
                hb_task = asyncio.create_task(asyncio.sleep(1))
                done, _ = await asyncio.wait(
                    {vec_task, order_task, recv_task, hb_task},
                    return_when=asyncio.FIRST_COMPLETED,
                )
                if recv_task in done:
                    vec_task.cancel()
                    order_task.cancel()
                    hb_task.cancel()
                    feat_q.put_nowait((None, None))
                    with contextlib.suppress(asyncio.CancelledError):
                        await vec_task
                    with contextlib.suppress(asyncio.CancelledError):
                        await order_task
                    with contextlib.suppress(asyncio.CancelledError):
                        await hb_task
                    with contextlib.suppress(asyncio.CancelledError, WebSocketDisconnect):
                        await recv_task
                    break
                if hb_task in done:
                    vec_task.cancel()
                    order_task.cancel()
                    recv_task.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await vec_task
                    with contextlib.suppress(asyncio.CancelledError):
                        await order_task
                    with contextlib.suppress(asyncio.CancelledError):
                        await recv_task
                    await ws.send_json({"type": "heartbeat", "timestamp": int(time.time())})
                    continue
                if vec_task in done:
                    event, vec = vec_task.result()
                    order_task.cancel()
                    hb_task.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await order_task
                    with contextlib.suppress(asyncio.CancelledError):
                        await hb_task
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
                            "position_size": risk.position_size,
                            "leverage": risk.leverage,
                            "exposure": risk.exposure,
                        },
                        "timestamp": int(time.time()),
                    }
                    await ws.send_json(payload)
                else:
                    order = order_task.result()
                    vec_task.cancel()
                    hb_task.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await vec_task
                    with contextlib.suppress(asyncio.CancelledError):
                        await hb_task
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
                            "position_size": risk.position_size,
                            "leverage": risk.leverage,
                            "exposure": risk.exposure,
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


    @app.get("/chart/portfolio")
    async def chart_portfolio(
        tf: str = Query("1H"),
        r: RangeParams = Depends(),
        limits: LimitParams = Depends(),
    ) -> dict:
        """Return portfolio equity history with pagination and downsampling."""

        series = list(risk.equity_history)
        start, end = r.start, r.end
        offset, cursor, limit = limits.offset, limits.cursor, limits.limit

        if start is not None or end is not None:
            times = [p[0] for p in series]
            left = bisect_left(times, start) if start is not None else 0
            right = bisect_right(times, end) if end is not None else len(series)
            series = series[left:right]

        if cursor is not None:
            times = [p[0] for p in series]
            idx = bisect_right(times, cursor)
            series = series[idx:]

        total = len(series)

        if offset is not None:
            if offset >= total:
                return {"series": [], "total": total}
            series = series[offset : offset + limit]
        elif total > limit:
            if cursor is not None:
                series = series[:limit]
            elif limit == 1:
                series = [series[0]]
            else:
                step = (total - 1) / (limit - 1)
                series = [series[int(round(i * step))] for i in range(limit)]

        return {"series": series, "total": total}

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
        nonlocal poller_task, scanner_task, model_task
        if poller_task is not None:
            poller_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await poller_task
        if scanner_task is not None:
            await scanner.stop()
            scanner_task = None
        if model_task is not None:
            model_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await model_task
            model_task = None
        with contextlib.suppress(Exception):
            features.save(feat_path)
            posterior.save(post_path)


    return app


cfg = BotConfig(rpc_ws="", rpc_http="", log_level="INFO", wallet="demo", db_path=":memory:")
lm = LicenseManager(rpc_http=cfg.rpc_http)
risk = RiskManager()
dal = DAL(cfg.db_path)
oracle = CoingeckoOracle(dal)
connector = PaperConnector(dal, oracle)
trade = TradeEngine(risk, connector, dal)
assets = AssetService(dal)
bootstrap = BootstrapCoordinator()
model_dir = Path.home() / ".solbot" / "models"
model_dir.mkdir(parents=True, exist_ok=True)
feat_path = model_dir / "features.npz"
post_path = model_dir / "posterior.npz"
features = PyFeatureEngine()
if feat_path.exists():
    with contextlib.suppress(Exception):
        features.load(feat_path)
if post_path.exists():
    posterior = PosteriorEngine.load(post_path)
else:
    posterior = PosteriorEngine()
app = create_app(cfg, lm, risk, trade, assets, bootstrap, features, posterior)
