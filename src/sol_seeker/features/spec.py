"""Authoritative feature specification.

Defines stable index mapping and metadata for all features.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Dict

DEFAULT_DECAY = 0.995


class FeatureCategory(str, Enum):
    """Feature categories grouped by index ranges."""

    LIQUIDITY = "L"
    ORDER_FLOW = "O"
    OWNERSHIP = "H"
    MICROSTRUCTURE = "M"


@dataclass(frozen=True)
class FeatureMeta:
    index: int
    category: FeatureCategory
    decay_lambda: float
    update_fn_key: str
    doc: str


FEATURES: Dict[str, FeatureMeta] = {}

# Explicit MVP feature definitions
FEATURES.update(
    {
        "liq_pool_delta_abs": FeatureMeta(
            index=0,
            category=FeatureCategory.LIQUIDITY,
            decay_lambda=DEFAULT_DECAY,
            update_fn_key="liq_pool_delta_abs",
            doc="Absolute change in pool token reserves per liquidity event.",
        ),
        "liq_pool_delta_ratio": FeatureMeta(
            index=1,
            category=FeatureCategory.LIQUIDITY,
            decay_lambda=DEFAULT_DECAY,
            update_fn_key="liq_pool_delta_ratio",
            doc="Reserve change divided by previous reserves per liquidity event.",
        ),
        "of_signed_volume": FeatureMeta(
            index=64,
            category=FeatureCategory.ORDER_FLOW,
            decay_lambda=DEFAULT_DECAY,
            update_fn_key="of_signed_volume",
            doc="Cumulative signed base volume since last slot.",
        ),
        "of_trade_count": FeatureMeta(
            index=65,
            category=FeatureCategory.ORDER_FLOW,
            decay_lambda=DEFAULT_DECAY,
            update_fn_key="of_trade_count",
            doc="Number of swaps observed within the slot.",
        ),
        "of_ia_time_ms": FeatureMeta(
            index=66,
            category=FeatureCategory.ORDER_FLOW,
            decay_lambda=DEFAULT_DECAY,
            update_fn_key="of_ia_time_ms",
            doc="Inter-arrival time between swaps in milliseconds.",
        ),
        "own_top_wallet_gini": FeatureMeta(
            index=128,
            category=FeatureCategory.OWNERSHIP,
            decay_lambda=DEFAULT_DECAY,
            update_fn_key="own_top_wallet_gini",
            doc="Gini coefficient of top holders, recomputed periodically.",
        ),
        "own_holder_entropy": FeatureMeta(
            index=129,
            category=FeatureCategory.OWNERSHIP,
            decay_lambda=DEFAULT_DECAY,
            update_fn_key="own_holder_entropy",
            doc="Entropy of holder distribution, recomputed periodically.",
        ),
        "mic_tick_volatility": FeatureMeta(
            index=192,
            category=FeatureCategory.MICROSTRUCTURE,
            decay_lambda=DEFAULT_DECAY,
            update_fn_key="mic_tick_volatility",
            doc="Rolling standard deviation of mid-price over last 25 swaps.",
        ),
        "mic_spread_bps": FeatureMeta(
            index=193,
            category=FeatureCategory.MICROSTRUCTURE,
            decay_lambda=DEFAULT_DECAY,
            update_fn_key="mic_spread_bps",
            doc="Bid-ask spread in basis points per tick update.",
        ),
    }
)

# Tombstone remaining indices to maintain stable mapping
USED_INDICES = {meta.index for meta in FEATURES.values()}
for i in range(256):
    if i in USED_INDICES:
        continue
    if i < 64:
        cat = FeatureCategory.LIQUIDITY
    elif i < 128:
        cat = FeatureCategory.ORDER_FLOW
    elif i < 192:
        cat = FeatureCategory.OWNERSHIP
    else:
        cat = FeatureCategory.MICROSTRUCTURE
    FEATURES[f"tombstone_{i}"] = FeatureMeta(
        index=i,
        category=cat,
        decay_lambda=DEFAULT_DECAY,
        update_fn_key="",
        doc="Tombstoned feature slot.",
    )


def idx(key: str) -> int:
    """Return the stable index for a feature key.

    Raises:
        KeyError: If the key is not present in the spec.
    """

    try:
        return FEATURES[key].index
    except KeyError as exc:  # pragma: no cover - explicit error branch
        raise KeyError(f"Unknown feature: {key}") from exc
