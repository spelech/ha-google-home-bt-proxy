"""Data models for Google Home Bluetooth Proxy."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field


@dataclass
class SpeakerNode:
    """Represents a physical Google Home / Nest speaker acting as a proxy node."""

    device_id: str
    name: str
    ip_address: str
    auth_token: str
    hardware: str = "Google Home"
    enabled: bool = True
    available: bool = True


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
    last_scan_count: int = 0
    last_scan_duration: float = 0.0
    last_scan_timestamp: float | None = None
    enabled: bool = True
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
