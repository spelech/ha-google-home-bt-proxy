# Bermuda BLE Calibration Guide

This guide explains how to calibrate RSSI offsets when using Google Home and Nest speakers with the [Bermuda BLE Trilateration](https://github.com/agners/homeassistant-bermuda) integration.

---

## Why Calibration Matters

Bermuda estimates device distance from reported RSSI:

$$\text{RSSI} = -10n \log_{10}(d) + A$$

Where:
- $d$ is distance in meters
- $n$ is the environmental path loss exponent
- $A$ is the reference RSSI at 1 meter

Different devices and antenna layouts report different signal levels at the same distance:

| Device | Antenna Layout | Typical 1m RSSI | Suggested Offset |
| :--- | :--- | :--- | :--- |
| **Google Home Mini (Gen 1)** | Inverted-F PCB trace | -68 dBm | `+4` to `+6 dBm` |
| **Google Nest Mini (Gen 2)** | Internal antenna with ground plane | -63 dBm | `0` to `+2 dBm` |
| **ESP32 Proxy (Reference)** | PCB / Dipole antenna | -62 dBm | `0 dBm` (baseline) |

Without calibration, a Google Home Mini may report weaker signals than an ESP32 in the same room, causing Bermuda to overestimate distance.

---

## How RSSI Offset Works

The `rssi_offset` setting adjusts reported RSSI before advertisements are sent to Home Assistant:

$$\text{RSSI}_{\text{calibrated}} = \max(-127, \min(0, \text{RSSI}_{\text{raw}} + \text{rssi\_offset}))$$

- **Applied at Ingestion**: Bermuda and other Bluetooth integrations receive the calibrated value.
- **Included in Metadata**: Both `raw_rssi` and `rssi_offset` remain available in the advertisement details for debugging.

---

## Calibration Steps

### 1. Place a Beacon at 1 Meter
Place a BLE beacon or test device with constant transmit power exactly 1 meter away from the speaker in line-of-sight.

### 2. Check the Reported RSSI
In Home Assistant Developer Tools > States or Bermuda diagnostics, check the average raw RSSI reported by that speaker over 30–60 seconds.

### 3. Calculate Offset
Subtract the measured RSSI from your baseline reference (for example, -62 dBm from an ESP32):

$$\text{Offset} = \text{Baseline RSSI} - \text{Measured RSSI}$$

*Example:*
- Baseline at 1 meter: -62 dBm
- Google Home Mini measured: -68 dBm
- Offset = -62 - (-68) = `+6 dBm`

### 4. Apply the Setting

#### Option A: In Bermuda Mode (Recommended)
When **Bermuda Mode** is enabled (`bermuda_mode: true`), the proxy forwards raw RSSI with 0 dBm offset, delegating all calibration to Bermuda:
1. In Home Assistant, go to **Settings** > **Devices & Services** > **Bermuda BLE Trilateration**.
2. Click **Configure** > **Configure Scanner Offsets**.
3. Enter the calculated offset for your speaker scanner.
4. Click **Submit**.

#### Option B: Standalone Mode (Without Bermuda)
If you are running the proxy without Bermuda:
1. In Home Assistant, go to **Settings** > **Devices & Services** > **Google Home Bluetooth Proxy**.
2. Click **Configure**, select the speaker, and enter the offset in **RSSI Calibration Offset**.
3. Click **Submit**. The change takes effect on the next scan cycle.

---

## Tips & Bermuda Troubleshooting

1. **Assign Speaker to an Area**: Bermuda strictly ignores any scanner that does not have an Area assigned (`area_id is None`). If your speaker is not assigned to a room in Home Assistant, Bermuda will raise `REPAIR_SCANNER_WITHOUT_AREA` and refuse to place devices in that room or use the speaker for distance estimation.
2. **Enable Per-Scanner Distance Entities in HA**: Bermuda disables individual distance sensors (`sensor.<device>_distance_to_<speaker>`) by default. Go to your tracked device in Home Assistant > **Entities** > enable the disabled **Distance to <Speaker>** entity.
3. **Tracking Phones and Smart Watches**: Google Home speakers perform Bluetooth Inquiry scans without decoding raw manufacturer advertisements. Use Home Assistant's native **Private BLE Device** integration with the device's Identity Resolving Key (IRK) instead of iBeacon UUIDs. Unlocking the phone or running the HA Companion App with the BLE Transmitter sensor active will ensure continuous BLE advertising.
4. **Placement**: Keep speakers a few inches away from walls or metal surfaces when possible to reduce signal bounce.
5. **Scan Interval**: Set the idle scan interval to 4–8 seconds for tracking walking movement, or 20–30 seconds for stationary items (keys, badges).
6. **Mixed Deployments**: Google Home proxies can run alongside ESPHome Bluetooth proxies; setting offsets aligns their readings in Bermuda.

