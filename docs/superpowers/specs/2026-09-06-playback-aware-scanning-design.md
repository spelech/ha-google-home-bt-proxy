# Design Specification: Standalone Playback-Aware Bluetooth Scanning

## 1. Objective

Enable `ha-google-home-bt-proxy` to intelligently adapt or suppress Bluetooth inquiry scanning whenever media is actively playing on a Google Home or Nest speaker, while preserving BLE room tracking (Bermuda) freshness via fully configurable intervals, durations, and skip ceilings.

The integration **must stand alone**—it must not depend on Home Assistant's `cast` integration, entity registry, or existing `media_player` entities. All playback detection is performed directly against the speaker's IP address on the local area network.

## 2. Problem Statement & Hardware Constraints

Google Home and Nest speakers (Home Mini, Nest Mini, Nest Audio) use integrated Wi-Fi/Bluetooth combo chipsets sharing 2.4 GHz RF paths and antenna elements. When the speaker executes an active inquiry scan (`POST /setup/bluetooth/scan`), the Bluetooth radio prioritizes channel inquiry:
1. **Bluetooth Audio (A2DP):** Causes audible audio stutter, buffer underruns, packet drops, or complete disconnects if streaming to or from a paired Bluetooth device.
2. **Cast Audio over Wi-Fi:** Coexistence contention and CPU load during 5-second inquiry sweeps can produce audible micro-glitches and crackling.
3. **Tracking Starvation:** If scanning is completely suspended during media playback without a bound, long listening sessions (e.g. 2-hour playlists, podcasts, or white noise) cause Bermuda BLE device tracking to go completely dark.

## 3. Architecture & Standalone Detection

Playback state is queried directly from each physical speaker using two standalone network channels:

```mermaid
flowchart TD
    subgraph Speaker["Google Home / Nest Speaker (IP Address)"]
        CastSocket["Port 8009: Cast V2 TLS Engine"]
        ApiPort["Port 8443: Local Setup HTTPS Server"]
    end

    subgraph Integration["custom_components/google_home_bt_proxy"]
        PlaybackDetector["SpeakerPlaybackDetector (playback.py)"]
        ApiClient["GoogleHomeApiClient (api.py)"]
        WorkerLoop["_speaker_scan_loop (__init__.py)"]
    end

    PlaybackDetector -->|Direct TLS Socket| CastSocket
    CastSocket -->|media_controller.status.player_state| PlaybackDetector

    PlaybackDetector -->|HTTPS GET /setup/bluetooth/status| ApiClient
    ApiClient -->|Port 8443| ApiPort
    ApiPort -->|connected_devices (A2DP stream)| ApiClient
    ApiClient --> PlaybackDetector

    PlaybackDetector -->|is_playing: bool| WorkerLoop
    WorkerLoop -->|Adaptive Interval & Timeout| ApiClient
```

### 3.1 Source A: Standalone Cast V2 Socket (Port 8009)
* Connects directly to `speaker.ip_address:8009` via `pychromecast`.
* Inspects `media_controller.status.player_state` (`PLAYING`, `BUFFERING`) and `cast.status.display_name` (detects active streaming applications such as Spotify, YouTube Music, TuneIn, TTS vs. idle backdrop).
* Operates completely out-of-band from Home Assistant's `cast` component.

### 3.2 Source B: Bluetooth Audio Status (Port 8443)
* Queries `GET https://{speaker.ip_address}:8443/setup/bluetooth/status` with `cast-local-authorization-token`.
* Inspects `connected_devices` for active A2DP audio profiles.

### 3.3 Evaluation Logic
If either Source A (Cast) or Source B (Bluetooth A2DP) indicates active media playback, `SpeakerPlaybackDetector.async_is_playing(speaker)` returns `True`. If both are idle or connection checks fail/time out, it safely falls back to `False`.

## 4. Playback Modes & Adaptive Scanning

The integration exposes three user-selectable playback modes:

1. **`throttle` (Default):**
   * While media is playing, continue scanning but at a relaxed cadence and shorter hardware sweep:
     * Scan Duration: `playing_scan_timeout` (default: 2s)
     * Scan Interval: `playing_scan_interval` (default: 30s)
   * Reduces RF contention by >85% while keeping BLE device tracker leases alive.
2. **`skip_ceiling`:**
   * While media is playing, completely skip/suppress inquiry scans.
   * Tracks `continuous_playing_start_time`. If continuous playback exceeds `max_playing_skip_duration` (default: 120s), forces a single rapid scan (`playing_scan_timeout`, 2s) to refresh beacons, then resets the timer.
3. **`ignore`:**
   * Unconditionally scans at idle interval/timeout regardless of playback status.

When media stops (transitions to `IDLE` or `PAUSED`), scanning immediately resets to normal idle cadence without waiting for the longer playing interval.

## 5. Configuration & Options Schema

Configured via the Home Assistant Options Flow in `config_flow.py`:

| Parameter Key | Type | Default | Range / Allowed Values | Description |
| :--- | :--- | :--- | :--- | :--- |
| `CONF_PLAYBACK_MODE` | `str` | `"throttle"` | `["throttle", "skip_ceiling", "ignore"]` | Policy when media is playing |
| `CONF_SCAN_TIMEOUT` | `int` | `5` | `2` – `15` seconds | Hardware scan duration when idle |
| `CONF_SCAN_INTERVAL` | `int` | `10` | `5` – `60` seconds | Wait time between scans when idle |
| `CONF_PLAYING_SCAN_TIMEOUT`| `int` | `2` | `1` – `10` seconds | Hardware scan duration when playing |
| `CONF_PLAYING_SCAN_INTERVAL`| `int` | `30` | `10` – `300` seconds | Interval between scans when playing (throttle mode) |
| `CONF_MAX_PLAYING_SKIP_DURATION`| `int` | `120` | `30` – `900` seconds | Max continuous skip duration before forced scan (skip_ceiling mode) |
| `CONF_RSSI_THRESHOLD` | `int` | `-90` | `-100` to `-40` dBm | Minimum RSSI filter threshold |

## 6. Implementation Components

1. **`custom_components/google_home_bt_proxy/const.py`**:
   * Add constants: `CONF_PLAYBACK_MODE`, `MODE_THROTTLE`, `MODE_SKIP_CEILING`, `MODE_IGNORE`, `CONF_PLAYING_SCAN_TIMEOUT`, `CONF_PLAYING_SCAN_INTERVAL`, `CONF_MAX_PLAYING_SKIP_DURATION`, `ENDPOINT_BLUETOOTH_STATUS`, and their defaults.
2. **`custom_components/google_home_bt_proxy/api.py`**:
   * Add `async def get_bluetooth_status(self, speaker: SpeakerNode) -> dict[str, Any]` to fetch `/setup/bluetooth/status`.
3. **`custom_components/google_home_bt_proxy/playback.py`**:
   * Implement `SpeakerPlaybackDetector` to handle standalone Cast V2 queries and Bluetooth status evaluation with timeout resilience.
4. **`custom_components/google_home_bt_proxy/config_flow.py`**:
   * Update `GoogleHomeBtProxyOptionsFlowHandler` schema with mode selection and all configurable intervals/durations.
5. **`custom_components/google_home_bt_proxy/strings.json`**:
   * Add localized strings and option titles for the new configuration parameters.
6. **`custom_components/google_home_bt_proxy/__init__.py`**:
   * Instantiate `SpeakerPlaybackDetector`.
   * Update `_speaker_scan_loop` state machine with mode evaluation, adaptive intervals, duration switching, and skip ceiling tracking.

## 7. Testing & Quality Assurance

* **`tests/test_playback.py`**: Unit tests verifying `SpeakerPlaybackDetector` correctly identifies Cast playback states, Bluetooth A2DP connections, and handles timeouts/exceptions gracefully.
* **`tests/test_api.py`**: Test `get_bluetooth_status` endpoint query and response handling.
* **`tests/test_config_flow.py`**: Test options flow form rendering, default population, and persistence of all new parameters.
* **`tests/test_init.py`**: Test `_speaker_scan_loop` behavior across `throttle`, `skip_ceiling` (including ceiling trigger), and `ignore` modes.
