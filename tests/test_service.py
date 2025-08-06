from datetime import datetime, timedelta, timezone
import jwt

from fastapi.testclient import TestClient
from solbot.service.license_issuer import app, verify_jwt
from solbot.service import publisher

from solbot.utils.license import LicenseManager


def make_token(secret: str, *, exp: timedelta = timedelta(minutes=5)) -> str:
    payload = {
        "iss": "issuer",
        "aud": "audience",
        "exp": datetime.now(tz=timezone.utc) + exp,
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def setup_env(monkeypatch, secret: str = "secret"):
    monkeypatch.setenv("LICENSE_JWT_SECRET", secret)
    monkeypatch.setenv("LICENSE_JWT_ISSUER", "issuer")
    monkeypatch.setenv("LICENSE_JWT_AUDIENCE", "audience")


def test_issue_endpoint(monkeypatch):
    setup_env(monkeypatch)
    client = TestClient(app)
    called = {}

    def fake_publish(req):
        called.update(req)

    monkeypatch.setattr(publisher, "publish_issue", fake_publish)
    token = make_token("secret")
    resp = client.post(
        "/issue",
        json={"wallet": "dest", "demo": True},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["queued"] is True
    assert called["wallet"] == "dest"
    assert called["demo"] is True


def test_issue_unauthorized(monkeypatch):
    setup_env(monkeypatch)
    client = TestClient(app)
    resp = client.post("/issue", json={"wallet": "dest"}, headers={"Authorization": "Bearer "})
    assert resp.status_code == 401


def test_healthz(monkeypatch):
    client = TestClient(app)
    monkeypatch.setattr(
        LicenseManager, "_client", lambda self: type("C", (), {"is_connected": lambda self: True})()
    )
    resp = client.get("/healthz")
    assert resp.status_code == 200


def test_verify_jwt_valid(monkeypatch):
    setup_env(monkeypatch)
    token = make_token("secret")
    assert verify_jwt(token) is True


def test_verify_jwt_expired(monkeypatch):
    setup_env(monkeypatch)
    token = make_token("secret", exp=timedelta(minutes=-5))
    assert verify_jwt(token) is False


def test_verify_jwt_tampered(monkeypatch):
    setup_env(monkeypatch)
    token = make_token("wrongsecret")
    assert verify_jwt(token) is False
