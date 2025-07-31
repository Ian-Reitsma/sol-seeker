"""Generic utility functions."""

from .config import BotConfig, parse_args
from .license import (
    LicenseManager,
    LICENSE_MINT,
    DEMO_MINT,
    LICENSE_AUTHORITY,
    LICENSE_KEYPAIR_PATH,
    LICENSE_KEYPAIR_KEY,
    load_authority_keypair,
)
from ..service.license_issuer import app as license_issuer_app

__all__ = [
    "BotConfig",
    "parse_args",
    "LicenseManager",
    "LICENSE_MINT",
    "LICENSE_AUTHORITY",
    "DEMO_MINT",
    "LICENSE_KEYPAIR_PATH",
    "LICENSE_KEYPAIR_KEY",
    "load_authority_keypair",
    "license_issuer_app",
]

