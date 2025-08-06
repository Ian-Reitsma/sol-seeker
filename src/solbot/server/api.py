"""FastAPI application exposing trading endpoints.

Startup verifies that the configured wallet holds a valid license token.
The authority wallet (`LICENSE_AUTHORITY`) bypasses this check, and demo
wallets log a warning and disable trading.

Endpoints:
* ``GET /`` – resource index
* ``GET /health`` – service liveness
* ``GET /status`` – bootstrap progress
* ``GET /assets`` – list available symbols
* ``GET /positions`` – open positions (API key required)
* ``GET /orders`` – order history (API key required)
* ``POST /orders`` – place an order (API key required)
* ``GET /chart/{symbol}`` – convenience redirect to TradingView
* ``GET /version`` – running commit and schema hash
* ``/ws`` – websocket stream of new orders
"""

from __future__ import annotations

import os
import asyncio
import time
import logging
import contextlib
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Depends
from fastapi.routing import APIRoute, APIWebSocketRoute
from fastapi.security import APIKeyHeader
from pydantic import BaseModel
from prometheus_fastapi_instrumentator import Instrumentator
from prometheus_client import Histogram
from typing import Optional

from ..utils import BotConfig, LicenseManager
from ..engine import RiskManager, TradeEngine, FeatureEngine, PosteriorEngine
from ..engine.features import FEATURES as FEATURE_SCHEMA
from ..types import Side
from ..persistence.assets import AssetService
from ..bootstrap import BootstrapCoordinator
from ..schema import SCHEMA_HASH


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


api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def create_app(
    cfg: BotConfig,
    lm: LicenseManager,
    risk: RiskManager,
    trade: TradeEngine,
    assets: AssetService,
    bootstrap: BootstrapCoordinator,
    features: FeatureEngine | None = None,
    posterior: PosteriorEngine | None = None,
) -> FastAPI:
    app = FastAPI(title="sol-bot API")
    Instrumentator().instrument(app).expose(app)
    latency_hist = Histogram(
        "order_latency_ns", "Order placement latency", buckets=(1e6, 5e6, 1e7, 5e7, 1e8)
    )

    connections: list[WebSocket] = []
    conn_lock = asyncio.Lock()

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

    @app.get("/")
    async def root() -> dict:
        """Return resource index and embed template for TradingView."""
        return {
            "tradingview": "https://www.tradingview.com/widgetembed/?symbol=<sym>USDT",
            "endpoints": {
                "features": app.url_path_for("features_endpoint"),
                "features_schema": app.url_path_for("features_schema_endpoint"),
                "posterior": app.url_path_for("posterior_endpoint"),
                "positions": app.url_path_for("positions"),
                "orders": app.url_path_for("orders"),
                "features_ws": "/features/ws",
                "posterior_ws": "/posterior/ws",
                "dashboard": app.url_path_for("dashboard"),
                "manifest": app.url_path_for("manifest"),
            },
            "timestamp": int(time.time()),
            "schema": SCHEMA_HASH,
        }

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok"}

    @app.get("/status")
    async def status() -> dict:
        return bootstrap.status()

    @app.get("/assets")
    async def assets_endpoint() -> list[dict]:
        return assets.list_assets()

    @app.get("/features")
    async def features_endpoint() -> list[float]:
        if features is None:
            raise HTTPException(status_code=503, detail="features unavailable")
        return features.snapshot().tolist()

    @app.get("/features/schema")
    async def features_schema_endpoint() -> dict:
        """Return metadata mapping feature indices to names."""
        return {
            "features": FEATURE_SCHEMA,
            "schema": SCHEMA_HASH,
            "timestamp": int(time.time()),
        }

    @app.get("/posterior")
    async def posterior_endpoint() -> dict:
        if features is None or posterior is None:
            raise HTTPException(status_code=503, detail="posterior unavailable")
        vec = features.snapshot()
        out = posterior.predict(vec)
        return {"rug": out.rug, "trend": out.trend, "revert": out.revert, "chop": out.chop}

    @app.get("/dashboard")
    async def dashboard() -> dict:
        vec = features.snapshot() if features else None
        posterior_out = (
            posterior.predict(vec).__dict__ if (features and posterior) else None
        )
        return {
            "features": vec.tolist() if vec is not None else None,
            "posterior": posterior_out,
            "positions": trade.list_positions() if bootstrap.is_ready() else {},
            "timestamp": int(time.time()),
        }

    @app.get("/positions")
    async def positions(key: None = Depends(check_key)) -> dict:
        if not bootstrap.is_ready():
            raise HTTPException(status_code=503, detail="state: BOOTSTRAPPING")
        return trade.list_positions()

    @app.get("/orders")
    async def orders(key: None = Depends(check_key)) -> list[dict]:
        if not bootstrap.is_ready():
            raise HTTPException(status_code=503, detail="state: BOOTSTRAPPING")
        return [order.__dict__ for order in trade.list_orders()]

    @app.post("/orders", response_model=OrderResponse)
    async def place_order(req: OrderRequest, key: None = Depends(check_key)) -> OrderResponse:
        if not bootstrap.is_ready():
            raise HTTPException(status_code=503, detail="state: BOOTSTRAPPING")
        if req.token not in [a["symbol"] for a in assets.list_assets()]:
            raise HTTPException(status_code=400, detail="unsupported asset")
        start = time.perf_counter_ns()
        order = await trade.place_order(req.token, req.qty, req.side, req.limit)
        latency_hist.observe(time.perf_counter_ns() - start)
        for ws in list(connections):
            try:
                await ws.send_json(order.__dict__)
            except WebSocketDisconnect:
                connections.remove(ws)
        return OrderResponse(**order.__dict__)

    @app.websocket("/ws")
    async def ws(ws: WebSocket):
        await ws.accept()
        async with conn_lock:
            connections.append(ws)
        try:
            while True:
                await ws.receive_text()
        except WebSocketDisconnect:
            async with conn_lock:
                if ws in connections:
                    connections.remove(ws)

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


    @app.get("/chart/{symbol}")
    async def chart(symbol: str) -> dict:
        return {
            "symbol": symbol.upper(),
            "url": f"https://www.tradingview.com/chart/?symbol={symbol.upper()}",
        }
    @app.get("/version")
    async def version() -> dict:
        return {"git": os.getenv("COMMIT_SHA", "dev"), "schema": SCHEMA_HASH}

    @app.get("/manifest")
    async def manifest() -> dict:
        rest, websockets = [], []
        for route in app.router.routes:
            if isinstance(route, APIRoute):
                rest.append({"path": route.path, "methods": sorted(route.methods)})
            elif isinstance(route, APIWebSocketRoute):
                websockets.append(route.path)
        return {"rest": rest, "websocket": websockets}


    return app
