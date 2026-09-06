# Signal Processing and Scan Orchestration

This document describes the signal processing pipeline, distance estimation model, and scan orchestration used by `ha-google-home-bt-proxy`.

---

## 1. Overview

Bluetooth Low Energy (BLE) signals fluctuate due to reflections and environmental obstacles. In addition, devices like phones rotate their MAC addresses (Randomized Private Addresses, or RPAs).

The integration processes advertisements through this pipeline before sending them to Home Assistant:

```
[Hardware Scan (/setup/bluetooth/scan)]
                 │
                 ▼
       [Scan Orchestrator]        <-- Serializes scans across speakers
                 │
                 ▼
       [Calibration Offset]       <-- Applies speaker-specific dBm adjustment
                 │
                 ▼
     [RSSI Smoothing Filter]      <-- Rolling median or EMA filter
                 │
                 ▼
     [Distance Estimation]        <-- Log-distance path loss calculation
                 │
                 ▼
       [Distance Cutoff]          <-- Drops packets beyond max_distance
                 │
                 ▼
       [Target Whitelist]         <-- all / known_only / whitelist modes
                 │
                 ▼
[Home Assistant Bluetooth Manager] <-- Injected with smoothed RSSI and metadata
```

---

## 2. RSSI Smoothing Filters

Multipath reflections can cause sudden jumps in RSSI even for stationary devices. The integration provides two smoothing filters, as well as an option to disable smoothing.

### Median Filter (`median`, Default)
The rolling median filter stores the most recent $N$ samples (default window: 3) for each MAC address and returns the median:

$$\text{RSSI}_{\text{smoothed}} = \text{median}(\text{RSSI}_{t}, \text{RSSI}_{t-1}, \dots, \text{RSSI}_{t-N+1})$$

This filter removes isolated signal spikes while preserving genuine step changes.

### Exponential Moving Average (`ema`)
The exponential moving average filter weights recent samples more heavily:

$$\text{RSSI}_{\text{smoothed}, t} = \alpha \cdot \text{RSSI}_{t} + (1 - \alpha) \cdot \text{RSSI}_{\text{smoothed}, t-1}$$

The smoothing factor $\alpha$ is set to 0.6.

### Sample Expiration
Samples older than 60 seconds are discarded so that old values do not affect current readings.

### Disabling Smoothing (`enable_rssi_smoothing`)
When `enable_rssi_smoothing` is set to `false`, the integration forwards the calibrated RSSI value directly without buffering or averaging.

---

## 3. Distance Estimation

Distance is calculated in meters using the log-distance path loss formula:

$$d = 10^{\left(\frac{\text{ref\_power} - \text{RSSI}_{\text{smoothed}}}{10 \cdot n}\right)}$$

### Parameters

| Parameter | Configuration Key | Default | Description |
|---|---|---|---|
| **Enable Distance Estimation** | `enable_distance_estimation` | `true` | Calculates distance in meters. When `false`, `estimated_distance` is set to `None` and distance cutoffs are skipped. |
| **Reference Power** | `ref_power` | `-59 dBm` | Expected RSSI at 1 meter in direct line-of-sight. |
| **Path Loss Exponent** | `path_loss_exponent` | `2.5` | Environmental attenuation rate ($n$). |
| **Max Distance Cutoff** | `max_distance` | `0.0 m` | Packets estimated beyond this distance are dropped. Set to `0.0` to disable. |

### Path Loss Exponent ($n$) Guidelines

- **$n = 2.0$**: Line-of-sight or open indoor spaces.
- **$n = 2.5 - 3.0$**: Typical homes with drywall and wood framing (default: `2.5`).
- **$n = 3.5 - 4.5$**: Buildings with concrete, brick, or metal walls.

---

## 4. Target Filtering

To prevent unknown or rotating addresses from flooding Home Assistant, three filter modes are available:

1. **All Devices (`all`, Default)**: All advertisements meeting the minimum RSSI threshold are forwarded.
2. **Known Devices Only (`known_only`)**: Discards unnamed random private addresses unless the device has a local name, matches a configured Identity Resolving Key (IRK), or is listed in `tracked_devices`.
3. **Whitelist (`whitelist`)**: Only allows devices matching `tracked_devices`. Matches can be:
   - Exact MAC addresses (e.g. `AA:BB:CC:DD:EE:FF`)
   - OUI or MAC prefixes (e.g. `AA:BB:CC`)
   - Name substrings (case-insensitive, matching advertised name or resolved IRK identity)

---

## 5. Scan Orchestration

Google Home and Nest speakers share their 2.4GHz antenna between Wi-Fi and Bluetooth. Running scans on several speakers simultaneously can increase packet loss on both networks.

The scan orchestrator manages inquiry timing across speakers:

- **Round-Robin (`round_robin`, Default)**: Only one speaker scans at a time. Other speakers wait in a queue until the active scan finishes. While waiting, the speaker sensor reports `status: waiting_slot`.
- **Independent (`independent`)**: Each speaker scans on its own schedule without coordinating with others.
