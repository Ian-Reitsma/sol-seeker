"""CLI for distributing license tokens.

This script sends a license SPL token from the authority wallet to a recipient.
Use environment variables or command line options to specify the authority keypair
and RPC endpoint.
"""
from __future__ import annotations

import argparse
import os
from typing import Optional, List
from solbot.utils.license import LicenseManager, load_authority_keypair


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    """Parse command line options."""
    parser = argparse.ArgumentParser(description="Send a license token")
    parser.add_argument("recipient", help="Wallet address receiving the license")
    parser.add_argument(
        "--rpc-http",
        default=os.getenv("RPC_HTTP", "https://api.mainnet-beta.solana.com"),
        help="Solana RPC endpoint",
    )
    parser.add_argument(
        "--keypair",
        default=os.getenv("LICENSE_KEYPAIR_PATH", ""),
        help="Path to the encrypted authority keypair",
    )
    parser.add_argument(
        "--key",
        default=os.getenv("LICENSE_KEYPAIR_KEY", ""),
        help="Base64 Fernet key for the authority keypair",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Send a demo license instead of a full license",
    )
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> None:
    """Run the distributor."""
    args = parse_args(argv)
    lm = LicenseManager(rpc_http=args.rpc_http)
    kp = load_authority_keypair(path=args.keypair or None, key=args.key or None)
    sig = lm.distribute_license(args.recipient, keypair=kp, demo=args.demo)
    print(f"License sent in transaction {sig}")


if __name__ == "__main__":  # pragma: no cover - manual usage
    main()
