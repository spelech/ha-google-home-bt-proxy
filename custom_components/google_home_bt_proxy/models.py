"""Data models for Google Home Bluetooth Proxy."""

from __future__ import annotations

import asyncio
import hashlib
from collections.abc import Callable
from dataclasses import dataclass, field


def format_or_derive_mac(device_id: str, raw_mac: str | None = None) -> str:
    """Return a normalized MAC address (XX:XX:XX:XX:XX:XX) or derive a deterministic unicast MAC."""
    target = raw_mac or device_id
    cleaned = target.replace(":", "").replace("-", "").replace(".", "").strip().upper()
    if len(cleaned) == 12 and all(c in "0123456789ABCDEF" for c in cleaned):
        return ":".join(cleaned[i : i + 2] for i in range(0, 12, 2))

    # Hash device_id to get deterministic bytes
    h = hashlib.sha256(device_id.encode("utf-8")).digest()
    # Set locally administered bit (bit 1) and clear multicast bit (bit 0) on byte 0
    first_byte = (h[0] & 0xFE) | 0x02
    return f"{first_byte:02X}:{h[1]:02X}:{h[2]:02X}:{h[3]:02X}:{h[4]:02X}:{h[5]:02X}"


def mac_math_offset(mac: str | None, offset: int = 0) -> str | None:
    """Calculate an offset MAC address, matching Bermuda's mac_math_offset."""
    if not mac or not isinstance(mac, str):
        return None
    cleaned = mac.strip()
    if len(cleaned) != 17 or cleaned.count(":") != 5:
        return None
    octet = cleaned[-2:]
    try:
        octet_int = bytes.fromhex(octet)[0]
    except ValueError:
        return None
    if 0 <= (octet_new := octet_int + offset) <= 255:
        prefix = cleaned[:-2]
        return f"{prefix}{octet_new:02X}" if cleaned.isupper() else f"{prefix}{octet_new:02x}"
    return None


@dataclass
class SpeakerNode:
    """Represents a physical Google Home / Nest speaker acting as a proxy node."""

    device_id: str
    name: str
    ip_address: str
    auth_token: str
    hardware: str = "Google Home"
    mac_address: str = ""
    enabled: bool = True
    available: bool = True

    def __post_init__(self) -> None:
        """Ensure a valid normalized MAC address is set."""
        self.mac_address = format_or_derive_mac(self.device_id, self.mac_address or None)


@dataclass
class DiscoveredDevice:
    """Represents a Bluetooth device detected by a Google Home speaker scan."""

    mac_address: str
    rssi: int
    name: str | None = None
    device_type: int | None = None
    device_class: int | None = None
    device_class_name: str | None = None
    expected_profiles: int | None = None
    is_rpa: bool = False
    service_uuids: list[str] = field(default_factory=list)


@dataclass
class SpeakerProxyState:
    """Runtime state of a speaker proxy node for operational visibility and controls."""

    status: str = "idle"
    total_advertisements: int = 0
    filtered_advertisements: int = 0
    last_scan_count: int = 0
    last_scan_duration: float = 0.0
    last_scan_timestamp: float | None = None
    enabled: bool = True
    bermuda_mode: bool = True
    rssi_mode: str = "raw"
    assigned_area: str | None = None
    bermuda_area_ready: bool = False
    trigger_scan_event: asyncio.Event = field(default_factory=asyncio.Event)
    callbacks: list[Callable[[], None]] = field(default_factory=list)

    def register_callback(self, cb: Callable[[], None]) -> Callable[[], None]:
        """Register a callback for state changes and return an unregister function."""
        self.callbacks.append(cb)
        return lambda: self.callbacks.remove(cb) if cb in self.callbacks else None

    def notify_callbacks(self) -> None:
        """Notify all registered callbacks of a state change."""
        for cb in list(self.callbacks):
            try:
                cb()
            except Exception:
                pass
