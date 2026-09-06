"""Google Home Bluetooth Proxy Integration."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from typing import Any

from homeassistant.components import bluetooth, zeroconf
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import GoogleHomeApiClient, SpeakerConnectionError, TokenExpiredError
from .const import (
    CONF_ANDROID_ID,
    CONF_DISABLED_SPEAKERS,
    CONF_MASTER_TOKEN,
    CONF_PASSWORD,
    CONF_RSSI_THRESHOLD,
    CONF_SCAN_INTERVAL,
    CONF_SCAN_TIMEOUT,
    CONF_USERNAME,
    DEFAULT_RSSI_THRESHOLD,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SCAN_TIMEOUT,
    DOMAIN,
)
from .coordinator import GoogleHomeProxyCoordinator
from .models import SpeakerNode
from .scanner import GoogleHomeRemoteScanner

_LOGGER = logging.getLogger(__name__)


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
    speakers = await coordinator.async_get_speakers()

    disabled_speakers: list[str] = entry.options.get(CONF_DISABLED_SPEAKERS, [])
    active_speakers = [s for s in speakers if s.device_id not in disabled_speakers]

    scanners: dict[str, GoogleHomeRemoteScanner] = {}
    unregister_callbacks: list[Callable[[], None]] = []
    worker_tasks: list[asyncio.Task[None]] = []

    for index, speaker in enumerate(active_speakers):
        scanner = GoogleHomeRemoteScanner(
            scanner_id=f"google_home_{speaker.device_id}",
            name=f"{speaker.name} Bluetooth Proxy",
        )
        scanners[speaker.device_id] = scanner

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
                hass, entry, coordinator, api_client, speaker, scanner, stagger_delay
            ),
            name=f"google_home_bt_proxy_{speaker.device_id}",
        )
        worker_tasks.append(task)

    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "api_client": api_client,
        "scanners": scanners,
        "unregister_callbacks": unregister_callbacks,
        "worker_tasks": worker_tasks,
    }

    return True


async def _speaker_scan_loop(
    hass: HomeAssistant,
    entry: ConfigEntry,
    coordinator: GoogleHomeProxyCoordinator,
    api_client: GoogleHomeApiClient,
    speaker: SpeakerNode,
    scanner: GoogleHomeRemoteScanner,
    initial_delay: float,
) -> None:
    """Continuous staggered polling scan loop for an individual speaker."""
    await asyncio.sleep(initial_delay)
    _LOGGER.info("Starting Bluetooth scan worker loop for %s", speaker.name)

    backoff = 1.0

    while True:
        scan_timeout = entry.options.get(CONF_SCAN_TIMEOUT, DEFAULT_SCAN_TIMEOUT)
        scan_interval = entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        rssi_threshold = entry.options.get(CONF_RSSI_THRESHOLD, DEFAULT_RSSI_THRESHOLD)

        try:
            # 1. Trigger hardware scan
            await api_client.start_scan(speaker, timeout=scan_timeout)

            # 2. Await hardware scan duration
            await asyncio.sleep(scan_timeout)

            # 3. Retrieve scan results
            results = await api_client.get_scan_results(speaker)

            # 4. Inject into Home Assistant Bluetooth Manager
            scanner.process_scan_results(results, min_rssi=rssi_threshold)
            backoff = 1.0

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
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2.0, 60.0)
            continue
        except asyncio.CancelledError:
            _LOGGER.info("Stopping Bluetooth scan worker for %s", speaker.name)
            raise
        except Exception:
            _LOGGER.exception("Unexpected error in scan loop for %s", speaker.name)

        await asyncio.sleep(scan_interval)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload Google Home Bluetooth Proxy entry."""
    entry_data: dict[str, Any] | None = hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    if not entry_data:
        return True

    # Cancel scan worker tasks
    for task in entry_data.get("worker_tasks", []):
        task.cancel()

    # Unregister scanners from Bluetooth Manager
    for unreg in entry_data.get("unregister_callbacks", []):
        if callable(unreg):
            unreg()

    return True
