"""Optional in-integration IRK (Identity Resolving Key) resolver for RPAs."""

from __future__ import annotations

import logging
from typing import Any

from bluetooth_data_tools import get_cipher_for_irk, resolve_private_address

from .classification import is_resolvable_private_address

_LOGGER = logging.getLogger(__name__)


def parse_irk_config(config_text: str) -> dict[str, str]:
    """Parse newline or comma-separated `irk_hex:Name` strings into a dict."""
    result: dict[str, str] = {}
    if not config_text:
        return result

    lines = config_text.replace(",", "\n").splitlines()
    for raw_line in lines:
        line = raw_line.strip()
        if not line or ":" not in line:
            continue
        parts = line.split(":", 1)
        irk_hex = parts[0].replace(" ", "").replace("-", "").strip()
        name = parts[1].strip()
        if len(irk_hex) == 32 and name:
            result[irk_hex] = name
        else:
            _LOGGER.warning("Invalid IRK entry '%s' (must be 32 hex chars:Name)", line)
    return result


class IrkResolver:
    """Resolves BLE Resolvable Private Addresses against configured Identity Resolving Keys."""

    def __init__(self, irk_map: dict[str, str] | None = None) -> None:
        """Initialize with an optional map of {irk_hex: friendly_name}."""
        self._ciphers: list[tuple[Any, str]] = []
        if irk_map:
            self.load_irk_map(irk_map)

    @property
    def count(self) -> int:
        """Return count of registered IRK ciphers."""
        return len(self._ciphers)

    def load_irk_map(self, irk_map: dict[str, str]) -> None:
        """Load and prepare AES ciphers for given 128-bit IRK keys."""
        self._ciphers.clear()
        for irk_hex, name in irk_map.items():
            clean_hex = irk_hex.replace(" ", "").replace("-", "").strip()
            if len(clean_hex) != 32:
                _LOGGER.warning(
                    "Skipping IRK for %s: invalid length %d (must be 32 hex chars / 16 bytes)",
                    name,
                    len(clean_hex),
                )
                continue
            try:
                irk_bytes = bytes.fromhex(clean_hex)
                cipher = get_cipher_for_irk(irk_bytes)
                self._ciphers.append((cipher, name))
                _LOGGER.debug("Registered IRK cipher for '%s'", name)
            except Exception as err:
                _LOGGER.error("Failed to initialize cipher for IRK (%s): %s", name, err)

    def resolve(self, address: str) -> str | None:
        """Check if an address is an RPA and matches any registered IRK.

        Returns the friendly name if resolved, or None if unmatched / not an RPA.
        """
        if not is_resolvable_private_address(address):
            return None

        for cipher, name in self._ciphers:
            try:
                if resolve_private_address(cipher, address):
                    _LOGGER.debug("Resolved RPA %s to identity '%s'", address, name)
                    return name
            except Exception as err:
                _LOGGER.debug("Error testing cipher for %s against %s: %s", name, address, err)

        return None
