"""Asset registry service."""

import os
import httpx
from typing import List, Dict, Optional
import hashlib

from .dal import DAL


class AssetService:
    """Fetch and store asset metadata."""

    def __init__(self, dal: DAL, url: Optional[str] = None) -> None:
        self.dal = dal
        self.url = url or os.getenv(
            "ASSET_LIST_URL",
            "https://raw.githubusercontent.com/solana-labs/token-list/main/src/tokens/solana.tokenlist.json",
        )

    def refresh(self) -> List[Dict]:
        try:
            resp = httpx.get(self.url, timeout=10)
            tokens = resp.json().get("tokens", [])
        except Exception:
            return self.dal.list_assets()
        checksum = hashlib.sha256(resp.content).hexdigest()
        stored = self.dal.get_meta("asset_checksum")
        if stored == checksum:
            return self.dal.list_assets()
        self.dal.save_assets(tokens)
        self.dal.set_meta("asset_checksum", checksum)
        return tokens

    def list_assets(self) -> List[Dict]:
        assets = self.dal.list_assets()
        if not assets:
            assets = self.refresh()
        return assets
