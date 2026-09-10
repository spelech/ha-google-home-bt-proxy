# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.4.1] - 2026-09-09

### Added
- **UI Speaker Revival (`Revive Speaker` Button & Scan Button Enhancement)**:
  - Added dedicated `button.<speaker>_revive` ("Revive Speaker") entity to instantly reconnect, refresh auth token and IP, clear unsupported/unavailable states, and restart the scan worker from the Home Assistant UI.
  - Enhanced existing `button.<speaker>_trigger_scan` ("Trigger Bluetooth Scan") to automatically revive an unsupported or unavailable speaker upon being pressed.
- **Resilient 404 Recovery & Transient Error Tolerance**:
  - Previously active speakers (`total_advertisements > 0`) are never permanently marked as unsupported on HTTP 404; errors during reboots or socket drops are treated as temporary connectivity glitches with exponential backoff.
  - New speakers require 5 consecutive HTTP 404 failures before the worker pauses, preventing false-positive terminations during speaker bootup.
  - Paused workers wait on UI revival event (`trigger_scan_event`) or periodic 30-minute retry without exiting the background task.

### Fixed
- **Duplicate Zeroconf Instance Deprecation Warning**:
  - Reused Home Assistant's managed Zeroconf instance directly in `resolve_cast_ipv4_map` without instantiating a duplicate `Zeroconf()`, utilizing Home Assistant's warm mDNS cache and silencing the warning.
- **Device Registry `.devices` Mapping Deprecation Warning**:
  - Directly iterated `device_registry.devices` in `_resolve_speaker_area` without calling `.values()`, ensuring forward compatibility with Home Assistant 2027.9.0.

## [1.4.0] - 2026-09-08

### Added
- **Startup Bermuda Auto-Detection (`_get_default_bermuda`)**:
  - Automatically queries `hass.config_entries` for an active `bermuda` configuration entry during integration setup and options initialization.
  - Automatically defaults `bermuda_mode` to `True` when Bermuda is installed, eliminating manual configuration steps.
- **Hardware Keyword Exclusion Filtering**:
  - Implemented `EXCLUDED_HARDWARE_KEYWORDS` in `coordinator.py` to cleanly ignore non-speaker Cast hardware (Android TVs, Nvidia SHIELD, Chromecasts, and audio/video receivers) during device discovery.
- **Graceful Unsupported Scan Endpoint Handling (`SpeakerUnsupportedError`)**:
  - Added dedicated exception handling in `GoogleHomeApiClient` and `_speaker_scan_loop` for Cast devices lacking the BLE scan endpoint, permanently preventing HTTP 404 scan warning spam.
- **mDNS Zeroconf Dual-Stack IPv4 Resolution (`resolve_cast_ipv4_map`)**:
  - Implemented Zeroconf mDNS discovery to automatically map Cast device IDs and friendly names to their IPv4 addresses, avoiding IPv6 link-local connection errors on dual-stack networks.

### Fixed
- **Dummy MAC Address Collision (`00:00:00:00:00:00`)**:
  - Fixed `is_valid_mac` in `models.py` to reject dummy/broadcast MAC addresses (`00:00:00:00:00:00` and `FF:FF:FF:FF:FF:FF`).
  - Updated `_extract_mac` in `api.py` to prioritize `hotspot_bssid` when the primary `mac_address` field contains dummy zeros, preventing entity collisions on Nest Minis.
- **Home Assistant Deprecation Warnings**:
  - Modernized device registry lookups with `async_get_device_by_identifier` and `async_get_device_by_connection` for Home Assistant 2026/2027 compatibility.
  - Eliminated Zeroconf multi-instance deprecation warnings by sharing Home Assistant's managed Zeroconf instance.
- **IPv6 URL Host Formatting**:
  - Wrapped IPv6 addresses in brackets (`[fe80::...]`) to ensure compliance with RFC 3986 and prevent socket connection failures.

## [1.3.0] - 2026-09-07

### Added
- **Automatic Speaker Area Inheritance (`_resolve_speaker_area`)**:
  - Automatically queries the Home Assistant Device Registry to detect and inherit existing Area assignments from official Google Cast or Google Home device entries, MAC connections, or friendly names.
  - Passes `suggested_area` during device creation and retroactively updates the speaker device if previously missing an area.
- **Dynamic Bluetooth Scanner Device Area Synchronization (`_sync_bluetooth_scanner_area`)**:
  - Ensures the underlying Home Assistant core Bluetooth scanner device entry (`CONNECTION_BLUETOOTH`) stays in sync with the speaker's assigned Area.
  - Monitors Area changes in `_speaker_scan_loop` on every cycle and updates entity listeners immediately when a user reassigns a speaker's room in Home Assistant.
- **Hardware MAC Resolution at Integration Startup**:
  - Queries `/setup/eureka_info` for all active speakers during integration initialization, resolving physical Wi-Fi/Bluetooth hardware MACs before scanner registration and peer exclusion set derivation.
- **Bermuda Telemetry Attributes on Status Sensor**:
  - Added `assigned_area` and `bermuda_area_ready` diagnostic attributes to `GoogleHomeBtProxyStatusSensor`.

### Fixed
- **Bermuda BLE Trilateration Scanner Disqualification**:
  - Resolved issue where Bermuda rejected Google Home speakers from room presence contests and distance estimation due to missing Area assignments (`area_id is None`).
  - Fixed missing hardware MAC matching between the proxy and Home Assistant's core device registry.

### Documentation
- **Bermuda Scan Result Caveats & Setup Guide**:
  - Added comprehensive documentation in `README.md` and `docs/bermuda_calibration.md` detailing Google Home local API inquiry scan limitations: lack of raw manufacturer data / iBeacon UUID frames, and active inquiry cadence.
  - Documented mobile device sleep/lock behavior and recommended Home Assistant Companion App BLE Transmitter configuration for 24/7 background tracking.
  - Documented how to enable disabled-by-default `Distance to <Speaker>` entities in Home Assistant.
  - Added step-by-step guidance on tracking rotating MAC addresses via Home Assistant's native Private BLE Device (IRK) integration.

## [1.2.0] - 2026-09-07

### Added
- **Categorized Options Flow Hub Menu**:
  - Replaced the single flat 20+ field form with a clean, high-level Hub Menu (`async_show_menu`) providing dedicated navigation to:
    - ⏱️ **Scanning & Bermuda Mode**: Core mode toggles, peer proxy suppression, and inquiry timing.
    - 🎵 **Media Playback Handling**: Playback mode (throttle, skip ceiling, ignore) and streaming timers.
    - 📡 **Signal Processing & RF**: Standalone signal smoothing, calibration offsets, and distance modeling.
    - 🔒 **Target Filtering & IRK Resolvers**: Filter modes, device whitelists, RSSI thresholds, and Apple/macOS IRK keys.
    - 🔊 **Speaker-Specific Overrides**: Tailored per-speaker overrides with an identical clean categorized structure.
- **Adaptive Bermuda Mode Auto-Hide**:
  - When Bermuda Optimization Mode is active (globally or for a specific speaker), the Signal Processing menu dynamically hides all 8 bypassed RF/calibration inputs (`rssi_offset`, `enable_rssi_smoothing`, `rssi_filter_mode`, `rssi_filter_window`, `enable_distance_estimation`, `max_distance`, `ref_power`, `path_loss_exponent`).
  - Renders a helpful informational notice explaining that Bermuda natively manages smoothing, antenna offsets, and trilateration, preventing user confusion.

## [1.1.0] - 2026-09-07

### Added
- **Bermuda BLE Optimization Mode (`bermuda_mode`)**:
  - Automatically enabled when Bermuda BLE Trilateration is detected in Home Assistant, or manually toggleable via Global Options and per-speaker overrides.
  - Forwards pure raw instantaneous RSSI directly to Home Assistant's Bluetooth manager (bypassing proxy rolling median/EMA smoothing) and resets proxy RSSI calibration offsets to $0\text{ dBm}$.
  - Allows Bermuda's native asymmetric velocity-limiting filter to process true signal peaks and delegates distance calibration directly to Bermuda's scanner offset configuration.
- **Peer Speaker Proxy Suppression (`filter_peer_proxies`)**:
  - Automatically detects and filters out Bluetooth advertisement packets transmitted by peer Google Home / Nest speakers across the local network.
  - Implements Bermuda-compatible $\pm 3$ MAC math offset suppression (`mac_math_offset`) to eliminate cross-proxy loops and phantom beacon tracking.
- **Bermuda Diagnostic Telemetry**:
  - Status sensors now expose diagnostic state attributes: `scanner_mac`, `wifi_mac`, `bermuda_compatible` (boolean), `bermuda_mode` (boolean), and `rssi_mode` (`"raw"` vs `"smoothed"`).
- **Sub-10s Inquiry Scan Timing for Bermuda `AREA_MAX_AD_AGE`**:
  - Updated default idle scan timeout to $4\text{s}$ and idle scan interval to $4\text{s}$ ($8\text{s}$ total inquiry cycle $\le 10.0\text{s}$). Ensures BLE advertisement packets never expire past Bermuda's area presence contest threshold.

## [1.0.6] - 2026-09-07

### Improved
- **Streamlined Setup to Auto-Import and Cookie Extraction**:
  - Removed Google App Password fields and prompts from the initial configuration dialog. Since Google actively blocks automated password-based login (`gpsoauth`) on modern accounts, the setup now focuses strictly on the two working methods:
    1. **1-Click Auto-Import** from existing `ha-google-home` installations.
    2. **Browser Cookie Extraction** via `accounts.google.com/EmbeddedSetup` (`oauth_token` cookie `oauth2_4/...`).
  - Greatly improves user experience by avoiding confusing login failures and eliminating password entry.

## [1.0.5] - 2026-09-07

### Security & Hardening
- **Removed Browser Extension & High-Privilege Permissions**:
  - Removed the browser extension completely, eliminating high-privilege browser permissions (`cookies`, `*://accounts.google.com/*`, `storage`).
- **Removed Unauthenticated HTTP Callback Endpoint**:
  - Removed `GoogleHomeBtProxyAuthCallbackView` and `/api/google_home_bt_proxy/auth_callback`, eliminating an open unauthenticated HTTP endpoint on Home Assistant.
- **Eliminated Plaintext Password Retention**:
  - Passwords and App Passwords are now immediately stripped from `entry.data` once master tokens are obtained, preventing plaintext credentials from being saved to `.storage/core.config_entries`.
- **Sanitized OAuth Error Logging**:
  - Sanitized error logs to prevent dumping upstream response payloads into Home Assistant logs.

## [1.0.4] - 2026-09-07

### Improved
- **Clipboard & Copy-Paste Trimming**:
  - Automatically scrubs zero-width spaces (`\u200b`, `\u200c`, `\u200d`), byte-order marks (`\ufeff`), directional formatting characters (`\u200e`, `\u200f`), and word joiners (`\u2060`) often invisibly copied from web browsers, DevTools, or rich text editors.
  - Automatically detects 16-character Google App Passwords copied with standard 4x4 grouping spaces (`"abcd efgh ijkl mnop"`) and strips spaces to prevent avoidable authentication failures.
  - Trims leading and trailing whitespace across all credentials, usernames, and tokens in both the Home Assistant config/token flows and the standalone `auth_helper` CLI.

## [1.0.3] - 2026-09-07

### Improved
- **Adaptive Auth Error Transition**:
  - Automatically transitions to a dedicated token entry step if password authentication fails, removing the password input and pre-filling the user's email.
  - Keeps the user on the token recovery step without looping back to asking for password credentials.
- **Tolerant Token Sanitization**:
  - Automatically parses and cleans complex cookie formats and DevTools copies (e.g. `oauth_token:"oauth2_4/..."`, `oauth_token=...; path=/`, and surrounding quotes/prefixes) across the config flow, options flow, and CLI helper.

## [1.0.2] - 2026-09-07

### Added
- **HACS & Brand Assets**:
  - Added official brand assets in `custom_components/google_home_bt_proxy/brand/` (`icon.png`, `icon@2x.png`, `logo.png`, `logo@2x.png`) and root `icon.png`/`logo.png` for HACS and Home Assistant 2024+ brand resolution.
- **In-UI Field Descriptors & Translations**:
  - Added dedicated `translations/en.json` directory so Home Assistant properly registers and displays all component UI strings at runtime.
  - Added detailed in-UI helper descriptions (`data_description`) under every single configuration and options field explaining expected formats and values.

## [1.0.1] - 2026-09-07

### Improved
- **Streamlined Authentication Flow**:
  - Simplified the initial configuration dialog to 3 clean fields: Google Account Email, App Password, and Master Token (Optional).
  - Automatically generate `android_id` in the background without user intervention.
  - Automatically detect and exchange `oauth2_4/...` tokens pasted into the Master Token field.
  - Added 1-click automatic credential import when `ha-google-home` is installed.
  - Added immediate actionable troubleshooting guidance for accounts triggering Google browser security checks.
- **Visual Authentication Guide**:
  - Added `docs/authentication_guide.md` with step-by-step instructions and DevTools extraction screenshots.

## [1.0.0] - 2026-09-06

### Added
- **Signal Processing & RSSI Smoothing**:
  - Rolling median and exponential moving average (EMA) filters to reduce RSSI fluctuations.
  - Configurable window sizes and 60-second sample age expiration.
  - Independent toggle (`enable_rssi_smoothing`) to forward raw calibrated RSSI without buffering.
- **Distance Estimation & Boundary Gating**:
  - Real-time distance calculation in meters using a log-distance path loss formula ($d = 10^{\frac{\text{ref\_power} - \text{RSSI}}{10 \times n}}$).
  - Configurable reference power (`ref_power`) and path loss exponent (`path_loss_exponent`).
  - Boundary cutoff threshold (`max_distance`) to drop distant or cross-floor advertisements.
  - Independent toggle (`enable_distance_estimation`) to bypass distance calculations.
- **Target Filtering & Ephemeral Address Suppression**:
  - Three filtering modes: `all`, `known_only` (named or IRK-resolved devices), and `whitelist`.
  - Whitelist support for exact MAC addresses, OUI/MAC prefixes, and name substrings.
- **Multi-Speaker Scan Orchestrator**:
  - Synchronized round-robin inquiry scan serialization to eliminate 2.4GHz Wi-Fi and Bluetooth interference across multi-speaker setups.
  - Configurable `independent` mode for single-speaker or uncoordinated deployments.
- **Diagnostics & Observability**:
  - `sensor.*_bluetooth_advertisements_filtered`: Real-time counter of suppressed advertisements per speaker.
  - Preserved signal processing details (`raw_rssi`, `calibrated_rssi`, `filtered_rssi`, `estimated_distance`, `samples_count`) in advertisement metadata.
- **Documentation & Usability**:
  - Technical guide in `docs/signal_processing.md`.
  - Thorough documentation review for plain, concise English across all guides.

## [0.3.0] - 2026-09-06

### Added
- **Operational Diagnostics & Control Entities**:
  - `sensor.*_bluetooth_proxy_status`: Live scanning lifecycle state (`idle`, `scanning`, `disabled`, `playback_paused`, `playback_throttled`) with packet counter, scan duration, and detected device count attributes.
  - `switch.*_bluetooth_proxy`: Interactive switch entity to enable or disable Bluetooth proxy inquiry scanning per speaker.
  - `button.*_trigger_bluetooth_scan`: Interactive button entity to immediately trigger an on-demand hardware inquiry scan.
- **Bermuda BLE Optimization & RF Calibration**:
  - Hardware-level `rssi_offset` calibration option applied directly to discovered advertisements before injection into Home Assistant's Bluetooth framework.
  - Clamping to `[-127, 0]` dBm range with `raw_rssi` and `rssi_offset` metadata preserved in advertisement details.
  - Comprehensive guide: `docs/bermuda_calibration.md`.
- **Per-Speaker Configuration Granularity**:
  - Hierarchical options flow allowing customization of individual speakers or global defaults.
  - Configurable scan intervals, timeouts, playback modes, throttle intervals, and RF offsets per speaker.
  - Granular overrides persisted in config entry options with automatic worker loop resolution.
- **Hardware Compatibility Matrix & Diagnostic Enhancements**:
  - Comprehensive documentation in `docs/hardware_matrix.md` cataloging empirical behavior across Google Home Minis, Nest Minis, Android TVs / Google TVs, and third-party Cast receivers.
  - Diagnostic CLI `scripts/probe_speaker.py` enhanced with optional tokens, Cast V2 control socket verification (`--check-cast`), and automated hardware classification.

## [0.2.0] - 2026-09-06

### Added
- Standalone media playback awareness (`SpeakerPlaybackDetector`) probing Cast V2 TLS (port 8009) and local Bluetooth status (port 8443) without Home Assistant `cast` or `media_player` dependencies.
- Playback handling modes: `throttle` (relaxed scan cadence and reduced scan timeout), `skip_ceiling` (pause scanning during music with maximum continuous skip ceiling), and `ignore`.
- Fully configurable timings in options flow: idle duration/interval, playing duration/interval, max skip ceiling, and RSSI threshold.

## [0.1.0] - 2026-09-06

### Added
- Native Home Assistant remote Bluetooth scanner integration (`custom_components/google_home_bt_proxy`).
- `GoogleHomeRemoteScanner` subclassing `habluetooth.BaseHaRemoteScanner` for seamless Bermuda BLE presence tracking.
- Google Home HTTPS API client querying port 8443 with `cast-local-authorization-token`.
- Background speaker coordinator supporting zeroconf mDNS discovery and automatic token renewal on HTTP 401.
- Staggered inquiry scan cycle loop with exponential backoff on network disconnects.
- Empirical hardware probe diagnostic CLI script (`scripts/probe_speaker.py`).
- Closed-loop mock speaker simulation harness (`tests/harness/mock_speaker.py`) and 100% test coverage.
- 4-stage GitHub Actions CI quality gate with CodeQL and release integrity verifier.
