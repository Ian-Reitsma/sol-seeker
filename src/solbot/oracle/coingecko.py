"""Coingecko-based price oracle."""

from __future__ import annotations

import httpx
from typing import Dict

from ..persistence import DAL


class PriceOracle:
    async def price(self, token: str) -> float:  # pragma: no cover - interface
        raise NotImplementedError


class CoingeckoOracle(PriceOracle):
    def __init__(self, dal: DAL) -> None:
        self.dal = dal
        self.session = httpx.AsyncClient()

    async def price(self, token: str) -> float:
        cached = self.dal.last_price(token)
        if cached is not None:
            return cached
        try:
            resp = await self.session.get(
                "https://api.coingecko.com/api/v3/simple/price",
                params={"ids": token.lower(), "vs_currencies": "usd"},
                timeout=5,
            )
            resp.raise_for_status()
            price = resp.json()[token.lower()]["usd"]
            self.dal.cache_price(token, price)
            return price
        except Exception:
            if cached is not None:
                return cached
            raise
