"""Button platform for Google Home Bluetooth Proxy."""

from __future__ import annotations

from typing import Any

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .models import SpeakerNode, SpeakerProxyState


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Google Home Bluetooth Proxy buttons from config entry."""
    entry_data = hass.data[DOMAIN][entry.entry_id]
    speakers_data: dict[str, dict[str, Any]] = entry_data.get("speakers", {})
    entities: list[ButtonEntity] = []

    for _speaker_id, data in speakers_data.items():
        speaker: SpeakerNode = data["speaker"]
        state: SpeakerProxyState = data["state"]
        entities.append(GoogleHomeBtProxyScanButton(speaker, state))

    async_add_entities(entities)


class GoogleHomeBtProxyScanButton(ButtonEntity):
    """Button to trigger an immediate on-demand Bluetooth scan on a speaker."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:radar"

    def __init__(self, speaker: SpeakerNode, state: SpeakerProxyState) -> None:
        """Initialize scan button."""
        self._speaker = speaker
        self._state = state
        self._attr_name = "Trigger Bluetooth Scan"
        self._attr_unique_id = f"{speaker.device_id}_trigger_scan"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, speaker.device_id)},
            name=speaker.name,
            manufacturer="Google",
            model=speaker.hardware,
        )

    async def async_press(self) -> None:
        """Handle button press by signaling scan event."""
        self._state.trigger_scan_event.set()
