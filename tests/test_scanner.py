"""Tests for GoogleHomeRemoteScanner."""

from unittest.mock import MagicMock

from custom_components.google_home_bt_proxy.models import DiscoveredDevice, SpeakerNode
from custom_components.google_home_bt_proxy.scanner import GoogleHomeRemoteScanner


def test_process_scan_results_filters_and_injects():
    speaker = SpeakerNode(
        device_id="spk-kitchen",
        name="Kitchen Speaker",
        ip_address="192.168.1.51",
        auth_token="token-xyz",
    )

    scanner = GoogleHomeRemoteScanner(
        scanner_id=speaker.device_id,
        name=f"{speaker.name} Bluetooth Scanner",
    )

    # Mock the internal _async_on_advertisement method from BaseHaRemoteScanner
    scanner._async_on_advertisement = MagicMock()

    devices = [
        DiscoveredDevice(
            mac_address="11:22:33:44:55:66",
            rssi=-65,
            name="Beacon 1",
            service_uuids=["180a"],
            device_type=1,
        ),
        DiscoveredDevice(
            mac_address="AA:BB:CC:DD:EE:FF",
            rssi=-95,
            name="Weak Beacon",
        ),  # Should be filtered (< -90)
    ]

    injected = scanner.process_scan_results(devices, min_rssi=-90)
    assert injected == 1
    scanner._async_on_advertisement.assert_called_once()
    call_args = scanner._async_on_advertisement.call_args[1]
    assert call_args["address"] == "11:22:33:44:55:66"
    assert call_args["rssi"] == -65
    assert call_args["local_name"] == "Beacon 1"
    assert call_args["service_uuids"] == ["180a"]
    assert call_args["details"]["device_type"] == 1
    assert call_args["details"]["source"] == scanner.source


def test_process_scan_results_empty_and_all_filtered():
    scanner = GoogleHomeRemoteScanner(
        scanner_id="google_home_living_room",
        name="Living Room Speaker Bluetooth Scanner",
    )
    scanner._async_on_advertisement = MagicMock()

    assert scanner.process_scan_results([], min_rssi=-90) == 0
    scanner._async_on_advertisement.assert_not_called()

    weak_devices = [
        DiscoveredDevice(mac_address="11:11:11:11:11:11", rssi=-95),
        DiscoveredDevice(mac_address="22:22:22:22:22:22", rssi=-100),
    ]
    assert scanner.process_scan_results(weak_devices, min_rssi=-90) == 0
    scanner._async_on_advertisement.assert_not_called()
