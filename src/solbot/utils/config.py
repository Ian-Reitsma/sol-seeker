"""Configuration management utilities."""

from dataclasses import dataclass
import argparse
import os


def parse_args(args: list[str] | None = None) -> argparse.Namespace:
    """Parse command line arguments or provided list."""
    parser = argparse.ArgumentParser(description="sol-bot configuration")
    parser.add_argument(
        "--rpc-ws",
        default=os.getenv("RPC_WS", "wss://api.mainnet-beta.solana.com/"),
        help="Solana websocket endpoint",
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
    return parser.parse_args(args)


@dataclass
class BotConfig:
    rpc_ws: str
    log_level: str
    wallet: str

    @classmethod
    def from_args(cls, args: argparse.Namespace) -> "BotConfig":
        return cls(rpc_ws=args.rpc_ws, log_level=args.log_level, wallet=args.wallet)
