"""FastAPI application exposing trading endpoints.

Startup verifies that the configured wallet holds a valid license token.
The authority wallet (`LICENSE_AUTHORITY`) bypasses this check, and demo
wallets log a warning and disable trading.

Endpoints:
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
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect, Depends
from fastapi.security import APIKeyHeader
from pydantic import BaseModel
from prometheus_fastapi_instrumentator import Instrumentator
from prometheus_client import Histogram
from typing import Optional

from ..utils import BotConfig, LicenseManager
from ..engine import RiskManager, TradeEngine
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

    @app.get("/health")
    async def health() -> dict:
        return {"status": "ok"}

    @app.get("/status")
    async def status() -> dict:
        return bootstrap.status()

    @app.get("/assets")
    async def assets_endpoint() -> list[dict]:
        return assets.list_assets()

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

    @app.get("/chart/{symbol}")
    async def chart(symbol: str) -> dict:
        return {
            "symbol": symbol.upper(),
            "url": f"https://www.tradingview.com/chart/?symbol={symbol.upper()}",
        }
    @app.get("/version")
    async def version() -> dict:
        return {"git": os.getenv("COMMIT_SHA", "dev"), "schema": SCHEMA_HASH}


    return app
