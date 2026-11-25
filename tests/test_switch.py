"""Tests for Google Home Bluetooth Proxy switch platform."""

from unittest.mock import MagicMock

import pytest

from custom_components.google_home_bt_proxy.const import DOMAIN
from custom_components.google_home_bt_proxy.models import SpeakerNode, SpeakerProxyState
from custom_components.google_home_bt_proxy.switch import (
    GoogleHomeBtProxyScannerSwitch,
    async_setup_entry,
)


@pytest.fixture
def speaker_and_state():
    speaker = SpeakerNode(
        device_id="spk-switch-1",
        name="Living Room Mini",
        ip_address="192.168.1.102",
        auth_token="token-switch",
        hardware="Google Nest Mini",
    )
    state = SpeakerProxyState(enabled=True)
    return speaker, state


@pytest.mark.asyncio
async def test_switch_setup_entry(speaker_and_state):
    speaker, state = speaker_and_state
    mock_hass = MagicMock()
    mock_entry = MagicMock()
    mock_entry.entry_id = "entry-switch-123"

    mock_hass.data = {
        DOMAIN: {
            "entry-switch-123": {
                "speakers": {
                    speaker.device_id: {
                        "speaker": speaker,
                        "state": state,
                    }
                }
            }
        }
    }

    added_entities = []

    def mock_add_entities(entities):
        added_entities.extend(entities)

    await async_setup_entry(mock_hass, mock_entry, mock_add_entities)

    assert len(added_entities) == 1
    assert isinstance(added_entities[0], GoogleHomeBtProxyScannerSwitch)


@pytest.mark.asyncio
async def test_switch_turn_on_and_off(speaker_and_state):
    speaker, state = speaker_and_state
    switch = GoogleHomeBtProxyScannerSwitch(speaker, state)
    switch.async_write_ha_state = MagicMock()

    await switch.async_added_to_hass()

    assert switch.unique_id == "spk-switch-1_scanner_switch"
    assert switch.is_on is True

    await switch.async_turn_off()
    assert state.enabled is False
    assert switch.is_on is False
    switch.async_write_ha_state.assert_called()

    await switch.async_turn_on()
    assert state.enabled is True
    assert switch.is_on is True

    await switch.async_will_remove_from_hass()


@pytest.mark.asyncio
async def test_switch_setup_with_global_state():
    """Verify global and per-speaker toggle switches are registered with global_state."""
    from homeassistant.helpers.device_registry import DeviceEntryType

    from custom_components.google_home_bt_proxy.const import (
        CONF_GLOBAL_SCANNING_ENABLED,
        CONF_PAUSED_SPEAKERS,
    )
    from custom_components.google_home_bt_proxy.models import GlobalProxyState
    from custom_components.google_home_bt_proxy.switch import (
        GoogleHomeBtProxyGlobalScannerSwitch,
    )

    speaker = SpeakerNode(
        device_id="spk-1",
        name="Kitchen Mini",
        ip_address="192.168.1.105",
        auth_token="token-k",
        hardware="Google Nest Mini",
    )
    state = SpeakerProxyState(enabled=True)
    global_state = GlobalProxyState(enabled=True)

    mock_hass = MagicMock()
    mock_entry = MagicMock()
    mock_entry.entry_id = "entry-global-1"
    mock_entry.options = {
        CONF_GLOBAL_SCANNING_ENABLED: True,
        CONF_PAUSED_SPEAKERS: [],
    }
    mock_hass.data = {
        DOMAIN: {
            "entry-global-1": {
                "global_state": global_state,
                "speakers": {
                    speaker.device_id: {
                        "speaker": speaker,
                        "state": state,
                    }
                },
            }
        }
    }

    added_entities = []
    await async_setup_entry(mock_hass, mock_entry, added_entities.extend)

    assert len(added_entities) == 2
    global_sw, spk_sw = added_entities
    assert isinstance(global_sw, GoogleHomeBtProxyGlobalScannerSwitch)
    assert isinstance(spk_sw, GoogleHomeBtProxyScannerSwitch)
    assert global_sw.unique_id == "entry-global-1_global_scanner_switch"
    assert global_sw.device_info["entry_type"] == DeviceEntryType.SERVICE
    assert global_sw.is_on is True
    assert global_sw.extra_state_attributes == {
        "total_speakers": 1,
        "enabled_speakers": 1,
        "paused_speakers": 0,
        "effective_active_speakers": 1,
    }
    assert spk_sw.extra_state_attributes == {
        "status": "idle",
        "global_scanning_enabled": True,
        "effective_scanning": True,
        "speaker_id": "spk-1",
    }


@pytest.mark.asyncio
async def test_speaker_switch_aborts_wakes_and_persists(speaker_and_state):
    """Verify per-speaker switch aborts active scan on off, wakes on on, and calls on_toggle."""
    from unittest.mock import AsyncMock

    from custom_components.google_home_bt_proxy.models import GlobalProxyState

    speaker, state = speaker_and_state
    global_state = GlobalProxyState(enabled=True)
    persisted = []

    async def _on_toggle(val: bool) -> None:
        persisted.append(val)

    switch = GoogleHomeBtProxyScannerSwitch(
        speaker,
        state,
        global_state=global_state,
        on_toggle=_on_toggle,
        options_explicit=True,
    )
    switch.async_write_ha_state = MagicMock()
    switch.async_get_last_state = AsyncMock(return_value=None)

    await switch.async_added_to_hass()
    await switch.async_turn_off()
    assert state.enabled is False
    assert state.status == "disabled"
    assert state.abort_scan_event.is_set()
    assert persisted == [False]

    state.abort_scan_event.clear()
    await switch.async_turn_on()
    assert state.enabled is True
    assert state.status == "idle"
    assert state.trigger_scan_event.is_set()
    assert persisted == [False, True]

    await switch.async_will_remove_from_hass()


@pytest.mark.asyncio
async def test_speaker_switch_restore_entity_behavior(speaker_and_state):
    """Verify RestoreEntity restores 'off' state only when options_explicit is False."""
    from unittest.mock import AsyncMock

    speaker, state = speaker_and_state
    restored_calls = []

    async def _on_toggle(val: bool) -> None:
        restored_calls.append(val)

    mock_last_state = MagicMock()
    mock_last_state.state = "off"

    # Case 1: options_explicit=False -> RestoreEntity takes effect
    sw = GoogleHomeBtProxyScannerSwitch(
        speaker,
        state,
        on_toggle=_on_toggle,
        options_explicit=False,
    )
    sw.async_write_ha_state = MagicMock()
    sw.async_get_last_state = AsyncMock(return_value=mock_last_state)

    await sw.async_added_to_hass()
    assert sw.is_on is False
    assert state.enabled is False
    assert state.status == "disabled"
    assert restored_calls == [False]
    await sw.async_will_remove_from_hass()

    # Case 2: options_explicit=True -> entry.options wins over RestoreEntity
    state2 = SpeakerProxyState(enabled=True)
    sw2 = GoogleHomeBtProxyScannerSwitch(
        speaker,
        state2,
        options_explicit=True,
    )
    sw2.async_write_ha_state = MagicMock()
    sw2.async_get_last_state = AsyncMock(return_value=mock_last_state)

    await sw2.async_added_to_hass()
    assert sw2.is_on is True
    assert state2.enabled is True
    await sw2.async_will_remove_from_hass()


@pytest.mark.asyncio
async def test_global_switch_toggle_respects_individually_paused_speakers():
    """Verify global toggle pauses all speakers and only wakes speakers not individually paused."""
    from unittest.mock import AsyncMock

    from custom_components.google_home_bt_proxy.models import GlobalProxyState
    from custom_components.google_home_bt_proxy.switch import (
        GoogleHomeBtProxyGlobalScannerSwitch,
    )

    spk_active = SpeakerNode(
        device_id="spk-active",
        name="Living Room",
        ip_address="192.168.1.11",
        auth_token="t1",
    )
    spk_paused = SpeakerNode(
        device_id="spk-paused",
        name="Hallway",
        ip_address="192.168.1.12",
        auth_token="t2",
    )
    st_active = SpeakerProxyState(enabled=True, status="idle")
    st_paused = SpeakerProxyState(enabled=False, status="disabled")
    speakers_data = {
        "spk-active": {"speaker": spk_active, "state": st_active},
        "spk-paused": {"speaker": spk_paused, "state": st_paused},
    }
    global_state = GlobalProxyState(enabled=True)
    mock_entry = MagicMock()
    mock_entry.entry_id = "entry-g"
    toggles = []

    async def _on_toggle(val: bool) -> None:
        toggles.append(val)

    gsw = GoogleHomeBtProxyGlobalScannerSwitch(
        entry=mock_entry,
        global_state=global_state,
        speakers_data=speakers_data,
        on_toggle=_on_toggle,
        options_explicit=True,
    )
    gsw.async_write_ha_state = MagicMock()
    gsw.async_get_last_state = AsyncMock(return_value=None)

    await gsw.async_added_to_hass()
    await gsw.async_turn_off()
    assert gsw.is_on is False
    assert st_active.status == "disabled"
    assert st_active.abort_scan_event.is_set()
    assert st_paused.status == "disabled"
    assert toggles == [False]
    assert gsw.extra_state_attributes["effective_active_speakers"] == 0

    st_active.trigger_scan_event.clear()
    st_paused.trigger_scan_event.clear()
    await gsw.async_turn_on()
    assert gsw.is_on is True
    assert st_active.status == "idle"
    assert st_active.trigger_scan_event.is_set()
    # Individually paused speaker must stay disabled!
    assert st_paused.status == "disabled"
    assert not st_paused.trigger_scan_event.is_set()
    assert toggles == [False, True]
    assert gsw.extra_state_attributes["effective_active_speakers"] == 1

    await gsw.async_will_remove_from_hass()
