from fastapi.testclient import TestClient
from solbot.service.license_issuer import app
from solbot.service import publisher

from solbot.utils.license import LicenseManager


def test_issue_endpoint(monkeypatch):
    client = TestClient(app)
    called = {}

    def fake_publish(req):
        called.update(req)

    monkeypatch.setattr(publisher, 'publish_issue', fake_publish)
    resp = client.post('/issue', json={'wallet': 'dest', 'demo': True}, headers={'Authorization': 'Bearer token'})
    assert resp.status_code == 200
    assert resp.json()['queued'] is True
    assert called['wallet'] == 'dest'
    assert called['demo'] is True


def test_issue_unauthorized(monkeypatch):
    client = TestClient(app)
    resp = client.post('/issue', json={'wallet': 'dest'}, headers={'Authorization': 'Bearer '})
    assert resp.status_code == 401


def test_healthz(monkeypatch):
    client = TestClient(app)
    monkeypatch.setattr(LicenseManager, '_client', lambda self: type('C', (), {'is_connected': lambda self: True})())
    resp = client.get('/healthz')
    assert resp.status_code == 200
