import pytest
from solders.pubkey import Pubkey
from solbot.utils.license import (
    LicenseManager,
    LICENSE_MINT,
    DEMO_MINT,
    load_authority_keypair,
)
from solders.keypair import Keypair
from cryptography.fernet import Fernet

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


def test_license_mode_demo(monkeypatch):
    lm = LicenseManager(rpc_http="https://example")

    monkeypatch.setattr("solbot.utils.license.LICENSE_MINT", "11111111111111111111111111111111")

    demo_mint = "1111111QLbz7JHiBTspS962RLKV8GndWFwiEaqKM"
    monkeypatch.setattr("solbot.utils.license.DEMO_MINT", demo_mint)

    class DemoClient:
        def get_token_accounts_by_owner(self, owner, opts):
            if opts.get("mint") == Pubkey.from_string(demo_mint):
                return {"result": {"value": ["demo"]}}
            return {"result": {"value": []}}

    monkeypatch.setattr(lm, "_client", lambda: DemoClient())
    assert lm.license_mode("11111111111111111111111111111111") == "demo"


def test_license_mode_authority(monkeypatch):
    lm = LicenseManager(rpc_http="https://example")
    admin = "11111111111111111111111111111111"
    monkeypatch.setattr("solbot.utils.license.LICENSE_AUTHORITY", admin)
    monkeypatch.setattr(lm, "license_balance", lambda wallet: 0)
    monkeypatch.setattr(lm, "has_demo", lambda wallet: False)
    assert lm.license_mode(admin) == "full"


def test_verify_or_exit(monkeypatch):
    lm = LicenseManager(rpc_http="https://example")

    monkeypatch.setattr(lm, "license_mode", lambda wallet: "none")
    with pytest.raises(SystemExit):
        lm.verify_or_exit("bad")


def test_load_authority_keypair(tmp_path, monkeypatch):
    keypair = Keypair()
    secret = keypair.to_json().encode()
    key = Fernet.generate_key()
    enc = Fernet(key).encrypt(secret)
    path = tmp_path / "kp.enc"
    path.write_bytes(enc)
    monkeypatch.setenv("LICENSE_KEYPAIR_PATH", str(path))
    monkeypatch.setenv("LICENSE_KEYPAIR_KEY", key.decode())
    monkeypatch.setattr("solbot.utils.license.LICENSE_KEYPAIR_PATH", str(path))
    monkeypatch.setattr("solbot.utils.license.LICENSE_KEYPAIR_KEY", key.decode())
    loaded = load_authority_keypair()
    assert loaded.pubkey() == keypair.pubkey()


def test_load_authority_keypair_scrub(monkeypatch):
    import json
    arr = bytearray(json.dumps(list(range(64))).encode())

    def fake_open(path, mode):
        class FH:
            def __enter__(self):
                return self
            def __exit__(self, exc_type, exc, tb):
                pass
            def read(self):
                return bytes(arr)
        return FH()

    captured = {}
    def fake_from_bytes(data):
        captured['buf'] = data
        return Keypair()

    monkeypatch.setattr("builtins.open", fake_open)
    monkeypatch.setattr(Keypair, 'from_bytes', fake_from_bytes)
    load_authority_keypair(path="dummy", key="")
    assert all(b == 0 for b in captured['buf'])

class BalanceClient:
    def __init__(self, amount):
        self.amount = amount
    def get_token_accounts_by_owner(self, owner, opts):
        # return a valid 32 byte pubkey string for the dummy token account
        return {"result": {"value": [{"pubkey": "11111111111111111111111111111111"}]}}
    def get_token_account_balance(self, pubkey):
        return {"result": {"value": {"amount": str(self.amount)}}}

def test_license_balance(monkeypatch):
    lm = LicenseManager(rpc_http="https://example")
    monkeypatch.setattr(lm, "_client", lambda: BalanceClient(2))
    monkeypatch.setattr("solbot.utils.license.LICENSE_MINT", "11111111111111111111111111111111")
    assert lm.license_balance("11111111111111111111111111111111") == 2


def test_distributor_cli(monkeypatch, capsys):
    called = {}
    def fake_dist(self, recipient, keypair=None, demo=False):
        called["recipient"] = recipient
        called["demo"] = demo
        return "sig"
    monkeypatch.setattr(LicenseManager, "distribute_license", fake_dist)
    monkeypatch.setattr("solbot.tools.distribute_license.load_authority_keypair", lambda path=None, key=None: "kp")
    from solbot.tools import distribute_license
    distribute_license.main(["dest", "--rpc-http", "https://example", "--demo"])
    out = capsys.readouterr().out
    assert "sig" in out
    assert called["recipient"] == "dest"
    assert called["demo"] is True
