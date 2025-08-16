import pytest
from sqlmodel import SQLModel
from httpx import AsyncClient


@pytest.fixture(scope="module")
def test_app():
    SQLModel.metadata.clear()
    from src.solbot.server.api import app
    return app


@pytest.mark.asyncio
async def test_performance_matrix_endpoint(test_app):
    async with AsyncClient(app=test_app, base_url="http://test") as ac:
        res = await ac.get("/strategy/performance_matrix?period=7d")
    assert res.status_code == 200
    data = res.json()
    assert "days" in data and len(data["days"]) > 0
    assert "strategies" in data and len(data["strategies"]) == 3
    assert "risk" in data and "sharpe" in data["risk"]
