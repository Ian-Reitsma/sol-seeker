"""License distribution and verification via Solana.

This module verifies that a user holds an on-chain license token before enabling
full functionality. Licenses are standard SPL tokens minted by an authority
wallet. A second mint may be issued for ``demo`` mode which allows users to
explore the interface without placing trades.

Replace the constants below with real addresses or set the corresponding
environment variables at runtime.
"""

from dataclasses import dataclass
import os
import json
from typing import Optional
from cryptography.fernet import Fernet
from solana.rpc.api import Client
from solders.transaction import Transaction
from solders.pubkey import Pubkey
from solders.keypair import Keypair
from spl.token.instructions import (
    transfer,
    get_associated_token_address,
    create_associated_token_account,
)
from spl.token.constants import TOKEN_PROGRAM_ID

# Address of the SPL token mint representing a valid license.
LICENSE_MINT = os.getenv("LICENSE_MINT", "REPLACE_WITH_LICENSE_MINT")
# Address of the SPL token mint granting demo (read-only) access.
DEMO_MINT = os.getenv("DEMO_MINT", "REPLACE_WITH_DEMO_MINT")
# Address of the wallet that issues licenses.
LICENSE_AUTHORITY = os.getenv("LICENSE_AUTHORITY", "REPLACE_WITH_AUTHORITY_WALLET")
# Path to the encrypted authority keypair used for distribution.
LICENSE_KEYPAIR_PATH = os.getenv("LICENSE_KEYPAIR_PATH", "")
# Base64 encoded Fernet key to decrypt the authority keypair file.
LICENSE_KEYPAIR_KEY = os.getenv("LICENSE_KEYPAIR_KEY", "")


def load_authority_keypair(path: Optional[str] = None, key: Optional[str] = None) -> Keypair:
    """Load and decrypt the authority keypair.

    Parameters
    ----------
    path:
        Optional path to the encrypted keypair file. Defaults to
        ``LICENSE_KEYPAIR_PATH``.
    key:
        Optional base64 encoded Fernet key used to decrypt ``path``. Defaults to
        ``LICENSE_KEYPAIR_KEY``. If empty the file is assumed to be plaintext.
    """
    path = path or LICENSE_KEYPAIR_PATH
    key = key or LICENSE_KEYPAIR_KEY
    if not path:
        raise ValueError("no keypair path specified")
    with open(path, "rb") as fh:
        data = fh.read()
    if key:
        data = Fernet(key).decrypt(data)
    secret = json.loads(data)
    return Keypair.from_bytes(bytes(secret))


@dataclass
class LicenseManager:
    """Manage license verification and distribution."""

    rpc_http: str

    def _client(self) -> Client:
        return Client(self.rpc_http)

    def _has_token(self, wallet: str, mint: str) -> bool:
        """Return ``True`` if ``wallet`` owns at least one token of ``mint``."""
        client = self._client()
        try:
            resp = client.get_token_accounts_by_owner(
                Pubkey.from_string(wallet), {"mint": Pubkey.from_string(mint)}
            )
            accounts = resp.get("result", {}).get("value", [])
            return len(accounts) > 0
        except Exception:
            return False

    def token_accounts(self, wallet: str, mint: str) -> list[dict]:
        """Return all token accounts for ``wallet`` and ``mint``."""
        client = self._client()
        resp = client.get_token_accounts_by_owner(
            Pubkey.from_string(wallet), {"mint": Pubkey.from_string(mint)}
        )
        return resp.get("result", {}).get("value", [])

    def token_balance(self, wallet: str, mint: str) -> int:
        """Return the balance of ``mint`` tokens held by ``wallet``."""
        accounts = self.token_accounts(wallet, mint)
        if not accounts:
            return 0
        client = self._client()
        balance = 0
        for acc in accounts:
            info = client.get_token_account_balance(Pubkey.from_string(acc["pubkey"]))
            amount = int(info["result"]["value"]["amount"])
            balance += amount
        return balance

    def fetch_license_account(self, wallet: str) -> Optional[str]:
        """Return the first token account address holding a license, if any."""
        accounts = self.token_accounts(wallet, LICENSE_MINT)
        return accounts[0]["pubkey"] if accounts else None

    def has_license(self, wallet: str) -> bool:
        """Return True if the wallet holds a full license."""
        return self._has_token(wallet, LICENSE_MINT)

    def has_demo(self, wallet: str) -> bool:
        """Return True if the wallet holds a demo license."""
        return self._has_token(wallet, DEMO_MINT)

    def license_balance(self, wallet: str) -> int:
        """Return the number of full license tokens owned by ``wallet``."""
        return self.token_balance(wallet, LICENSE_MINT)

    def license_mode(self, wallet: str) -> str:
        """Return ``full``, ``demo`` or ``none`` for the given wallet."""
        if self.license_balance(wallet) > 0:
            return "full"
        if self.has_demo(wallet):
            return "demo"
        return "none"

    def distribute_license(
        self, recipient: str, keypair: Optional[Keypair] = None, demo: bool = False
    ) -> str:
        """Send a license token to ``recipient``.

        Parameters
        ----------
        recipient:
            Wallet receiving the license.
        keypair:
            Optional authority keypair. When ``None`` the keypair is loaded from
            :func:`load_authority_keypair` and must match
            :data:`LICENSE_AUTHORITY`.
        demo:
            If ``True`` the demo mint is sent, otherwise the full license mint is
            used.

        Returns
        -------
        str
            Transaction signature of the transfer.
        """
        keypair = keypair or load_authority_keypair()
        if str(keypair.pubkey()) != LICENSE_AUTHORITY:
            raise ValueError("authority mismatch")

        mint = DEMO_MINT if demo else LICENSE_MINT
        client = self._client()

        source_token = get_associated_token_address(keypair.pubkey(), Pubkey.from_string(mint))
        dest_token = get_associated_token_address(Pubkey.from_string(recipient), Pubkey.from_string(mint))

        # Create destination account if required
        try:
            acc = client.get_account_info(dest_token)
            if acc.get("result", {}).get("value") is None:
                raise Exception
        except Exception:
            create_instr = create_associated_token_account(
                payer=keypair.pubkey(),
                owner=Pubkey.from_string(recipient),
                mint=Pubkey.from_string(mint),
            )
            tx = Transaction().add(create_instr)
            client.send_transaction(tx, keypair)

        tx = Transaction().add(
            transfer(
                source=source_token,
                dest=dest_token,
                owner=keypair.pubkey(),
                amount=1,
                program_id=TOKEN_PROGRAM_ID,
            )
        )
        resp = client.send_transaction(tx, keypair)
        return resp["result"]

    def verify_or_exit(self, wallet: str) -> str:
        """Ensure ``wallet`` has a license, exiting the process if not."""
        mode = self.license_mode(wallet)
        if mode == "none":
            import sys

            print(
                "License check failed. Obtain a license token from the"
                f" authority wallet {LICENSE_AUTHORITY}."
            )
            sys.exit(1)
        return mode
