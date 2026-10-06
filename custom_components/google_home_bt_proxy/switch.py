"""Switch platform for Google Home Bluetooth Proxy."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from homeassistant.components.switch import SwitchEntity
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
    """Set up Google Home Bluetooth Proxy switches from config entry."""
    entry_data = hass.data[DOMAIN][entry.entry_id]
    speakers_data: dict[str, dict[str, Any]] = entry_data.get("speakers", {})
    entities: list[SwitchEntity] = []

    for _speaker_id, data in speakers_data.items():
        speaker: SpeakerNode = data["speaker"]
        state: SpeakerProxyState = data["state"]
        entities.append(GoogleHomeBtProxyScannerSwitch(speaker, state))

    async_add_entities(entities)


class GoogleHomeBtProxyScannerSwitch(SwitchEntity):
    """Switch allowing users to enable or disable scanning on a specific speaker."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:bluetooth-connect"

    def __init__(self, speaker: SpeakerNode, state: SpeakerProxyState) -> None:
        """Initialize scanner switch."""
        self._speaker = speaker
        self._state = state
        self._unsub_callback: Callable[[], None] | None = None
        self._attr_name = "Bluetooth Proxy Scanner"
        self._attr_unique_id = f"{speaker.device_id}_scanner_switch"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, speaker.device_id)},
            name=speaker.name,
            manufacturer="Google",
            model=speaker.hardware,
        )

    @property
    def is_on(self) -> bool:
        """Return True if speaker proxy scanner is enabled."""
        return self._state.enabled

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable speaker proxy scanner."""
        self._state.enabled = True
        self._state.notify_callbacks()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable speaker proxy scanner."""
        self._state.enabled = False
        self._state.notify_callbacks()

    async def async_added_to_hass(self) -> None:
        """Register state update callback when added to hass."""
        self._unsub_callback = self._state.register_callback(self.async_write_ha_state)

    async def async_will_remove_from_hass(self) -> None:
        """Unregister callback when removing from hass."""
        if self._unsub_callback is not None:
            self._unsub_callback()
            self._unsub_callback = None
