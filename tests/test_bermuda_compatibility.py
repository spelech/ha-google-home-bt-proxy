"""Tests verifying compatibility with Bermuda Bluetooth Proxy (v0.8.7)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.helpers import device_registry as dr

from custom_components.google_home_bt_proxy import async_setup_entry
from custom_components.google_home_bt_proxy.api import GoogleHomeApiClient
from custom_components.google_home_bt_proxy.button import GoogleHomeBtProxyScanButton
from custom_components.google_home_bt_proxy.const import DOMAIN
from custom_components.google_home_bt_proxy.models import (
    DiscoveredDevice,
    SpeakerNode,
    SpeakerProxyState,
    format_or_derive_mac,
)
from custom_components.google_home_bt_proxy.scanner import GoogleHomeRemoteScanner
from custom_components.google_home_bt_proxy.sensor import GoogleHomeBtProxyStatusSensor
from custom_components.google_home_bt_proxy.switch import GoogleHomeBtProxyScannerSwitch


def bermuda_mac_norm(mac: str) -> str:
    """Replication of Bermuda's mac_norm utility function."""
    to_test = mac
    if len(to_test) == 17:
        if to_test.count(":") == 5:
            return to_test.lower()
        if to_test.count("-") == 5:
            return to_test.replace("-", ":").lower()
        if to_test.count("_") == 5:
            return to_test.replace("_", ":").lower()
    elif len(to_test) == 14 and to_test.count(".") == 2:
        to_test = to_test.replace(".", "")
    if len(to_test) == 12:
        return ":".join(to_test.lower()[i : i + 2] for i in range(0, 12, 2))
    return mac.lower()


def bermuda_mac_math_offset(mac: str | None, offset: int = 0) -> str | None:
    """Replication of Bermuda's mac_math_offset utility function."""
    if mac is None:
        return None
    octet = mac[-2:]
    try:
        octet_int = bytes.fromhex(octet)[0]
    except ValueError:
        return None
    if 0 <= (octet_new := octet_int + offset) <= 255:
        return f"{mac[:-3]}:{(octet_new):02x}"
    return None


def test_mac_derivation_and_normalization():
    """Verify format_or_derive_mac handles real MACs and arbitrary IDs."""
    # Standard MAC formats
    assert format_or_derive_mac("any_id", "aa:bb:cc:dd:ee:ff") == "AA:BB:CC:DD:EE:FF"
    assert format_or_derive_mac("any_id", "AA-BB-CC-DD-EE-FF") == "AA:BB:CC:DD:EE:FF"
    assert format_or_derive_mac("any_id", "aabbccddeeff") == "AA:BB:CC:DD:EE:FF"
    assert format_or_derive_mac("aa:bb:cc:dd:ee:ff") == "AA:BB:CC:DD:EE:FF"

    # Arbitrary non-MAC speaker IDs (derived deterministically)
    mac1 = format_or_derive_mac("google_home_hub_kitchen")
    mac2 = format_or_derive_mac("google_home_hub_kitchen")
    mac3 = format_or_derive_mac("google_home_mini_bedroom")

    assert mac1 == mac2
    assert mac1 != mac3
    assert len(mac1) == 17
    assert mac1.count(":") == 5

    # Check locally administered unicast bit
    first_byte = int(mac1.split(":")[0], 16)
    assert first_byte & 0x02 != 0  # locally administered
    assert first_byte & 0x01 == 0  # unicast

    # Verify Bermuda's mac_norm and mac_math_offset accept derived MAC
    norm = bermuda_mac_norm(mac1)
    assert norm == mac1.lower()
    for offset in range(-3, 3):
        altmac = bermuda_mac_math_offset(norm, offset)
        assert altmac is not None
        assert len(altmac) == 17


def test_speaker_node_mac_address():
    """Verify SpeakerNode always has a valid mac_address."""
    speaker = SpeakerNode(
        device_id="spk-12345",
        name="Living Room Speaker",
        ip_address="192.168.1.100",
        auth_token="token",
    )
    assert speaker.mac_address
    assert len(speaker.mac_address) == 17
    assert speaker.mac_address.count(":") == 5


def test_eureka_mac_extraction():
    """Verify api_client._extract_mac extracts hardware MAC from various eureka structures."""
    # Direct field
    assert (
        GoogleHomeApiClient._extract_mac({"mac_address": "6C:AD:F8:11:22:33"})
        == "6C:AD:F8:11:22:33"
    )
    # device_info nested
    assert (
        GoogleHomeApiClient._extract_mac({"device_info": {"mac_address": "6C:AD:F8:11:22:44"}})
        == "6C:AD:F8:11:22:44"
    )
    # net.wlan0 nested
    assert (
        GoogleHomeApiClient._extract_mac({"net": {"wlan0": {"mac": "6c:ad:f8:11:22:55"}}})
        == "6c:ad:f8:11:22:55"
    )
    # net.ethernet nested
    assert (
        GoogleHomeApiClient._extract_mac({"net": {"ethernet": {"mac": "6c:ad:f8:11:22:66"}}})
        == "6c:ad:f8:11:22:66"
    )
    # wifi.wlan0_mac nested
    assert (
        GoogleHomeApiClient._extract_mac({"wifi": {"wlan0_mac": "6C:AD:F8:11:22:77"}})
        == "6C:AD:F8:11:22:77"
    )
    # Empty / none
    assert GoogleHomeApiClient._extract_mac({}) is None
    assert GoogleHomeApiClient._extract_mac("not_a_dict") is None


def test_scanner_discovered_device_timestamps_dual_case():
    """Verify GoogleHomeRemoteScanner provides timestamps with both uppercase and lowercase keys."""
    scanner = GoogleHomeRemoteScanner(
        scanner_id="AA:BB:CC:DD:EE:FF",
        name="Test Scanner",
    )

    dev1 = DiscoveredDevice(mac_address="11:22:33:44:55:66", rssi=-65)
    dev2 = DiscoveredDevice(mac_address="AA:BB:CC:77:88:99", rssi=-70)

    # Process scan results
    scanner.process_scan_results([dev1, dev2], min_rssi=-90)

    timestamps = scanner.discovered_device_timestamps
    # Bermuda checks uppercase: self.stamps[address.upper()]
    assert "11:22:33:44:55:66" in timestamps
    assert "11:22:33:44:55:66".upper() in timestamps
    assert "AA:BB:CC:77:88:99" in timestamps
    assert "AA:BB:CC:77:88:99".lower() in timestamps

    # Verify deprecated property for older versions
    deprecated_timestamps = scanner._discovered_device_timestamps
    assert "11:22:33:44:55:66".upper() in deprecated_timestamps


def test_bermuda_connlist_resolution_simulation():
    """Simulate Bermuda's exact connlist resolution logic against device registry entries."""
    speaker_mac = "AA:BB:CC:11:22:33"
    scanner_source = speaker_mac.upper()

    # Bermuda's connlist construction (from bermuda_device.py:314-319)
    scanner_address = bermuda_mac_norm(scanner_source)
    connlist = set()
    for offset in range(-3, 3):
        if (altmac := bermuda_mac_math_offset(scanner_address, offset)) is not None:
            connlist.add(("bluetooth", altmac.upper()))
            connlist.add(("mac", altmac))

    # In our integration:
    # 1. Speaker device has connection ("mac", speaker.mac_address.lower())
    speaker_conn = ("mac", speaker_mac.lower())
    assert speaker_conn in connlist

    # 2. Bluetooth scanner device created by HA Bluetooth discovery has
    # ("bluetooth", scanner.source)
    bt_scanner_conn = ("bluetooth", scanner_source)
    assert bt_scanner_conn in connlist


@pytest.mark.asyncio
async def test_async_setup_bermuda_registration():
    """Verify async_setup_entry registers scanner with source_config_entry_id and device_id."""
    mock_hass = MagicMock()
    mock_hass.data = {}
    mock_hass.async_create_background_task.side_effect = lambda target, name=None: (
        target.close(),
        MagicMock(),
    )[1]
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry_bermuda"
    mock_entry.data = {}
    mock_entry.options = {}

    speaker = SpeakerNode(
        device_id="spk_kitchen",
        name="Kitchen Speaker",
        ip_address="192.168.1.50",
        auth_token="token",
        hardware="Google Home Mini",
        mac_address="AA:BB:CC:DD:EE:01",
    )

    mock_coordinator = MagicMock()
    mock_coordinator.async_get_speakers = AsyncMock(return_value=[speaker])

    mock_devreg = MagicMock()
    mock_speaker_dev_entry = MagicMock()
    mock_speaker_dev_entry.id = "devreg_speaker_kitchen_id"
    mock_devreg.async_get_or_create.return_value = mock_speaker_dev_entry

    with (
        patch(
            "custom_components.google_home_bt_proxy.GoogleHomeProxyCoordinator",
            return_value=mock_coordinator,
        ),
        patch(
            "custom_components.google_home_bt_proxy.dr.async_get",
            return_value=mock_devreg,
        ),
        patch(
            "custom_components.google_home_bt_proxy.bluetooth.async_register_scanner",
            return_value=MagicMock(),
        ) as mock_register,
        patch(
            "custom_components.google_home_bt_proxy.async_get_clientsession",
            return_value=MagicMock(),
        ),
        patch(
            "custom_components.google_home_bt_proxy.zeroconf.async_get_instance",
            return_value=MagicMock(),
        ),
    ):
        result = await async_setup_entry(mock_hass, mock_entry)
        assert result is True

        # Verify device registry registration for speaker
        mock_devreg.async_get_or_create.assert_called_once_with(
            config_entry_id=mock_entry.entry_id,
            identifiers={(DOMAIN, speaker.device_id)},
            connections={(dr.CONNECTION_NETWORK_MAC, speaker.mac_address.lower())},
            name=speaker.name,
            manufacturer="Google",
            model=speaker.hardware,
        )

        # Verify bluetooth scanner registration includes source_config_entry_id and source_device_id
        mock_register.assert_called_once()
        _, kwargs = mock_register.call_args
        assert kwargs["source_domain"] == DOMAIN
        assert kwargs["source_model"] == speaker.hardware
        assert kwargs["source_config_entry_id"] == mock_entry.entry_id
        assert kwargs["source_device_id"] == "devreg_speaker_kitchen_id"

        registered_scanner = mock_register.call_args[0][1]
        assert registered_scanner.source == speaker.mac_address.upper()


def test_entity_device_info_connections():
    """Verify entities across platforms declare CONNECTION_NETWORK_MAC."""
    speaker = SpeakerNode(
        device_id="spk_bedroom",
        name="Bedroom Speaker",
        ip_address="192.168.1.51",
        auth_token="token",
        mac_address="6C:AD:F8:AA:BB:CC",
    )
    state = SpeakerProxyState()

    sensor = GoogleHomeBtProxyStatusSensor(speaker, state)
    switch = GoogleHomeBtProxyScannerSwitch(speaker, state)
    button = GoogleHomeBtProxyScanButton(speaker, state)

    expected_conn = {("mac", "6c:ad:f8:aa:bb:cc")}
    assert sensor.device_info["connections"] == expected_conn
    assert switch.device_info["connections"] == expected_conn
    assert button.device_info["connections"] == expected_conn
