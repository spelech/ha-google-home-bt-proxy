"""Simulation and disturbance tests using MockGoogleHomeSpeaker."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.google_home_bt_proxy import _speaker_scan_loop
from custom_components.google_home_bt_proxy.api import (
    GoogleHomeApiClient,
    SpeakerConnectionError,
    TokenExpiredError,
)
from custom_components.google_home_bt_proxy.models import SpeakerNode
from custom_components.google_home_bt_proxy.scanner import GoogleHomeRemoteScanner
from tests.harness.mock_speaker import MockGoogleHomeSpeaker


@pytest.mark.asyncio
async def test_simulation_load_and_disturbances(aiohttp_client) -> None:
    """Test high-volume packet injection (25 devices) and error disturbances."""
    mock_speaker = MockGoogleHomeSpeaker(name="Living Room Hub")
    client = await aiohttp_client(mock_speaker.create_app())

    api_client = GoogleHomeApiClient(client.session, port=client.server.port, use_ssl=False)
    speaker = SpeakerNode("hub-1", "Living Room Hub", str(client.server.host), "valid-token")

    scanner = GoogleHomeRemoteScanner("test_scanner", "Living Room Hub Scanner")
    scanner._async_on_advertisement = MagicMock()

    # 1. Normal run with 25 BLE devices
    await api_client.start_scan(speaker, timeout=1)
    assert mock_speaker.scan_count == 1
    results = await api_client.get_scan_results(speaker)
    assert len(results) == 25

    injected = scanner.process_scan_results(results, min_rssi=-85)
    assert injected > 0
    assert scanner._async_on_advertisement.call_count == injected

    # 2. Injected disturbance: 401 Unauthorized
    mock_speaker.simulate_401 = True
    with pytest.raises(TokenExpiredError):
        await api_client.start_scan(speaker, timeout=1)

    # 3. Injected disturbance: HTTP 500 Drop
    mock_speaker.simulate_401 = False
    mock_speaker.simulate_drop = True
    with pytest.raises(SpeakerConnectionError):
        await api_client.start_scan(speaker, timeout=1)


@pytest.mark.asyncio
async def test_token_expiration_recovery(aiohttp_client) -> None:
    """Test token expiration disturbance and subsequent recovery."""
    mock_speaker = MockGoogleHomeSpeaker(name="Office Hub", auth_token="valid-token")
    client = await aiohttp_client(mock_speaker.create_app())

    api_client = GoogleHomeApiClient(client.session, port=client.server.port, use_ssl=False)
    speaker = SpeakerNode("hub-2", "Office Hub", str(client.server.host), "valid-token")

    # Speaker returns 401 Unauthorized
    mock_speaker.simulate_401 = True
    with pytest.raises(TokenExpiredError):
        await api_client.start_scan(speaker, timeout=1)

    # Recover token
    mock_speaker.simulate_401 = False
    mock_speaker.auth_token = "refreshed-token"
    speaker.auth_token = "refreshed-token"

    success = await api_client.start_scan(speaker, timeout=1)
    assert success is True
    results = await api_client.get_scan_results(speaker)
    assert len(results) == 25


@pytest.mark.asyncio
async def test_http_500_drop_handling_and_recovery(aiohttp_client) -> None:
    """Test HTTP 500 simulated network drop on scan, results, and device info."""
    mock_speaker = MockGoogleHomeSpeaker(name="Kitchen Hub")
    client = await aiohttp_client(mock_speaker.create_app())

    api_client = GoogleHomeApiClient(client.session, port=client.server.port, use_ssl=False)
    speaker = SpeakerNode("hub-3", "Kitchen Hub", str(client.server.host), "valid-token")

    # Normal device info
    info = await api_client.get_device_info(speaker)
    assert info["name"] == "Kitchen Hub"

    # Simulate network drop
    mock_speaker.simulate_drop = True

    with pytest.raises(SpeakerConnectionError):
        await api_client.start_scan(speaker, timeout=1)

    with pytest.raises(SpeakerConnectionError):
        await api_client.get_scan_results(speaker)

    with pytest.raises(SpeakerConnectionError):
        await api_client.get_device_info(speaker)

    # Recover
    mock_speaker.simulate_drop = False
    assert await api_client.start_scan(speaker, timeout=1) is True
    results = await api_client.get_scan_results(speaker)
    assert len(results) == 25


@pytest.mark.asyncio
async def test_http_500_server_error_response_handling(aiohttp_client) -> None:
    """Test HTTP 500 internal server error responses without network drop."""
    mock_speaker = MockGoogleHomeSpeaker(name="Bedroom Hub")
    client = await aiohttp_client(mock_speaker.create_app())

    api_client = GoogleHomeApiClient(client.session, port=client.server.port, use_ssl=False)
    speaker = SpeakerNode("hub-5", "Bedroom Hub", str(client.server.host), "valid-token")

    mock_speaker.simulate_500 = True

    assert await api_client.start_scan(speaker, timeout=1) is False
    assert await api_client.get_scan_results(speaker) == []
    assert await api_client.get_device_info(speaker) == {}

    # Recover
    mock_speaker.simulate_500 = False
    assert await api_client.start_scan(speaker, timeout=1) is True
    results = await api_client.get_scan_results(speaker)
    assert len(results) == 25


@pytest.mark.asyncio
async def test_scan_loop_closed_loop_token_refresh(aiohttp_client) -> None:
    """Test full closed-loop scan worker recovering from 401 via coordinator refresh."""
    mock_speaker = MockGoogleHomeSpeaker(name="Patio Hub", auth_token="initial-token")
    client = await aiohttp_client(mock_speaker.create_app())

    api_client = GoogleHomeApiClient(client.session, port=client.server.port, use_ssl=False)
    speaker = SpeakerNode("hub-4", "Patio Hub", str(client.server.host), "initial-token")

    scanner = GoogleHomeRemoteScanner("patio_scanner", "Patio Hub Scanner")
    scanner._async_on_advertisement = MagicMock()

    mock_hass = MagicMock()
    mock_entry = MagicMock()
    mock_entry.options = {
        "scan_timeout": 0.01,
        "scan_interval": 0.01,
        "rssi_threshold": -90,
    }

    mock_coordinator = MagicMock()

    async def fake_refresh(node: SpeakerNode) -> None:
        new_token = "refreshed-secret"
        node.auth_token = new_token
        mock_speaker.auth_token = new_token
        mock_speaker.simulate_401 = False

    mock_coordinator.async_refresh_token = AsyncMock(side_effect=fake_refresh)

    # Trigger 401 initially
    mock_speaker.simulate_401 = True

    real_sleep = asyncio.sleep

    async def fast_sleep(delay: float) -> None:
        await real_sleep(min(delay, 0.01))

    with patch("asyncio.sleep", side_effect=fast_sleep):
        loop_task = asyncio.create_task(
            _speaker_scan_loop(
                mock_hass,
                mock_entry,
                mock_coordinator,
                api_client,
                speaker,
                scanner,
                initial_delay=0.0,
            )
        )

        for _ in range(50):
            if scanner._async_on_advertisement.call_count > 0:
                break
            await real_sleep(0.02)

        loop_task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await loop_task

    mock_coordinator.async_refresh_token.assert_called_once_with(speaker)
    assert speaker.auth_token == "refreshed-secret"
    assert scanner._async_on_advertisement.call_count > 0
