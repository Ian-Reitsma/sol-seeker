from solbot.utils import parse_args, BotConfig


def test_parse_args_defaults(monkeypatch):
    monkeypatch.delenv("RPC_WS", raising=False)
    monkeypatch.delenv("RPC_HTTP", raising=False)
    args = parse_args([])
    assert args.rpc_ws.startswith("ws")
    assert args.rpc_http.startswith("http")


def test_bot_config_from_args():
    ns = parse_args(["--rpc-ws", "wss://custom"])
    cfg = BotConfig.from_args(ns)
    assert cfg.rpc_ws == "wss://custom"
    assert cfg.rpc_http.startswith("http")
