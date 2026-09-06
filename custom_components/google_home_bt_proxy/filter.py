"""Signal processing, distance estimation, and advertisement filtering for Google Home BT Proxy."""

from __future__ import annotations

import logging
import statistics
import time
from collections import deque
from dataclasses import dataclass
from typing import TYPE_CHECKING

from .const import (
    DEFAULT_PATH_LOSS_EXPONENT,
    DEFAULT_REF_POWER,
    DEFAULT_RSSI_FILTER_MODE,
    DEFAULT_RSSI_FILTER_WINDOW,
    FILTER_MODE_ALL,
    FILTER_MODE_KNOWN_ONLY,
    FILTER_MODE_WHITELIST,
    RSSI_FILTER_EMA,
    RSSI_FILTER_MEDIAN,
    RSSI_FILTER_NONE,
)

if TYPE_CHECKING:
    from .models import DiscoveredDevice

_LOGGER = logging.getLogger(__name__)


def calculate_distance(
    rssi: int,
    ref_power: int = DEFAULT_REF_POWER,
    path_loss_exponent: float = DEFAULT_PATH_LOSS_EXPONENT,
) -> float:
    """Calculate estimated distance in meters using the Log-Distance Path Loss model.

    Formula: d = 10 ** ((ref_power - rssi) / (10 * path_loss_exponent))
    """
    if rssi >= 0:
        return 0.0
    if path_loss_exponent <= 0:
        path_loss_exponent = 2.0

    exponent = (ref_power - rssi) / (10.0 * path_loss_exponent)
    try:
        dist = 10.0**exponent
        return round(dist, 2)
    except OverflowError:
        return 999.99


@dataclass
class ProcessedSignal:
    """Represents the output of the signal processor for a single discovered device."""

    filtered_rssi: int
    raw_rssi: int
    calibrated_rssi: int
    estimated_distance: float
    is_allowed: bool
    filter_reason: str | None = None
    samples_count: int = 1


class RssiSmoothingFilter:
    """Maintains recent RSSI history per MAC address and applies smoothing algorithms."""

    def __init__(
        self,
        mode: str = DEFAULT_RSSI_FILTER_MODE,
        window_size: int = DEFAULT_RSSI_FILTER_WINDOW,
        max_age: float = 60.0,
        ema_alpha: float = 0.6,
    ) -> None:
        """Initialize the smoothing filter."""
        self.mode = mode
        self.window_size = max(1, min(10, window_size))
        self.max_age = max_age
        self.ema_alpha = ema_alpha
        # mac -> deque of (timestamp, rssi)
        self._history: dict[str, deque[tuple[float, int]]] = {}

    def filter(self, mac: str, rssi: int, now: float | None = None) -> tuple[int, int]:
        """Add an RSSI observation and return (smoothed_rssi, sample_count)."""
        if now is None:
            now = time.monotonic()

        if self.mode == RSSI_FILTER_NONE or self.window_size <= 1:
            return rssi, 1

        if mac not in self._history:
            self._history[mac] = deque(maxlen=self.window_size)

        queue = self._history[mac]

        # Prune expired samples
        while queue and (now - queue[0][0]) > self.max_age:
            queue.popleft()

        queue.append((now, rssi))
        sample_count = len(queue)

        if sample_count == 1:
            return rssi, 1

        if self.mode == RSSI_FILTER_MEDIAN:
            values = [val for _, val in queue]
            smoothed = int(round(statistics.median(values)))
            return smoothed, sample_count

        if self.mode == RSSI_FILTER_EMA:
            ema = float(queue[0][1])
            for _, val in list(queue)[1:]:
                ema = self.ema_alpha * float(val) + (1.0 - self.ema_alpha) * ema
            return int(round(ema)), sample_count

        return rssi, sample_count

    def clear(self) -> None:
        """Clear all historical RSSI samples."""
        self._history.clear()


class SignalProcessor:
    """Applies RF calibration, smoothing, distance calculation, and target filtering."""

    def __init__(
        self,
        filter_mode: str = FILTER_MODE_ALL,
        tracked_devices: list[str] | set[str] | None = None,
        max_distance: float = 0.0,
        ref_power: int = DEFAULT_REF_POWER,
        path_loss_exponent: float = DEFAULT_PATH_LOSS_EXPONENT,
        rssi_offset: int = 0,
        smoothing_mode: str = DEFAULT_RSSI_FILTER_MODE,
        smoothing_window: int = DEFAULT_RSSI_FILTER_WINDOW,
    ) -> None:
        """Initialize the signal processor."""
        self.filter_mode = filter_mode
        self.tracked_devices: set[str] = (
            {d.strip().upper() for d in tracked_devices if d.strip()} if tracked_devices else set()
        )
        self.max_distance = max(0.0, max_distance)
        self.ref_power = ref_power
        self.path_loss_exponent = path_loss_exponent
        self.rssi_offset = rssi_offset
        self.smoother = RssiSmoothingFilter(mode=smoothing_mode, window_size=smoothing_window)

    def process(
        self,
        device: DiscoveredDevice,
        resolved_identity: str | None = None,
        now: float | None = None,
    ) -> ProcessedSignal:
        """Process a single discovered device through the signal pipeline."""
        raw_rssi = device.rssi
        # Apply hardware calibration offset and clamp to [-127, 0] dBm
        calibrated_rssi = max(-127, min(0, raw_rssi + self.rssi_offset))

        # Apply multi-sample RSSI smoothing
        smoothed_rssi, samples_count = self.smoother.filter(
            device.mac_address, calibrated_rssi, now=now
        )
        smoothed_rssi = max(-127, min(0, smoothed_rssi))

        # Calculate estimated distance
        dist = calculate_distance(
            smoothed_rssi,
            ref_power=self.ref_power,
            path_loss_exponent=self.path_loss_exponent,
        )

        # 1. Check distance cutoff
        if self.max_distance > 0.0 and dist > self.max_distance:
            return ProcessedSignal(
                filtered_rssi=smoothed_rssi,
                raw_rssi=raw_rssi,
                calibrated_rssi=calibrated_rssi,
                estimated_distance=dist,
                is_allowed=False,
                filter_reason=f"Exceeds max distance ({dist}m > {self.max_distance}m)",
                samples_count=samples_count,
            )

        # 2. Check target whitelist / filter mode
        is_allowed, reason = self._check_target_allowed(device, resolved_identity)
        return ProcessedSignal(
            filtered_rssi=smoothed_rssi,
            raw_rssi=raw_rssi,
            calibrated_rssi=calibrated_rssi,
            estimated_distance=dist,
            is_allowed=is_allowed,
            filter_reason=reason,
            samples_count=samples_count,
        )

    def _check_target_allowed(
        self,
        device: DiscoveredDevice,
        resolved_identity: str | None,
    ) -> tuple[bool, str | None]:
        """Check if device is permitted by active filter mode."""
        if self.filter_mode == FILTER_MODE_ALL:
            return True, None

        upper_mac = device.mac_address.upper()
        local_name = (device.name or resolved_identity or "").strip().upper()

        if self.filter_mode == FILTER_MODE_WHITELIST:
            # Check MAC exact or prefix match, or local name match
            if self._matches_whitelist(upper_mac, local_name):
                return True, None
            return False, "Not in tracked whitelist"

        if self.filter_mode == FILTER_MODE_KNOWN_ONLY:
            # Device has resolved IRK identity
            if resolved_identity:
                return True, None
            # Device has advertised name
            if device.name and device.name.strip():
                return True, None
            # Device matches explicit tracked list
            if self._matches_whitelist(upper_mac, local_name):
                return True, None
            return False, "Unnamed ephemeral address (known_only filter active)"

        return True, None

    def _matches_whitelist(self, upper_mac: str, local_name: str) -> bool:
        """Check if upper MAC or local name matches any tracked device entry."""
        if not self.tracked_devices:
            return False

        for target in self.tracked_devices:
            if upper_mac == target or upper_mac.startswith(target):
                return True
            if local_name and target in local_name:
                return True
        return False
