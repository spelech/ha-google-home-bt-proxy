"""Tests for Google Home Bluetooth Proxy button platform."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.google_home_bt_proxy.button import (
    GoogleHomeBtProxyReviveButton,
    GoogleHomeBtProxyScanButton,
    async_setup_entry,
)
from custom_components.google_home_bt_proxy.const import DOMAIN
from custom_components.google_home_bt_proxy.models import SpeakerNode, SpeakerProxyState


@pytest.fixture
def speaker_and_state():
    speaker = SpeakerNode(
        device_id="spk-btn-1",
        name="Office Mini",
        ip_address="192.168.1.103",
        auth_token="token-btn",
        hardware="Google Home Mini",
    )
    state = SpeakerProxyState()
    return speaker, state


@pytest.mark.asyncio
async def test_button_setup_entry(speaker_and_state):
    speaker, state = speaker_and_state
    mock_hass = MagicMock()
    mock_entry = MagicMock()
    mock_entry.entry_id = "entry-btn-123"

    mock_coordinator = MagicMock()
    mock_hass.data = {
        DOMAIN: {
            "entry-btn-123": {
                "coordinator": mock_coordinator,
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

    def mock_add_entities(entities):
        added_entities.extend(entities)

    await async_setup_entry(mock_hass, mock_entry, mock_add_entities)

    assert len(added_entities) == 2
    assert isinstance(added_entities[0], GoogleHomeBtProxyScanButton)
    assert isinstance(added_entities[1], GoogleHomeBtProxyReviveButton)


@pytest.mark.asyncio
async def test_button_press(speaker_and_state):
    speaker, state = speaker_and_state
    button = GoogleHomeBtProxyScanButton(speaker, state)

    assert button.unique_id == "spk-btn-1_trigger_scan"
    assert not state.trigger_scan_event.is_set()

    await button.async_press()
    assert state.trigger_scan_event.is_set()


@pytest.mark.asyncio
async def test_scan_button_press_revives_unsupported_speaker(speaker_and_state):
    speaker, state = speaker_and_state
    speaker.available = False
    state.status = "unsupported"

    mock_coord = MagicMock()
    mock_coord.async_refresh_token = AsyncMock()

    button = GoogleHomeBtProxyScanButton(speaker, state, coordinator=mock_coord)
    await button.async_press()

    assert speaker.available is True
    assert state.status == "idle"
    assert state.trigger_scan_event.is_set()
    mock_coord.async_refresh_token.assert_awaited_once_with(speaker)


@pytest.mark.asyncio
async def test_revive_button_press(speaker_and_state):
    speaker, state = speaker_and_state
    speaker.available = False
    state.status = "unsupported"

    mock_coord = MagicMock()
    mock_coord.async_refresh_token = AsyncMock()

    revive_btn = GoogleHomeBtProxyReviveButton(speaker, state, coordinator=mock_coord)
    assert revive_btn.unique_id == "spk-btn-1_revive"
    assert revive_btn.name == "Revive Speaker"

    await revive_btn.async_press()

    assert speaker.available is True
    assert state.status == "idle"
    assert state.trigger_scan_event.is_set()
    mock_coord.async_refresh_token.assert_awaited_once_with(speaker)


@pytest.mark.asyncio
async def test_revive_button_press_error_handling(speaker_and_state):
    speaker, state = speaker_and_state
    speaker.available = False
    state.status = "unavailable"

    mock_coord = MagicMock()
    mock_coord.async_refresh_token = AsyncMock(side_effect=RuntimeError("Token error"))

    revive_btn = GoogleHomeBtProxyReviveButton(speaker, state, coordinator=mock_coord)
    await revive_btn.async_press()

    assert speaker.available is True
    assert state.status == "idle"
    assert state.trigger_scan_event.is_set()
