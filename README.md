<p align="center">
  <img src="images/icon.png" alt="Google Home Bluetooth Proxy Logo" width="160">
</p>

<h1 align="center">ha-google-home-bt-proxy</h1>

<p align="center">
  <em>Turn your existing Google Home and Nest speakers into native Home Assistant Bluetooth proxies for Bermuda BLE room tracking without extra hardware.</em>
</p>

<p align="center">
  <a href="https://github.com/spelech/ha-google-home-bt-proxy/actions/workflows/ci.yml"><img src="https://github.com/spelech/ha-google-home-bt-proxy/actions/workflows/ci.yml/badge.svg" alt="CI Quality Gate"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-blue.svg" alt="License: MIT"></a>
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.12+-blue.svg" alt="Python 3.12+"></a>
  <a href="https://www.home-assistant.io/"><img src="https://img.shields.io/badge/Home%20Assistant-2024.11+-41BDF5.svg" alt="Home Assistant"></a>
</p>

---

## 🎯 Features

- **Native Bluetooth Remote Scanner**: Implements `habluetooth.BaseHaRemoteScanner` to inject discovered Bluetooth advertisements directly into Home Assistant's native Bluetooth Manager.
- **Bermuda BLE Ready**: Injects live RSSI signal readings and source hardware MACs so [Bermuda BLE Trilateration](https://github.com/agittins/bermuda) can compute room presence and proximity without dedicated ESP32s.
- **Self-Healing Connection**: Automatically handles Google local authorization token renewal via `glocaltokens` and recovers from temporary Wi-Fi drops with exponential backoff.
- **Staggered Polling**: Scans across multiple speakers are offset to minimize network spikes and maintain local speaker responsiveness.
- **Empirical Diagnostic Probe**: Includes `scripts/probe_speaker.py` for testing and verifying speaker endpoints (`/setup/bluetooth/scan`, `/setup/bluetooth/scan_results`) from the command line.

---

## 🚀 Quickstart

### 1. Installation

#### HACS (Custom Repository)
1. In Home Assistant, open **HACS** > **Integrations**.
2. Click the three dots in the top-right corner > **Custom repositories**.
3. Enter `https://github.com/spelech/ha-google-home-bt-proxy` as the Repository and select **Integration** as the Category.
4. Search for **Google Home Bluetooth Proxy**, click **Download**, and restart Home Assistant.

#### Manual Installation
Clone or download this repository and copy `custom_components/google_home_bt_proxy` into your Home Assistant `config/custom_components/` directory:

```bash
cp -r custom_components/google_home_bt_proxy /path/to/homeassistant/config/custom_components/
```
Restart Home Assistant.

---

### 2. Configuration

1. In the Home Assistant UI, go to **Settings** > **Devices & Services** > **Add Integration**.
2. Search for **Google Home Bluetooth Proxy**.
3. Provide your Google Account credentials:
   - **Recommended**: Provide your Google **Master Token** (`oauth2_rt_...`) and **Android ID**.
   - **Alternative**: Enter your Google account email and an App Password.
4. Once authenticated, the integration discovers all Google Home and Nest speakers on your local network and registers a Bluetooth scanner proxy for each enabled speaker.

#### Configuration Options
Access **Configure** on the integration card to customize:
- **Hardware Scan Duration** (`scan_timeout`): Duration in seconds for each active inquiry scan on the speaker (default: `5s`).
- **Interval Between Scans** (`scan_interval`): Cooldown pause between scans (default: `10s`).
- **Minimum RSSI Threshold** (`rssi_threshold`): Discards weak or fringe signals below this dBm value (default: `-90 dBm`).
- **Speaker Selection**: Disable specific speakers from acting as proxy nodes.

---

## 📍 Bermuda BLE Room Presence Integration

[Bermuda](https://github.com/agittins/bermuda) is a popular Home Assistant integration that tracks BLE devices (iBeacons, smartwatches, smartphones, fitness bands) and calculates which room they are in based on signal strengths reported by Bluetooth proxies.

1. **Verify Proxies in Home Assistant**:
   - Go to **Settings** > **Devices & Services** > **Bluetooth**.
   - You will see each Google Home speaker listed as a remote Bluetooth scanner (e.g. `Living Room Speaker Bluetooth Proxy`).
2. **Assign Speakers to Areas**:
   - Assign each speaker's proxy device to its corresponding physical Area/Room in Home Assistant (e.g. *Living Room*, *Kitchen*, *Office*).
3. **Configure Bermuda**:
   - Install and open the **Bermuda BLE Trilateration** integration.
   - Bermuda will automatically detect the Google Home proxy scanners from the Bluetooth framework.
   - Set each scanner's reference location/area. Bermuda will then provide room-level `device_tracker` and `sensor` entities for all tracked BLE devices.

---

## 🔍 Empirical Speaker Probing Utility

The repository includes a standalone diagnostic tool to test speaker Bluetooth scanning directly:

```bash
uv run scripts/probe_speaker.py --host 192.168.1.50 --token "your-cast-local-authorization-token" --timeout 5
```

### Options:
- `--host`: IP address of your Google Home or Nest speaker.
- `--port`: HTTPS API port (default: `8443`).
- `--token`: Speaker local authorization token (`cast-local-authorization-token`).
- `--timeout`: Hardware scan window in seconds (default: `5`).

The script queries:
- `GET /setup/eureka_info`: Device metadata, firmware, and capabilities.
- `GET /setup/bluetooth/status`: Bluetooth subsystem readiness.
- `POST /setup/bluetooth/scan`: Triggers an active inquiry scan.
- `GET /setup/bluetooth/scan_results`: Dumps detected MAC addresses, RSSI values, and device names.

---

## 🏗️ Architecture

For in-depth architectural details, sequence flows, and subsystem diagrams, see [ARCHITECTURE.md](ARCHITECTURE.md).

---

## 🛠️ Development & Testing

This project uses `uv` for package management, `ruff` for linting and formatting, and `pytest` for testing:

```bash
# Install dependencies into virtual environment
uv sync

# Run format and lint checks
uv run ruff format --check .
uv run ruff check .

# Run pytest suite with >= 80% coverage requirement
uv run pytest --cov=custom_components/google_home_bt_proxy --cov-fail-under=80 -v
```

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
