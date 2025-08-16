import pytest
from sqlmodel import SQLModel
from httpx import AsyncClient


@pytest.fixture(scope="module")
def test_app():
    SQLModel.metadata.clear()
    from src.solbot.server.api import app
    return app


@pytest.mark.asyncio
async def test_sentiment_pulse_and_influencers(test_app):
    async with AsyncClient(app=test_app, base_url="http://test") as ac:
        pulse = await ac.get("/sentiment/pulse")
        inf = await ac.get("/sentiment/influencers")
        trending = await ac.get("/sentiment/trending")
    assert pulse.status_code == 200
    assert inf.status_code == 200
    assert trending.status_code == 200
    data = pulse.json()
    assert "fear_greed" in data
    infl = inf.json()
    assert isinstance(infl, list) and len(infl) > 0
    trend = trending.json()
    symbols = {t["symbol"] for t in trend}
    assert "BONK" in symbols
