"""Tests for coordinator."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.google_home_bt_proxy.coordinator import GoogleHomeProxyCoordinator
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
