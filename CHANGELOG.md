# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
