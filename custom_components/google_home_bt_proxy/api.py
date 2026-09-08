"""HTTPS API client for communicating with Google Home speakers on port 8443."""

from __future__ import annotations

import logging
from typing import Any

import aiohttp

from .classification import decode_device_class, is_resolvable_private_address
from .const import (
    ENDPOINT_BLUETOOTH_SCAN,
    ENDPOINT_BLUETOOTH_SCAN_RESULTS,
    ENDPOINT_BLUETOOTH_STATUS,
    ENDPOINT_EUREKA_INFO,
    HEADER_CONTENT_TYPE,
    HEADER_LOCAL_AUTH,
    PORT_HTTPS,
)
from .models import DiscoveredDevice, SpeakerNode, format_or_derive_mac, is_valid_mac

_LOGGER = logging.getLogger(__name__)


class TokenExpiredError(Exception):
    """Raised when the speaker returns HTTP 401 Unauthorized."""


class SpeakerConnectionError(Exception):
    """Raised on connection timeout or network failure."""


class SpeakerUnsupportedError(Exception):
    """Raised when the device returns HTTP 404 (Bluetooth scan API not implemented)."""


class GoogleHomeApiClient:
    """Client for local Google Home API requests."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        port: int = PORT_HTTPS,
        use_ssl: bool = True,
        request_timeout: int = 5,
    ) -> None:
        """Initialize GoogleHomeApiClient."""
        self._session = session
        self._port = port
        self._use_ssl = use_ssl
        self._timeout = aiohttp.ClientTimeout(total=request_timeout)

    def _build_url(self, ip_address: str, endpoint: str) -> str:
        protocol = "https" if self._use_ssl else "http"
        host = f"[{ip_address}]" if ":" in ip_address and not ip_address.startswith("[") else ip_address
        return f"{protocol}://{host}:{self._port}/{endpoint}"

    def _headers(self, auth_token: str) -> dict[str, str]:
        return {
            HEADER_LOCAL_AUTH: auth_token,
            HEADER_CONTENT_TYPE: "application/json",
        }

    async def start_scan(
        self,
        speaker: SpeakerNode,
        timeout: int = 5,  # noqa: ASYNC109
    ) -> bool:
        """Trigger an inquiry Bluetooth scan on the speaker."""
        url = self._build_url(speaker.ip_address, ENDPOINT_BLUETOOTH_SCAN)
        payload = {"enable": True, "clear_results": True, "timeout": timeout}

        try:
            async with self._session.post(
                url,
                json=payload,
                headers=self._headers(speaker.auth_token),
                timeout=self._timeout,
                ssl=False,
            ) as resp:
                if resp.status == 401:
                    raise TokenExpiredError(f"Token expired on speaker {speaker.name}")
                if resp.status == 404:
                    speaker.available = False
                    raise SpeakerUnsupportedError(
                        f"Bluetooth scan API not supported on {speaker.name} (HTTP 404)"
                    )
                if resp.status == 200:
                    speaker.available = True
                    return True
                _LOGGER.warning("Failed to start scan on %s: HTTP %d", speaker.name, resp.status)
                return False
        except (aiohttp.ClientError, TimeoutError) as err:
            speaker.available = False
            raise SpeakerConnectionError(f"Connection failed to {speaker.name}: {err}") from err

    async def get_scan_results(self, speaker: SpeakerNode) -> list[DiscoveredDevice]:
        """Fetch discovered Bluetooth devices from the speaker."""
        url = self._build_url(speaker.ip_address, ENDPOINT_BLUETOOTH_SCAN_RESULTS)

        try:
            async with self._session.get(
                url,
                headers=self._headers(speaker.auth_token),
                timeout=self._timeout,
                ssl=False,
            ) as resp:
                if resp.status == 401:
                    raise TokenExpiredError(f"Token expired on speaker {speaker.name}")
                if resp.status == 404:
                    speaker.available = False
                    raise SpeakerUnsupportedError(
                        f"Bluetooth scan results API not supported on {speaker.name} (HTTP 404)"
                    )
                if resp.status == 200:
                    speaker.available = True
                    data = await resp.json()
                    if not isinstance(data, list):
                        _LOGGER.warning(
                            "Unexpected scan results data format from %s: %s",
                            speaker.name,
                            type(data),
                        )
                        return []
                    results: list[DiscoveredDevice] = []
                    for item in data:
                        if not isinstance(item, dict):
                            continue
                        mac = item.get("mac_address")
                        rssi = item.get("rssi")
                        if mac and rssi is not None:
                            dev_class = item.get("device_class")
                            results.append(
                                DiscoveredDevice(
                                    mac_address=mac,
                                    rssi=int(rssi),
                                    name=item.get("name"),
                                    device_type=item.get("device_type"),
                                    device_class=dev_class,
                                    device_class_name=decode_device_class(dev_class),
                                    expected_profiles=item.get("expected_profiles"),
                                    is_rpa=is_resolvable_private_address(mac),
                                )
                            )
                    return results
                _LOGGER.warning(
                    "Failed to fetch scan results on %s: HTTP %d",
                    speaker.name,
                    resp.status,
                )
                return []
        except (aiohttp.ClientError, TimeoutError) as err:
            speaker.available = False
            raise SpeakerConnectionError(f"Connection failed to {speaker.name}: {err}") from err

    async def get_device_info(self, speaker: SpeakerNode) -> dict[str, Any]:
        """Retrieve eureka_info from the speaker."""
        url = self._build_url(speaker.ip_address, ENDPOINT_EUREKA_INFO)
        try:
            async with self._session.get(
                url,
                headers=self._headers(speaker.auth_token),
                timeout=self._timeout,
                ssl=False,
            ) as resp:
                if resp.status == 401:
                    raise TokenExpiredError(f"Token expired on speaker {speaker.name}")
                if resp.status == 200:
                    speaker.available = True
                    data = await resp.json()
                    if isinstance(data, dict):
                        extracted_mac = self._extract_mac(data)
                        if extracted_mac:
                            speaker.mac_address = format_or_derive_mac(
                                speaker.device_id, extracted_mac
                            )
                    return data if isinstance(data, dict) else {}
                return {}
        except (aiohttp.ClientError, TimeoutError) as err:
            speaker.available = False
            raise SpeakerConnectionError(f"Connection failed to {speaker.name}: {err}") from err

    @staticmethod
    def _extract_mac(data: dict[str, Any]) -> str | None:
        """Extract valid MAC address from eureka_info payload if present."""
        if not isinstance(data, dict):
            return None
        for key in ("mac_address", "hotspot_bssid"):
            if (mac := data.get(key)) and is_valid_mac(str(mac)):
                return str(mac)
        dev_info = data.get("device_info")
        if isinstance(dev_info, dict) and (mac := dev_info.get("mac_address")) and is_valid_mac(str(mac)):
            return str(mac)
        net_info = data.get("net")
        if isinstance(net_info, dict):
            wlan0 = net_info.get("wlan0")
            if isinstance(wlan0, dict) and (mac := wlan0.get("mac")) and is_valid_mac(str(mac)):
                return str(mac)
            eth = net_info.get("ethernet")
            if isinstance(eth, dict) and (mac := eth.get("mac")) and is_valid_mac(str(mac)):
                return str(mac)
        wifi_info = data.get("wifi")
        if isinstance(wifi_info, dict) and (mac := wifi_info.get("wlan0_mac")) and is_valid_mac(str(mac)):
            return str(mac)
        return None

    async def get_bluetooth_status(self, speaker: SpeakerNode) -> dict[str, Any]:
        """Retrieve bluetooth status from the speaker."""
        url = self._build_url(speaker.ip_address, ENDPOINT_BLUETOOTH_STATUS)
        try:
            async with self._session.get(
                url,
                headers=self._headers(speaker.auth_token),
                timeout=self._timeout,
                ssl=False,
            ) as resp:
                if resp.status == 401:
                    raise TokenExpiredError(f"Token expired on speaker {speaker.name}")
                if resp.status == 200:
                    speaker.available = True
                    data = await resp.json()
                    return data if isinstance(data, dict) else {}
                return {}
        except (aiohttp.ClientError, TimeoutError) as err:
            speaker.available = False
            raise SpeakerConnectionError(f"Connection failed to {speaker.name}: {err}") from err
