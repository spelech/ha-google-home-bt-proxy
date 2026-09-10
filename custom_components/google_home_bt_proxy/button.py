"""Button platform for Google Home Bluetooth Proxy."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import CONNECTION_NETWORK_MAC, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .models import SpeakerNode, SpeakerProxyState

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Google Home Bluetooth Proxy buttons from config entry."""
    entry_data = hass.data[DOMAIN][entry.entry_id]
    coordinator = entry_data.get("coordinator")
    speakers_data: dict[str, dict[str, Any]] = entry_data.get("speakers", {})
    entities: list[ButtonEntity] = []

    for _speaker_id, data in speakers_data.items():
        speaker: SpeakerNode = data["speaker"]
        state: SpeakerProxyState = data["state"]
        entities.append(GoogleHomeBtProxyScanButton(speaker, state, coordinator=coordinator))
        entities.append(GoogleHomeBtProxyReviveButton(speaker, state, coordinator=coordinator))

    async_add_entities(entities)


class GoogleHomeBtProxyScanButton(ButtonEntity):
    """Button to trigger an immediate on-demand Bluetooth scan on a speaker."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:radar"

    def __init__(
        self,
        speaker: SpeakerNode,
        state: SpeakerProxyState,
        coordinator: Any | None = None,
    ) -> None:
        """Initialize scan button."""
        self._speaker = speaker
        self._state = state
        self._coordinator = coordinator
        self._attr_name = "Trigger Bluetooth Scan"
        self._attr_unique_id = f"{speaker.device_id}_trigger_scan"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, speaker.device_id)},
            connections={(CONNECTION_NETWORK_MAC, speaker.mac_address.lower())},
            name=speaker.name,
            manufacturer="Google",
            model=speaker.hardware,
        )

    async def async_press(self) -> None:
        """Handle button press by signaling scan event."""
        if self._state.status in ("unsupported", "unavailable"):
            self._speaker.available = True
            self._state.status = "idle"
            if self._coordinator is not None and hasattr(self._coordinator, "async_refresh_token"):
                try:
                    await self._coordinator.async_refresh_token(self._speaker)
                except Exception as err:
                    _LOGGER.debug(
                        "Token refresh error during scan trigger for %s: %s",
                        self._speaker.name,
                        err,
                    )
            self._state.notify_callbacks()
        self._state.trigger_scan_event.set()


class GoogleHomeBtProxyReviveButton(ButtonEntity):
    """Button to revive / reconnect an unavailable or unsupported speaker."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:restart"

    def __init__(
        self,
        speaker: SpeakerNode,
        state: SpeakerProxyState,
        coordinator: Any | None = None,
    ) -> None:
        """Initialize revive button."""
        self._speaker = speaker
        self._state = state
        self._coordinator = coordinator
        self._attr_name = "Revive Speaker"
        self._attr_unique_id = f"{speaker.device_id}_revive"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, speaker.device_id)},
            connections={(CONNECTION_NETWORK_MAC, speaker.mac_address.lower())},
            name=speaker.name,
            manufacturer="Google",
            model=speaker.hardware,
        )

    async def async_press(self) -> None:
        """Handle revive button press."""
        _LOGGER.info(
            "Revive button pressed for %s; resetting state and refreshing token...",
            self._speaker.name,
        )
        self._speaker.available = True
        self._state.status = "idle"
        if self._coordinator is not None and hasattr(self._coordinator, "async_refresh_token"):
            try:
                await self._coordinator.async_refresh_token(self._speaker)
            except Exception as err:
                _LOGGER.debug(
                    "Token refresh error during revival for %s: %s",
                    self._speaker.name,
                    err,
                )
        self._state.notify_callbacks()
        self._state.trigger_scan_event.set()
