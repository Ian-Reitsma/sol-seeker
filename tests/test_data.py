import pytest
from solbot.solana import data


def test_streamer_init():
    s = data.SlotStreamer()
    assert s.rpc_ws_url.startswith("ws")
