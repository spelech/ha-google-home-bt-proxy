# Bermuda BLE Trilateration & Setup Guide

This guide details how to configure Google Home and Nest speakers with the [Bermuda BLE Trilateration](https://github.com/agittins/bermuda) integration for room presence and distance tracking, including essential scan result caveats, setup requirements, and antenna calibration steps.

---

## ⚠️ Important Scan Result Caveats

Google Home and Nest speakers function as Bluetooth proxies by interfacing with Google's on-device local HTTP API (`/setup/bluetooth/scan_results`). Because this mechanism relies on the speaker's internal firmware inquiry scanning rather than dedicated raw radio packet sniffing (like an ESP32), several important architectural and physical caveats apply:

### 1. No Raw Manufacturer Data / No iBeacon Support
- **Firmware Constraint**: The Google Home local API returns high-level parsed fields: `mac_address`, `rssi`, `name`, `device_type`, and `device_class`. It **does not return raw advertisement payloads**, `manufacturer_data` (AD type `0xFF`), service UUIDs, or TX power bytes.
- **Bermuda Impact**: Bermuda detects iBeacon frames (`0x004C0215`) strictly by inspecting `advert.manufacturer_data`. Because this payload is stripped by Google Home firmware, **Bermuda cannot identify or track iBeacons through Google Home speakers**.
- **Supported Device Types**:
  - Devices with fixed/static Bluetooth MAC addresses (BLE beacons, fitness bands, tags).
  - Modern smartphones and smartwatches (iOS, Apple Watch, Android) using rotating Resolvable Private Addresses (RPAs), tracked via Home Assistant's native **[Private BLE Device](https://www.home-assistant.io/integrations/private_ble_device/)** integration (IRK).

### 2. Smartphone Sleep & Lock Behavior (iOS / Android)
- **Power Management**: When locked with screens off, iOS and modern Android versions drastically reduce or halt unassociated BLE advertisements to preserve battery life.
- **Symptom**: Your phone or smartwatch may only report distance or show as "Home" when unlocked, awake, or moving.
- **Solution**: To enable continuous 24/7 background tracking while locked, turn on the **BLE Transmitter** sensor in the **Home Assistant Companion App** (*Settings* > *Companion App* > *Manage Sensors* > *BLE Transmitter*). This commands the phone OS to maintain periodic BLE broadcasts even while the phone is asleep.

### 3. Active Inquiry Cadence vs Passive Sniffing
- ESP32 proxies continuously listen passively. Google Home speakers perform periodic active inquiry sweeps (default: 4s active scan, followed by 4s pause).
- This 8-second cycle is tuned to stay comfortably below Bermuda's strict 10-second advertisement expiration cutoff (`AREA_MAX_AD_AGE`).

### 4. Raw RSSI Passthrough
- When **Bermuda Mode** is enabled (`bermuda_mode: true`), the proxy intentionally forwards raw instantaneous RSSI and sets an internal 0 dBm offset.
- Bermuda's distance calculation engine uses an **asymmetric velocity-limiting filter** that requires unfiltered peak signal levels to track moving targets without artificial phase lag.

---

## 📋 Mandatory Setup Requirements

To ensure Bermuda recognizes your Google Home speakers and computes accurate distance and room presence, follow these requirements:

### 1. Mandatory Area Assignment in Home Assistant
- **Why It Is Required**: In Bermuda's core trilateration algorithm (`coordinator.py:1350-1355`), **any scanner without an assigned Area (`area_id is None`) is strictly disqualified from distance calculations and area contests**:
  ```python
  if (
      challenger.rssi_distance is None
      or challenger.rssi_distance > _max_radius
      or challenger.area_id is None
  ):
      continue
  ```
  An area-less scanner triggers a `REPAIR_SCANNER_WITHOUT_AREA` repair issue and will **never** attribute room presence or distance to any device.
- **How to Verify**:
  1. In Home Assistant, navigate to **Settings** > **Devices & Services** > **Google Home Bluetooth Proxy**.
  2. Click each speaker device.
  3. Ensure the **Area** field is assigned to the physical room where the speaker is located.

### 2. Enabling Per-Scanner Distance Entities in Home Assistant
- **Why It Is Required**: Bermuda configures all individual per-scanner distance entities (`sensor.<device>_distance_to_<speaker>`) as **disabled by default** (`entity_registry_enabled_default = False`) to prevent entity registry bloat. Only aggregate `Area`, `Distance` (closest overall), and `Floor` entities are enabled out of the box.
- **How to Enable**:
  1. In Home Assistant, go to **Settings** > **Devices & Services** > **Bermuda BLE Trilateration**.
  2. Click on your tracked device (e.g., your phone or watch).
  3. Click **Entities** (or toggle *Show disabled entities*).
  4. Find **Distance to <Speaker Name>** and click **Enable entity**.

### 3. Tracking Phones & Watches via Private BLE Device (IRK)
- Because Google Home inquiry scans lack iBeacon manufacturer data, devices that use rotating Resolvable Private Addresses (RPAs) must be tracked using Identity Resolving Keys (IRK).
- Add the **[Private BLE Device](https://www.home-assistant.io/integrations/private_ble_device/)** integration in Home Assistant, enter your device's IRK (extracted via macOS Keychain or ESPHome BLE tools), and Bermuda will automatically track that device across all Google Home proxies.

---

## 📡 Antenna Calibration & Offsets

Bermuda estimates physical distance from received signal strength using the log-distance path loss equation:

$$\text{RSSI} = -10n \log_{10}(d) + A$$

Where $d$ is distance in meters, $n$ is path loss exponent, and $A$ is reference RSSI at 1 meter.

Different hardware enclosures and antenna designs report varying signal levels at the same physical distance:

| Device | Antenna Layout | Typical 1m RSSI | Suggested Bermuda Offset |
| :--- | :--- | :--- | :--- |
| **Google Home Mini (Gen 1)** | Inverted-F PCB trace | -68 dBm | `+4` to `+6 dBm` |
| **Google Nest Mini (Gen 2)** | Internal antenna with ground plane | -63 dBm | `0` to `+2 dBm` |
| **ESP32 Proxy (Reference)** | PCB / Dipole antenna | -62 dBm | `0 dBm` (baseline) |

### Calibration Steps
1. Place a BLE beacon or test device exactly 1 meter line-of-sight from the speaker.
2. In Home Assistant **Developer Tools** > **States** or Bermuda diagnostics, check the average raw RSSI reported by that speaker over 30–60 seconds.
3. Calculate the offset relative to your baseline (e.g. -62 dBm):
   $$\text{Offset} = \text{Baseline RSSI} - \text{Measured RSSI}$$
4. In Home Assistant, navigate to **Settings** > **Devices & Services** > **Bermuda BLE Trilateration** > **Configure** > **Configure Scanner Offsets**.
5. Enter the calculated offset for the speaker scanner and click **Submit**.

> [!CAUTION]
> Always configure offsets inside **Bermuda**, not in the Google Home Proxy's speaker settings when Bermuda Mode is enabled. Configuring offsets in both places causes double-calibration.

---

## Troubleshooting Checklist

- [ ] Is **Bermuda BLE Optimization Mode** enabled in the proxy options?
- [ ] Is the speaker assigned to an **Area** in Home Assistant?
- [ ] For tracked phones/watches, is the device configured with **Private BLE Device (IRK)**?
- [ ] For phones, is the **BLE Transmitter** sensor enabled in the Home Assistant Companion App?
- [ ] Is the individual **Distance to <Speaker>** entity enabled in Home Assistant?
- [ ] Is **Filter Peer Google Home Speakers** enabled to prevent inter-speaker crosstalk?


