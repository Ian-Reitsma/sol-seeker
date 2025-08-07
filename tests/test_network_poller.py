import asyncio

from solbot.engine.features import PyFeatureEngine
from solbot.service import start_network_poller


def test_network_poller_updates_features():
    fe = PyFeatureEngine()

    def fetcher(url: str):
        return 3.0, 7.0

    async def run():
        task = start_network_poller(fe, "http://dummy", interval=0.01, fetcher=fetcher)
        await asyncio.sleep(0.05)
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
    asyncio.run(run())
    assert fe.curr[6] == 3.0
    assert fe.curr[7] == 7.0
