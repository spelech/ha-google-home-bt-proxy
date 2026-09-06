"""Tests for SpeakerPlaybackDetector."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.google_home_bt_proxy.models import SpeakerNode
from custom_components.google_home_bt_proxy.playback import SpeakerPlaybackDetector


@pytest.fixture
def speaker() -> SpeakerNode:
    return SpeakerNode(
        device_id="spk-123",
        name="Living Room Speaker",
        ip_address="192.168.1.50",
        auth_token="token-abc",
    )


@pytest.fixture
def mock_api_client() -> MagicMock:
    client = MagicMock()
    client.get_bluetooth_status = AsyncMock(return_value={"connected_devices": []})
    return client


@pytest.mark.asyncio
async def test_is_playing_returns_true_when_cast_playing(speaker, mock_api_client) -> None:
    """Verify returns True when Cast V2 reports MEDIA_PLAYER_STATE_PLAYING."""
    detector = SpeakerPlaybackDetector(mock_api_client, cast_timeout=1.0)

    with patch.object(detector, "_check_cast_playing", AsyncMock(return_value=True)):
        is_playing = await detector.async_is_playing(speaker)
        assert is_playing is True


@pytest.mark.asyncio
async def test_is_playing_returns_true_when_bluetooth_streaming(speaker, mock_api_client) -> None:
    """Verify returns True when local Bluetooth status has connected streaming devices."""
    mock_api_client.get_bluetooth_status.return_value = {
        "connected_devices": [
            {"mac_address": "AA:BB:CC:DD:EE:FF", "name": "Pixel 8", "device_class": 5898764}
        ]
    }
    detector = SpeakerPlaybackDetector(mock_api_client, cast_timeout=1.0)

    with patch.object(detector, "_check_cast_playing", AsyncMock(return_value=False)):
        is_playing = await detector.async_is_playing(speaker)
        assert is_playing is True
        mock_api_client.get_bluetooth_status.assert_called_once_with(speaker)


@pytest.mark.asyncio
async def test_is_playing_returns_false_when_idle(speaker, mock_api_client) -> None:
    """Verify returns False when both Cast and Bluetooth are idle."""
    mock_api_client.get_bluetooth_status.return_value = {"connected_devices": []}
    detector = SpeakerPlaybackDetector(mock_api_client, cast_timeout=1.0)

    with patch.object(detector, "_check_cast_playing", AsyncMock(return_value=False)):
        is_playing = await detector.async_is_playing(speaker)
        assert is_playing is False


@pytest.mark.asyncio
async def test_is_playing_handles_exceptions_gracefully(speaker, mock_api_client) -> None:
    """Verify returns False gracefully on network errors or unexpected exceptions."""
    mock_api_client.get_bluetooth_status.side_effect = Exception("API connection dropped")
    detector = SpeakerPlaybackDetector(mock_api_client, cast_timeout=1.0)

    with patch.object(
        detector,
        "_check_cast_playing",
        AsyncMock(side_effect=Exception("Cast socket timeout")),
    ):
        is_playing = await detector.async_is_playing(speaker)
        assert is_playing is False


def test_sync_check_cast_detects_playback(speaker, mock_api_client) -> None:
    """Verify _sync_check_cast inspects media_controller status."""
    detector = SpeakerPlaybackDetector(mock_api_client, cast_timeout=1.0)

    mock_cast = MagicMock()
    mock_cast.media_controller.status.player_state = "PLAYING"

    with patch("pychromecast.Chromecast", return_value=mock_cast):
        assert detector._sync_check_cast(speaker.ip_address, speaker.hardware, speaker.name) is True
        mock_cast.disconnect.assert_called_once()
