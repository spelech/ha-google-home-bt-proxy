"""Round-robin scan orchestrator to prevent 2.4GHz RF contention across speakers."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from .const import (
    DEFAULT_ORCHESTRATION_MODE,
    ORCHESTRATION_ROUND_ROBIN,
)

_LOGGER = logging.getLogger(__name__)


class ScanOrchestrator:
    """Orchestrates BLE scanning slots among multiple Google Home speakers.

    Ensures that in multi-speaker environments, active inquiry scans (which broadcast
    and receive on 2.4GHz channels) are serialized in a fair round-robin manner to prevent
    Wi-Fi/Bluetooth coexistence interference and packet collision.
    """

    def __init__(self, mode: str = DEFAULT_ORCHESTRATION_MODE) -> None:
        """Initialize the scan orchestrator."""
        self.mode = mode
        self._lock = asyncio.Lock()
        self._current_speaker: str | None = None
        self._waiters: list[str] = []
        self._total_orchestrated_scans: int = 0
        self._last_scan_time: float | None = None

    @property
    def is_enabled(self) -> bool:
        """Return True if round-robin orchestration is active."""
        return self.mode == ORCHESTRATION_ROUND_ROBIN

    @property
    def current_speaker(self) -> str | None:
        """Return the ID of the speaker currently performing an active scan."""
        return self._current_speaker

    @property
    def queue_depth(self) -> int:
        """Return the number of speakers waiting for an orchestration slot."""
        return len(self._waiters)

    @property
    def total_scans(self) -> int:
        """Return the total number of scans coordinated."""
        return self._total_orchestrated_scans

    @property
    def last_scan_time(self) -> float | None:
        """Return the timestamp when the last scan slot completed."""
        return self._last_scan_time

    @asynccontextmanager
    async def acquire_slot(
        self,
        speaker_id: str,
        timeout: float | None = 60.0,  # noqa: ASYNC109
    ) -> AsyncIterator[bool]:
        """Acquire an exclusive scanning slot for the given speaker.

        If orchestration is set to independent, this yields True immediately.
        Otherwise, it waits for the lock, tracks queue depth, and safely releases.
        """
        if not self.is_enabled:
            yield True
            return

        self._waiters.append(speaker_id)
        start_wait = time.monotonic()
        try:
            if timeout is not None:
                await asyncio.wait_for(self._lock.acquire(), timeout=timeout)
            else:
                await self._lock.acquire()
        except TimeoutError:
            wait_duration = time.monotonic() - start_wait
            _LOGGER.warning(
                "Speaker %s timed out after %.1fs waiting for scan orchestration slot",
                speaker_id,
                wait_duration,
            )
            yield False
            return
        finally:
            if speaker_id in self._waiters:
                self._waiters.remove(speaker_id)

        # Slot successfully acquired
        self._current_speaker = speaker_id
        self._total_orchestrated_scans += 1
        wait_duration = time.monotonic() - start_wait
        _LOGGER.debug(
            "Speaker %s acquired scan slot (waited %.2fs, queue depth: %d)",
            speaker_id,
            wait_duration,
            len(self._waiters),
        )

        try:
            yield True
        finally:
            self._current_speaker = None
            self._last_scan_time = time.monotonic()
            self._lock.release()
            _LOGGER.debug("Speaker %s released scan slot", speaker_id)
