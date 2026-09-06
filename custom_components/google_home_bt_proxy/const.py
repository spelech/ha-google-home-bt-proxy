"""Constants for the Google Home Bluetooth Proxy integration."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "google_home_bt_proxy"
NAME: Final = "Google Home Bluetooth Proxy"

# Configuration keys
CONF_USERNAME: Final = "username"
CONF_PASSWORD: Final = "password"
CONF_MASTER_TOKEN: Final = "master_token"
CONF_OAUTH_TOKEN: Final = "oauth_token"
CONF_ANDROID_ID: Final = "android_id"

# Options keys
CONF_SCAN_TIMEOUT: Final = "scan_timeout"
CONF_SCAN_INTERVAL: Final = "scan_interval"
CONF_RSSI_THRESHOLD: Final = "rssi_threshold"
CONF_DISABLED_SPEAKERS: Final = "disabled_speakers"
CONF_KNOWN_IRKS: Final = "known_irks"

# Defaults
DEFAULT_SCAN_TIMEOUT: Final = 5  # seconds for active scan
DEFAULT_SCAN_INTERVAL: Final = 10  # seconds between scans
DEFAULT_RSSI_THRESHOLD: Final = -90  # dBm

# API Constants
PORT_HTTPS: Final = 8443
ENDPOINT_EUREKA_INFO: Final = "setup/eureka_info"
ENDPOINT_BLUETOOTH_STATUS: Final = "setup/bluetooth/status"
ENDPOINT_BLUETOOTH_SCAN: Final = "setup/bluetooth/scan"
ENDPOINT_BLUETOOTH_SCAN_RESULTS: Final = "setup/bluetooth/scan_results"

HEADER_LOCAL_AUTH: Final = "cast-local-authorization-token"
HEADER_CONTENT_TYPE: Final = "content-type"
