# Bermuda BLE Triangulation & RF Calibration Guide

## Overview

[Bermuda BLE Trilateration](https://github.com/agners/homeassistant-bermuda) is a popular Home Assistant integration that determines the room presence and millimeter-level coordinates of Bluetooth devices (smart watches, BLE beacons, fitness trackers, phones) by analyzing the Received Signal Strength Indicator (RSSI) reported by distributed Bluetooth Proxies throughout your home.

When using physical Google Home / Nest speakers and Cast TVs as Bluetooth proxies via `ha-google-home-bt-proxy`, RF calibration is essential to obtain accurate distance calculations and room presence detection.

---

## The RF Discrepancy Problem

The log-distance path loss model used by trilateration algorithms assumes that a given RSSI corresponds predictably to distance:

$$RSSI = -10n \log_{10}(d) + A$$

Where:
- $d$ is the distance in meters.
- $n$ is the path loss exponent (typically $2.0$ to $3.0$ in indoor environments).
- $A$ is the received signal strength at a reference distance of 1 meter ($1\text{m}$ RSSI).

However, different hardware platforms feature radically different antenna configurations:

| Hardware Type | Antenna Design | RF Characteristics | Typical Raw 1m RSSI | Recommended Starting Offset |
| :--- | :--- | :--- | :--- | :--- |
| **Google Home Mini (Gen 1)** | Compact inverted-F PCB trace under fabric cover | Higher internal attenuation, slightly lower receiver sensitivity | -68 dBm | `+4 dBm` to `+6 dBm` |
| **Google Nest Mini (Gen 2)** | Enhanced RF layout with dedicated ground plane | Balanced sensitivity, closer to standard ESP32 proxies | -63 dBm | `0 dBm` to `+2 dBm` |
| **Smart TV / Cast Receiver (Shield / TCL)** | Larger chassis, directional antennas, or metal shielding | Significant variation; rear-mounted antennas suffer wall reflections | -58 dBm to -74 dBm | `-3 dBm` (front-facing) / `+5 dBm` (rear wall) |
| **ESP32 BLE Proxy (Reference)** | PCB / external dipole antenna | Baseline standard reference | -62 dBm | `0 dBm` (Baseline) |

Without calibration offset, a device 2 meters away from a Google Home Mini may report an RSSI of -76 dBm, causing Bermuda to calculate that the device is 4 to 5 meters away in another room!

---

## How `ha-google-home-bt-proxy` Solves This

`ha-google-home-bt-proxy` introduces a dedicated **RSSI Calibration Offset** (`rssi_offset`, configured in dBm, range `-30` to `+30`).

### Calibration Formula
For every detected Bluetooth advertisement:

$$\text{RSSI}_{\text{calibrated}} = \max(-127, \min(0, \text{RSSI}_{\text{raw}} + \text{Offset}))$$

1. **Applied Prior to Bluetooth Manager Injection**: The adjusted signal strength is fed directly into Home Assistant's central Bluetooth stack, ensuring Bermuda, core integrations, and distance filters receive uniformly calibrated signal strengths.
2. **Diagnostic Transparency**: Both the original `raw_rssi` and applied `rssi_offset` are included in the advertisement `details` dictionary for debugging and auditing.
3. **RSSI Threshold Consistency**: If a minimum RSSI threshold is configured (e.g. -90 dBm), the threshold is evaluated against the *calibrated* RSSI, preventing artificially attenuated speakers from prematurely discarding valid packets.

---

## Step-by-Step Calibration Procedure

To achieve optimal presence tracking accuracy:

### 1. Prepare a Reference Beacon
Use a dedicated BLE beacon (e.g. BlueCharm, Feasycom, Tile, or an ESP32 emitting an iBeacon) with known transmit power ($0\text{ dBm}$ Tx Power).

### 2. Measure at Exactly 1 Meter
1. Place the reference beacon exactly **1 meter (3.28 feet)** away from your Google Home speaker or TV, in direct line of sight at the same elevation.
2. Open Home Assistant Developer Tools -> States or check Bermuda's proxy distance diagnostics.
3. Observe the reported raw RSSI over 60 seconds (take the median value).

### 3. Calculate the Required Offset

$$\text{Offset} = \text{Target Reference RSSI} - \text{Measured Raw RSSI}$$

*Example:*
- Your standard ESP32 proxy measures the beacon at 1 meter as **-62 dBm**.
- Your Google Home Mini in the same room measures the beacon at 1 meter as **-68 dBm**.
- $\text{Offset} = -62 - (-68) = \mathbf{+6\text{ dBm}}$.

### 4. Apply the Offset in Home Assistant
1. In Home Assistant, navigate to **Settings -> Devices & Services -> Google Home Bluetooth Proxy**.
2. Click **Configure** on the integration card.
3. Adjust **RSSI Calibration Offset (dBm)** to your calculated value (e.g. `+6`).
4. Click **Submit**. Changes take effect immediately without restarting Home Assistant.

---

## Best Practices for Bermuda Integration

1. **Avoid Corner Placement**: Placing Google Home Minis directly against concrete walls or in metal corners adds multi-path reflection. Keep at least 15 cm (6 inches) of clearance from walls when possible.
2. **Match Scan Cadence to Tracking Needs**: If tracking fast-moving targets (e.g., room-to-room walking), set Idle Scan Interval to 5–10 seconds. For stationary presence (keys, desk beacons), 20–30 seconds is sufficient and conserves speaker resources.
3. **Combine with ESP32 Proxies**: Google Home proxies integrate seamlessly alongside ESPHome Bluetooth Proxies; Bermuda will automatically triangulate across both types of nodes.
