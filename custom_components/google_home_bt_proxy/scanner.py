"""Remote Bluetooth scanner for Google Home speakers."""

from __future__ import annotations

import logging
import time

from habluetooth import BaseHaRemoteScanner

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
        _LOGGER.debug(
            "Initialized GoogleHomeRemoteScanner [%s] %s (offset: %d dBm)",
            scanner_id,
            name,
            rssi_offset,
        )

    def process_scan_results(
        self,
        devices: list[DiscoveredDevice],
        min_rssi: int = -90,
    ) -> int:
        """Inject discovered devices into Home Assistant's Bluetooth Manager."""
        injected_count = 0
        now = time.monotonic()

        for device in devices:
            calibrated_rssi = max(-127, min(0, device.rssi + self._rssi_offset))
            if calibrated_rssi < min_rssi:
                _LOGGER.debug(
                    "Skipping device %s on %s: Calibrated RSSI %d below threshold %d "
                    "(raw: %d, offset: %d)",
                    device.mac_address,
                    self.name,
                    calibrated_rssi,
                    min_rssi,
                    device.rssi,
                    self._rssi_offset,
                )
                continue

            resolved_identity: str | None = None
            if self._irk_resolver and device.is_rpa:
                resolved_identity = self._irk_resolver.resolve(device.mac_address)

            # Preserve raw address so HA Core & Bermuda resolution takes precedence.
            # Use advertised name if available; fallback to resolved identity name if matched.
            local_name = device.name or resolved_identity

            self._async_on_advertisement(
                address=device.mac_address,
                rssi=calibrated_rssi,
                local_name=local_name,
                service_uuids=device.service_uuids,
                service_data={},
                manufacturer_data={},
                tx_power=None,
                details={
                    "source": self.source,
                    "scanner_id": self.source,
                    "raw_rssi": device.rssi,
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
