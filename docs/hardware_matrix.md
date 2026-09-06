# Google Cast & Google Home Hardware Compatibility Matrix

This document details hardware architecture, operating systems, network ports, authentication mechanisms, Bluetooth capabilities, and media playback detection behaviors across Google Cast, Google Home, Nest, and third-party streaming devices.

All data in this document has been empirically validated against real-world hardware running live in local test environments.

---

## 📊 Hardware Support Overview

| Hardware Model | Form Factor | OS & Architecture | Setup API (Port 8443) | Cast V2 (Port 8009) | Remote BLE Proxy | Playback Detection | Status & Recommendations |
| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :--- |
| **Google Home Mini** (1st Gen) | Smart Speaker | CastOS / ARMv7 (Marvell 88DE3006) | ✅ Full (Token req.) | ✅ Active | ✅ Full Support | Cast V2 + A2DP (Port 8443) | **Recommended**: Excellent, low-cost distributed proxy node |
| **Google Nest Mini** (2nd Gen) | Smart Speaker | CastOS / ARMv8 (Synaptics AS370) | ✅ Full (Token req.) | ✅ Active | ✅ Full Support | Cast V2 + A2DP (Port 8443) | **Recommended**: Highly sensitive RF front-end |
| **Google Home** (Original / "Air Freshener") | Smart Speaker | CastOS / ARMv7 (Marvell 88DE3006) | ✅ Full (Token req.) | ✅ Active | ✅ Full Support | Cast V2 + A2DP (Port 8443) | **Fully Supported**: Identical API & stack to Home Mini |
| **Google Home Max** | Large Speaker | CastOS / ARMv7 | ✅ Full (Token req.) | ✅ Active | ✅ Full Support | Cast V2 + A2DP (Port 8443) | **Fully Supported**: High-gain antenna array |
| **Google Nest Audio** | Smart Speaker | CastOS / ARMv8 (Amlogic A113X) | ✅ Full (Token req.) | ✅ Active | ✅ Full Support | Cast V2 + A2DP (Port 8443) | **Recommended**: Modern SoC, fast inquiry processing |
| **Google Nest Hub / Hub Max** | Smart Display | Fuchsia OS / ARMv8 | ⚠️ Partial | ✅ Active | ⚠️ Experimental | Cast V2 (Port 8009) | **Notice**: Display radios prioritize Zigbee/Thread time-slicing |
| **NVIDIA SHIELD Android TV** | Set-Top Box | Android TV OS / ARMv8 (Tegra X1+) | ❌ Returns 404 on BT | ✅ Active | ❌ Ineligible | Cast V2 (Port 8009) | **Playback-Only**: Bluetooth managed by Android OS subsystem |
| **Smart TV Pro / Sony / TCL** | Google TV | Google TV OS / ARMv8 (MediaTek/RTK) | ❌ Returns 404 on BT | ✅ Active | ❌ Ineligible | Cast V2 (Port 8009) | **Playback-Only**: Bluetooth managed by Android OS subsystem |
| **Chromecast with Google TV** | Streaming Dongle | Android TV OS / ARMv8 (Amlogic S905X3) | ❌ Returns 404 on BT | ✅ Active | ❌ Ineligible | Cast V2 (Port 8009) | **Playback-Only**: Bluetooth managed by Android OS subsystem |
| **Chromecast (Gen 1 - 3, Ultra)** | Streaming Dongle | CastOS / ARMv7 | ❌ No BLE Radio | ✅ Active | ❌ Ineligible | Cast V2 (Port 8009) | **Playback-Only**: Lacks hardware Bluetooth adapter |
| **Third-Party Cast Soundbars** (e.g. Samsung Q700B) | Audio Soundbar | OEM Cast Embedded Linux | ❌ Rejects scan (400) | ✅ Active | ❌ Ineligible | Cast V2 (Port 8009) | **Playback-Only**: OEM firmware omits Google BLE scan daemon |
| **Google Cast Audio Groups** | Virtual Multi-Room | Software mDNS / Dynamic Ports | ❌ None | ✅ Active (High Ports) | ❌ Ineligible | Cast V2 Group State | **Filtered Automatically**: Virtual endpoint, no physical radio |

---

## 🔍 Detailed Empirical Analysis

### 1. Google Home Mini (1st Gen, H0A) & Google Nest Mini (2nd Gen, H2C)

Google Home Minis and Google Nest Minis represent the ideal hardware target for `ha-google-home-bt-proxy`.

- **Operating System**: Minimal embedded Linux (CastOS).
- **Network Stack**:
  - `Port 8008`: HTTP setup and DIAL discovery.
  - `Port 8009`: Cast V2 protocol over TLS (mandatory Google Cast control channel).
  - `Port 8443`: Local Google Home HTTPS setup API (`https://<IP>:8443/setup/...`).
- **Authentication Model**:
  - The local setup API requires a secure per-device session header: `cast-local-authorization-token: <token>`.
  - Unauthenticated requests to `/setup/bluetooth/*` immediately fail with `HTTP 401 Unauthorized`.
  - Tokens are negotiated automatically from Google Cloud via the integration's master token exchange and cached locally.
- **Bluetooth Subsystem**:
  - BlueZ / vendor-adapted stack with active inquiry scanning exposed via `/setup/bluetooth/scan`.
  - Inquiry scans populate the internal table read via `/setup/bluetooth/scan_results`.
  - Empirical testing verifies full detection of iBeacon, BLE sensor advertisements, smartwatches, and tracker tags.
- **Media Playback Detection**:
  - Dual-layer detection: queries Cast V2 receiver/media status on port 8009 and Bluetooth A2DP sink status on port 8443 (`connected_devices`).

---

### 2. Android TV & Google TV Devices (NVIDIA SHIELD, Sony, TCL, Hisense)

Many home environments feature Android TV or Google TV devices alongside smart speakers.

- **Port Inspection**:
  - `Port 8008`: Open.
  - `Port 8009`: Open (standard Cast V2 receiver).
  - `Port 8443`: Open (`/setup/eureka_info` responds with cast build revision e.g. `3.72.446070`).
- **Why Bluetooth Scanning Is Ineligible**:
  - Probing `/setup/bluetooth/status` or `/setup/bluetooth/scan` on Android TV returns **`HTTP 404 Not Found`**.
  - On Android TV, the Cast receiver is implemented as an Android application (`com.google.android.apps.mediashell`). The underlying Bluetooth hardware is controlled by Android OS's native Bluetooth stack (`com.android.bluetooth`) and exposed via Android Framework APIs, rather than the CastOS setup web daemon.
- **Integration Behavior**:
  - `ha-google-home-bt-proxy` detects that Android TV devices lack the `/setup/bluetooth/*` endpoints during device classification and automatically prevents worker allocation for them.
  - They can still be used for standalone Cast V2 playback monitoring if needed.

---

### 3. Third-Party Cast Receivers (Soundbars, AVRs, Smart Displays)

Third-party devices licensed with "Chromecast built-in" (such as Samsung Soundbars, JBL Link speakers, Denon/Marantz HEOS, Pioneer AVRs) run OEM-modified Cast receiver implementations.

- **Port Inspection**:
  - `Port 8008`, `Port 8009`, and `Port 8443` are open.
  - `/setup/eureka_info` returns valid firmware metadata.
  - `/setup/bluetooth/status` may return `200 OK` unauthenticated, indicating idle audio state.
- **Why Bluetooth Scanning Fails**:
  - Submitting `POST /setup/bluetooth/scan` returns **`HTTP 400 Bad Request`**.
  - The OEM firmware does not implement the active BLE inquiry scanning routines present in first-party Google Home firmware.
- **Integration Behavior**:
  - The integration flags OEM receivers as unsupported for BLE scanning and gracefully bypasses them.

---

### 4. Cast Audio Groups (Virtual Multi-Room Endpoints)

When speakers are combined into speaker groups in the Google Home app (e.g. *Whole Home*, *Main Floor*):
- Cast groups advertise on the local network via mDNS (`_googlecast._tcp.local.`) on dynamic high ports (typically in the `32000-33000` range).
- The `md` (model) field in the mDNS TXT record is explicitly set to `"Google Cast Group"`.
- Because these are virtual software abstractions rather than physical hardware with Bluetooth radios, `ha-google-home-bt-proxy` filters out any device matching the `Google Cast Group` model signature during initial speaker classification.

---

## 🛠️ Testing Your Hardware with `probe_speaker.py`

You can test any device on your local network using the included command-line diagnostic tool:

```bash
# Basic probe (checks eureka_info and open endpoints)
uv run scripts/probe_speaker.py --host 192.168.1.110

# Full hardware inquiry scan with local authorization token
uv run scripts/probe_speaker.py --host 192.168.1.110 --token "YOUR_LOCAL_TOKEN" --timeout 5 --check-cast
```

### Interpreting Probe Output

The probe script evaluates endpoint status codes and outputs a definitive classification:

#### Google Home / Nest Speaker (Fully Supported)
```json
{
  "eureka": { "name": "Office Speaker", "build_version": "3.78.540761" },
  "status": { "audio_mode": 1, "connected_devices": [], "scanning_enabled": false },
  "scan": { "status": 200, "message": "Scan started successfully" },
  "results": [
    { "mac_address": "E4:5F:01:23:45:67", "rssi": -68, "name": "Tile Tracker" }
  ],
  "cast_v2": { "open": true, "port": 8009 },
  "classification": "Google Home / Nest Speaker: Fully compatible hardware for BLE proxy scanning."
}
```

#### Android TV / Google TV (Playback Only)
```json
{
  "eureka": { "name": "SHIELD Android TV", "cast_build_revision": "3.72.446070" },
  "status": { "status": 404 },
  "scan": { "status": 404 },
  "results": { "status": 404 },
  "cast_v2": { "open": true, "port": 8009 },
  "classification": "Android TV / Google TV: Cast V2 supported, local BLE scanning endpoint not implemented (HTTP 404)."
}
```

#### Third-Party Soundbar (Playback Only)
```json
{
  "eureka": { "name": "Living Room Soundbar", "cast_build_revision": "1.52.272222" },
  "status": { "audio_mode": 1, "connected_devices": [] },
  "scan": { "status": 400 },
  "results": [],
  "cast_v2": { "open": true, "port": 8009 },
  "classification": "Third-Party Cast Device: Cast V2 supported, active BLE scanning rejected (HTTP 400)."
}
```

---

## 🎯 Best Practices for Deployment

1. **Physical Placement**:
   - Place Google Home Minis and Nest Minis centrally in each room, elevated from the floor (e.g. on shelves or tables) to minimize signal attenuation.
2. **Scan Windows & Intervals**:
   - Default: `scan_timeout: 5s`, `scan_interval: 10s`.
   - For high-density tracker environments (Bermuda room-level triangulation), 5s scan duration with 10s interval provides the optimal balance of fresh advertisement updates and Wi-Fi stability.
3. **Playback Mode Handling**:
   - Keep `playback_mode` set to `"pause"` (default) to ensure that background BLE inquiry scans are paused while listening to music or podcasts, eliminating audio stuttering.
4. **RF Calibration**:
   - Because Nest Minis (Gen 2) have higher RF front-end sensitivity than Home Minis (Gen 1), apply an RSSI calibration offset (e.g. `-2 dBm` to `-4 dBm`) via per-speaker options to align signal readings across mixed generations.
