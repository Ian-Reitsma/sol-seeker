import asyncio
from solbot.oracle.coingecko import CoingeckoOracle
from solbot.persistence import DAL


def test_oracle_session_closed(tmp_path):
    dal = DAL(str(tmp_path / "db.sqlite"))

    async def run():
        async with CoingeckoOracle(dal) as oracle:
            session = oracle.session
        return session.is_closed

    assert asyncio.run(run())
