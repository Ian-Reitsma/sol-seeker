"""Social sentiment collectors for Sol Seeker.

This package provides lightweight parsers and async helpers to gather
mentions of Solana tokens from various social platforms. The collectors
expose a common :class:`TokenMention` data structure so the server can
aggregate counts regardless of the source (Twitter, Telegram, etc.).
"""

from __future__ import annotations

from dataclasses import dataclass
import time


@dataclass
class TokenMention:
    """Represents a single token mention from a social message."""

    symbol: str
    user: str
    sentiment: float
    timestamp: float

    @classmethod
    def from_parts(cls, symbol: str, user: str, sentiment: float) -> "TokenMention":
        return cls(symbol=symbol.upper(), user=user, sentiment=sentiment, timestamp=time.time())
