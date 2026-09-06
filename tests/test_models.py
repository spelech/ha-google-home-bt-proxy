"""Tests for models and constants."""
from custom_components.google_home_bt_proxy.const import (
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SCAN_TIMEOUT,
    DOMAIN,
)
from custom_components.google_home_bt_proxy.models import DiscoveredDevice, SpeakerNode


def test_constants():
    """Verify integration constants."""
    assert DOMAIN == "google_home_bt_proxy"
    assert DEFAULT_SCAN_INTERVAL == 10
    assert DEFAULT_SCAN_TIMEOUT == 5


def test_speaker_node_model():
    node = SpeakerNode(
        device_id="spk-123",
        name="Office Speaker",
        ip_address="192.168.1.50",
        auth_token="secret-token-abc",
        hardware="Google Home Mini",
    )
    assert node.device_id == "spk-123"
    assert node.name == "Office Speaker"
    assert node.enabled is True
    assert node.available is True


def test_discovered_device_model():
    dev = DiscoveredDevice(
        mac_address="AA:BB:CC:DD:EE:FF",
        rssi=-72,
        name="Tile Beacon",
        device_type=1,
    )
    assert dev.mac_address == "AA:BB:CC:DD:EE:FF"
    assert dev.rssi == -72
    assert dev.name == "Tile Beacon"
