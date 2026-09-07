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
CONF_SPEAKER_OVERRIDES: Final = "speaker_overrides"
CONF_SELECTED_SPEAKER: Final = "selected_speaker"
CONF_CUSTOM_SETTINGS: Final = "custom_settings"
GLOBAL_SETTINGS: Final = "global"

# Filter & Signal Processing Keys
CONF_ENABLE_RSSI_SMOOTHING: Final = "enable_rssi_smoothing"
CONF_ENABLE_DISTANCE_ESTIMATION: Final = "enable_distance_estimation"
CONF_FILTER_MODE: Final = "filter_mode"
CONF_TRACKED_DEVICES: Final = "tracked_devices"
CONF_RSSI_FILTER_MODE: Final = "rssi_filter_mode"
CONF_RSSI_FILTER_WINDOW: Final = "rssi_filter_window"
CONF_MAX_DISTANCE: Final = "max_distance"
CONF_REF_POWER: Final = "ref_power"
CONF_PATH_LOSS_EXPONENT: Final = "path_loss_exponent"
CONF_ORCHESTRATION_MODE: Final = "orchestration_mode"

# Filter Modes
FILTER_MODE_ALL: Final = "all"
FILTER_MODE_KNOWN_ONLY: Final = "known_only"
FILTER_MODE_WHITELIST: Final = "whitelist"

# RSSI Filter Algorithms
RSSI_FILTER_NONE: Final = "none"
RSSI_FILTER_MEDIAN: Final = "median"
RSSI_FILTER_EMA: Final = "ema"

# Orchestration Modes
ORCHESTRATION_INDEPENDENT: Final = "independent"
ORCHESTRATION_ROUND_ROBIN: Final = "round_robin"

# Playback modes
MODE_THROTTLE: Final = "throttle"
MODE_SKIP_CEILING: Final = "skip_ceiling"
MODE_IGNORE: Final = "ignore"

CONF_BERMUDA_MODE: Final = "bermuda_mode"
CONF_FILTER_PEER_PROXIES: Final = "filter_peer_proxies"

# Defaults
DEFAULT_SCAN_TIMEOUT: Final = 4  # seconds for active scan
DEFAULT_SCAN_INTERVAL: Final = 4  # seconds between scans (cycle <= 10s for Bermuda)
DEFAULT_PLAYBACK_MODE: Final = MODE_THROTTLE
DEFAULT_PLAYING_SCAN_TIMEOUT: Final = 2  # seconds for active scan during playback
DEFAULT_PLAYING_SCAN_INTERVAL: Final = 30  # seconds between scans during playback
DEFAULT_MAX_PLAYING_SKIP_DURATION: Final = 120  # seconds maximum continuous skip before forced scan
DEFAULT_RSSI_THRESHOLD: Final = -90  # dBm
DEFAULT_RSSI_OFFSET: Final = 0  # dBm calibration offset
DEFAULT_ENABLE_RSSI_SMOOTHING: Final = True
DEFAULT_ENABLE_DISTANCE_ESTIMATION: Final = True
DEFAULT_FILTER_MODE: Final = FILTER_MODE_ALL
DEFAULT_RSSI_FILTER_MODE: Final = RSSI_FILTER_MEDIAN
DEFAULT_RSSI_FILTER_WINDOW: Final = 3
DEFAULT_MAX_DISTANCE: Final = 0.0  # 0.0 means disabled
DEFAULT_REF_POWER: Final = -59  # dBm @ 1m
DEFAULT_PATH_LOSS_EXPONENT: Final = 2.5
DEFAULT_ORCHESTRATION_MODE: Final = ORCHESTRATION_ROUND_ROBIN
DEFAULT_BERMUDA_MODE: Final = False
DEFAULT_FILTER_PEER_PROXIES: Final = True

BERMUDA_NOTICE: Final = (
    "Bermuda Optimization Mode is active. Signal smoothing, hardware RSSI offsets, "
    "and distance modeling are managed natively by Bermuda to preserve peak velocity "
    "tracking. To configure antenna offsets, use Bermuda's Configure Scanner Offsets menu."
)
STANDALONE_NOTICE: Final = (
    "Configure signal filtering, smoothing, and distance estimation parameters "
    "for standalone deployments."
)


# API Constants
PORT_HTTPS: Final = 8443
ENDPOINT_EUREKA_INFO: Final = "setup/eureka_info"
ENDPOINT_BLUETOOTH_STATUS: Final = "setup/bluetooth/status"
ENDPOINT_BLUETOOTH_SCAN: Final = "setup/bluetooth/scan"
ENDPOINT_BLUETOOTH_SCAN_RESULTS: Final = "setup/bluetooth/scan_results"

HEADER_LOCAL_AUTH: Final = "cast-local-authorization-token"
HEADER_CONTENT_TYPE: Final = "content-type"
