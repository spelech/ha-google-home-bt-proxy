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
CONF_PLAYBACK_MODE: Final = "playback_mode"
CONF_PLAYING_SCAN_TIMEOUT: Final = "playing_scan_timeout"
CONF_PLAYING_SCAN_INTERVAL: Final = "playing_scan_interval"
CONF_MAX_PLAYING_SKIP_DURATION: Final = "max_playing_skip_duration"
CONF_RSSI_THRESHOLD: Final = "rssi_threshold"
CONF_RSSI_OFFSET: Final = "rssi_offset"
CONF_DISABLED_SPEAKERS: Final = "disabled_speakers"
CONF_KNOWN_IRKS: Final = "known_irks"

# Playback modes
MODE_THROTTLE: Final = "throttle"
MODE_SKIP_CEILING: Final = "skip_ceiling"
MODE_IGNORE: Final = "ignore"

# Defaults
DEFAULT_SCAN_TIMEOUT: Final = 5  # seconds for active scan
DEFAULT_SCAN_INTERVAL: Final = 10  # seconds between scans
DEFAULT_PLAYBACK_MODE: Final = MODE_THROTTLE
DEFAULT_PLAYING_SCAN_TIMEOUT: Final = 2  # seconds for active scan during playback
DEFAULT_PLAYING_SCAN_INTERVAL: Final = 30  # seconds between scans during playback
DEFAULT_MAX_PLAYING_SKIP_DURATION: Final = 120  # seconds maximum continuous skip before forced scan
DEFAULT_RSSI_THRESHOLD: Final = -90  # dBm
DEFAULT_RSSI_OFFSET: Final = 0  # dBm calibration offset


# API Constants
PORT_HTTPS: Final = 8443
ENDPOINT_EUREKA_INFO: Final = "setup/eureka_info"
ENDPOINT_BLUETOOTH_STATUS: Final = "setup/bluetooth/status"
ENDPOINT_BLUETOOTH_SCAN: Final = "setup/bluetooth/scan"
ENDPOINT_BLUETOOTH_SCAN_RESULTS: Final = "setup/bluetooth/scan_results"

HEADER_LOCAL_AUTH: Final = "cast-local-authorization-token"
HEADER_CONTENT_TYPE: Final = "content-type"
