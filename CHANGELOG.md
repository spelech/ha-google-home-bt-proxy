# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
