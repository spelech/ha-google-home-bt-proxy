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


def test_playback_constants():
    """Verify playback configuration constants and defaults."""
    from custom_components.google_home_bt_proxy.const import (
        CONF_MAX_PLAYING_SKIP_DURATION,
        CONF_PLAYBACK_MODE,
        CONF_PLAYING_SCAN_INTERVAL,
        CONF_PLAYING_SCAN_TIMEOUT,
        DEFAULT_MAX_PLAYING_SKIP_DURATION,
        DEFAULT_PLAYBACK_MODE,
        DEFAULT_PLAYING_SCAN_INTERVAL,
        DEFAULT_PLAYING_SCAN_TIMEOUT,
        MODE_IGNORE,
        MODE_SKIP_CEILING,
        MODE_THROTTLE,
    )

    assert CONF_PLAYBACK_MODE == "playback_mode"
    assert CONF_PLAYING_SCAN_TIMEOUT == "playing_scan_timeout"
    assert CONF_PLAYING_SCAN_INTERVAL == "playing_scan_interval"
    assert CONF_MAX_PLAYING_SKIP_DURATION == "max_playing_skip_duration"
    assert MODE_THROTTLE == "throttle"
    assert MODE_SKIP_CEILING == "skip_ceiling"
    assert MODE_IGNORE == "ignore"
    assert DEFAULT_PLAYBACK_MODE == MODE_THROTTLE
    assert DEFAULT_PLAYING_SCAN_TIMEOUT == 2
    assert DEFAULT_PLAYING_SCAN_INTERVAL == 30
    assert DEFAULT_MAX_PLAYING_SKIP_DURATION == 120


def test_speaker_override_constants():
    """Verify constants for hierarchical per-speaker configuration."""
    from custom_components.google_home_bt_proxy.const import (
        CONF_CUSTOM_SETTINGS,
        CONF_SELECTED_SPEAKER,
        CONF_SPEAKER_OVERRIDES,
        GLOBAL_SETTINGS,
    )

    assert CONF_SPEAKER_OVERRIDES == "speaker_overrides"
    assert CONF_SELECTED_SPEAKER == "selected_speaker"
    assert CONF_CUSTOM_SETTINGS == "custom_settings"
    assert GLOBAL_SETTINGS == "global"
