"""Tests for Google Home Bluetooth Proxy sensor platform."""

from unittest.mock import MagicMock

import pytest
from homeassistant.components.sensor import SensorStateClass

from custom_components.google_home_bt_proxy.const import DOMAIN
from custom_components.google_home_bt_proxy.models import SpeakerNode, SpeakerProxyState
from custom_components.google_home_bt_proxy.sensor import (
    GoogleHomeBtProxyAdvertisementsSensor,
    GoogleHomeBtProxyStatusSensor,
    async_setup_entry,
)


@pytest.fixture
def speaker_and_state():
    speaker = SpeakerNode(
        device_id="spk-sensor-1",
        name="Bedroom Speaker",
        ip_address="192.168.1.101",
        auth_token="token-1",
        hardware="Google Home Mini",
    )
    state = SpeakerProxyState()
    return speaker, state


@pytest.mark.asyncio
async def test_sensor_setup_entry(speaker_and_state):
    speaker, state = speaker_and_state
    mock_hass = MagicMock()
    mock_entry = MagicMock()
    mock_entry.entry_id = "entry-123"

    mock_hass.data = {
        DOMAIN: {
            "entry-123": {
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

    assert len(added_entities) == 2
    assert isinstance(added_entities[0], GoogleHomeBtProxyStatusSensor)
    assert isinstance(added_entities[1], GoogleHomeBtProxyAdvertisementsSensor)


def test_status_sensor_properties_and_updates(speaker_and_state):
    speaker, state = speaker_and_state
    sensor = GoogleHomeBtProxyStatusSensor(speaker, state)

    assert sensor.unique_id == "spk-sensor-1_proxy_status"
    assert sensor.native_value == "idle"
    assert sensor.device_info["name"] == "Bedroom Speaker"
    assert sensor.device_info["identifiers"] == {(DOMAIN, "spk-sensor-1")}

    # Update state and verify attributes
    state.status = "scanning"
    state.last_scan_count = 5
    state.last_scan_duration = 2.5
    state.last_scan_timestamp = 1700000000.0

    assert sensor.native_value == "scanning"
    attrs = sensor.extra_state_attributes
    assert attrs["last_scan_count"] == 5
    assert attrs["last_scan_duration"] == 2.5
    assert attrs["last_scan_timestamp"] == 1700000000.0


def test_advertisements_sensor_properties_and_updates(speaker_and_state):
    speaker, state = speaker_and_state
    sensor = GoogleHomeBtProxyAdvertisementsSensor(speaker, state)

    assert sensor.unique_id == "spk-sensor-1_advertisements_processed"
    assert sensor.native_value == 0
    assert sensor.state_class == SensorStateClass.TOTAL_INCREASING
    assert sensor.native_unit_of_measurement == "pkts"

    # Simulate advertisements incoming
    state.total_advertisements = 42
    state.last_scan_count = 12

    assert sensor.native_value == 42
    assert sensor.extra_state_attributes["last_scan_count"] == 12


@pytest.mark.asyncio
async def test_sensor_callback_subscription(speaker_and_state):
    speaker, state = speaker_and_state
    sensor = GoogleHomeBtProxyStatusSensor(speaker, state)
    sensor.async_write_ha_state = MagicMock()

    # Simulate adding to hass
    await sensor.async_added_to_hass()
    state.status = "playback_throttled"
    state.notify_callbacks()

    sensor.async_write_ha_state.assert_called_once()

    # Simulate removing from hass
    await sensor.async_will_remove_from_hass()
    sensor.async_write_ha_state.reset_mock()
    state.notify_callbacks()

    sensor.async_write_ha_state.assert_not_called()
