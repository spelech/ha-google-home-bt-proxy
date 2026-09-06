"""Google Home Bluetooth Proxy Integration."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable
from typing import Any

from homeassistant.components import bluetooth, zeroconf
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

from .api import GoogleHomeApiClient, SpeakerConnectionError, TokenExpiredError
from .auth_view import GoogleHomeBtProxyAuthCallbackView
from .const import (
    CONF_ANDROID_ID,
    CONF_DISABLED_SPEAKERS,
    CONF_KNOWN_IRKS,
    CONF_MASTER_TOKEN,
    CONF_MAX_PLAYING_SKIP_DURATION,
    CONF_PASSWORD,
    CONF_PLAYBACK_MODE,
    CONF_PLAYING_SCAN_INTERVAL,
    CONF_PLAYING_SCAN_TIMEOUT,
    CONF_RSSI_THRESHOLD,
    CONF_SCAN_INTERVAL,
    CONF_SCAN_TIMEOUT,
    CONF_USERNAME,
    DEFAULT_MAX_PLAYING_SKIP_DURATION,
    DEFAULT_PLAYBACK_MODE,
    DEFAULT_PLAYING_SCAN_INTERVAL,
    DEFAULT_PLAYING_SCAN_TIMEOUT,
    DEFAULT_RSSI_THRESHOLD,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SCAN_TIMEOUT,
    DOMAIN,
    MODE_IGNORE,
    MODE_SKIP_CEILING,
    MODE_THROTTLE,
)
from .coordinator import GoogleHomeProxyCoordinator
from .irk import IrkResolver, parse_irk_config
from .models import SpeakerNode, SpeakerProxyState
from .playback import SpeakerPlaybackDetector
from .scanner import GoogleHomeRemoteScanner

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.BUTTON,
]


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Google Home Bluetooth Proxy component."""
    hass.http.register_view(GoogleHomeBtProxyAuthCallbackView)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Google Home Bluetooth Proxy from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    session = async_get_clientsession(hass, verify_ssl=False)
    zc = await zeroconf.async_get_instance(hass)

    coordinator = GoogleHomeProxyCoordinator(
        hass=hass,
        username=entry.data.get(CONF_USERNAME),
        password=entry.data.get(CONF_PASSWORD),
        master_token=entry.data.get(CONF_MASTER_TOKEN),
        android_id=entry.data.get(CONF_ANDROID_ID),
        zeroconf_instance=zc,
    )

    api_client = GoogleHomeApiClient(session=session)
    playback_detector = SpeakerPlaybackDetector(api_client=api_client)
    speakers = await coordinator.async_get_speakers()

    disabled_speakers: list[str] = entry.options.get(CONF_DISABLED_SPEAKERS, [])
    active_speakers = [s for s in speakers if s.device_id not in disabled_speakers]

    irk_config_text = entry.options.get(CONF_KNOWN_IRKS, "")
    irk_map = parse_irk_config(irk_config_text)
    irk_resolver = IrkResolver(irk_map) if irk_map else None

    scanners: dict[str, GoogleHomeRemoteScanner] = {}
    speakers_data: dict[str, dict[str, Any]] = {}
    unregister_callbacks: list[Callable[[], None]] = []
    worker_tasks: list[asyncio.Task[None]] = []

    for index, speaker in enumerate(active_speakers):
        scanner = GoogleHomeRemoteScanner(
            scanner_id=f"google_home_{speaker.device_id}",
            name=f"{speaker.name} Bluetooth Proxy",
            irk_resolver=irk_resolver,
        )
        scanners[speaker.device_id] = scanner
        proxy_state = SpeakerProxyState(enabled=speaker.enabled)
        speakers_data[speaker.device_id] = {
            "speaker": speaker,
            "state": proxy_state,
            "scanner": scanner,
        }

        unreg = bluetooth.async_register_scanner(
            hass,
            scanner,
            source_domain=DOMAIN,
            source_model=speaker.hardware,
            source_device_id=speaker.device_id,
        )
        unregister_callbacks.append(unreg)

        # Stagger worker starts by 1.5 seconds per speaker
        stagger_delay = index * 1.5
        task = hass.async_create_background_task(
            _speaker_scan_loop(
                hass,
                entry,
                coordinator,
                api_client,
                speaker,
                scanner,
                stagger_delay,
                playback_detector=playback_detector,
                state=proxy_state,
            ),
            name=f"google_home_bt_proxy_{speaker.device_id}",
        )
        worker_tasks.append(task)

    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "api_client": api_client,
        "playback_detector": playback_detector,
        "scanners": scanners,
        "speakers": speakers_data,
        "unregister_callbacks": unregister_callbacks,
        "worker_tasks": worker_tasks,
    }

    forward_setups = getattr(
        getattr(hass, "config_entries", None), "async_forward_entry_setups", None
    )
    if forward_setups:
        res = forward_setups(entry, PLATFORMS)
        if asyncio.iscoroutine(res):
            await res

    return True


async def _speaker_scan_loop(
    hass: HomeAssistant,
    entry: ConfigEntry,
    coordinator: GoogleHomeProxyCoordinator,
    api_client: GoogleHomeApiClient,
    speaker: SpeakerNode,
    scanner: GoogleHomeRemoteScanner,
    initial_delay: float,
    playback_detector: SpeakerPlaybackDetector | None = None,
    state: SpeakerProxyState | None = None,
) -> None:
    """Continuous staggered polling scan loop for an individual speaker."""
    if playback_detector is None:
        playback_detector = SpeakerPlaybackDetector(api_client)
    if state is None:
        state = SpeakerProxyState(enabled=speaker.enabled)

    await asyncio.sleep(initial_delay)
    _LOGGER.info("Starting Bluetooth scan worker loop for %s", speaker.name)

    backoff = 1.0
    continuous_skip_start: float | None = None

    while True:
        if not state.enabled:
            state.status = "disabled"
            state.notify_callbacks()
            await asyncio.sleep(1.0)
            continue

        playback_mode = entry.options.get(CONF_PLAYBACK_MODE, DEFAULT_PLAYBACK_MODE)
        idle_scan_timeout = entry.options.get(CONF_SCAN_TIMEOUT, DEFAULT_SCAN_TIMEOUT)
        idle_scan_interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        playing_scan_timeout = entry.options.get(
            CONF_PLAYING_SCAN_TIMEOUT, DEFAULT_PLAYING_SCAN_TIMEOUT
        )
        playing_scan_interval = entry.options.get(
            CONF_PLAYING_SCAN_INTERVAL, DEFAULT_PLAYING_SCAN_INTERVAL
        )
        max_skip_duration = entry.options.get(
            CONF_MAX_PLAYING_SKIP_DURATION, DEFAULT_MAX_PLAYING_SKIP_DURATION
        )
        rssi_threshold = entry.options.get(CONF_RSSI_THRESHOLD, DEFAULT_RSSI_THRESHOLD)

        is_playing = False
        if playback_mode != MODE_IGNORE:
            try:
                is_playing = await playback_detector.async_is_playing(speaker)
            except Exception as err:
                _LOGGER.debug("Error checking playback status on %s: %s", speaker.name, err)
                is_playing = False

        should_scan = True
        active_timeout = idle_scan_timeout
        active_interval = idle_scan_interval

        now = time.monotonic()

        if is_playing:
            if continuous_skip_start is None:
                continuous_skip_start = now

            if playback_mode == MODE_THROTTLE:
                active_timeout = playing_scan_timeout
                active_interval = playing_scan_interval
                should_scan = True
                state.status = "playback_throttled"
            elif playback_mode == MODE_SKIP_CEILING:
                elapsed_skip = now - continuous_skip_start
                if elapsed_skip >= max_skip_duration:
                    _LOGGER.info(
                        "Max continuous skip ceiling reached (%0.1fs >= %0.1fs) on %s; "
                        "forcing refresh scan",
                        elapsed_skip,
                        max_skip_duration,
                        speaker.name,
                    )
                    should_scan = True
                    active_timeout = playing_scan_timeout
                    continuous_skip_start = now
                    state.status = "playback_throttled"
                else:
                    should_scan = False
                    active_interval = idle_scan_interval
                    state.status = "playback_skipped"
            state.notify_callbacks()
        else:
            continuous_skip_start = None
            should_scan = True
            active_timeout = idle_scan_timeout
            active_interval = idle_scan_interval

        if should_scan:
            try:
                state.status = "scanning"
                state.notify_callbacks()

                # 1. Trigger hardware scan
                await api_client.start_scan(speaker, timeout=active_timeout)

                # 2. Await hardware scan duration
                await asyncio.sleep(active_timeout)

                # 3. Retrieve scan results
                results = await api_client.get_scan_results(speaker)

                # 4. Inject into Home Assistant Bluetooth Manager
                scanner.process_scan_results(results, min_rssi=rssi_threshold)
                backoff = 1.0

                state.last_scan_count = len(results)
                state.total_advertisements += len(results)
                state.last_scan_duration = float(active_timeout)
                state.last_scan_timestamp = time.time()
                state.status = "idle"
                state.notify_callbacks()

            except TokenExpiredError:
                _LOGGER.warning("Auth token expired for %s, requesting refresh...", speaker.name)
                await coordinator.async_refresh_token(speaker)
                await asyncio.sleep(2.0)
                continue
            except SpeakerConnectionError as err:
                _LOGGER.debug(
                    "Connection issue with %s: %s (backing off %0.1fs)",
                    speaker.name,
                    err,
                    backoff,
                )
                state.status = "unavailable"
                state.notify_callbacks()
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2.0, 60.0)
                continue
            except asyncio.CancelledError:
                _LOGGER.info("Stopping Bluetooth scan worker for %s", speaker.name)
                raise
            except Exception:
                _LOGGER.exception("Unexpected error in scan loop for %s", speaker.name)
                state.status = "unavailable"
                state.notify_callbacks()
        else:
            state.notify_callbacks()

        if state.trigger_scan_event.is_set():
            state.trigger_scan_event.clear()
            _LOGGER.debug("Immediate scan triggered via event for %s", speaker.name)
        else:
            await asyncio.sleep(active_interval)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Google Home Bluetooth Proxy entry."""
    entry_data: dict[str, Any] | None = hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    if not entry_data:
        return True

    unload_platforms = getattr(
        getattr(hass, "config_entries", None), "async_unload_platforms", None
    )
    if unload_platforms:
        res = unload_platforms(entry, PLATFORMS)
        if asyncio.iscoroutine(res):
            unload_ok = await res
        elif isinstance(res, bool):
            unload_ok = res
        else:
            unload_ok = True
    else:
        unload_ok = True

    # Cancel scan worker tasks
    for task in entry_data.get("worker_tasks", []):
        task.cancel()

    # Unregister scanners from Bluetooth Manager
    for unreg in entry_data.get("unregister_callbacks", []):
        if callable(unreg):
            unreg()

    return unload_ok
