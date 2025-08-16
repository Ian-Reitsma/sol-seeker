from fastapi.testclient import TestClient

from tests.test_price_endpoint import build_app


def test_mev_alpha_endpoints():
    app = build_app()
    with TestClient(app) as client:
        mev = client.get("/mev/status")
        assert mev.status_code == 200
        data = mev.json()
        assert {
            "saved_today",
            "attacks_blocked",
            "success_rate",
            "latency_ms",
        } <= data.keys()

        alpha = client.get("/alpha/signals")
        assert alpha.status_code == 200
        a = alpha.json()
        assert {
            "strength",
            "social_sentiment",
            "onchain_momentum",
            "whale_activity",
        } <= a.keys()

