from solbot.utils.license import LicenseManager, LICENSE_MINT

class DummyClient:
    def __init__(self, result):
        self._result = result

    def get_token_accounts_by_owner(self, owner, opts):
        return {"result": {"value": self._result}}


def test_has_license(monkeypatch):
    lm = LicenseManager(rpc_http="https://example")

    def fake_client(self):
        return DummyClient([{"pubkey": "x"}])

    monkeypatch.setattr(lm, "_client", fake_client.__get__(lm))
    monkeypatch.setattr("solbot.utils.license.LICENSE_MINT", "11111111111111111111111111111111")
    assert lm.has_license("11111111111111111111111111111111")
