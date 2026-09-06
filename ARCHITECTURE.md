# Architecture: ha-google-home-bt-proxy

## 1. Overview

`ha-google-home-bt-proxy` turns existing Google Home and Nest speakers into native Home Assistant remote Bluetooth Low Energy (BLE) scanners (`habluetooth.BaseHaRemoteScanner`). By periodically executing local hardware inquiry scans on each speaker over HTTPS (port 8443) with authentication tokens provided by `glocaltokens`, the integration feeds real-time Bluetooth advertisement packets—complete with source MAC address, RSSI signal strength, and device identifiers—directly into Home Assistant Core's Bluetooth Manager.

Downstream integrations such as [Bermuda BLE Triangulation / Trilateration](https://github.com/agittins/bermuda) consume these native Bluetooth advertisements to provide pinpoint room-level device presence and proximity tracking without requiring auxiliary ESP32 microcontrollers or external daemons.

---

## 2. System Topology

```mermaid
flowchart TD
    subgraph LAN["Local Area Network (LAN)"]
        GHSpeaker1["Google Home Mini (Living Room)"]
        GHSpeaker2["Nest Audio (Kitchen)"]
        BLEDevice["BLE Beacon / Wearable / Phone"]
    end

    subgraph Integration["custom_components/google_home_bt_proxy"]
        ConfigFlow["Config & Options Flow"]
        TokenCoordinator["GoogleHomeProxyCoordinator (glocaltokens)"]
        ApiClient["GoogleHomeApiClient (HTTPS Port 8443)"]
        ScannerWorker1["Scanner Worker Loop 1"]
        ScannerWorker2["Scanner Worker Loop 2"]
        RemoteScanner1["GoogleHomeRemoteScanner (Living Room)"]
        RemoteScanner2["GoogleHomeRemoteScanner (Kitchen)"]
    end

    subgraph HomeAssistant["Home Assistant Core"]
        HABtManager["Bluetooth Manager (habluetooth)"]
        Bermuda["Bermuda BLE Room Presence Integration"]
        DeviceTracker["Area & Room Device Tracker Entities"]
    end

    BLEDevice -.->|BLE In-Air Advertisements| GHSpeaker1
    BLEDevice -.->|BLE In-Air Advertisements| GHSpeaker2

    ConfigFlow --> TokenCoordinator
    TokenCoordinator -->|Tokens & IPs| ApiClient

    ApiClient <-->|HTTPS 8443 /setup/bluetooth/*| GHSpeaker1
    ApiClient <-->|HTTPS 8443 /setup/bluetooth/*| GHSpeaker2

    ApiClient --> ScannerWorker1
    ApiClient --> ScannerWorker2

    ScannerWorker1 -->|Discovered BLE Packets| RemoteScanner1
    ScannerWorker2 -->|Discovered BLE Packets| RemoteScanner2

    RemoteScanner1 -->|_async_on_advertisement| HABtManager
    RemoteScanner2 -->|_async_on_advertisement| HABtManager

    HABtManager -->|Bluetooth Advertisements with RSSI & Source| Bermuda
    Bermuda --> DeviceTracker
```

---

## 3. Sequence Flow

The integration orchestrates periodic, staggered hardware scans across all registered Google Home speakers.

```mermaid
sequenceDiagram
    autonumber
    participant Worker as Scan Worker Loop
    participant Api as GoogleHomeApiClient
    participant Spk as Google Home Speaker (8443)
    participant Scanner as GoogleHomeRemoteScanner
    participant HABT as Home Assistant Bluetooth Manager
    participant Bermuda as Bermuda Integration

    Note over Worker,Spk: Trigger Active Inquiry Scan
    Worker->>Api: start_scan(timeout=5)
    Api->>Spk: POST /setup/bluetooth/scan {"enable": true, "clear_results": true, "timeout": 5}
    Spk-->>Api: 200 OK {"success": true}

    Note over Worker: Wait for hardware scan window
    Worker->>Worker: sleep(5s)

    Note over Worker,Spk: Retrieve Detected Bluetooth Radios
    Worker->>Api: get_scan_results()
    Api->>Spk: GET /setup/bluetooth/scan_results
    Spk-->>Api: 200 [{"mac_address": "AA:BB:...", "rssi": -65, "name": "..."}]

    Note over Worker,HABT: Filter and Inject into HA Bluetooth Framework
    Worker->>Scanner: process_scan_results(devices, min_rssi=-90)
    loop Each Discovered Device >= RSSI Threshold
        Scanner->>HABT: _async_on_advertisement(address, rssi, local_name, scanner_id, ...)
    end

    Note over HABT,Bermuda: Downstream Presence Tracking
    HABT->>Bermuda: Dispatched BLE Advertisement Event
    Bermuda->>Bermuda: Compute Distance & Room/Area Presence
```

---

## 4. Component Structure & Responsibilities

| Module | File | Primary Responsibility |
|---|---|---|
| **Lifecycle Coordinator** | `__init__.py` | Initializes config entries, registers scanners via `bluetooth.async_register_scanner`, manages staggered background worker loops, and handles clean unregistration on unload. |
| **Speaker Coordinator** | `coordinator.py` | Discovers Google Home speakers via mDNS / Zeroconf (`_googlecast._tcp.local.`), authenticates using `glocaltokens` master tokens or app passwords, and coordinates token refreshes. |
| **HTTPS API Client** | `api.py` | Asynchronously executes HTTPS requests against speaker port 8443 with `cast-local-authorization-token` header, parsing `eureka_info`, `bluetooth/scan`, and `bluetooth/scan_results`. |
| **Remote Scanner Node** | `scanner.py` | Subclasses `habluetooth.BaseHaRemoteScanner`, translating raw JSON speaker payloads into Home Assistant `_async_on_advertisement` events. |
| **Configuration Flow** | `config_flow.py` | User and options UI configuration flows allowing authentication, interval tuning, scan timeouts, RSSI threshold calibration, and speaker disabling. |
| **Data Models** | `models.py` | Strongly typed dataclasses for `SpeakerNode` and `DiscoveredDevice`. |
| **Constants** | `const.py` | Configuration constants, default values, and API endpoint paths. |
| **Hardware Probe** | `scripts/probe_speaker.py` | Standalone CLI utility for discovering, authenticating, and dumping raw diagnostic endpoints directly from physical speakers. |

---

## 5. Resilience & Fault Tolerance

1. **Staggered Initialization**: To prevent network saturation and bursty load on Home Assistant's event loop, background workers are launched with a 1.5-second stagger delay per speaker.
2. **Token Expiration Recovery**: When a speaker returns HTTP 401 Unauthorized, `TokenExpiredError` is caught, prompting `coordinator.async_refresh_token(speaker)` to refresh credentials from Google servers before retrying.
3. **Exponential Backoff on Connection Drops**: Network timeouts or unreachable speakers trigger exponential backoff (1s -> 2s -> 4s -> ... up to 60s), ensuring the integration automatically self-heals when speakers reboot or re-associate with Wi-Fi.
4. **Clean Resource Teardown**: Upon integration reload or unload, worker tasks are cancelled cleanly and scanner instances are deregistered from `homeassistant.components.bluetooth`.
