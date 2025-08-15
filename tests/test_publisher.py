import asyncio

import pytest

from solbot.service import publisher


@pytest.mark.asyncio
async def test_fan_out_multiple_subscribers():
    publisher.configure(maxsize=10)
    q1 = publisher.subscribe()
    q2 = publisher.subscribe()

    message = {"hello": "world"}
    publisher.publish(message)

    r1 = await asyncio.wait_for(q1.get(), 1)
    r2 = await asyncio.wait_for(q2.get(), 1)
    assert r1 == message
    assert r2 == message

