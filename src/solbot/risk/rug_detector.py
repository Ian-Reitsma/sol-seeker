from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List


@dataclass
class RugAlert:
    token: str
    reason: str


class RugDetector:
    """Basic heuristics for detecting potential rug pulls.

    The detector consumes simplified token events with the following optional
    boolean/float keys:

    - ``liquidity_removed``: fraction of pool liquidity pulled.
    - ``owner_withdraw``: token owner withdrew funds.
    - ``mint_paused``: mint authority revoked or paused.

    If any of these exceed conservative thresholds the detector records an
    alert for the token.  The design favours readability over exhaustive
    on-chain coverage so unit tests can exercise common rug patterns easily.
    """

    def __init__(self) -> None:
        self._alerts: Dict[str, RugAlert] = {}

    def update(self, event: Dict) -> None:
        token = event.get("token")
        if not token:
            return
        # Large fraction of liquidity yanked from the pool
        if event.get("liquidity_removed", 0.0) > 0.5:
            self._alerts[token] = RugAlert(token, "liquidity removed")
        # Owner suddenly withdrawing funds
        if event.get("owner_withdraw"):
            self._alerts[token] = RugAlert(token, "owner withdrawal")
        # Mint authority paused or burned
        if event.get("mint_paused"):
            self._alerts[token] = RugAlert(token, "mint authority revoked")

    def alerts(self) -> List[RugAlert]:
        return list(self._alerts.values())

    def reset(self) -> None:
        self._alerts.clear()
