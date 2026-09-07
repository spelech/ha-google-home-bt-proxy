"""Remote Bluetooth scanner for Google Home speakers."""

from __future__ import annotations

import logging
import time

from habluetooth import BaseHaRemoteScanner

from .filter import SignalProcessor
from .irk import IrkResolver
from .models import DiscoveredDevice

_LOGGER = logging.getLogger(__name__)


class GoogleHomeRemoteScanner(BaseHaRemoteScanner):
    """Bridges Google Home Bluetooth scan results into Home Assistant Bluetooth Manager."""

    def __init__(
        self,
        scanner_id: str,
        name: str,
        connectable: bool = False,
        irk_resolver: IrkResolver | None = None,
        rssi_offset: int = 0,
        signal_processor: SignalProcessor | None = None,
    ) -> None:
        """Initialize the remote scanner."""
        super().__init__(
            source=scanner_id,
            adapter=scanner_id,
            connector=None,
            connectable=connectable,
        )
        self.name = name
        self._irk_resolver = irk_resolver
        self._rssi_offset = rssi_offset
        self._signal_processor = signal_processor or SignalProcessor(rssi_offset=rssi_offset)
        _LOGGER.debug(
            "Initialized GoogleHomeRemoteScanner [%s] %s (offset: %d dBm)",
            scanner_id,
            name,
            rssi_offset,
        )

    @property
    def signal_processor(self) -> SignalProcessor:
        """Return the scanner's signal processor."""
        return self._signal_processor

    @property
    def discovered_device_timestamps(self) -> dict[str, float]:
        """Return discovered device timestamps with both upper and lower case keys.

        Ensures full Bermuda and Home Assistant compatibility.
        """
        try:
            base = super().discovered_device_timestamps
        except AttributeError:
            base = self._build_discovered_device_timestamps()
        result = dict(base)
        for k, v in base.items():
            result[k.upper()] = v
            result[k.lower()] = v
        return result

    @property
    def _discovered_device_timestamps(self) -> dict[str, float]:
        """Deprecated property in HA >= 2025.4, kept for Bermuda and backward compatibility."""
        return self.discovered_device_timestamps

    def process_scan_results(
        self,
        devices: list[DiscoveredDevice],
        min_rssi: int = -90,
    ) -> int:
        """Inject discovered devices into Home Assistant's Bluetooth Manager."""
        injected_count = 0
        now = time.monotonic()

        for device in devices:
            resolved_identity: str | None = None
            device_mac = device.mac_address
            if self._irk_resolver and device.is_rpa:
                resolved_identity = self._irk_resolver.resolve(device_mac)

            signal = self._signal_processor.process(
                device, resolved_identity=resolved_identity, now=now
            )

            if not signal.is_allowed:
                _LOGGER.debug(
                    "Skipping device %s on %s: Filtered (%s)",
                    device_mac,
                    self.name,
                    signal.filter_reason,
                )
                continue

            if signal.filtered_rssi < min_rssi:
                _LOGGER.debug(
                    "Skipping device %s on %s: Filtered RSSI %d below threshold %d "
                    "(raw: %d, calibrated: %d, offset: %d)",
                    device_mac,
                    self.name,
                    signal.filtered_rssi,
                    min_rssi,
                    device.rssi,
                    signal.calibrated_rssi,
                    self._rssi_offset,
                )
                continue

            # Preserve raw address so HA Core & Bermuda resolution takes precedence.
            # Use advertised name if available; fallback to resolved identity name if matched.
            local_name = device.name or resolved_identity

            self._async_on_advertisement(
                address=device_mac,
                rssi=signal.filtered_rssi,
                local_name=local_name,
                service_uuids=device.service_uuids,
                service_data={},
                manufacturer_data={},
                tx_power=None,
                details={
                    "source": self.source,
                    "scanner_id": self.source,
                    "raw_rssi": device.rssi,
                    "calibrated_rssi": signal.calibrated_rssi,
                    "filtered_rssi": signal.filtered_rssi,
                    "estimated_distance": signal.estimated_distance,
                    "samples_count": signal.samples_count,
                    "rssi_offset": self._rssi_offset,
                    "device_type": device.device_type,
                    "device_class": device.device_class,
                    "device_class_name": device.device_class_name,
                    "expected_profiles": device.expected_profiles,
                    "is_rpa": device.is_rpa,
                    "resolved_identity": resolved_identity,
                },
                advertisement_monotonic_time=now,
            )
            injected_count += 1

        _LOGGER.debug(
            "Injected %d/%d advertisements from scanner %s",
            injected_count,
            len(devices),
            self.name,
        )
        return injected_count
