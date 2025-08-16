"""Minimal Telegram collector for token mentions.

Similar to :mod:`solbot.social.twitter`, this module exposes a coroutine
that parses an async iterator of Telegram-style messages.  The function is
framework agnostic so tests can supply their own iterators.
"""

from __future__ import annotations

import asyncio
import re
from collections.abc import AsyncIterator
from . import TokenMention

TOKEN_PATTERN = re.compile(r"\$([A-Z]{2,10})")


async def stream_mentions(source: AsyncIterator[dict], queue: asyncio.Queue[TokenMention]) -> None:
    """Consume ``source`` async iterator of Telegram messages and push mentions."""
    async for msg in source:
        text = msg.get("text", "")
        user = msg.get("user", "")
        sentiment = float(msg.get("sentiment", 0))
        for match in TOKEN_PATTERN.findall(text):
            await queue.put(TokenMention.from_parts(match, user, sentiment))
