"""Media playback and TTS alert detector for Google Home / Nest speakers."""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

import pychromecast
from homeassistant.const import EVENT_CALL_SERVICE, EVENT_STATE_CHANGED
from homeassistant.core import Event, HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.util import slugify
from pychromecast.models import CastInfo, HostServiceInfo

if TYPE_CHECKING:
    from .api import GoogleHomeApiClient
    from .models import SpeakerNode, SpeakerProxyState

_LOGGER = logging.getLogger(__name__)

ACTIVE_PLAYER_STATES = {"PLAYING", "BUFFERING"}
HA_ACTIVE_STATES = {"playing", "buffering"}
DEFAULT_TTS_COOLDOWN = 5.0
DEFAULT_TTS_RESERVATION = 15.0


class SpeakerPlaybackDetector:
    """Detects active media playback and suppresses scans during TTS announcements."""

    def __init__(
        self,
        api_client: GoogleHomeApiClient,
        hass: HomeAssistant | None = None,
        cast_timeout: float = 3.0,
        tts_cooldown: float = DEFAULT_TTS_COOLDOWN,
    ) -> None:
        """Initialize the playback detector."""
        self._api_client = api_client
        self._hass = hass
        self._cast_timeout = cast_timeout
        self._tts_cooldown = tts_cooldown
        self._speaker_entity_map: dict[str, set[str]] = {}
        self._speakers_data: dict[str, dict[str, Any]] = {}
        self._speaker_tts_active_until: dict[str, float] = {}
        self._unsub_callbacks: list[Callable[[], None]] = []

    def async_setup(self, speakers_data: dict[str, dict[str, Any]]) -> Callable[[], None]:
        """Set up event listeners for TTS calls and media player state changes."""
        self._speakers_data = speakers_data

        # Pre-resolve media player entities for known speakers
        for _speaker_id, data in speakers_data.items():
            speaker: SpeakerNode = data["speaker"]
            self._speaker_entity_map[speaker.device_id] = self._resolve_speaker_entities(speaker)

        if not self._hass:
            return lambda: None

        unsub_service = self._hass.bus.async_listen(EVENT_CALL_SERVICE, self._handle_call_service)
        unsub_state = self._hass.bus.async_listen(EVENT_STATE_CHANGED, self._handle_state_changed)
        self._unsub_callbacks.extend([unsub_service, unsub_state])

        def _unsubscribe_all() -> None:
            for unsub in self._unsub_callbacks:
                try:
                    unsub()
                except Exception:
                    pass
            self._unsub_callbacks.clear()

        return _unsubscribe_all

    def is_tts_active(self, speaker: SpeakerNode) -> bool:
        """Return True if TTS alert or active playback grace period is active."""
        return time.monotonic() < self._speaker_tts_active_until.get(speaker.device_id, 0.0)

    async def async_is_playing(self, speaker: SpeakerNode) -> bool:
        """Check if media is actively playing via TTS, HA state, Bluetooth, or Cast."""
        # 0. Check TTS or alert priority window
        if self.is_tts_active(speaker):
            _LOGGER.debug("Speaker %s is in active TTS / alert playback window", speaker.name)
            return True

        # 1. Check local Bluetooth audio streaming (Port 8443)
        try:
            if await self._check_bluetooth_streaming(speaker):
                _LOGGER.debug("Speaker %s is playing audio via Bluetooth", speaker.name)
                return True
        except Exception as err:
            _LOGGER.debug("Failed checking Bluetooth status on %s: %s", speaker.name, err)

        # 2. Check Home Assistant media_player states (Zero network sockets, 0ms latency)
        if self._hass is not None:
            try:
                if self._check_ha_media_player_playing(speaker):
                    _LOGGER.debug(
                        "Speaker %s is actively playing media in Home Assistant", speaker.name
                    )
                    return True
            except Exception as err:
                _LOGGER.debug("Failed checking HA media_player state on %s: %s", speaker.name, err)
            return False

        # 3. Fallback when hass is None (e.g. standalone test mode only)
        try:
            if await self._check_cast_playing(speaker):
                _LOGGER.debug("Speaker %s is actively casting media", speaker.name)
                return True
        except Exception as err:
            _LOGGER.debug("Failed checking Cast playback on %s: %s", speaker.name, err)

        return False

    async def _check_bluetooth_streaming(self, speaker: SpeakerNode) -> bool:
        """Query local HTTPS port 8443 for connected Bluetooth devices."""
        status = await self._api_client.get_bluetooth_status(speaker)
        connected_devices = status.get("connected_devices", [])
        return bool(connected_devices)

    def _check_ha_media_player_playing(self, speaker: SpeakerNode) -> bool:
        """Check if mapped Home Assistant media player or Cast group is playing."""
        if not self._hass:
            return False

        # 1. Check mapped media_player entities for this speaker
        eids = self._speaker_entity_map.get(speaker.device_id)
        if eids is None:
            eids = self._resolve_speaker_entities(speaker)
            self._speaker_entity_map[speaker.device_id] = eids

        for eid in eids:
            state = self._hass.states.get(eid)
            if state and state.state.lower() in HA_ACTIVE_STATES:
                return True

        # 2. Check Whole Home Cast Group
        whole_home_state = self._hass.states.get("media_player.whole_home")
        if whole_home_state and whole_home_state.state.lower() in HA_ACTIVE_STATES:
            return True

        # 3. Check any active Cast group
        for group_eid in self._get_cast_group_entity_ids():
            state = self._hass.states.get(group_eid)
            if state and state.state.lower() in HA_ACTIVE_STATES:
                return True

        return False

    def _resolve_speaker_entities(self, speaker: SpeakerNode) -> set[str]:
        """Resolve media_player entity IDs associated with this speaker."""
        if not self._hass:
            return set()

        matched: set[str] = set()

        # 1. Direct slugified name check
        slug_name = slugify(speaker.name)
        direct_eid = f"media_player.{slug_name}"
        matched.add(direct_eid)

        # 2. Device and entity registry check
        dev_reg = dr.async_get(self._hass)
        ent_reg = er.async_get(self._hass)

        speaker_mac = (speaker.mac_address or "").lower()
        norm_name = speaker.name.lower().strip()

        target_dev_ids: set[str] = set()
        if hasattr(dev_reg, "devices"):
            for dev in dev_reg.devices:
                dev_id = getattr(dev, "id", None)
                dev_macs = [
                    conn[1].lower()
                    for conn in getattr(dev, "connections", [])
                    if len(conn) >= 2 and conn[0] in ("mac", "bluetooth")
                ]
                dev_name = (getattr(dev, "name", None) or "").lower().strip()
                dev_user_name = (getattr(dev, "name_by_user", None) or "").lower().strip()

                if (
                    (speaker_mac and speaker_mac in dev_macs)
                    or dev_name == norm_name
                    or dev_user_name == norm_name
                    or (norm_name and dev_name and norm_name in dev_name)
                ):
                    target_dev_ids.add(dev_id)

        if hasattr(ent_reg, "entities"):
            for ent in ent_reg.entities:
                eid = getattr(ent, "entity_id", None)
                if not eid or not eid.startswith("media_player."):
                    continue
                if getattr(ent, "device_id", None) in target_dev_ids:
                    matched.add(eid)
                orig_name = (getattr(ent, "original_name", None) or "").lower().strip()
                ent_name = (getattr(ent, "name", None) or "").lower().strip()
                if orig_name == norm_name or ent_name == norm_name:
                    matched.add(eid)

        # 3. Check states for matching friendly_name
        for state in self._hass.states.async_all("media_player"):
            fn = (state.attributes.get("friendly_name") or "").lower().strip()
            if fn == norm_name:
                matched.add(state.entity_id)

        return matched

    def _get_cast_group_entity_ids(self) -> set[str]:
        """Find all Google Cast group media_player entities."""
        if not self._hass:
            return set()

        groups: set[str] = {"media_player.whole_home"}

        dev_reg = dr.async_get(self._hass)
        ent_reg = er.async_get(self._hass)

        group_dev_ids: set[str] = set()
        if hasattr(dev_reg, "devices"):
            for dev in dev_reg.devices:
                dev_id = getattr(dev, "id", None)
                model = getattr(dev, "model", None) or ""
                if model in ("Google Cast Group", "Cast Group") and dev_id:
                    group_dev_ids.add(dev_id)

        if hasattr(ent_reg, "entities"):
            for ent in ent_reg.entities:
                eid = getattr(ent, "entity_id", None)
                if (
                    eid
                    and eid.startswith("media_player.")
                    and getattr(ent, "device_id", None) in group_dev_ids
                ):
                    groups.add(eid)

        for state in self._hass.states.async_all("media_player"):
            eid = state.entity_id.lower()
            if "whole_home" in eid or "speakers" in eid or "group" in eid or "intercom" in eid:
                groups.add(state.entity_id)

        return groups

    def _is_cast_group_entity(self, entity_id: str) -> bool:
        """Check if an entity_id is a known Cast group."""
        if not entity_id:
            return False
        return entity_id in self._get_cast_group_entity_ids()

    async def _handle_call_service(self, event: Event) -> None:
        """Handle service call events to detect TTS and audio playback initiation."""
        domain = event.data.get("domain")
        service = event.data.get("service")

        is_tts = domain == "tts"
        is_play_media = domain == "media_player" and service == "play_media"

        if not (is_tts or is_play_media):
            return

        service_data = event.data.get("service_data", {})
        target_raw = (
            service_data.get("media_player_entity_id")
            or service_data.get("entity_id")
            or event.data.get("target", {}).get("entity_id")
        )

        targets: list[str] = []
        if isinstance(target_raw, str):
            targets = [target_raw]
        elif isinstance(target_raw, list):
            targets = [t for t in target_raw if isinstance(t, str)]

        now = time.monotonic()
        reservation_duration = DEFAULT_TTS_RESERVATION if is_tts else 30.0

        is_all_speakers = (
            not targets
            or "all" in targets
            or any("whole_home" in t.lower() for t in targets)
            or any(self._is_cast_group_entity(t) for t in targets)
        )

        affected_speakers: list[SpeakerNode] = []

        for _speaker_id, data in self._speakers_data.items():
            speaker: SpeakerNode = data["speaker"]
            state: SpeakerProxyState | None = data.get("state")
            eids = self._speaker_entity_map.get(speaker.device_id, set())

            is_targeted = is_all_speakers or bool(eids.intersection(targets))

            if is_targeted:
                self._speaker_tts_active_until[speaker.device_id] = now + reservation_duration
                affected_speakers.append(speaker)
                if state:
                    state.abort_scan_event.set()

        if affected_speakers:
            _LOGGER.info(
                "TTS/Media alert initiated via %s.%s; immediately suspending BT scans on %s",
                domain,
                service,
                [s.name for s in affected_speakers],
            )
            for spk in affected_speakers:
                data = self._speakers_data.get(spk.device_id)
                if data and data.get("state") and data["state"].status == "scanning":
                    asyncio.create_task(self._safe_stop_scan(spk))

    def _handle_state_changed(self, event: Event) -> None:
        """Handle media_player state change events."""
        entity_id = event.data.get("entity_id", "")
        if not entity_id.startswith("media_player."):
            return

        old_state = event.data.get("old_state")
        new_state = event.data.get("new_state")
        if not new_state:
            return

        old_s = old_state.state.lower() if old_state and old_state.state else ""
        new_s = new_state.state.lower() if new_state and new_state.state else ""

        now = time.monotonic()

        for _speaker_id, data in self._speakers_data.items():
            speaker: SpeakerNode = data["speaker"]
            state: SpeakerProxyState | None = data.get("state")
            eids = self._speaker_entity_map.get(speaker.device_id, set())

            is_relevant = (
                entity_id in eids
                or entity_id == "media_player.whole_home"
                or self._is_cast_group_entity(entity_id)
            )

            if not is_relevant:
                continue

            if new_s in HA_ACTIVE_STATES:
                # Active playback ongoing; extend lock
                self._speaker_tts_active_until[speaker.device_id] = now + 30.0
                if state and state.status == "scanning":
                    state.abort_scan_event.set()
                    asyncio.create_task(self._safe_stop_scan(speaker))
            elif old_s in HA_ACTIVE_STATES and new_s not in HA_ACTIVE_STATES:
                # Transitioned from playing to idle/off/paused; grant cooldown buffer
                self._speaker_tts_active_until[speaker.device_id] = now + self._tts_cooldown

    async def _safe_stop_scan(self, speaker: SpeakerNode) -> None:
        """Abort an active hardware Bluetooth scan safely."""
        try:
            await self._api_client.stop_scan(speaker)
            _LOGGER.debug("Successfully issued stop_scan to %s", speaker.name)
        except Exception as err:
            _LOGGER.debug("Could not issue stop_scan to %s: %s", speaker.name, err)

    async def _check_cast_playing(self, speaker: SpeakerNode) -> bool:
        """Run blocking pychromecast socket check in executor thread (fallback only)."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None,
            self._sync_check_cast,
            speaker.ip_address,
            speaker.hardware,
            speaker.name,
        )

    def _sync_check_cast(self, host: str, hardware: str, name: str) -> bool:
        """Query Cast V2 receiver and media controller status."""
        cast: pychromecast.Chromecast | None = None
        try:
            cast_info = CastInfo(
                services={HostServiceInfo(host, 8009)},
                uuid=uuid.uuid4(),
                model_name=hardware,
                friendly_name=name,
                host=host,
                port=8009,
                cast_type="audio",
                manufacturer="Google Inc.",
            )
            cast = pychromecast.Chromecast(
                cast_info=cast_info,
                tries=1,
                timeout=self._cast_timeout,
            )
            cast.wait(timeout=self._cast_timeout)

            # Check media controller player state
            if cast.media_controller and cast.media_controller.status:
                state = cast.media_controller.status.player_state
                if state in ACTIVE_PLAYER_STATES:
                    return True

            return False
        except Exception as err:
            _LOGGER.debug("Error probing Cast V2 status on %s: %s", host, err)
            return False
        finally:
            if cast is not None:
                try:
                    cast.disconnect()
                except Exception:
                    pass
