# Hardware Compatibility Matrix

This document outlines hardware support, operating systems, network ports, authentication requirements, Bluetooth capabilities, and playback detection across Google Home, Nest, and Cast devices.

---

## Device Support Table

| Device | Operating System | Setup API (Port 8443) | Cast V2 (Port 8009) | BLE Proxy | Playback Detection | Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Google Home Mini** (1st Gen) | CastOS / ARMv7 | Supported (token required) | Open | Supported | Cast V2 + A2DP | Fully supported |
| **Google Nest Mini** (2nd Gen) | CastOS / ARMv8 | Supported (token required) | Open | Supported | Cast V2 + A2DP | Fully supported |
| **Google Home** (Original) | CastOS / ARMv7 | Supported (token required) | Open | Supported | Cast V2 + A2DP | Fully supported |
| **Google Home Max** | CastOS / ARMv7 | Supported (token required) | Open | Supported | Cast V2 + A2DP | Fully supported |
| **Google Nest Audio** | CastOS / ARMv8 | Supported (token required) | Open | Supported | Cast V2 + A2DP | Fully supported |
| **Google Nest Hub / Hub Max** | Fuchsia / CastOS | Partial | Open | Partial | Cast V2 | Experimental; display radios prioritize Thread/Zigbee |
| **NVIDIA SHIELD Android TV** | Android TV OS | Returns 404 on BT endpoints | Open | Unsupported | Cast V2 | Playback detection only; Bluetooth managed by Android OS |
| **Sony / TCL / Hisense Smart TVs** | Google TV OS | Returns 404 on BT endpoints | Open | Unsupported | Cast V2 | Playback detection only; Bluetooth managed by Android OS |
| **Chromecast with Google TV** | Android TV OS | Returns 404 on BT endpoints | Open | Unsupported | Cast V2 | Playback detection only; Bluetooth managed by Android OS |
| **Chromecast (Gen 1 - 3, Ultra)** | CastOS | No Bluetooth hardware | Open | Unsupported | Cast V2 | Playback detection only |
| **Third-Party Cast Soundbars** | Cast Linux | Returns 400 on scan request | Open | Unsupported | Cast V2 | Playback detection only; firmware omits scan routines |
| **Cast Speaker Groups** | Virtual mDNS | None | Open (dynamic ports) | Unsupported | Cast V2 | Skipped; virtual group endpoint with no radio |

---

## Device Details

### 1. Google Home & Nest Speakers (Home Mini, Nest Mini, Nest Audio, Home Max)

These speakers run minimal embedded Linux (CastOS) and support the local setup endpoints required for Bluetooth scanning:

- **Ports**:
  - `8008`: HTTP setup and DIAL discovery
  - `8009`: Cast V2 control channel (TLS)
  - `8443`: HTTPS setup API (`https://<IP>:8443/setup/...`)
- **Authentication**:
  - Requires the `cast-local-authorization-token` header.
  - The integration requests tokens automatically and caches them locally.
- **Bluetooth Subsystem**:
  - `POST /setup/bluetooth/scan`: Starts an inquiry scan.
  - `GET /setup/bluetooth/scan_results`: Returns discovered devices with MAC, RSSI, and name.
- **Playback Detection**:
  - Checks Cast V2 media state on port 8009 and Bluetooth A2DP audio connections on port 8443.

### 2. Android TV & Google TV (NVIDIA SHIELD, Sony, TCL)

- **Ports**: Ports 8008, 8009, and 8443 are open.
- **Bluetooth Endpoints**: Returning `HTTP 404 Not Found` for `/setup/bluetooth/scan` because Bluetooth is handled by the Android operating system rather than the Cast web service.
- **Integration Behavior**: The integration classifies these as playback-only devices and does not start scanning workers on them.

### 3. Third-Party Cast Devices (Soundbars, AVRs)

- **Ports**: Ports 8008, 8009, and 8443 are open.
- **Bluetooth Endpoints**: Submitting `POST /setup/bluetooth/scan` returns `HTTP 400 Bad Request` because OEM firmware does not implement Google's inquiry scan handler.
- **Integration Behavior**: Automatically flagged as unsupported for scanning and skipped during scanner initialization.

### 4. Cast Speaker Groups

- Virtual speaker groups appear in mDNS with model `"Google Cast Group"`.
- Because these are software groups rather than physical hardware, the integration automatically filters them out.

---

## Testing Hardware with `probe_speaker.py`

You can test any Cast device on your network using the CLI diagnostic probe:

```bash
# Basic probe: checks eureka_info and open endpoints
uv run scripts/probe_speaker.py --host 192.168.1.110

# Scan probe with token: tests active scanning
uv run scripts/probe_speaker.py --host 192.168.1.110 --token "YOUR_LOCAL_TOKEN" --timeout 5 --check-cast
```

### Example Outputs

#### Google Home / Nest Speaker (Supported)
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

---

## Deployment Recommendations

1. **Placement**: Place speakers centrally in rooms and elevated off the floor (such as on shelves or desks).
2. **Scan Timing**: Defaults of 5-second scan duration and 10-second interval provide good balance between update frequency and Wi-Fi performance.
3. **Playback Handling**: Keep playback handling enabled (`throttle` or `skip_ceiling`) so scans pause or slow down during media playback to prevent audio dropouts.
4. **Calibration**: Use `rssi_offset` to calibrate signal levels across different speaker generations (e.g. Nest Mini vs Home Mini).
