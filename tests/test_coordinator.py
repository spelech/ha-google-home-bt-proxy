"""Tests for coordinator."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.google_home_bt_proxy.coordinator import (
    GoogleHomeProxyCoordinator,
    resolve_cast_ipv4_map,
)
from custom_components.google_home_bt_proxy.models import SpeakerNode


@pytest.mark.asyncio
async def test_coordinator_get_speakers():
    mock_hass = MagicMock()
    mock_hass.async_add_executor_job = AsyncMock()

    mock_dev1 = MagicMock()
    mock_dev1.device_id = "spk-1"
    mock_dev1.device_name = "Living Room Speaker"
    mock_dev1.ip_address = "192.168.1.10"
    mock_dev1.local_auth_token = "token-1"
    mock_dev1.hardware = "Google Home"

    mock_hass.async_add_executor_job.return_value = [mock_dev1]

    coordinator = GoogleHomeProxyCoordinator(
        hass=mock_hass,
        master_token="test-master-token",
        android_id="test-android-id",
    )

    speakers = await coordinator.async_get_speakers()
    assert len(speakers) == 1
    assert speakers[0].name == "Living Room Speaker"
    assert speakers[0].ip_address == "192.168.1.10"
    assert speakers[0].auth_token == "token-1"


@pytest.mark.asyncio
async def test_coordinator_get_speakers_cached():
    mock_hass = MagicMock()
    mock_hass.async_add_executor_job = AsyncMock()

    mock_dev = MagicMock()
    mock_dev.device_id = "spk-1"
    mock_dev.device_name = "Kitchen Speaker"
    mock_dev.ip_address = "192.168.1.20"
    mock_dev.local_auth_token = "token-xyz"
    mock_dev.hardware = "Google Nest Mini"

    mock_hass.async_add_executor_job.return_value = [mock_dev]

    coordinator = GoogleHomeProxyCoordinator(
        hass=mock_hass,
        master_token="test-master-token",
        android_id="test-android-id",
    )

    speakers_first = await coordinator.async_get_speakers()
    assert len(speakers_first) == 1
    assert mock_hass.async_add_executor_job.call_count == 1

    # Second call without force_reload should use cached speakers
    speakers_second = await coordinator.async_get_speakers(force_reload=False)
    assert len(speakers_second) == 1
    assert mock_hass.async_add_executor_job.call_count == 1


@pytest.mark.asyncio
async def test_coordinator_skips_invalid_devices():
    mock_hass = MagicMock()
    mock_hass.async_add_executor_job = AsyncMock()

    dev_valid = MagicMock()
    dev_valid.device_id = "spk-1"
    dev_valid.device_name = "Valid Speaker"
    dev_valid.ip_address = "192.168.1.10"
    dev_valid.local_auth_token = "token-1"
    dev_valid.hardware = "Google Home"

    dev_no_ip = MagicMock()
    dev_no_ip.device_id = "spk-2"
    dev_no_ip.device_name = "No IP Speaker"
    dev_no_ip.ip_address = None
    dev_no_ip.local_auth_token = "token-2"

    dev_no_token = MagicMock()
    dev_no_token.device_id = "spk-3"
    dev_no_token.device_name = "No Token Speaker"
    dev_no_token.ip_address = "192.168.1.30"
    dev_no_token.local_auth_token = None

    mock_hass.async_add_executor_job.return_value = [dev_valid, dev_no_ip, dev_no_token]

    coordinator = GoogleHomeProxyCoordinator(
        hass=mock_hass,
        master_token="test-master-token",
    )

    speakers = await coordinator.async_get_speakers()
    assert len(speakers) == 1
    assert speakers[0].device_id == "spk-1"


@pytest.mark.asyncio
async def test_coordinator_refresh_token():
    mock_hass = MagicMock()

    speaker = SpeakerNode(
        device_id="spk-1",
        name="Living Room Speaker",
        ip_address="192.168.1.10",
        auth_token="old-token",
    )

    refreshed_dev = MagicMock()
    refreshed_dev.device_id = "spk-1"
    refreshed_dev.device_name = "Living Room Speaker"
    refreshed_dev.ip_address = "192.168.1.10"
    refreshed_dev.local_auth_token = "new-token-123"
    refreshed_dev.hardware = "Google Home"

    mock_hass.async_add_executor_job = AsyncMock(return_value=[refreshed_dev])

    coordinator = GoogleHomeProxyCoordinator(
        hass=mock_hass,
        master_token="test-master-token",
    )

    new_token = await coordinator.async_refresh_token(speaker)
    assert new_token == "new-token-123"
    assert speaker.auth_token == "new-token-123"


@pytest.mark.asyncio
async def test_coordinator_refresh_token_not_found():
    mock_hass = MagicMock()

    speaker = SpeakerNode(
        device_id="spk-missing",
        name="Missing Speaker",
        ip_address="192.168.1.99",
        auth_token="old-token",
    )

    mock_hass.async_add_executor_job = AsyncMock(return_value=[])

    coordinator = GoogleHomeProxyCoordinator(
        hass=mock_hass,
        master_token="test-master-token",
    )

    new_token = await coordinator.async_refresh_token(speaker)
    assert new_token is None


@pytest.mark.asyncio
async def test_coordinator_fetch_devices_executor_invoked():
    mock_hass = MagicMock()

    async def run_sync(func):
        return func()

    mock_hass.async_add_executor_job = AsyncMock(side_effect=run_sync)

    coordinator = GoogleHomeProxyCoordinator(
        hass=mock_hass,
        master_token="test-master-token",
    )
    mock_dev = MagicMock()
    mock_dev.device_id = "spk-1"
    mock_dev.device_name = "Living Room Speaker"
    mock_dev.ip_address = "192.168.1.10"
    mock_dev.local_auth_token = "token-1"
    mock_dev.hardware = "Google Home"

    coordinator._client.get_google_devices = MagicMock(return_value=[mock_dev])

    speakers = await coordinator.async_get_speakers(force_reload=True)
    assert len(speakers) == 1
    coordinator._client.get_google_devices.assert_called_once_with(
        zeroconf_instance=None,
        force_homegraph_reload=True,
    )


@pytest.mark.asyncio
async def test_coordinator_skips_non_speaker_cast_hardware():
    """Verify coordinator skips non-speaker Cast hardware (TVs, Shield, AVRs)."""
    mock_hass = MagicMock()
    mock_hass.async_add_executor_job = AsyncMock()

    spk_real = MagicMock(
        device_id="spk-real",
        device_name="Living Room Speaker",
        ip_address="192.168.1.50",
        local_auth_token="token-real",
        hardware="Google Nest Mini",
    )
    dev_shield = MagicMock(
        device_id="shield-1",
        device_name="SHIELD",
        ip_address="192.168.1.51",
        local_auth_token="token-shield",
        hardware="SHIELD Android TV",
    )
    dev_tv = MagicMock(
        device_id="tv-1",
        device_name="Family Room TV",
        ip_address="192.168.1.52",
        local_auth_token="token-tv",
        hardware="Smart TV Pro",
    )
    dev_chromecast = MagicMock(
        device_id="cc-1",
        device_name="Gym TV",
        ip_address="192.168.1.53",
        local_auth_token="token-cc",
        hardware="Chromecast Ultra",
    )
    dev_onkyo = MagicMock(
        device_id="onkyo-1",
        device_name="Onkyo Receiver",
        ip_address="192.168.1.54",
        local_auth_token="token-onkyo",
        hardware="Onkyo TX-NR676",
    )

    mock_hass.async_add_executor_job.return_value = [
        spk_real,
        dev_shield,
        dev_tv,
        dev_chromecast,
        dev_onkyo,
    ]

    coordinator = GoogleHomeProxyCoordinator(
        hass=mock_hass,
        master_token="test-master-token",
    )

    speakers = await coordinator.async_get_speakers()
    assert len(speakers) == 1
    assert speakers[0].device_id == "spk-real"
    assert speakers[0].name == "Living Room Speaker"


def test_resolve_cast_ipv4_map_reuses_hazeroconf():
    """Verify resolve_cast_ipv4_map reuses HA zeroconf without new Zeroconf when records found."""
    mock_ha_zc = MagicMock()
    type(mock_ha_zc).__name__ = "HaZeroconf"
    mock_ha_zc.close = MagicMock()

    mock_info = MagicMock()
    mock_info.parsed_addresses.return_value = ["192.168.1.100"]
    mock_info.properties = {
        b"fn": b"Living Room Speaker",
        b"id": b"7f16e76e-dd80-f2a0-3cfd-084fbb6affd0",
        b"cd": b"E6C5AC2867F5D9202DEAEC1DD1BDEFC5",
    }
    mock_ha_zc.get_service_info.return_value = mock_info

    from unittest.mock import patch

    with (
        patch("custom_components.google_home_bt_proxy.coordinator.ServiceBrowser") as mock_browser,
        patch("custom_components.google_home_bt_proxy.coordinator.Zeroconf") as mock_new_zc,
        patch("time.sleep"),
    ):
        mock_browser_inst = MagicMock()

        def simulate_service(zc, type_, listener):
            listener.add_service(zc, type_, "Google-Nest-Mini._googlecast._tcp.local.")
            return mock_browser_inst

        mock_browser.side_effect = simulate_service

        ipv4_by_id, ipv4_by_name = resolve_cast_ipv4_map(mock_ha_zc, timeout=0.01)

        # Should NOT instantiate a new Zeroconf because records were found
        mock_new_zc.assert_not_called()
        # Should NOT close the shared HaZeroconf
        mock_ha_zc.close.assert_not_called()
        assert ipv4_by_name["living room speaker"] == "192.168.1.100"
        assert ipv4_by_id["7f16e76e-dd80-f2a0-3cfd-084fbb6affd0"] == "192.168.1.100"
        assert ipv4_by_id["e6c5ac2867f5d9202deaec1dd1bdefc5"] == "192.168.1.100"


def test_resolve_cast_ipv4_map_fallback_when_hazeroconf_empty():
    """Verify resolve_cast_ipv4_map invokes standalone Zeroconf when HA zeroconf has 0 records."""
    mock_ha_zc = MagicMock()
    type(mock_ha_zc).__name__ = "HaZeroconf"
    mock_ha_zc.close = MagicMock()

    from unittest.mock import patch

    with (
        patch("custom_components.google_home_bt_proxy.coordinator.ServiceBrowser") as mock_browser,
        patch("custom_components.google_home_bt_proxy.coordinator.Zeroconf") as mock_new_zc,
        patch("time.sleep"),
    ):
        mock_fallback_zc = MagicMock()
        mock_new_zc.return_value = mock_fallback_zc
        mock_browser_inst = MagicMock()
        mock_browser.return_value = mock_browser_inst

        ipv4_by_id, ipv4_by_name = resolve_cast_ipv4_map(mock_ha_zc, timeout=0.01)

        # Should have instantiated fallback Zeroconf and closed it
        mock_new_zc.assert_called_once()
        mock_fallback_zc.close.assert_called_once()
        # HaZeroconf should never be closed
        mock_ha_zc.close.assert_not_called()


def test_resolve_cast_ipv4_map_fallback_when_none():
    """Verify resolve_cast_ipv4_map creates and closes standalone Zeroconf when zc is None."""
    from unittest.mock import patch

    with (
        patch("custom_components.google_home_bt_proxy.coordinator.ServiceBrowser") as mock_browser,
        patch("custom_components.google_home_bt_proxy.coordinator.Zeroconf") as mock_new_zc,
        patch("time.sleep"),
    ):
        mock_zc_inst = MagicMock()
        mock_new_zc.return_value = mock_zc_inst
        mock_browser_inst = MagicMock()
        mock_browser.return_value = mock_browser_inst

        ipv4_by_id, ipv4_by_name = resolve_cast_ipv4_map(None, timeout=0.01)

        mock_new_zc.assert_called_once()
        mock_zc_inst.close.assert_called_once()
        mock_browser_inst.cancel.assert_called_once()


def test_coordinator_initializes_glocaltokens_with_empty_password_and_master_token():
    """Verify coordinator passes empty password to glocaltokens to bypass upstream check."""
    mock_hass = MagicMock()
    token = "aas_et/test_valid_master_token_format_1234567890"
    coordinator = GoogleHomeProxyCoordinator(
        hass=mock_hass,
        username="test@example.com",
        master_token=token,
        android_id="android_id_123",
    )

    assert coordinator._client.username == "test@example.com"
    assert coordinator._client.password == ""
    assert coordinator._client.master_token == token
    # Verify glocaltokens get_master_token returns master_token without missing password error
    assert coordinator._client.get_master_token() == token


@pytest.mark.asyncio
async def test_coordinator_resolves_ipv4_from_certificate_hash():
    """Verify coordinator resolves non-IPv4 addresses using certificate hash (cd) unique_id."""
    mock_hass = MagicMock()

    async def run_sync(func):
        return func()

    mock_hass.async_add_executor_job = AsyncMock(side_effect=run_sync)

    dev_ipv6 = MagicMock()
    dev_ipv6.device_id = "spk-1"
    dev_ipv6.device_name = "Living Room Speaker"
    dev_ipv6.ip_address = "fe80::fa0f:f9ff:fe65:5ffe"
    dev_ipv6.local_auth_token = "token-1"
    dev_ipv6.hardware = "Google Nest Mini"

    # NetworkDevice with certificate hash unique_id
    mock_nd = MagicMock()
    mock_nd.unique_id = "E6C5AC2867F5D9202DEAEC1DD1BDEFC5"
    dev_ipv6.network_device = mock_nd

    coordinator = GoogleHomeProxyCoordinator(
        hass=mock_hass,
        master_token="test-master-token",
    )
    coordinator._client.get_google_devices = MagicMock(return_value=[dev_ipv6])

    from unittest.mock import patch

    with patch(
        "custom_components.google_home_bt_proxy.coordinator.resolve_cast_ipv4_map"
    ) as mock_resolve:
        # map has certificate hash in lowercase
        mock_resolve.return_value = (
            {"e6c5ac2867f5d9202deaec1dd1bdefc5": "10.0.0.114"},
            {},
        )
        speakers = await coordinator.async_get_speakers()

    assert len(speakers) == 1
    assert speakers[0].ip_address == "10.0.0.114"
    # Coordinator cache should now be populated
    assert coordinator._ipv4_cache["spk-1"] == "10.0.0.114"


@pytest.mark.asyncio
async def test_coordinator_resolves_ipv4_from_cache_fallback():
    """Verify coordinator uses cached IPv4 when Zeroconf returns no match."""
    mock_hass = MagicMock()

    async def run_sync(func):
        return func()

    mock_hass.async_add_executor_job = AsyncMock(side_effect=run_sync)

    dev_ipv6 = MagicMock()
    dev_ipv6.device_id = "spk-1"
    dev_ipv6.device_name = "Office Speaker"
    dev_ipv6.ip_address = "fe80::22df:b9ff:fe2a:db3c"
    dev_ipv6.local_auth_token = "token-1"
    dev_ipv6.hardware = "Google Home Mini"
    dev_ipv6.network_device = None

    coordinator = GoogleHomeProxyCoordinator(
        hass=mock_hass,
        master_token="test-master-token",
    )
    # Pre-populate cache
    coordinator._ipv4_cache["spk-1"] = "10.0.0.110"
    coordinator._client.get_google_devices = MagicMock(return_value=[dev_ipv6])

    from unittest.mock import patch

    with patch(
        "custom_components.google_home_bt_proxy.coordinator.resolve_cast_ipv4_map"
    ) as mock_resolve:
        mock_resolve.return_value = ({}, {})
        speakers = await coordinator.async_get_speakers()

    assert len(speakers) == 1
    assert speakers[0].ip_address == "10.0.0.110"
