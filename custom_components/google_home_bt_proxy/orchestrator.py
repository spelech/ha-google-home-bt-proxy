"""Round-robin scan orchestrator with adaptive concurrency for Bermuda lifespan compliance."""

from __future__ import annotations

import asyncio
import logging
import math
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from .const import (
    DEFAULT_ORCHESTRATION_MODE,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SCAN_TIMEOUT,
    ORCHESTRATION_ROUND_ROBIN,
)

_LOGGER = logging.getLogger(__name__)


def calculate_recommended_concurrency(
    speaker_count: int,
    scan_timeout: float = DEFAULT_SCAN_TIMEOUT,
    scan_interval: float = DEFAULT_SCAN_INTERVAL,
) -> int:
    """Calculate the minimum concurrent scan slots required so every speaker cycles in time.

    For N speakers with active scan duration T_scan and inter-scan pause T_interval,
    each speaker targets a cycle period T_target = T_scan + T_interval (default 8s,
    safely below Bermuda's 10.0s AREA_MAX_AD_AGE expiration cutoff).
    To ensure N speakers each get a T_scan slot every T_target seconds without
    accumulating queue lag:
        K >= ceil((N * T_scan) / T_target)
    """
    if speaker_count <= 1:
        return 1
    target_cycle = max(float(scan_timeout) + float(scan_interval), float(scan_timeout), 1.0)
    return max(1, math.ceil((speaker_count * float(scan_timeout)) / target_cycle))


class ScanOrchestrator:
    """Orchestrates BLE scanning slots among multiple Google Home speakers.

    Serializes or bounds concurrent active inquiry scans (which broadcast and receive
    on 2.4GHz channels) in a fair FIFO manner to prevent Wi-Fi/Bluetooth coexistence
    bursts while scaling slot concurrency so large speaker fleets never exceed
    Bermuda's 10-second advertisement expiration window.
    """

    def __init__(
        self,
        mode: str = DEFAULT_ORCHESTRATION_MODE,
        speaker_count: int = 1,
        scan_timeout: float = DEFAULT_SCAN_TIMEOUT,
        scan_interval: float = DEFAULT_SCAN_INTERVAL,
        max_concurrent: int | None = None,
    ) -> None:
        """Initialize the scan orchestrator."""
        self.mode = mode
        self._explicit_max_concurrent = max_concurrent
        if max_concurrent is not None:
            self._max_concurrent = max(1, int(max_concurrent))
        else:
            self._max_concurrent = calculate_recommended_concurrency(
                speaker_count=speaker_count,
                scan_timeout=scan_timeout,
                scan_interval=scan_interval,
            )
        self._cond = asyncio.Condition()
        self._active_speakers: list[str] = []
        self._waiters: list[str] = []
        self._total_orchestrated_scans: int = 0
        self._last_scan_time: float | None = None
        self._last_wait_durations: dict[str, float] = {}

    @property
    def is_enabled(self) -> bool:
        """Return True if round-robin orchestration is active."""
        return self.mode == ORCHESTRATION_ROUND_ROBIN

    @property
    def max_concurrent(self) -> int:
        """Return the maximum number of simultaneous active scans allowed."""
        return self._max_concurrent

    def update_scaling(
        self,
        speaker_count: int,
        scan_timeout: float = DEFAULT_SCAN_TIMEOUT,
        scan_interval: float = DEFAULT_SCAN_INTERVAL,
    ) -> None:
        """Dynamically recalculate slot concurrency when speaker count or timings change."""
        if self._explicit_max_concurrent is not None:
            return
        self._max_concurrent = calculate_recommended_concurrency(
            speaker_count=speaker_count,
            scan_timeout=scan_timeout,
            scan_interval=scan_interval,
        )

    @property
    def current_speaker(self) -> str | None:
        """Return the ID of the primary speaker currently performing an active scan."""
        return self._active_speakers[0] if self._active_speakers else None

    @property
    def active_speakers(self) -> list[str]:
        """Return a copy of speaker IDs currently performing an active scan."""
        return list(self._active_speakers)

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

    def get_last_wait_duration(self, speaker_id: str) -> float:
        """Return the queue wait duration in seconds from the speaker's last acquire_slot call."""
        return self._last_wait_durations.get(speaker_id, 0.0)

    @asynccontextmanager
    async def acquire_slot(
        self,
        speaker_id: str,
        timeout: float | None = 60.0,  # noqa: ASYNC109
    ) -> AsyncIterator[bool]:
        """Acquire an orchestration scanning slot for the given speaker.

        If orchestration is set to independent, this yields True immediately.
        Otherwise, it waits in FIFO order until an active slot (< max_concurrent) is open.
        """
        if not self.is_enabled:
            self._last_wait_durations[speaker_id] = 0.0
            yield True
            return

        start_wait = time.monotonic()
        self._waiters.append(speaker_id)

        def _can_acquire() -> bool:
            return (
                len(self._active_speakers) < self._max_concurrent
                and bool(self._waiters)
                and self._waiters[0] == speaker_id
            )

        try:
            async with self._cond:
                if timeout is not None:
                    await asyncio.wait_for(self._cond.wait_for(_can_acquire), timeout=timeout)
                else:
                    await self._cond.wait_for(_can_acquire)

                if speaker_id in self._waiters:
                    self._waiters.remove(speaker_id)
                self._active_speakers.append(speaker_id)
                self._total_orchestrated_scans += 1
                # If additional slots are still available for the next waiter, wake them up too
                if len(self._active_speakers) < self._max_concurrent and self._waiters:
                    self._cond.notify_all()
        except TimeoutError:
            wait_duration = time.monotonic() - start_wait
            self._last_wait_durations[speaker_id] = wait_duration
            async with self._cond:
                if speaker_id in self._waiters:
                    self._waiters.remove(speaker_id)
                self._cond.notify_all()
            _LOGGER.warning(
                "Speaker %s timed out after %.1fs waiting for scan orchestration slot",
                speaker_id,
                wait_duration,
            )
            yield False
            return
        except BaseException:
            async with self._cond:
                if speaker_id in self._waiters:
                    self._waiters.remove(speaker_id)
                self._cond.notify_all()
            raise

        wait_duration = time.monotonic() - start_wait
        self._last_wait_durations[speaker_id] = wait_duration
        _LOGGER.debug(
            "Speaker %s acquired scan slot (waited %.2fs, active: %d/%d, queue depth: %d)",
            speaker_id,
            wait_duration,
            len(self._active_speakers),
            self._max_concurrent,
            len(self._waiters),
        )

        try:
            yield True
        finally:
            async with self._cond:
                if speaker_id in self._active_speakers:
                    self._active_speakers.remove(speaker_id)
                self._last_scan_time = time.monotonic()
                self._cond.notify_all()
            _LOGGER.debug("Speaker %s released scan slot", speaker_id)
