"""Switch platform for Google Home Bluetooth Proxy."""

from __future__ import annotations

import inspect
from collections.abc import Callable
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import CONF_GLOBAL_SCANNING_ENABLED, CONF_PAUSED_SPEAKERS, DOMAIN
from .models import GlobalProxyState, SpeakerNode, SpeakerProxyState
from .persistence import ProxyStateStore, update_options_in_place


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Google Home Bluetooth Proxy switches from config entry."""
    entry_data = hass.data[DOMAIN][entry.entry_id]
    speakers_data: dict[str, dict[str, Any]] = entry_data.get("speakers", {})
    global_state: GlobalProxyState | None = entry_data.get("global_state")
    state_store: ProxyStateStore | None = entry_data.get("state_store")
    entry_options = getattr(entry, "options", {}) or {}
    paused_explicit = CONF_PAUSED_SPEAKERS in entry_options
    global_explicit = CONF_GLOBAL_SCANNING_ENABLED in entry_options

    entities: list[SwitchEntity] = []

    if isinstance(global_state, GlobalProxyState):

        async def _persist_global(enabled: bool) -> None:
            update_options_in_place(hass, entry, global_scanning_enabled=enabled)
            if state_store is not None:
                await state_store.async_save_now(global_state, speakers_data)

        entities.append(
            GoogleHomeBtProxyGlobalScannerSwitch(
                entry=entry,
                global_state=global_state,
                speakers_data=speakers_data,
                on_toggle=_persist_global,
                options_explicit=global_explicit,
            )
        )

    for speaker_id, data in speakers_data.items():
        speaker: SpeakerNode = data["speaker"]
        state: SpeakerProxyState = data["state"]

        def _make_persist_cb(spk_id: str) -> Callable[[bool], Any]:
            async def _persist_speaker(enabled: bool) -> None:
                update_options_in_place(
                    hass,
                    entry,
                    speaker_id=spk_id,
                    speaker_enabled=enabled,
                )
                if state_store is not None and isinstance(global_state, GlobalProxyState):
                    await state_store.async_save_now(global_state, speakers_data)

            return _persist_speaker

        entities.append(
            GoogleHomeBtProxyScannerSwitch(
                speaker,
                state,
                global_state=global_state,
                on_toggle=_make_persist_cb(speaker_id) if global_state is not None else None,
                options_explicit=paused_explicit,
            )
        )

    async_add_entities(entities)


class GoogleHomeBtProxyScannerSwitch(SwitchEntity, RestoreEntity):
    """Switch allowing users to enable or disable scanning on a specific speaker."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:bluetooth-connect"

    def __init__(
        self,
        speaker: SpeakerNode,
        state: SpeakerProxyState,
        global_state: GlobalProxyState | None = None,
        on_toggle: Callable[[bool], Any] | None = None,
        options_explicit: bool = False,
    ) -> None:
        """Initialize scanner switch."""
        self._speaker = speaker
        self._state = state
        self._global_state = global_state
        self._on_toggle = on_toggle
        self._options_explicit = options_explicit
        self._unsub_callbacks: list[Callable[[], None]] = []
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

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return speaker scanner toggle status attributes for automations."""
        global_enabled = self._global_state.enabled if self._global_state is not None else True
        return {
            "status": self._state.status,
            "global_scanning_enabled": global_enabled,
            "effective_scanning": self._state.enabled and global_enabled,
            "speaker_id": self._speaker.device_id,
        }

    async def _persist_state(self, enabled: bool) -> None:
        """Invoke persistence callback if configured."""
        if self._on_toggle is None:
            return
        res = self._on_toggle(enabled)
        if inspect.isawaitable(res):
            await res

    def _apply_enabled_state(self, enabled: bool) -> None:
        """Apply enabled/disabled state to the speaker proxy and notify listeners."""
        self._state.enabled = enabled
        if enabled:
            global_enabled = self._global_state.enabled if self._global_state is not None else True
            if global_enabled and self._state.status == "disabled":
                self._state.status = "idle"
            self._state.trigger_scan_event.set()
        else:
            self._state.status = "disabled"
            self._state.abort_scan_event.set()
        self._state.notify_callbacks()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable speaker proxy scanner."""
        self._apply_enabled_state(True)
        await self._persist_state(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Disable speaker proxy scanner."""
        self._apply_enabled_state(False)
        await self._persist_state(False)

    async def async_added_to_hass(self) -> None:
        """Restore previous switch state if needed and register state update callbacks."""
        await super().async_added_to_hass()

        if not self._options_explicit:
            last_state = await self.async_get_last_state()
            if last_state is not None and last_state.state in ("on", "off"):
                restored_enabled = last_state.state == "on"
                if restored_enabled != self._state.enabled:
                    self._apply_enabled_state(restored_enabled)
                    await self._persist_state(restored_enabled)

        self._unsub_callbacks.append(self._state.register_callback(self.async_write_ha_state))
        if self._global_state is not None:
            self._unsub_callbacks.append(
                self._global_state.register_callback(self.async_write_ha_state)
            )

    async def async_will_remove_from_hass(self) -> None:
        """Unregister callbacks when removing from hass."""
        for unsub in self._unsub_callbacks:
            unsub()
        self._unsub_callbacks.clear()


class GoogleHomeBtProxyGlobalScannerSwitch(SwitchEntity, RestoreEntity):
    """Master switch to toggle all proxy scanning without disabling the integration."""

    _attr_has_entity_name = True
    _attr_icon = "mdi:bluetooth-settings"

    def __init__(
        self,
        entry: ConfigEntry,
        global_state: GlobalProxyState,
        speakers_data: dict[str, dict[str, Any]],
        on_toggle: Callable[[bool], Any] | None = None,
        options_explicit: bool = False,
    ) -> None:
        """Initialize the global Bluetooth proxy scanning switch."""
        self._entry = entry
        self._global_state = global_state
        self._speakers_data = speakers_data
        self._on_toggle = on_toggle
        self._options_explicit = options_explicit
        self._unsub_callbacks: list[Callable[[], None]] = []
        self._attr_name = "Global Bluetooth Proxy Scanning"
        self._attr_unique_id = f"{entry.entry_id}_global_scanner_switch"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Google Home Bluetooth Proxy",
            manufacturer="Google",
            model="Bluetooth Proxy Hub",
            entry_type=DeviceEntryType.SERVICE,
        )

    @property
    def is_on(self) -> bool:
        """Return True if global Bluetooth proxy scanning is enabled."""
        return self._global_state.enabled

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return summary counts of active and paused speakers for automations."""
        total = len(self._speakers_data)
        enabled_speakers = sum(
            1
            for data in self._speakers_data.values()
            if getattr(data.get("state"), "enabled", True)
        )
        return {
            "total_speakers": total,
            "enabled_speakers": enabled_speakers,
            "paused_speakers": total - enabled_speakers,
            "effective_active_speakers": enabled_speakers if self._global_state.enabled else 0,
        }

    async def _persist_state(self, enabled: bool) -> None:
        """Invoke persistence callback if configured."""
        if self._on_toggle is None:
            return
        res = self._on_toggle(enabled)
        if inspect.isawaitable(res):
            await res

    def _apply_global_state(self, enabled: bool) -> None:
        """Apply global enabled state and propagate status/wake signals to speaker workers."""
        self._global_state.enabled = enabled
        for data in self._speakers_data.values():
            spk_state: SpeakerProxyState | None = data.get("state")
            if spk_state is None:
                continue
            if enabled:
                if spk_state.enabled and spk_state.status == "disabled":
                    spk_state.status = "idle"
                if spk_state.enabled:
                    spk_state.trigger_scan_event.set()
            else:
                spk_state.status = "disabled"
                spk_state.abort_scan_event.set()
            spk_state.notify_callbacks()
        self._global_state.notify_callbacks()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Enable global Bluetooth proxy scanning across enabled speakers."""
        self._apply_global_state(True)
        await self._persist_state(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Pause all Google Home Bluetooth proxy scanning without disabling the integration."""
        self._apply_global_state(False)
        await self._persist_state(False)

    async def async_added_to_hass(self) -> None:
        """Restore previous global switch state if needed and register callbacks."""
        await super().async_added_to_hass()

        if not self._options_explicit:
            last_state = await self.async_get_last_state()
            if last_state is not None and last_state.state in ("on", "off"):
                restored_enabled = last_state.state == "on"
                if restored_enabled != self._global_state.enabled:
                    self._apply_global_state(restored_enabled)
                    await self._persist_state(restored_enabled)

        self._unsub_callbacks.append(
            self._global_state.register_callback(self.async_write_ha_state)
        )
        for data in self._speakers_data.values():
            spk_state: SpeakerProxyState | None = data.get("state")
            if spk_state is not None:
                self._unsub_callbacks.append(spk_state.register_callback(self.async_write_ha_state))

    async def async_will_remove_from_hass(self) -> None:
        """Unregister callbacks when removing from hass."""
        for unsub in self._unsub_callbacks:
            unsub()
        self._unsub_callbacks.clear()
