"""Standalone media playback detector for Google Home / Nest speakers."""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import TYPE_CHECKING

import pychromecast
from pychromecast.models import CastInfo, HostServiceInfo

if TYPE_CHECKING:
    from .api import GoogleHomeApiClient
    from .models import SpeakerNode

_LOGGER = logging.getLogger(__name__)

ACTIVE_PLAYER_STATES = {"PLAYING", "BUFFERING"}


class SpeakerPlaybackDetector:
    """Detects active media playback directly against a speaker without Home Assistant core dependencies."""

    def __init__(self, api_client: GoogleHomeApiClient, cast_timeout: float = 3.0) -> None:
        """Initialize the playback detector."""
        self._api_client = api_client
        self._cast_timeout = cast_timeout

    async def async_is_playing(self, speaker: SpeakerNode) -> bool:
        """Check if media is actively playing via Cast V2 or Bluetooth A2DP."""
        # 1. Check local Bluetooth audio streaming (Port 8443)
        try:
            if await self._check_bluetooth_streaming(speaker):
                _LOGGER.debug("Speaker %s is playing audio via Bluetooth", speaker.name)
                return True
        except Exception as err:
            _LOGGER.debug("Failed checking Bluetooth status on %s: %s", speaker.name, err)

        # 2. Check Cast V2 socket streaming (Port 8009)
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

    async def _check_cast_playing(self, speaker: SpeakerNode) -> bool:
        """Run blocking pychromecast socket check in executor thread."""
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
