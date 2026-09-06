"""Coordinator managing speaker discovery and authentication tokens."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from glocaltokens.client import GLocalAuthenticationTokens

from .models import SpeakerNode

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant
    from zeroconf import Zeroconf

_LOGGER = logging.getLogger(__name__)


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
            return self._client.get_google_devices(
                zeroconf_instance=self._zeroconf,
                force_homegraph_reload=force_reload,
            )

        raw_devices = await self.hass.async_add_executor_job(_fetch_devices)
        speakers: dict[str, SpeakerNode] = {}

        for dev in raw_devices:
            if not dev.ip_address or not dev.local_auth_token:
                _LOGGER.debug(
                    "Skipping device %s: missing IP or auth token",
                    getattr(dev, "device_name", dev),
                )
                continue

            node = SpeakerNode(
                device_id=dev.device_id,
                name=dev.device_name,
                ip_address=dev.ip_address,
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
                return spk.auth_token
        return None
