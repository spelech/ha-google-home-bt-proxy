"""Tests for SpeakerPlaybackDetector."""

from __future__ import annotations

import asyncio
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


@pytest.mark.asyncio
async def test_is_playing_uses_ha_state_without_cast_socket(speaker, mock_api_client) -> None:
    """Verify HA state is used with zero socket connections when hass is provided."""
    mock_hass = MagicMock()
    mock_state = MagicMock()
    mock_state.state = "playing"
    mock_hass.states.get.return_value = mock_state
    mock_hass.states.async_all.return_value = []

    detector = SpeakerPlaybackDetector(mock_api_client, hass=mock_hass)

    with patch("pychromecast.Chromecast") as mock_cast_cls:
        is_playing = await detector.async_is_playing(speaker)
        assert is_playing is True
        mock_cast_cls.assert_not_called()


@pytest.mark.asyncio
async def test_is_playing_returns_true_when_whole_home_group_playing(
    speaker, mock_api_client
) -> None:
    """Verify any speaker reports playing if media_player.whole_home is playing."""
    mock_hass = MagicMock()

    def mock_get(entity_id: str):
        if entity_id == "media_player.whole_home":
            s = MagicMock()
            s.state = "playing"
            return s
        return None

    mock_hass.states.get.side_effect = mock_get
    mock_hass.states.async_all.return_value = []

    detector = SpeakerPlaybackDetector(mock_api_client, hass=mock_hass)

    with patch("pychromecast.Chromecast") as mock_cast_cls:
        is_playing = await detector.async_is_playing(speaker)
        assert is_playing is True
        mock_cast_cls.assert_not_called()


@pytest.mark.asyncio
async def test_is_playing_returns_false_when_ha_state_idle(speaker, mock_api_client) -> None:
    """Verify returns False when HA media_player state is idle/off without socket checks."""
    mock_hass = MagicMock()
    mock_state = MagicMock()
    mock_state.state = "idle"
    mock_hass.states.get.return_value = mock_state
    mock_hass.states.async_all.return_value = []

    detector = SpeakerPlaybackDetector(mock_api_client, hass=mock_hass)

    with patch("pychromecast.Chromecast") as mock_cast_cls:
        is_playing = await detector.async_is_playing(speaker)
        assert is_playing is False
        mock_cast_cls.assert_not_called()


@pytest.mark.asyncio
async def test_tts_call_service_intercepts_and_aborts_active_scan(speaker, mock_api_client) -> None:
    """Verify TTS service call immediately marks speaker active and aborts scanning."""
    from custom_components.google_home_bt_proxy.models import SpeakerProxyState

    mock_hass = MagicMock()
    mock_hass.states.get.return_value = None
    mock_hass.states.async_all.return_value = []

    detector = SpeakerPlaybackDetector(mock_api_client, hass=mock_hass)

    proxy_state = SpeakerProxyState(status="scanning")
    speakers_data = {
        speaker.device_id: {
            "speaker": speaker,
            "state": proxy_state,
        }
    }
    unsub = detector.async_setup(speakers_data)

    mock_api_client.stop_scan = AsyncMock(return_value=True)

    # Fire tts.speak targeting this speaker
    tts_event = MagicMock()
    tts_event.data = {
        "domain": "tts",
        "service": "speak",
        "service_data": {
            "media_player_entity_id": f"media_player.{speaker.name.lower().replace(' ', '_')}"
        },
    }

    await detector._handle_call_service(tts_event)

    # TTS must be active immediately
    assert detector.is_tts_active(speaker) is True
    # Abort event must be signaled
    assert proxy_state.abort_scan_event.is_set() is True

    # Allow background safe_stop_scan task to execute
    await asyncio.sleep(0.01)
    mock_api_client.stop_scan.assert_called_once_with(speaker)

    # Calling async_is_playing should return True immediately due to TTS active
    assert await detector.async_is_playing(speaker) is True

    # Cleanup
    unsub()


@pytest.mark.asyncio
async def test_tts_whole_home_broadcast_affects_all_speakers(mock_api_client) -> None:
    """Verify TTS targeting whole_home or broadcast marks all speakers active."""
    from custom_components.google_home_bt_proxy.models import SpeakerProxyState

    spk1 = SpeakerNode(device_id="spk-1", name="Living Room", ip_address="1.1.1.1", auth_token="t1")
    spk2 = SpeakerNode(device_id="spk-2", name="Office", ip_address="1.1.1.2", auth_token="t2")

    mock_hass = MagicMock()
    detector = SpeakerPlaybackDetector(mock_api_client, hass=mock_hass)

    speakers_data = {
        spk1.device_id: {"speaker": spk1, "state": SpeakerProxyState()},
        spk2.device_id: {"speaker": spk2, "state": SpeakerProxyState()},
    }
    detector.async_setup(speakers_data)

    event = MagicMock()
    event.data = {
        "domain": "tts",
        "service": "speak",
        "service_data": {"media_player_entity_id": "media_player.whole_home"},
    }

    await detector._handle_call_service(event)

    assert detector.is_tts_active(spk1) is True
    assert detector.is_tts_active(spk2) is True


@pytest.mark.asyncio
async def test_state_changed_extends_lock_and_applies_cooldown(speaker, mock_api_client) -> None:
    """Verify state change to playing extends reservation, and to idle applies cooldown."""
    from custom_components.google_home_bt_proxy.models import SpeakerProxyState

    mock_hass = MagicMock()
    detector = SpeakerPlaybackDetector(mock_api_client, hass=mock_hass, tts_cooldown=2.0)

    proxy_state = SpeakerProxyState(status="scanning")
    speakers_data = {speaker.device_id: {"speaker": speaker, "state": proxy_state}}
    detector.async_setup(speakers_data)

    mock_api_client.stop_scan = AsyncMock(return_value=True)

    # 1. Transition from idle to playing -> extends lock and aborts scanning
    eid = f"media_player.{speaker.name.lower().replace(' ', '_')}"
    event_playing = MagicMock()
    event_playing.data = {
        "entity_id": eid,
        "old_state": MagicMock(state="idle"),
        "new_state": MagicMock(state="playing"),
    }
    detector._handle_state_changed(event_playing)

    assert detector.is_tts_active(speaker) is True
    assert proxy_state.abort_scan_event.is_set() is True

    # 2. Transition from playing to idle -> sets cooldown
    event_idle = MagicMock()
    event_idle.data = {
        "entity_id": eid,
        "old_state": MagicMock(state="playing"),
        "new_state": MagicMock(state="idle"),
    }
    detector._handle_state_changed(event_idle)

    # Cooldown should keep TTS active for 2.0s
    assert detector.is_tts_active(speaker) is True
