"""In-process publish/subscribe queue utilities.

This module provides a very small pub/sub helper around ``asyncio.Queue``. A
single global :class:`Publisher` instance fan-outs published messages to all
subscribers.  Consumers receive their own queue so they do not compete for
messages.
"""

from __future__ import annotations

import asyncio
from typing import List


class Publisher:
    """Fan-out message distributor backed by ``asyncio.Queue``.

    Parameters
    ----------
    maxsize:
        Maximum size for subscriber queues.  ``0`` means unbounded.
    overflow:
        Behaviour when a subscriber queue is full.  ``"drop_new"`` will drop
        the message for that subscriber, ``"drop_oldest"`` removes the oldest
        message before enqueuing the new one and ``"raise"`` propagates
        :class:`asyncio.QueueFull`.
    """

    def __init__(self, maxsize: int = 0, overflow: str = "drop_new") -> None:
        self._maxsize = maxsize
        self._overflow = overflow
        self._subscribers: List[asyncio.Queue] = []

    def subscribe(self) -> asyncio.Queue:
        """Return a new queue receiving all future messages."""

        q: asyncio.Queue = asyncio.Queue(maxsize=self._maxsize)
        self._subscribers.append(q)
        return q

    def publish(self, message: dict) -> None:
        """Publish *message* to all subscribers."""

        for q in list(self._subscribers):
            try:
                q.put_nowait(message)
            except asyncio.QueueFull:
                if self._overflow == "drop_oldest":
                    q.get_nowait()
                    q.put_nowait(message)
                elif self._overflow == "drop_new":
                    continue
                else:  # "raise"
                    raise


_publisher = Publisher()


def configure(*, maxsize: int = 0, overflow: str = "drop_new") -> None:
    """Configure the global publisher instance.

    Parameters mirror :class:`Publisher`'s constructor and replace the existing
    instance so tests may reset state easily.
    """

    global _publisher
    _publisher = Publisher(maxsize=maxsize, overflow=overflow)


def publish_issue(request: dict) -> None:
    """Enqueue a license issuance request.

    ``license_issuer`` keeps compatibility with this helper which simply
    delegates to :func:`publish`.
    """

    publish(request)


def publish(message: dict) -> None:
    """Publish *message* to all subscribers."""

    _publisher.publish(message)


def subscribe() -> asyncio.Queue:
    """Register a new subscriber queue."""

    return _publisher.subscribe()


__all__ = ["publish", "subscribe", "configure", "publish_issue"]

