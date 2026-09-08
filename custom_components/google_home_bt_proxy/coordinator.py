"""Coordinator managing speaker discovery and authentication tokens."""

from __future__ import annotations

import ipaddress
import logging
import time
from typing import TYPE_CHECKING

from glocaltokens.client import GLocalAuthenticationTokens
from zeroconf import ServiceBrowser, Zeroconf

from .models import SpeakerNode

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

_LOGGER = logging.getLogger(__name__)


EXCLUDED_HARDWARE_KEYWORDS: tuple[str, ...] = (
    "shield",
    "smart tv",
    "android tv",
    "oled",
    "chromecast",
    "receiver",
    "soundbar",
    "tx-nr",
    "group",
    "matterhub",
)


def is_valid_ipv4(address: str) -> bool:
    """Check if the string is a valid IPv4 address."""
    try:
        return isinstance(ipaddress.ip_address(address), ipaddress.IPv4Address)
    except ValueError:
        return False


def resolve_cast_ipv4_map(
    zc: Zeroconf | None = None, timeout: float = 3.5
) -> tuple[dict[str, str], dict[str, str]]:
    """Discover IPv4 addresses for Cast devices using Zeroconf."""
    ipv4_by_id: dict[str, str] = {}
    ipv4_by_name: dict[str, str] = {}

    class _CastIPv4Listener:
        def add_service(self, zc_instance: Zeroconf, type_: str, name: str) -> None:
            try:
                info = zc_instance.get_service_info(type_, name, 2000)
                if not info:
                    return
                ipv4_addrs = [a for a in info.parsed_addresses() if is_valid_ipv4(a)]
                if not ipv4_addrs:
                    return
                ipv4 = ipv4_addrs[0]
                fn = info.properties.get(b"fn", b"").decode("utf-8", "ignore")
                uid = info.properties.get(b"id", b"").decode("utf-8", "ignore")
                if fn:
                    ipv4_by_name[fn.strip().lower()] = ipv4
                if uid:
                    ipv4_by_id[uid.strip().lower()] = ipv4
            except Exception:
                pass

        def update_service(self, zc_instance: Zeroconf, type_: str, name: str) -> None:
            self.add_service(zc_instance, type_, name)

        def remove_service(self, zc_instance: Zeroconf, type_: str, name: str) -> None:
            pass

    should_close = False
    try:
        zc_raw = zc
        if zc_raw is None or type(zc_raw).__name__ == "HaZeroconf":
            zc_raw = Zeroconf()
            should_close = True
        browser = ServiceBrowser(zc_raw, "_googlecast._tcp.local.", _CastIPv4Listener())
        time.sleep(timeout)
        browser.cancel()
        if should_close:
            zc_raw.close()
    except Exception as err:
        _LOGGER.debug("Zeroconf IPv4 resolution encountered error: %s", err)

    return ipv4_by_id, ipv4_by_name


class GoogleHomeProxyCoordinator:
    """Manages glocaltokens client, discovery, and token renewals."""

    def __init__(
        self,
        hass: HomeAssistant,
        username: str | None = None,
        password: str | None = None,
        master_token: str | None = None,
        android_id: str | None = None,
        zeroconf_instance: Zeroconf | None = None,
    ) -> None:
        """Initialize coordinator."""
        self.hass = hass
        self._username = username
        self._password = password
        self._master_token = master_token
        self._android_id = android_id
        self._zeroconf = zeroconf_instance
        self._client = GLocalAuthenticationTokens(
            username=username,
            password=password,
            master_token=master_token,
            android_id=android_id,
            verbose=False,
        )
        self.speakers: dict[str, SpeakerNode] = {}

    async def async_get_speakers(self, force_reload: bool = False) -> list[SpeakerNode]:
        """Discover Google Home speakers and retrieve local authentication tokens."""
        if self.speakers and not force_reload:
            return list(self.speakers.values())

        def _fetch_devices():
            ipv4_by_id, ipv4_by_name = resolve_cast_ipv4_map(self._zeroconf)
            raw = self._client.get_google_devices(
                zeroconf_instance=self._zeroconf,
                force_homegraph_reload=force_reload,
            )
            return raw, ipv4_by_id, ipv4_by_name

        job_result = await self.hass.async_add_executor_job(_fetch_devices)
        if isinstance(job_result, tuple) and len(job_result) == 3:
            raw_devices, ipv4_by_id, ipv4_by_name = job_result
        else:
            raw_devices = job_result
            ipv4_by_id, ipv4_by_name = {}, {}

        speakers: dict[str, SpeakerNode] = {}

        for dev in raw_devices:
            if not dev.ip_address or not dev.local_auth_token:
                _LOGGER.debug(
                    "Skipping device %s: missing IP or auth token",
                    getattr(dev, "device_name", dev),
                )
                continue

            hardware = (getattr(dev, "hardware", "") or "").lower()
            name = (getattr(dev, "device_name", "") or "").lower()
            if any(kw in hardware or kw in name for kw in EXCLUDED_HARDWARE_KEYWORDS):
                _LOGGER.info(
                    "Skipping non-speaker Cast device '%s' (hardware: '%s')",
                    getattr(dev, "device_name", dev),
                    getattr(dev, "hardware", "Unknown"),
                )
                continue

            ip_address = dev.ip_address
            if not is_valid_ipv4(ip_address):
                unique_id = getattr(getattr(dev, "network_device", None), "unique_id", "") or ""
                target_name = (dev.device_name or "").strip().lower()
                if unique_id and unique_id.lower() in ipv4_by_id:
                    ip_address = ipv4_by_id[unique_id.lower()]
                    _LOGGER.info(
                        "Resolved IPv4 address %s for %s via Cast ID %s (overriding %s)",
                        ip_address,
                        dev.device_name,
                        unique_id,
                        dev.ip_address,
                    )
                elif target_name in ipv4_by_name:
                    ip_address = ipv4_by_name[target_name]
                    _LOGGER.info(
                        "Resolved IPv4 address %s for %s via Cast name (overriding %s)",
                        ip_address,
                        dev.device_name,
                        dev.ip_address,
                    )
                else:
                    _LOGGER.warning(
                        "Could not resolve IPv4 for %s; retaining address %s",
                        dev.device_name,
                        dev.ip_address,
                    )

            node = SpeakerNode(
                device_id=dev.device_id,
                name=dev.device_name,
                ip_address=ip_address,
                auth_token=dev.local_auth_token,
                hardware=getattr(dev, "hardware", "Google Home"),
            )
            speakers[node.device_id] = node

        self.speakers = speakers
        _LOGGER.info("Discovered %d Google Home speakers with valid tokens", len(self.speakers))
        return list(self.speakers.values())

    async def async_refresh_token(self, speaker: SpeakerNode) -> str | None:
        """Force reload tokens from HomeGraph on HTTP 401."""
        _LOGGER.info("Refreshing local auth token for speaker %s...", speaker.name)
        speakers = await self.async_get_speakers(force_reload=True)
        for spk in speakers:
            if spk.device_id == speaker.device_id:
                speaker.auth_token = spk.auth_token
                speaker.ip_address = spk.ip_address
                return spk.auth_token
        return None
