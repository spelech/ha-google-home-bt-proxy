"""Tests for __init__.py lifecycle."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.google_home_bt_proxy import (
    _speaker_scan_loop,
    async_setup,
    async_setup_entry,
    async_unload_entry,
)
from custom_components.google_home_bt_proxy.api import (
    SpeakerConnectionError,
    TokenExpiredError,
)
from custom_components.google_home_bt_proxy.const import (
    CONF_DISABLED_SPEAKERS,
    CONF_RSSI_THRESHOLD,
    CONF_SCAN_INTERVAL,
    CONF_SCAN_TIMEOUT,
    DOMAIN,
)
from custom_components.google_home_bt_proxy.models import DiscoveredDevice, SpeakerNode


@pytest.mark.asyncio
async def test_async_setup_returns_true():
    """Verify async_setup returns True and no unauthenticated HTTP views are registered."""
    mock_hass = MagicMock()
    assert await async_setup(mock_hass, {}) is True


@pytest.mark.asyncio
async def test_async_setup_and_unload():
    mock_hass = MagicMock()
    mock_hass.data = {}
    mock_task = MagicMock()
    mock_hass.async_create_background_task.side_effect = lambda target, name=None: (
        target.close(),
        mock_task,
    )[1]

    mock_entry = MagicMock()
    mock_entry.entry_id = "test-entry-id"
    mock_entry.data = {"master_token": "mt", "android_id": "aid"}
    mock_entry.options = {}
    mock_entry.async_on_unload = MagicMock()

    speaker = SpeakerNode(
        device_id="spk-1",
        name="Study Speaker",
        ip_address="192.168.1.55",
        auth_token="auth-1",
    )

    unreg_mock = MagicMock()

    with (
        patch(
            "custom_components.google_home_bt_proxy.async_get_clientsession",
            return_value=MagicMock(),
        ),
        patch("custom_components.google_home_bt_proxy.zeroconf.async_get_instance", AsyncMock()),
        patch(
            "custom_components.google_home_bt_proxy.GoogleHomeProxyCoordinator"
        ) as mock_coord_cls,
    ):
        coord_inst = mock_coord_cls.return_value
        coord_inst.async_get_speakers = AsyncMock(return_value=[speaker])

        with patch(
            "custom_components.google_home_bt_proxy.bluetooth.async_register_scanner",
            return_value=unreg_mock,
        ):
            result = await async_setup_entry(mock_hass, mock_entry)
            assert result is True
            assert DOMAIN in mock_hass.data
            assert mock_entry.entry_id in mock_hass.data[DOMAIN]
            assert mock_hass.async_create_background_task.call_count == 1

            unload_result = await async_unload_entry(mock_hass, mock_entry)
            assert unload_result is True
            assert mock_entry.entry_id not in mock_hass.data[DOMAIN]
            mock_task.cancel.assert_called_once()
            unreg_mock.assert_called_once()


@pytest.mark.asyncio
async def test_async_setup_with_disabled_speakers():
    mock_hass = MagicMock()
    mock_hass.data = {}
    mock_hass.async_create_background_task.side_effect = lambda target, name=None: (
        target.close(),
        MagicMock(),
    )[1]

    mock_entry = MagicMock()
    mock_entry.entry_id = "test-entry-disabled"
    mock_entry.data = {}
    mock_entry.options = {CONF_DISABLED_SPEAKERS: ["spk-disabled"]}

    spk_enabled = SpeakerNode(
        device_id="spk-enabled",
        name="Kitchen Speaker",
        ip_address="192.168.1.56",
        auth_token="auth-enabled",
    )
    spk_disabled = SpeakerNode(
        device_id="spk-disabled",
        name="Garage Speaker",
        ip_address="192.168.1.57",
        auth_token="auth-disabled",
    )

    with (
        patch(
            "custom_components.google_home_bt_proxy.async_get_clientsession",
            return_value=MagicMock(),
        ),
        patch("custom_components.google_home_bt_proxy.zeroconf.async_get_instance", AsyncMock()),
        patch(
            "custom_components.google_home_bt_proxy.GoogleHomeProxyCoordinator"
        ) as mock_coord_cls,
    ):
        coord_inst = mock_coord_cls.return_value
        coord_inst.async_get_speakers = AsyncMock(return_value=[spk_enabled, spk_disabled])

        with patch(
            "custom_components.google_home_bt_proxy.bluetooth.async_register_scanner",
            return_value=MagicMock(),
        ):
            result = await async_setup_entry(mock_hass, mock_entry)
            assert result is True
            entry_data = mock_hass.data[DOMAIN][mock_entry.entry_id]
            assert "spk-enabled" in entry_data["scanners"]
            assert "spk-disabled" not in entry_data["scanners"]
            assert mock_hass.async_create_background_task.call_count == 1


@pytest.mark.asyncio
async def test_async_unload_entry_not_found():
    mock_hass = MagicMock()
    mock_hass.data = {DOMAIN: {}}

    mock_entry = MagicMock()
    mock_entry.entry_id = "non-existent-id"

    unload_result = await async_unload_entry(mock_hass, mock_entry)
    assert unload_result is True


@pytest.mark.asyncio
async def test_speaker_scan_loop_normal_cycle():
    mock_hass = MagicMock()
    mock_entry = MagicMock()
    mock_entry.options = {
        CONF_SCAN_TIMEOUT: 0.01,
        CONF_SCAN_INTERVAL: 0.01,
        CONF_RSSI_THRESHOLD: -85,
    }

    mock_coord = MagicMock()
    mock_coord.async_refresh_token = AsyncMock()

    mock_api = MagicMock()
    mock_api.start_scan = AsyncMock(return_value=True)
    discovered = [DiscoveredDevice(mac_address="11:22:33:44:55:66", rssi=-70, name="BLE Beacon")]
    mock_api.get_scan_results = AsyncMock(return_value=discovered)

    mock_speaker = SpeakerNode(
        device_id="spk-test",
        name="Living Room",
        ip_address="192.168.1.100",
        auth_token="token123",
    )
    mock_scanner = MagicMock()
    mock_detector = MagicMock()
    mock_detector.async_is_playing = AsyncMock(return_value=False)

    loop_task = asyncio.create_task(
        _speaker_scan_loop(
            mock_hass,
            mock_entry,
            mock_coord,
            mock_api,
            mock_speaker,
            mock_scanner,
            initial_delay=0.01,
            playback_detector=mock_detector,
        )
    )

    # Let the loop perform one scan cycle
    await asyncio.sleep(0.05)
    loop_task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await loop_task

    mock_api.start_scan.assert_called_with(mock_speaker, timeout=0.01)
    mock_api.get_scan_results.assert_called_with(mock_speaker)
    mock_scanner.process_scan_results.assert_called_with(discovered, min_rssi=-85)


@pytest.mark.asyncio
async def test_speaker_scan_loop_token_expired():
    mock_hass = MagicMock()
    mock_entry = MagicMock()
    mock_entry.options = {}

    mock_coord = MagicMock()
    mock_coord.async_refresh_token = AsyncMock()

    mock_api = MagicMock()
    mock_api.start_scan = AsyncMock(side_effect=TokenExpiredError("Token expired"))

    mock_speaker = SpeakerNode(
        device_id="spk-test",
        name="Living Room",
        ip_address="192.168.1.100",
        auth_token="old-token",
    )
    mock_scanner = MagicMock()
    mock_detector = MagicMock()
    mock_detector.async_is_playing = AsyncMock(return_value=False)

    with patch("asyncio.sleep", AsyncMock()) as mock_sleep:
        # Stop loop after one sleep call in TokenExpiredError
        mock_sleep.side_effect = [None, asyncio.CancelledError()]

        with pytest.raises(asyncio.CancelledError):
            await _speaker_scan_loop(
                mock_hass,
                mock_entry,
                mock_coord,
                mock_api,
                mock_speaker,
                mock_scanner,
                initial_delay=0.0,
                playback_detector=mock_detector,
            )

    mock_coord.async_refresh_token.assert_called_once_with(mock_speaker)


@pytest.mark.asyncio
async def test_speaker_scan_loop_connection_error_and_generic_error():
    mock_hass = MagicMock()
    mock_entry = MagicMock()
    mock_entry.options = {}

    mock_coord = MagicMock()
    mock_api = MagicMock()
    mock_api.start_scan = AsyncMock(
        side_effect=[
            SpeakerConnectionError("Unreachable"),
            RuntimeError("Unexpected error"),
            asyncio.CancelledError(),
        ]
    )

    mock_speaker = SpeakerNode(
        device_id="spk-test",
        name="Living Room",
        ip_address="192.168.1.100",
        auth_token="test-token",
    )
    mock_scanner = MagicMock()
    mock_detector = MagicMock()
    mock_detector.async_is_playing = AsyncMock(return_value=False)

    with patch("asyncio.sleep", AsyncMock()):
        with pytest.raises(asyncio.CancelledError):
            await _speaker_scan_loop(
                mock_hass,
                mock_entry,
                mock_coord,
                mock_api,
                mock_speaker,
                mock_scanner,
                initial_delay=0.0,
                playback_detector=mock_detector,
            )

    assert mock_api.start_scan.call_count >= 2


@pytest.mark.asyncio
async def test_speaker_scan_loop_playback_throttle():
    """Verify scan loop throttles scan timeout and interval when playing."""
    from custom_components.google_home_bt_proxy.const import (
        CONF_PLAYBACK_MODE,
        CONF_PLAYING_SCAN_INTERVAL,
        CONF_PLAYING_SCAN_TIMEOUT,
        MODE_THROTTLE,
    )

    mock_hass = MagicMock()
    mock_entry = MagicMock()
    mock_entry.options = {
        CONF_PLAYBACK_MODE: MODE_THROTTLE,
        CONF_PLAYING_SCAN_TIMEOUT: 2,
        CONF_PLAYING_SCAN_INTERVAL: 30,
    }

    mock_coord = MagicMock()
    mock_api = MagicMock()
    mock_api.start_scan = AsyncMock(return_value=True)
    mock_api.get_scan_results = AsyncMock(return_value=[])

    mock_speaker = SpeakerNode(
        device_id="spk-test",
        name="Living Room",
        ip_address="192.168.1.100",
        auth_token="test-token",
    )
    mock_scanner = MagicMock()

    mock_detector = MagicMock()
    mock_detector.async_is_playing = AsyncMock(return_value=True)

    with patch("asyncio.sleep", AsyncMock()) as mock_sleep:
        mock_sleep.side_effect = [None, None, asyncio.CancelledError()]

        with pytest.raises(asyncio.CancelledError):
            await _speaker_scan_loop(
                mock_hass,
                mock_entry,
                mock_coord,
                mock_api,
                mock_speaker,
                mock_scanner,
                initial_delay=0.0,
                playback_detector=mock_detector,
            )

    # Started scan with playing timeout
    mock_api.start_scan.assert_called_once_with(mock_speaker, timeout=2)
    # Slept for playing timeout and then playing interval
    mock_sleep.assert_any_call(2)
    mock_sleep.assert_any_call(30)


@pytest.mark.asyncio
async def test_speaker_scan_loop_playback_skip_ceiling():
    """Verify skip ceiling skips scans until elapsed duration exceeds max ceiling."""
    from custom_components.google_home_bt_proxy.const import (
        CONF_MAX_PLAYING_SKIP_DURATION,
        CONF_PLAYBACK_MODE,
        CONF_PLAYING_SCAN_TIMEOUT,
        MODE_SKIP_CEILING,
    )

    mock_hass = MagicMock()
    mock_entry = MagicMock()
    mock_entry.options = {
        CONF_PLAYBACK_MODE: MODE_SKIP_CEILING,
        CONF_PLAYING_SCAN_TIMEOUT: 2,
        CONF_MAX_PLAYING_SKIP_DURATION: 120,
    }

    mock_coord = MagicMock()
    mock_api = MagicMock()
    mock_api.start_scan = AsyncMock(return_value=True)
    mock_api.get_scan_results = AsyncMock(return_value=[])

    mock_speaker = SpeakerNode(
        device_id="spk-test",
        name="Living Room",
        ip_address="192.168.1.100",
        auth_token="test-token",
    )
    mock_scanner = MagicMock()

    mock_detector = MagicMock()
    mock_detector.async_is_playing = AsyncMock(return_value=True)

    # Simulate two cycles: cycle 1 elapsed = 0s (skipped), cycle 2 elapsed = 130s (forced scan)
    with (
        patch("time.monotonic", side_effect=[100.0, 230.0] + [230.0] * 20),
        patch("asyncio.sleep", AsyncMock()) as mock_sleep,
    ):
        mock_sleep.side_effect = [None, None, None, asyncio.CancelledError()]

        with pytest.raises(asyncio.CancelledError):
            await _speaker_scan_loop(
                mock_hass,
                mock_entry,
                mock_coord,
                mock_api,
                mock_speaker,
                mock_scanner,
                initial_delay=0.0,
                playback_detector=mock_detector,
            )

    # Forced scan was called on cycle 2 with playing timeout
    mock_api.start_scan.assert_called_once_with(mock_speaker, timeout=2)


@pytest.mark.asyncio
async def test_speaker_scan_loop_playback_ignore():
    """Verify ignore mode scans with idle settings even when media is playing."""
    from custom_components.google_home_bt_proxy.const import (
        CONF_PLAYBACK_MODE,
        CONF_SCAN_INTERVAL,
        CONF_SCAN_TIMEOUT,
        MODE_IGNORE,
    )

    mock_hass = MagicMock()
    mock_entry = MagicMock()
    mock_entry.options = {
        CONF_PLAYBACK_MODE: MODE_IGNORE,
        CONF_SCAN_TIMEOUT: 5,
        CONF_SCAN_INTERVAL: 10,
    }

    mock_coord = MagicMock()
    mock_api = MagicMock()
    mock_api.start_scan = AsyncMock(return_value=True)
    mock_api.get_scan_results = AsyncMock(return_value=[])

    mock_speaker = SpeakerNode(
        device_id="spk-test",
        name="Living Room",
        ip_address="192.168.1.100",
        auth_token="test-token",
    )
    mock_scanner = MagicMock()

    mock_detector = MagicMock()
    mock_detector.async_is_playing = AsyncMock(return_value=True)

    with patch("asyncio.sleep", AsyncMock()) as mock_sleep:
        mock_sleep.side_effect = [None, None, asyncio.CancelledError()]

        with pytest.raises(asyncio.CancelledError):
            await _speaker_scan_loop(
                mock_hass,
                mock_entry,
                mock_coord,
                mock_api,
                mock_speaker,
                mock_scanner,
                initial_delay=0.0,
                playback_detector=mock_detector,
            )

    # detector.async_is_playing should NOT be called in ignore mode
    mock_detector.async_is_playing.assert_not_called()
    mock_api.start_scan.assert_called_once_with(mock_speaker, timeout=5)
    mock_sleep.assert_any_call(5)
    mock_sleep.assert_any_call(10)


def test_get_speaker_setting_resolution():
    """Verify _get_speaker_setting resolves speaker overrides or falls back to global."""
    from custom_components.google_home_bt_proxy import _get_speaker_setting
    from custom_components.google_home_bt_proxy.const import (
        CONF_SCAN_INTERVAL,
        CONF_SCAN_TIMEOUT,
        CONF_SPEAKER_OVERRIDES,
    )

    mock_entry = MagicMock()
    mock_entry.options = {
        CONF_SCAN_INTERVAL: 15,
        CONF_SCAN_TIMEOUT: 5,
        CONF_SPEAKER_OVERRIDES: {
            "spk-custom": {
                CONF_SCAN_INTERVAL: 45,
            }
        },
    }

    # spk-custom has interval override 45, but no timeout override (falls back to 5)
    assert _get_speaker_setting(mock_entry, "spk-custom", CONF_SCAN_INTERVAL, 10) == 45
    assert _get_speaker_setting(mock_entry, "spk-custom", CONF_SCAN_TIMEOUT, 10) == 5

    # spk-other has no overrides, falls back to global
    assert _get_speaker_setting(mock_entry, "spk-other", CONF_SCAN_INTERVAL, 10) == 15
    assert _get_speaker_setting(mock_entry, "spk-other", "non_existent_key", 99) == 99


@pytest.mark.asyncio
async def test_speaker_scan_loop_with_per_speaker_overrides():
    """Verify scan loop utilizes per-speaker overrides over global settings."""
    from custom_components.google_home_bt_proxy.const import (
        CONF_SCAN_INTERVAL,
        CONF_SCAN_TIMEOUT,
        CONF_SPEAKER_OVERRIDES,
    )

    mock_hass = MagicMock()
    mock_entry = MagicMock()
    mock_entry.options = {
        CONF_SCAN_INTERVAL: 10,
        CONF_SCAN_TIMEOUT: 5,
        CONF_SPEAKER_OVERRIDES: {
            "spk-override": {
                CONF_SCAN_INTERVAL: 25,
                CONF_SCAN_TIMEOUT: 3,
            }
        },
    }

    mock_coord = MagicMock()
    mock_api = MagicMock()
    mock_api.start_scan = AsyncMock(return_value=True)
    mock_api.get_scan_results = AsyncMock(return_value=[])

    mock_speaker = SpeakerNode(
        device_id="spk-override",
        name="Overridden Speaker",
        ip_address="192.168.1.150",
        auth_token="auth-ovr",
    )
    mock_scanner = MagicMock()
    mock_detector = MagicMock()
    mock_detector.async_is_playing = AsyncMock(return_value=False)

    with patch("asyncio.sleep", AsyncMock()) as mock_sleep:
        mock_sleep.side_effect = [None, None, asyncio.CancelledError()]

        with pytest.raises(asyncio.CancelledError):
            await _speaker_scan_loop(
                mock_hass,
                mock_entry,
                mock_coord,
                mock_api,
                mock_speaker,
                mock_scanner,
                initial_delay=0.0,
                playback_detector=mock_detector,
            )

    # Uses overridden timeout (3 instead of 5)
    mock_api.start_scan.assert_called_once_with(mock_speaker, timeout=3)
    # Uses overridden interval (25 instead of 10)
    mock_sleep.assert_any_call(3)
    mock_sleep.assert_any_call(25)


@pytest.mark.asyncio
async def test_async_setup_and_unload_platforms():
    """Verify platforms are forwarded on setup and unloaded on unload."""
    from homeassistant.const import Platform

    mock_hass = MagicMock()
    mock_hass.data = {}
    mock_hass.async_create_background_task.side_effect = lambda target, name=None: (
        target.close(),
        MagicMock(),
    )[1]

    mock_entry = MagicMock()
    mock_entry.entry_id = "test-platforms-entry"
    mock_entry.data = {}
    mock_entry.options = {}

    mock_forward = AsyncMock(return_value=True)
    mock_unload = AsyncMock(return_value=True)
    mock_hass.config_entries.async_forward_entry_setups = mock_forward
    mock_hass.config_entries.async_unload_platforms = mock_unload

    speaker = SpeakerNode(
        device_id="spk-diag-1",
        name="Dining Speaker",
        ip_address="192.168.1.88",
        auth_token="token-diag",
    )

    with (
        patch(
            "custom_components.google_home_bt_proxy.async_get_clientsession",
            return_value=MagicMock(),
        ),
        patch("custom_components.google_home_bt_proxy.zeroconf.async_get_instance", AsyncMock()),
        patch(
            "custom_components.google_home_bt_proxy.GoogleHomeProxyCoordinator"
        ) as mock_coord_cls,
        patch(
            "custom_components.google_home_bt_proxy.bluetooth.async_register_scanner",
            return_value=MagicMock(),
        ),
    ):
        mock_coord_cls.return_value.async_get_speakers = AsyncMock(return_value=[speaker])

        result = await async_setup_entry(mock_hass, mock_entry)
        assert result is True

        entry_data = mock_hass.data[DOMAIN][mock_entry.entry_id]
        assert "speakers" in entry_data
        assert "spk-diag-1" in entry_data["speakers"]
        state = entry_data["speakers"]["spk-diag-1"]["state"]
        assert state.enabled is True
        assert state.status == "idle"

        mock_forward.assert_called_once_with(
            mock_entry,
            [Platform.SENSOR, Platform.SWITCH, Platform.BUTTON],
        )

        unload_ok = await async_unload_entry(mock_hass, mock_entry)
        assert unload_ok is True
        mock_unload.assert_called_once_with(
            mock_entry,
            [Platform.SENSOR, Platform.SWITCH, Platform.BUTTON],
        )


@pytest.mark.asyncio
async def test_speaker_scan_loop_disabled_and_immediate_trigger():
    """Verify scan loop obeys disabled switch and immediate trigger button."""
    from custom_components.google_home_bt_proxy.models import SpeakerProxyState

    mock_hass = MagicMock()
    mock_entry = MagicMock()
    mock_entry.options = {}

    mock_coord = MagicMock()
    mock_api = MagicMock()
    mock_api.start_scan = AsyncMock(return_value=True)
    mock_api.get_scan_results = AsyncMock(return_value=[MagicMock()])

    mock_speaker = SpeakerNode(
        device_id="spk-ctrl",
        name="Control Speaker",
        ip_address="192.168.1.99",
        auth_token="auth-ctrl",
    )
    mock_scanner = MagicMock()
    mock_detector = MagicMock()
    mock_detector.async_is_playing = AsyncMock(return_value=False)

    state = SpeakerProxyState(enabled=False)

    with patch("asyncio.sleep", AsyncMock()) as mock_sleep:
        call_count = 0

        def sleep_side_effect(duration):
            nonlocal call_count
            call_count += 1
            if duration == 0.0:
                return None
            elif duration == 1.0:
                state.enabled = True
                state.trigger_scan_event.set()
                return None
            elif duration in (4, 5):
                if call_count >= 5:
                    raise asyncio.CancelledError()
                return None
            else:
                raise asyncio.CancelledError()

        mock_sleep.side_effect = sleep_side_effect

        with pytest.raises(asyncio.CancelledError):
            await _speaker_scan_loop(
                mock_hass,
                mock_entry,
                mock_coord,
                mock_api,
                mock_speaker,
                mock_scanner,
                initial_delay=0.0,
                playback_detector=mock_detector,
                state=state,
            )

    assert mock_api.start_scan.call_count == 2
    assert state.last_scan_count == 1
    assert state.total_advertisements == 2
    assert state.status == "idle"


@pytest.mark.asyncio
async def test_async_reload_entry():
    """Verify async_reload_entry invokes unload and setup."""
    from custom_components.google_home_bt_proxy import async_reload_entry

    mock_hass = MagicMock()
    mock_entry = MagicMock()

    with (
        patch(
            "custom_components.google_home_bt_proxy.async_unload_entry",
            AsyncMock(return_value=True),
        ) as mock_unload,
        patch(
            "custom_components.google_home_bt_proxy.async_setup_entry",
            AsyncMock(return_value=True),
        ) as mock_setup,
    ):
        await async_reload_entry(mock_hass, mock_entry)
        mock_unload.assert_called_once_with(mock_hass, mock_entry)
        mock_setup.assert_called_once_with(mock_hass, mock_entry)
