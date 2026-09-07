"""Sensor platform for Google Home Bluetooth Proxy."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .models import SpeakerNode, SpeakerProxyState


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Google Home Bluetooth Proxy sensors from config entry."""
    entry_data = hass.data[DOMAIN][entry.entry_id]
    speakers_data: dict[str, dict[str, Any]] = entry_data.get("speakers", {})
    entities: list[SensorEntity] = []

    for _speaker_id, data in speakers_data.items():
        speaker: SpeakerNode = data["speaker"]
        state: SpeakerProxyState = data["state"]
        entities.append(GoogleHomeBtProxyStatusSensor(speaker, state))
        entities.append(GoogleHomeBtProxyAdvertisementsSensor(speaker, state))
        entities.append(GoogleHomeBtProxyFilteredAdvertisementsSensor(speaker, state))

    async_add_entities(entities)


class GoogleHomeBtProxyBaseSensor(SensorEntity):
    """Base sensor for Google Home Bluetooth Proxy."""

    _attr_has_entity_name = True

    def __init__(self, speaker: SpeakerNode, state: SpeakerProxyState) -> None:
        """Initialize base sensor."""
        self._speaker = speaker
        self._state = state
        self._unsub_callback: Callable[[], None] | None = None
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, speaker.device_id)},
            connections={(CONNECTION_NETWORK_MAC, speaker.mac_address.lower())},
            name=speaker.name,
            manufacturer="Google",
            model=speaker.hardware,
        )

    async def async_added_to_hass(self) -> None:
        """Register state update callback when added to hass."""
        self._unsub_callback = self._state.register_callback(self.async_write_ha_state)

    async def async_will_remove_from_hass(self) -> None:
        """Unregister callback when removing from hass."""
        if self._unsub_callback is not None:
            self._unsub_callback()
            self._unsub_callback = None


class GoogleHomeBtProxyStatusSensor(GoogleHomeBtProxyBaseSensor):
    """Sensor reporting the current scanning/playback status of the proxy."""

    _attr_icon = "mdi:bluetooth-audio"

    def __init__(self, speaker: SpeakerNode, state: SpeakerProxyState) -> None:
        """Initialize status sensor."""
        super().__init__(speaker, state)
        self._attr_name = "Bluetooth Proxy Status"
        self._attr_unique_id = f"{speaker.device_id}_proxy_status"

    @property
    def native_value(self) -> str:
        """Return current proxy operational status."""
        return self._state.status

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return operational diagnostic attributes."""
        return {
            "last_scan_count": self._state.last_scan_count,
            "last_scan_duration": self._state.last_scan_duration,
            "last_scan_timestamp": self._state.last_scan_timestamp,
            "filtered_advertisements": self._state.filtered_advertisements,
        }


class GoogleHomeBtProxyAdvertisementsSensor(GoogleHomeBtProxyBaseSensor):
    """Sensor reporting total processed BLE advertisements."""

    _attr_icon = "mdi:counter"
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_native_unit_of_measurement = "pkts"

    def __init__(self, speaker: SpeakerNode, state: SpeakerProxyState) -> None:
        """Initialize advertisements sensor."""
        super().__init__(speaker, state)
        self._attr_name = "Bluetooth Advertisements Processed"
        self._attr_unique_id = f"{speaker.device_id}_advertisements_processed"

    @property
    def native_value(self) -> int:
        """Return total advertisements processed."""
        return self._state.total_advertisements

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return diagnostic metrics."""
        return {
            "last_scan_count": self._state.last_scan_count,
            "filtered_advertisements": self._state.filtered_advertisements,
        }


class GoogleHomeBtProxyFilteredAdvertisementsSensor(GoogleHomeBtProxyBaseSensor):
    """Sensor reporting BLE advertisements filtered out by RSSI, distance, or whitelist."""

    _attr_icon = "mdi:filter-check"
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_native_unit_of_measurement = "pkts"

    def __init__(self, speaker: SpeakerNode, state: SpeakerProxyState) -> None:
        """Initialize filtered advertisements sensor."""
        super().__init__(speaker, state)
        self._attr_name = "Bluetooth Advertisements Filtered"
        self._attr_unique_id = f"{speaker.device_id}_advertisements_filtered"

    @property
    def native_value(self) -> int:
        """Return total advertisements filtered."""
        return self._state.filtered_advertisements
