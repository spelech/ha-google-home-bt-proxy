# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
