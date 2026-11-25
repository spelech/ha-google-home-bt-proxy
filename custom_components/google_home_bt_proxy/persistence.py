"""Persistent storage and in-place config options synchronization."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import (
    CONF_GLOBAL_SCANNING_ENABLED,
    CONF_PAUSED_SPEAKERS,
    DOMAIN,
    STORAGE_KEY_PREFIX,
    STORAGE_VERSION,
)
from .models import GlobalProxyState, SpeakerProxyState

_LOGGER = logging.getLogger(__name__)


def _has_real_event_loop(hass: HomeAssistant) -> bool:
    """Return True if hass exposes a real asyncio event loop."""
    return isinstance(getattr(hass, "loop", None), asyncio.AbstractEventLoop)


class ProxyStateStore:
    """Persists runtime operational counters and switch states across restarts and reloads."""

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        """Initialize the persistent state store for a config entry."""
        self._hass = hass
        self._entry_id = entry_id
        self._store: Store[dict[str, Any]] | None = None
        if _has_real_event_loop(hass):
            self._store = Store(hass, STORAGE_VERSION, f"{STORAGE_KEY_PREFIX}.{entry_id}")

    async def async_load(self) -> dict[str, Any]:
        """Load persisted runtime state, returning an empty dict if unavailable."""
        if self._store is None:
            return {}
        try:
            loaded = await self._store.async_load()
            return loaded if isinstance(loaded, dict) else {}
        except Exception as err:
            _LOGGER.debug("Failed to load persisted state for %s: %s", self._entry_id, err)
            return {}

    @staticmethod
    def build_snapshot(
        global_state: GlobalProxyState,
        speakers_data: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        """Build a JSON-serializable snapshot of global and per-speaker runtime state."""
        speakers_snapshot: dict[str, dict[str, Any]] = {}
        for speaker_id, data in speakers_data.items():
            state: SpeakerProxyState | None = data.get("state")
            if isinstance(state, SpeakerProxyState):
                speakers_snapshot[speaker_id] = state.to_persisted_dict()
        return {
            "global": {"enabled": global_state.enabled},
            "speakers": speakers_snapshot,
        }

    async def async_save_now(
        self,
        global_state: GlobalProxyState,
        speakers_data: dict[str, dict[str, Any]],
    ) -> None:
        """Immediately flush runtime state to disk."""
        if self._store is None:
            return
        snapshot = self.build_snapshot(global_state, speakers_data)
        try:
            await self._store.async_save(snapshot)
        except Exception as err:
            _LOGGER.debug("Failed to save persisted state for %s: %s", self._entry_id, err)

    def schedule_save(
        self,
        global_state: GlobalProxyState,
        speakers_data: dict[str, dict[str, Any]],
        delay: float = 30.0,
    ) -> None:
        """Schedule a debounced write of runtime state to disk."""
        if self._store is None:
            return
        try:
            self._store.async_delay_save(
                lambda: self.build_snapshot(global_state, speakers_data),
                delay=delay,
            )
        except Exception as err:
            _LOGGER.debug("Failed to schedule state save for %s: %s", self._entry_id, err)


def update_options_in_place(
    hass: HomeAssistant,
    entry: ConfigEntry,
    *,
    global_scanning_enabled: bool | None = None,
    speaker_id: str | None = None,
    speaker_enabled: bool | None = None,
) -> None:
    """Persist toggle state in config entry options without triggering a full integration reload."""
    if not hasattr(hass, "config_entries") or not hasattr(
        hass.config_entries, "async_update_entry"
    ):
        return

    new_options = dict(getattr(entry, "options", {}) or {})

    if global_scanning_enabled is not None:
        new_options[CONF_GLOBAL_SCANNING_ENABLED] = bool(global_scanning_enabled)

    if speaker_id is not None and speaker_enabled is not None:
        paused = list(new_options.get(CONF_PAUSED_SPEAKERS, []))
        if speaker_enabled:
            paused = [sid for sid in paused if sid != speaker_id]
        elif speaker_id not in paused:
            paused.append(speaker_id)
        new_options[CONF_PAUSED_SPEAKERS] = paused

    domain_data = getattr(hass, "data", {}).get(DOMAIN, {})
    entry_data = domain_data.get(entry.entry_id) if isinstance(domain_data, dict) else None
    if isinstance(entry_data, dict):
        entry_data["_in_place_options"] = dict(new_options)

    hass.config_entries.async_update_entry(entry, options=new_options)
