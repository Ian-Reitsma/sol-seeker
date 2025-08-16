"""Minimal Twitter collector for token mentions.

This module doesn't hit the real Twitter API but exposes a coroutine that
can parse an async iterator of tweet-like objects.  It is primarily meant
for tests and local demos where a queue of messages is provided.
"""

from __future__ import annotations

import asyncio
import re
from collections.abc import AsyncIterator
from . import TokenMention

TOKEN_PATTERN = re.compile(r"\$([A-Z]{2,10})")


async def stream_mentions(source: AsyncIterator[dict], queue: asyncio.Queue[TokenMention]) -> None:
    """Consume ``source`` async iterator of tweets and push token mentions.

    Each item in ``source`` is expected to be a mapping with ``text``,
    ``user`` and optional ``sentiment`` fields.  For every ``$TOKEN`` symbol
    found in the text a :class:`TokenMention` is added to ``queue``.
    """

    async for tweet in source:
        text = tweet.get("text", "")
        user = tweet.get("user", "")
        sentiment = float(tweet.get("sentiment", 0))
        for match in TOKEN_PATTERN.findall(text):
            await queue.put(TokenMention.from_parts(match, user, sentiment))
