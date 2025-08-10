"""Configuration management utilities."""

from dataclasses import dataclass
import argparse
import os
from typing import Optional, List


def parse_args(args: Optional[List[str]] = None) -> argparse.Namespace:
    """Parse command line arguments or provided list."""
    parser = argparse.ArgumentParser(description="sol-bot configuration")
    parser.add_argument(
        "--rpc-ws",
        default=os.getenv("RPC_WS", "wss://api.devnet.solana.com/"),
        help="Solana websocket endpoint",
    )
    parser.add_argument(
        "--rpc-http",
        default=os.getenv("RPC_HTTP"),
        help="Solana HTTP endpoint",
    )
    parser.add_argument(
        "--log-level",
        default=os.getenv("LOG_LEVEL", "INFO"),
        help="Logging level",
    )
    parser.add_argument(
        "--wallet",
        default=os.getenv("WALLET_ADDR", ""),
        help="Public key of the wallet running the bot",
    )
    parser.add_argument(
        "--db-path",
        default=os.getenv("DB_PATH", os.path.expanduser("~/.solbot/state.db")),
        help="Path to SQLite database for persistence",
    )
    parser.add_argument(
        "--bootstrap",
        action="store_true",
        help="Run bootstrap process then exit",
    )
    ns = parser.parse_args(args)
    if ns.rpc_http is None:
        ns.rpc_http = ns.rpc_ws.replace("wss", "https").replace("ws", "http")
    return ns


@dataclass
class BotConfig:
    rpc_ws: str
    rpc_http: str
    log_level: str
    wallet: str
    db_path: str
    bootstrap: bool = False

    @classmethod
    def from_args(cls, args: argparse.Namespace) -> "BotConfig":
        return cls(
            rpc_ws=args.rpc_ws,
            rpc_http=args.rpc_http,
            log_level=args.log_level,
            wallet=args.wallet,
            db_path=args.db_path,
            bootstrap=args.bootstrap,
        )
