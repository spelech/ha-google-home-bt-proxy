<p align="center">
  <img src="images/icon.png" alt="Google Home Bluetooth Proxy Logo" width="160">
</p>

<h1 align="center">ha-google-home-bt-proxy</h1>

<p align="center">
  <em>A Home Assistant integration that turns Google Home and Nest speakers into Bluetooth proxies.</em>
</p>

<p align="center">
  <a href="https://github.com/spelech/ha-google-home-bt-proxy/actions/workflows/ci.yml"><img src="https://github.com/spelech/ha-google-home-bt-proxy/actions/workflows/ci.yml/badge.svg" alt="CI Quality Gate"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-blue.svg" alt="License: MIT"></a>
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.12+-blue.svg" alt="Python 3.12+"></a>
  <a href="https://www.home-assistant.io/"><img src="https://img.shields.io/badge/Home%20Assistant-2024.11+-41BDF5.svg" alt="Home Assistant"></a>
</p>

---

## Features

- **Bluetooth Remote Scanner**: Uses Home Assistant's native Bluetooth remote scanner interface (`habluetooth.BaseHaRemoteScanner`) to inject discovered BLE advertisements directly into Home Assistant.
- **Signal Filtering and Smoothing**: Supports rolling median and exponential moving average (EMA) filters to reduce RSSI fluctuations. Can be disabled to forward raw calibrated values.
- **Distance Estimation**: Calculates approximate distance in meters using a log-distance path loss formula. Can be disabled if distance calculations are not needed.
- **Distance Cutoff**: Drops advertisements beyond a configured `max_distance` threshold.
- **Target Filtering**: Provides `all`, `known_only` (named or IRK-resolved devices), and `whitelist` modes to suppress randomized private addresses (RPAs) and filter noise.
- **Scan Orchestration**: Serializes active Bluetooth scans across speakers in round-robin order to minimize 2.4GHz Wi-Fi and Bluetooth interference.
- **Playback Awareness**: Detects active Cast V2 media sessions and Bluetooth audio connections to throttle or pause scans during media playback.
- **Per-Speaker Settings**: Overrides scan intervals, timeouts, playback handling, and calibration offsets per speaker or falls back to global defaults.
- **Entities and Controls**: Provides status and packet counter sensors, an on/off switch to toggle scanning per speaker, and a button to trigger manual scans.
- **Token Handling**: Automatically handles Google local authorization token renewal and retries connection failures with backoff.
- **Diagnostic Tool**: Includes `scripts/probe_speaker.py` to inspect local speaker endpoints and verify device capabilities.

---

## Screenshots

<p align="center">
  <img src="images/options_flow.jpg" alt="Integration Options Flow Dialog" width="700">
  <br>
  <em>Options Flow showing orchestration, distance gating, and signal smoothing settings.</em>
</p>

<p align="center">
  <img src="images/diagnostics.jpg" alt="Device Diagnostics & Controls Card" width="600">
  <br>
  <em>Device card showing operational status, packet counters, proxy toggle switch, and scan trigger button.</em>
</p>

---

## Hardware Compatibility

For technical details on ports and protocols, see [docs/hardware_matrix.md](docs/hardware_matrix.md).

| Device | Operating System | BLE Proxy | Playback Detection | Status |
| :--- | :--- | :--- | :--- | :--- |
| **Google Home Mini** (1st Gen) | CastOS | Supported | Cast V2 + A2DP | Fully supported |
| **Google Nest Mini** (2nd Gen) | CastOS | Supported | Cast V2 + A2DP | Fully supported |
| **Google Home / Home Max / Nest Audio** | CastOS | Supported | Cast V2 + A2DP | Fully supported |
| **Google Nest Hub / Hub Max** | Fuchsia / CastOS | Partial | Cast V2 | Experimental; display radios prioritize Thread/Zigbee |
| **Android TV / Google TV** (Shield, smart TVs) | Android TV OS | Unsupported | Cast V2 | Playback detection only; Bluetooth is managed by Android OS |
| **Third-Party Cast Soundbars** | Cast Linux | Unsupported | Cast V2 | Playback detection only; firmware rejects scan commands |
| **Cast Speaker Groups** | Virtual mDNS | Unsupported | Cast V2 | Skipped; virtual group endpoint with no physical radio |

---

## Installation

### HACS (Recommended)

1. In Home Assistant, open **HACS** > **Integrations**.
2. Open the menu in the top-right corner and select **Custom repositories**.
3. Enter `https://github.com/spelech/ha-google-home-bt-proxy` as the Repository and select **Integration** as the Category.
4. Click **Download**, then restart Home Assistant.

### Manual Installation

Copy `custom_components/google_home_bt_proxy` into your Home Assistant `config/custom_components/` directory:

```bash
cp -r custom_components/google_home_bt_proxy /path/to/homeassistant/config/custom_components/
```

Restart Home Assistant.

---

## Configuration

1. In Home Assistant, navigate to **Settings** > **Devices & Services** > **Add Integration**.
2. Search for **Google Home Bluetooth Proxy**.
3. Authenticate using your preferred method:
   - **Existing Google Home Users (Automatic)**: If you already have the `google_home` integration configured, credentials are automatically detected and imported with 1 click.
   - **App Password (Recommended)**: Enter your Google account email and a 16-character App Password generated at [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords).
   - **Master Token**: Enter your Google account email and Master Token (`aas_et/...` or `oauth2_4/...`). (Android ID is generated automatically in the background.)
4. The integration discovers supported speakers on your local network and sets up Bluetooth scanner proxies for them.

### Configuration Options

Click **Configure** on the integration card to adjust settings globally or for specific speakers:

- **Configure Settings For**: Choose `Global Settings` or a specific speaker to customize.
- **Multi-Speaker Orchestration** (`orchestration_mode`): `round_robin` to serialize scans across speakers, or `independent` (default: `round_robin`).
- **Idle Scan Duration** (`scan_timeout`): Duration in seconds for each active scan (default: `5s`).
- **Idle Scan Interval** (`scan_interval`): Pause between scans in seconds (default: `10s`).
- **Playback Scan Duration / Interval** (`playing_scan_timeout`, `playing_scan_interval`): Scan timing while media is playing.
- **Playback Handling Mode** (`playback_mode`): `throttle` (slower scans during playback), `skip_ceiling` (pause until max duration), or `ignore` (default: `throttle`).
- **Minimum RSSI Threshold** (`rssi_threshold`): Minimum signal level in dBm to ingest (default: `-90 dBm`).
- **RSSI Calibration Offset** (`rssi_offset`): Hardware calibration adjustment in dBm applied to incoming signals (default: `0 dBm`).
- **Target Filter Mode** (`filter_mode`): `all`, `known_only` (named or IRK-resolved devices), or `whitelist` (default: `all`).
- **Tracked Devices** (`tracked_devices`): Comma-separated list of MAC addresses, prefixes (e.g. `AA:BB:CC`), or name substrings.
- **Enable RSSI Smoothing** (`enable_rssi_smoothing`): Enables rolling smoothing filter (default: `true`).
- **RSSI Smoothing Algorithm** (`rssi_filter_mode`): `none`, `median`, or `ema` (default: `median`).
- **Smoothing Window Size** (`rssi_filter_window`): Number of samples kept for smoothing (default: `3`).
- **Enable Distance Estimation** (`enable_distance_estimation`): Enables distance calculation and distance gating (default: `true`).
- **Maximum Distance Cutoff** (`max_distance`): Drops packets estimated beyond this distance in meters (`0.0` disables cutoff, default: `0.0m`).
- **Reference RSSI at 1 Meter** (`ref_power`): Expected RSSI at 1 meter in dBm (default: `-59 dBm`).
- **Path Loss Exponent** (`path_loss_exponent`): RF attenuation factor $n$ (indoor default: `2.5`).
- **Known IRKs** (`known_irks`): Resolves private addresses for iOS and macOS devices (format: `name:hex_key`, one per line).

---

## Bermuda Integration

[Bermuda](https://github.com/agittins/bermuda) is a Home Assistant integration that tracks BLE devices (beacons, phones, wearables) and estimates room presence using Bluetooth proxy RSSI data.

1. **Verify Proxies**: In **Settings** > **Devices & Services** > **Bluetooth**, verify that your speakers appear as remote Bluetooth scanners.
2. **Assign Areas**: Assign each speaker device to its physical room in Home Assistant (e.g., Living Room, Kitchen).
3. **Configure Bermuda**: In Bermuda settings, set the reference location for each scanner. Bermuda will use the proxy data for room presence tracking.
4. **Calibrate Offsets**: If you use multiple speaker generations (such as Home Mini Gen 1 and Nest Mini Gen 2), set `rssi_offset` per speaker to align signal levels. See [docs/bermuda_calibration.md](docs/bermuda_calibration.md) for calibration steps.

---

## Diagnostic Probe Script

The repository includes a script to test speaker endpoints and verify compatibility:

```bash
# Basic probe: checks eureka_info and open endpoints
uv run scripts/probe_speaker.py --host 192.168.1.110

# Scan probe: runs an inquiry scan with local auth token
uv run scripts/probe_speaker.py --host 192.168.1.110 --token "your-token" --timeout 5 --check-cast
```

### Options
- `--host`: IP address of the speaker or Cast device.
- `--port`: HTTPS API port (default: `8443`).
- `--token`: Local authorization token.
- `--timeout`: Scan duration in seconds (default: `5`).
- `--check-cast`: Probes the Cast V2 TLS socket on port `8009`.

The script tests:
- `GET /setup/eureka_info`: Firmware version and capabilities.
- `GET /setup/bluetooth/status`: Bluetooth state.
- `POST /setup/bluetooth/scan`: Triggers an active inquiry scan.
- `GET /setup/bluetooth/scan_results`: Displays detected devices and RSSI values.
- Port `8009`: Checks Cast V2 media controller connectivity.

---

## Development & Testing

This project uses `uv`, `ruff`, and `pytest`:

```bash
# Install dependencies
uv sync

# Format and lint checks
uv run ruff format --check .
uv run ruff check .

# Run tests with coverage
uv run pytest --cov=custom_components/google_home_bt_proxy --cov-fail-under=80 -v
```

---

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.
