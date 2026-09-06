# Signal Processing, Distance Estimation & Scan Orchestration

Google Home Bluetooth Proxy includes an advanced RF signal processing engine and multi-speaker scan orchestrator designed to eliminate multipath flutter, estimate physical distance, suppress ephemeral MAC noise, and prevent 2.4GHz coexistence contention.

---

## 1. Architecture Overview

In residential environments, Bluetooth Low Energy (BLE) signals suffer from severe multipath reflections, absorption by furniture and walls, and interference from 2.4GHz Wi-Fi networks. Furthermore, modern smartphones and wearables continuously rotate Randomized Private Addresses (RPAs), which can flood the Home Assistant event bus with hundreds of transient, unrecognizable devices.

Google Home Bluetooth Proxy solves these issues through a multi-stage pipeline:

```
[Hardware Inquiry (Eureka /setup/bluetooth/scan)]
                     │
                     ▼
          [Scan Orchestrator] ◄── Fair round-robin slot serialization
                     │
                     ▼
          [RF Calibration Offset] ◄── Hardware-specific dBm compensation
                     │
                     ▼
        [RSSI Smoothing Filter] ◄── Rolling median / Exponential Moving Average
                     │
                     ▼
      [Log-Distance Path Loss] ◄── Real-time distance estimation in meters
                     │
                     ▼
      [Floor / Distance Gating] ◄── Drop packets beyond max_distance
                     │
                     ▼
         [Target Whitelisting] ◄── all / known_only / whitelist modes
                     │
                     ▼
[Home Assistant Bluetooth Manager] ◄── Injected with smoothed RSSI & distance metadata
```

---

## 2. Multi-Sample RSSI Smoothing Filters

Multipath flutter causes instantaneous RSSI fluctuations of ±10 to 15 dBm even when a device is stationary. Without smoothing, presence detection engines (such as Bermuda or Room-Assistant) frequently experience rapid "room hopping" or false departure triggers.

### Median Smoothing Filter (`median`, Default)
The rolling median filter tracks the most recent $N$ samples (default window: 3) for each unique MAC address.
- Computes the mathematical median of observations within the window:
  $$\text{RSSI}_{\text{smoothed}} = \text{median}(\text{RSSI}_{t}, \text{RSSI}_{t-1}, \dots, \text{RSSI}_{t-N+1})$$
- Completely rejects non-Gaussian outliers (e.g., sharp multipath spikes or temporary antenna nulls) without distorting the underlying trend.

### Exponential Moving Average Filter (`ema`)
The recursive EMA filter assigns higher weight to recent observations while providing continuous exponential smoothing:
$$\text{RSSI}_{\text{smoothed}, t} = \alpha \cdot \text{RSSI}_{t} + (1 - \alpha) \cdot \text{RSSI}_{\text{smoothed}, t-1}$$
- Default smoothing factor $\alpha = 0.6$.
- Offers smooth, continuous signal transitions ideal for tracking moving targets.

### Sample Age Expiration
RSSI observations older than 60 seconds are automatically pruned from the window buffer to guarantee that stale data does not artificially delay presence departure detection.

### Disabling Smoothing (`enable_rssi_smoothing`)
Users can toggle RSSI smoothing off globally or per-speaker. When `enable_rssi_smoothing` is disabled (`false`), raw calibrated RSSI values are passed directly to downstream consumers without historical sample buffering or averaging.

---

## 3. Log-Distance Path Loss Model & Distance Estimation

Estimated distance $d$ (in meters) is computed dynamically using the Log-Distance Path Loss formula:

$$d = 10^{\left(\frac{\text{ref\_power} - \text{RSSI}_{\text{smoothed}}}{10 \cdot n}\right)}$$

### Parameters

| Parameter | Configuration Key | Default | Description |
|---|---|---|---|
| **Enable Distance Estimation** | `enable_distance_estimation` | `true` | Toggle log-distance calculation and distance cutoff gating on/off. When `false`, `estimated_distance` is omitted (`None`) and `max_distance` filtering is bypassed. |
| **Reference Power** | `ref_power` | `-59 dBm` | Expected RSSI at exactly 1 meter distance in line-of-sight. |
| **Path Loss Exponent** | `path_loss_exponent` | `2.5` | Environmental RF attenuation rate ($n$). |
| **Max Distance Cutoff** | `max_distance` | `0.0 m` (Disabled) | Boundary threshold. Advertisements detected beyond this distance are dropped. |

### Path Loss Exponent ($n$) Tuning Guide

- **$n = 2.0$**: Free space / unobstructed line-of-sight (outdoors or large open living rooms).
- **$n = 2.5 - 3.0$**: Typical residential interior with drywall and wood studs (Recommended default).
- **$n = 3.5 - 4.5$**: Dense commercial or apartment buildings with reinforced concrete, masonry, or metallic ductwork.

### Floor & Room Boundary Gating (`max_distance`)
Setting `max_distance` (e.g., `5.0` meters) ensures that weak, distant advertisements originating from adjacent floors or neighboring apartments are dropped before reaching Home Assistant. This drastically reduces false room detections in multi-speaker setups.

---

## 4. Target Whitelisting & Ephemeral MAC Filtering

Modern BLE beacons, phones, and smartwatches rotate their MAC addresses every 15 minutes. In dense urban environments, passive scanning can detect hundreds of nearby devices, leading to database bloat and excessive event bus traffic.

Google Home Bluetooth Proxy provides three filter modes:

### 1. All Devices (`all`)
- Standard Home Assistant behavior: all discovered advertisements meeting the minimum RSSI threshold are injected.

### 2. Known Devices Only (`known_only`)
- Drops unnamed, ephemeral random MAC addresses (RPA) unless:
  - The device advertises a local name (e.g. `Smart Bulb`, `Tile Pro`).
  - The device matches a configured cryptographic Identity Resolving Key (**IRK**).
  - The device is explicitly listed in `tracked_devices`.
- Dramatically cleans up the Home Assistant entity registry while allowing all recognized devices and tracked beacons through.

### 3. Strict Whitelist (`whitelist`)
- Only advertisements matching the `tracked_devices` list are permitted.
- Supports:
  - **Exact MAC address**: `AA:BB:CC:DD:EE:FF`
  - **OUI / Manufacturer Prefix**: `AA:BB:CC` (tracks any device matching the prefix)
  - **Name Substring**: `Beacon`, `Tile` (case-insensitive substring match against local name or resolved IRK)

---

## 5. Synchronized Round-Robin Scan Orchestrator

### The RF Coexistence Challenge
Google Home and Nest speakers feature integrated 2.4GHz Wi-Fi and Bluetooth chipsets sharing a single RF front-end and antenna. When multiple speakers in a home initiate active inquiry scans (`POST /setup/bluetooth/scan`) at the exact same moment:
1. **Packet Collisions**: Simultaneous 2.4GHz BLE inquiries in adjacent rooms cause packet collisions and missed advertisements.
2. **Wi-Fi Throughput Drops**: Concurrent scanning by several speakers saturates local Wi-Fi airtime.

### The Orchestrator Solution
The `ScanOrchestrator` coordinates active inquiry windows across all configured proxy nodes:

- **Round-Robin Serialization (`round_robin`, Default)**:
  - Only **one** Google Home speaker conducts active hardware transmission at any given second.
  - Subsequent speakers queue into a lightweight async waiting queue (`queue_depth`).
  - While waiting, the speaker sensor reports `status: waiting_slot`.
  - As soon as the active speaker finishes its scan window (typically 2–5 seconds), the orchestrator immediately hands the slot to the next queued speaker.
- **Independent Mode (`independent`)**:
  - Disables serialization. Each speaker polls independently according to its own configured interval and stagger delay. Useful for single-speaker installations.
