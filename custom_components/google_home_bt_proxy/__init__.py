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
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

from .api import GoogleHomeApiClient, SpeakerConnectionError, TokenExpiredError
from .const import (
    CONF_ANDROID_ID,
    CONF_DISABLED_SPEAKERS,
    CONF_ENABLE_DISTANCE_ESTIMATION,
    CONF_ENABLE_RSSI_SMOOTHING,
    CONF_FILTER_MODE,
    CONF_KNOWN_IRKS,
    CONF_MASTER_TOKEN,
    CONF_MAX_DISTANCE,
    CONF_MAX_PLAYING_SKIP_DURATION,
    CONF_ORCHESTRATION_MODE,
    CONF_PASSWORD,
    CONF_PATH_LOSS_EXPONENT,
    CONF_PLAYBACK_MODE,
    CONF_PLAYING_SCAN_INTERVAL,
    CONF_PLAYING_SCAN_TIMEOUT,
    CONF_REF_POWER,
    CONF_RSSI_FILTER_MODE,
    CONF_RSSI_FILTER_WINDOW,
    CONF_RSSI_OFFSET,
    CONF_RSSI_THRESHOLD,
    CONF_SCAN_INTERVAL,
    CONF_SCAN_TIMEOUT,
    CONF_SPEAKER_OVERRIDES,
    CONF_TRACKED_DEVICES,
    CONF_USERNAME,
    DEFAULT_ENABLE_DISTANCE_ESTIMATION,
    DEFAULT_ENABLE_RSSI_SMOOTHING,
    DEFAULT_FILTER_MODE,
    DEFAULT_MAX_DISTANCE,
    DEFAULT_MAX_PLAYING_SKIP_DURATION,
    DEFAULT_ORCHESTRATION_MODE,
    DEFAULT_PATH_LOSS_EXPONENT,
    DEFAULT_PLAYBACK_MODE,
    DEFAULT_PLAYING_SCAN_INTERVAL,
    DEFAULT_PLAYING_SCAN_TIMEOUT,
    DEFAULT_REF_POWER,
    DEFAULT_RSSI_FILTER_MODE,
    DEFAULT_RSSI_FILTER_WINDOW,
    DEFAULT_RSSI_OFFSET,
    DEFAULT_RSSI_THRESHOLD,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SCAN_TIMEOUT,
    DOMAIN,
    MODE_IGNORE,
    MODE_SKIP_CEILING,
    MODE_THROTTLE,
    ORCHESTRATION_INDEPENDENT,
)
from .coordinator import GoogleHomeProxyCoordinator
from .filter import SignalProcessor
from .irk import IrkResolver, parse_irk_config
from .models import SpeakerNode, SpeakerProxyState
from .orchestrator import ScanOrchestrator
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

    orchestrator_mode = entry.options.get(CONF_ORCHESTRATION_MODE, DEFAULT_ORCHESTRATION_MODE)
    orchestrator = ScanOrchestrator(mode=orchestrator_mode)

    scanners: dict[str, GoogleHomeRemoteScanner] = {}
    speakers_data: dict[str, dict[str, Any]] = {}
    unregister_callbacks: list[Callable[[], None]] = []
    worker_tasks: list[asyncio.Task[None]] = []

    for index, speaker in enumerate(active_speakers):
        speaker_rssi_offset = _get_speaker_setting(
            entry, speaker.device_id, CONF_RSSI_OFFSET, DEFAULT_RSSI_OFFSET
        )
        filter_mode = _get_speaker_setting(
            entry, speaker.device_id, CONF_FILTER_MODE, DEFAULT_FILTER_MODE
        )
        tracked_raw = _get_speaker_setting(entry, speaker.device_id, CONF_TRACKED_DEVICES, [])
        if isinstance(tracked_raw, str):
            tracked_devices = [d.strip() for d in tracked_raw.split(",") if d.strip()]
        else:
            tracked_devices = list(tracked_raw or [])

        max_distance = float(
            _get_speaker_setting(entry, speaker.device_id, CONF_MAX_DISTANCE, DEFAULT_MAX_DISTANCE)
        )
        ref_power = int(
            _get_speaker_setting(entry, speaker.device_id, CONF_REF_POWER, DEFAULT_REF_POWER)
        )
        path_loss_exponent = float(
            _get_speaker_setting(
                entry, speaker.device_id, CONF_PATH_LOSS_EXPONENT, DEFAULT_PATH_LOSS_EXPONENT
            )
        )
        enable_rssi_smoothing = bool(
            _get_speaker_setting(
                entry,
                speaker.device_id,
                CONF_ENABLE_RSSI_SMOOTHING,
                DEFAULT_ENABLE_RSSI_SMOOTHING,
            )
        )
        smoothing_mode = _get_speaker_setting(
            entry, speaker.device_id, CONF_RSSI_FILTER_MODE, DEFAULT_RSSI_FILTER_MODE
        )
        smoothing_window = int(
            _get_speaker_setting(
                entry, speaker.device_id, CONF_RSSI_FILTER_WINDOW, DEFAULT_RSSI_FILTER_WINDOW
            )
        )
        enable_distance_estimation = bool(
            _get_speaker_setting(
                entry,
                speaker.device_id,
                CONF_ENABLE_DISTANCE_ESTIMATION,
                DEFAULT_ENABLE_DISTANCE_ESTIMATION,
            )
        )

        signal_processor = SignalProcessor(
            filter_mode=filter_mode,
            tracked_devices=tracked_devices,
            enable_distance_estimation=enable_distance_estimation,
            max_distance=max_distance,
            ref_power=ref_power,
            path_loss_exponent=path_loss_exponent,
            rssi_offset=speaker_rssi_offset,
            enable_rssi_smoothing=enable_rssi_smoothing,
            smoothing_mode=smoothing_mode,
            smoothing_window=smoothing_window,
        )

        device_registry = dr.async_get(hass)
        speaker_device_id = speaker.device_id
        if hasattr(device_registry, "async_get_or_create"):
            try:
                speaker_device = device_registry.async_get_or_create(
                    config_entry_id=entry.entry_id,
                    identifiers={(DOMAIN, speaker.device_id)},
                    connections={(dr.CONNECTION_NETWORK_MAC, speaker.mac_address.lower())},
                    name=speaker.name,
                    manufacturer="Google",
                    model=speaker.hardware,
                )
                speaker_device_id = speaker_device.id
            except Exception:
                speaker_device_id = speaker.device_id

        scanner = GoogleHomeRemoteScanner(
            scanner_id=speaker.mac_address.upper(),
            name=f"{speaker.name} Bluetooth Proxy",
            irk_resolver=irk_resolver,
            rssi_offset=speaker_rssi_offset,
            signal_processor=signal_processor,
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
            source_config_entry_id=entry.entry_id,
            source_device_id=speaker_device_id,
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
                orchestrator=orchestrator,
            ),
            name=f"google_home_bt_proxy_{speaker.device_id}",
        )
        worker_tasks.append(task)

    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "api_client": api_client,
        "playback_detector": playback_detector,
        "orchestrator": orchestrator,
        "scanners": scanners,
        "speakers": speakers_data,
        "unregister_callbacks": unregister_callbacks,
        "worker_tasks": worker_tasks,
    }

    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    forward_setups = getattr(
        getattr(hass, "config_entries", None), "async_forward_entry_setups", None
    )
    if forward_setups:
        res = forward_setups(entry, PLATFORMS)
        if asyncio.iscoroutine(res):
            await res

    return True


def _get_speaker_setting(
    entry: ConfigEntry,
    speaker_id: str,
    key: str,
    default: Any,
) -> Any:
    """Resolve a setting for a specific speaker, falling back to global options."""
    overrides = entry.options.get(CONF_SPEAKER_OVERRIDES, {}).get(speaker_id, {})
    if key in overrides and overrides[key] is not None:
        return overrides[key]
    return entry.options.get(key, default)


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
    orchestrator: ScanOrchestrator | None = None,
) -> None:
    """Continuous staggered polling scan loop for an individual speaker."""
    if playback_detector is None:
        playback_detector = SpeakerPlaybackDetector(api_client)
    if state is None:
        state = SpeakerProxyState(enabled=speaker.enabled)
    if orchestrator is None:
        orchestrator = ScanOrchestrator(mode=ORCHESTRATION_INDEPENDENT)

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

        playback_mode = _get_speaker_setting(
            entry, speaker.device_id, CONF_PLAYBACK_MODE, DEFAULT_PLAYBACK_MODE
        )
        idle_scan_timeout = _get_speaker_setting(
            entry, speaker.device_id, CONF_SCAN_TIMEOUT, DEFAULT_SCAN_TIMEOUT
        )
        idle_scan_interval = _get_speaker_setting(
            entry, speaker.device_id, CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
        )
        playing_scan_timeout = _get_speaker_setting(
            entry, speaker.device_id, CONF_PLAYING_SCAN_TIMEOUT, DEFAULT_PLAYING_SCAN_TIMEOUT
        )
        playing_scan_interval = _get_speaker_setting(
            entry, speaker.device_id, CONF_PLAYING_SCAN_INTERVAL, DEFAULT_PLAYING_SCAN_INTERVAL
        )
        max_skip_duration = _get_speaker_setting(
            entry,
            speaker.device_id,
            CONF_MAX_PLAYING_SKIP_DURATION,
            DEFAULT_MAX_PLAYING_SKIP_DURATION,
        )
        rssi_threshold = _get_speaker_setting(
            entry, speaker.device_id, CONF_RSSI_THRESHOLD, DEFAULT_RSSI_THRESHOLD
        )
        speaker_rssi_offset = _get_speaker_setting(
            entry, speaker.device_id, CONF_RSSI_OFFSET, DEFAULT_RSSI_OFFSET
        )
        scanner._rssi_offset = speaker_rssi_offset

        # Dynamically sync scanner signal processor and orchestrator settings
        if hasattr(scanner, "signal_processor"):
            sp = scanner.signal_processor
            sp.rssi_offset = speaker_rssi_offset
            sp.filter_mode = _get_speaker_setting(
                entry, speaker.device_id, CONF_FILTER_MODE, DEFAULT_FILTER_MODE
            )
            tracked_raw = _get_speaker_setting(entry, speaker.device_id, CONF_TRACKED_DEVICES, [])
            if isinstance(tracked_raw, str):
                sp.tracked_devices = {
                    d.strip().upper() for d in tracked_raw.split(",") if d.strip()
                }
            else:
                sp.tracked_devices = {d.strip().upper() for d in tracked_raw if d.strip()}
            sp.max_distance = max(
                0.0,
                float(
                    _get_speaker_setting(
                        entry, speaker.device_id, CONF_MAX_DISTANCE, DEFAULT_MAX_DISTANCE
                    )
                ),
            )
            sp.ref_power = int(
                _get_speaker_setting(entry, speaker.device_id, CONF_REF_POWER, DEFAULT_REF_POWER)
            )
            sp.path_loss_exponent = float(
                _get_speaker_setting(
                    entry, speaker.device_id, CONF_PATH_LOSS_EXPONENT, DEFAULT_PATH_LOSS_EXPONENT
                )
            )
            sp.enable_rssi_smoothing = bool(
                _get_speaker_setting(
                    entry,
                    speaker.device_id,
                    CONF_ENABLE_RSSI_SMOOTHING,
                    DEFAULT_ENABLE_RSSI_SMOOTHING,
                )
            )
            sp.smoother.mode = _get_speaker_setting(
                entry, speaker.device_id, CONF_RSSI_FILTER_MODE, DEFAULT_RSSI_FILTER_MODE
            )
            sp.smoother.window_size = int(
                _get_speaker_setting(
                    entry, speaker.device_id, CONF_RSSI_FILTER_WINDOW, DEFAULT_RSSI_FILTER_WINDOW
                )
            )
            sp.enable_distance_estimation = bool(
                _get_speaker_setting(
                    entry,
                    speaker.device_id,
                    CONF_ENABLE_DISTANCE_ESTIMATION,
                    DEFAULT_ENABLE_DISTANCE_ESTIMATION,
                )
            )

        orchestrator.mode = entry.options.get(CONF_ORCHESTRATION_MODE, DEFAULT_ORCHESTRATION_MODE)

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
                state.status = "waiting_slot"
                state.notify_callbacks()

                async with orchestrator.acquire_slot(speaker.device_id) as acquired:
                    if not acquired:
                        _LOGGER.debug(
                            "Speaker %s timed out waiting for scan slot; skipping cycle",
                            speaker.name,
                        )
                        state.status = "idle"
                        state.notify_callbacks()
                        await asyncio.sleep(active_interval)
                        continue

                    state.status = "scanning"
                    state.notify_callbacks()

                    # 1. Trigger hardware scan
                    await api_client.start_scan(speaker, timeout=active_timeout)

                    # 2. Await hardware scan duration
                    await asyncio.sleep(active_timeout)

                    # 3. Retrieve scan results
                    results = await api_client.get_scan_results(speaker)

                # 4. Inject into Home Assistant Bluetooth Manager
                injected = scanner.process_scan_results(results, min_rssi=rssi_threshold)
                backoff = 1.0

                state.last_scan_count = len(results)
                state.total_advertisements += len(results)
                state.filtered_advertisements += len(results) - injected
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


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)


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
