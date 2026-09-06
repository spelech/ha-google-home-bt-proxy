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
        hardware="Google Home Mini",
    )


@pytest.fixture
def mock_api_client() -> MagicMock:
    client = MagicMock()
    client.get_bluetooth_status = AsyncMock(return_value={"connected_devices": []})
    return client


@pytest.mark.asyncio
async def test_is_playing_returns_true_when_cast_playing(speaker, mock_api_client) -> None:
    """Verify returns True when Cast V2 reports PLAYING, testing full executor invocation."""
    detector = SpeakerPlaybackDetector(mock_api_client, cast_timeout=1.0)
    mock_cast = MagicMock()
    mock_cast.media_controller.status.player_state = "PLAYING"

    with patch("pychromecast.Chromecast", return_value=mock_cast):
        is_playing = await detector.async_is_playing(speaker)
        assert is_playing is True
        mock_cast.wait.assert_called_once_with(timeout=1.0)
        mock_cast.disconnect.assert_called_once()


@pytest.mark.asyncio
async def test_is_playing_returns_true_when_cast_buffering(speaker, mock_api_client) -> None:
    """Verify returns True when Cast V2 reports BUFFERING."""
    detector = SpeakerPlaybackDetector(mock_api_client, cast_timeout=1.0)
    mock_cast = MagicMock()
    mock_cast.media_controller.status.player_state = "BUFFERING"

    with patch("pychromecast.Chromecast", return_value=mock_cast):
        is_playing = await detector.async_is_playing(speaker)
        assert is_playing is True
        mock_cast.disconnect.assert_called_once()


@pytest.mark.asyncio
async def test_is_playing_returns_false_when_cast_paused(speaker, mock_api_client) -> None:
    """Verify returns False when Cast V2 reports PAUSED."""
    detector = SpeakerPlaybackDetector(mock_api_client, cast_timeout=1.0)
    mock_cast = MagicMock()
    mock_cast.media_controller.status.player_state = "PAUSED"

    with patch("pychromecast.Chromecast", return_value=mock_cast):
        is_playing = await detector.async_is_playing(speaker)
        assert is_playing is False
        mock_cast.disconnect.assert_called_once()


@pytest.mark.asyncio
async def test_is_playing_returns_false_when_cast_idle_or_none(speaker, mock_api_client) -> None:
    """Verify returns False when Cast V2 media controller status is IDLE or None."""
    detector = SpeakerPlaybackDetector(mock_api_client, cast_timeout=1.0)

    # 1. State is IDLE
    mock_cast_idle = MagicMock()
    mock_cast_idle.media_controller.status.player_state = "IDLE"
    with patch("pychromecast.Chromecast", return_value=mock_cast_idle):
        assert await detector.async_is_playing(speaker) is False

    # 2. media_controller is None
    mock_cast_no_mc = MagicMock()
    mock_cast_no_mc.media_controller = None
    with patch("pychromecast.Chromecast", return_value=mock_cast_no_mc):
        assert await detector.async_is_playing(speaker) is False

    # 3. media_controller.status is None
    mock_cast_no_status = MagicMock()
    mock_cast_no_status.media_controller.status = None
    with patch("pychromecast.Chromecast", return_value=mock_cast_no_status):
        assert await detector.async_is_playing(speaker) is False


@pytest.mark.asyncio
async def test_is_playing_returns_true_when_bluetooth_streaming(speaker, mock_api_client) -> None:
    """Verify returns True when local Bluetooth status has connected streaming devices."""
    mock_api_client.get_bluetooth_status.return_value = {
        "connected_devices": [
            {"mac_address": "AA:BB:CC:DD:EE:FF", "name": "Pixel 8", "device_class": 5898764}
        ]
    }
    detector = SpeakerPlaybackDetector(mock_api_client, cast_timeout=1.0)

    # Should short-circuit and return True without needing to invoke Cast socket
    with patch("pychromecast.Chromecast") as mock_cast_cls:
        is_playing = await detector.async_is_playing(speaker)
        assert is_playing is True
        mock_api_client.get_bluetooth_status.assert_called_once_with(speaker)
        mock_cast_cls.assert_not_called()


@pytest.mark.asyncio
async def test_is_playing_returns_false_when_all_idle(speaker, mock_api_client) -> None:
    """Verify returns False when both Bluetooth and Cast are idle."""
    mock_api_client.get_bluetooth_status.return_value = {"connected_devices": []}
    detector = SpeakerPlaybackDetector(mock_api_client, cast_timeout=1.0)
    mock_cast = MagicMock()
    mock_cast.media_controller.status.player_state = "UNKNOWN"

    with patch("pychromecast.Chromecast", return_value=mock_cast):
        is_playing = await detector.async_is_playing(speaker)
        assert is_playing is False


@pytest.mark.asyncio
async def test_is_playing_handles_exceptions_gracefully(speaker, mock_api_client) -> None:
    """Verify returns False gracefully on network errors or unexpected exceptions."""
    mock_api_client.get_bluetooth_status.side_effect = Exception("API connection dropped")
    detector = SpeakerPlaybackDetector(mock_api_client, cast_timeout=1.0)

    with patch("pychromecast.Chromecast", side_effect=Exception("Cast socket timeout")):
        is_playing = await detector.async_is_playing(speaker)
        assert is_playing is False


def test_sync_check_cast_disconnect_on_exception(speaker, mock_api_client) -> None:
    """Verify cast.disconnect() is always called even if inspecting player state raises."""
    detector = SpeakerPlaybackDetector(mock_api_client, cast_timeout=1.0)
    mock_cast = MagicMock()
    type(mock_cast.media_controller).status = property(
        lambda self: (_ for _ in ()).throw(RuntimeError("Inspection error"))
    )

    with patch("pychromecast.Chromecast", return_value=mock_cast):
        result = detector._sync_check_cast(speaker.ip_address, speaker.hardware, speaker.name)
        assert result is False
        mock_cast.disconnect.assert_called_once()
