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
