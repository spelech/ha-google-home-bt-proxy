"""Data models for Google Home Bluetooth Proxy."""

from __future__ import annotations

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
