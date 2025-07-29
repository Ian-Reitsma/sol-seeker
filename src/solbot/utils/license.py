"""License distribution and verification via Solana."""

from dataclasses import dataclass
from solana.rpc.api import Client
from solders.transaction import Transaction
from solders.pubkey import Pubkey
from solders.keypair import Keypair
from spl.token.instructions import transfer, get_associated_token_address
from spl.token.constants import TOKEN_PROGRAM_ID

# Address of the SPL token mint representing a valid license.
LICENSE_MINT = "REPLACE_WITH_LICENSE_MINT"  # TODO: set actual mint address
# Address of the wallet that issues licenses.
LICENSE_AUTHORITY = "REPLACE_WITH_AUTHORITY_WALLET"  # TODO: set actual authority


@dataclass
class LicenseManager:
    """Manage license verification and distribution."""

    rpc_http: str

    def _client(self) -> Client:
        return Client(self.rpc_http)

    def has_license(self, wallet: str) -> bool:
        """Check if the wallet holds the license token."""
        client = self._client()
        resp = client.get_token_accounts_by_owner(Pubkey.from_string(wallet), {
            "mint": Pubkey.from_string(LICENSE_MINT)
        })
        accounts = resp.get("result", {}).get("value", [])
        return len(accounts) > 0

    def distribute_license(self, recipient: str, keypair: Keypair) -> str:
        """Transfer one license token to ``recipient``.

        The ``keypair`` must correspond to ``LICENSE_AUTHORITY``. This function
        builds and sends a simple SPL token transfer transaction. The caller is
        responsible for funding fees. The returned string is the transaction
        signature.
        """
        client = self._client()
        source_token = get_associated_token_address(
            keypair.pubkey(), Pubkey.from_string(LICENSE_MINT)
        )
        dest_token = get_associated_token_address(
            Pubkey.from_string(recipient), Pubkey.from_string(LICENSE_MINT)
        )
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
