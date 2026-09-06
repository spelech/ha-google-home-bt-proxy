# Operational Visibility, Bermuda Calibration, Per-Speaker Granularity, and Hardware Matrix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement 4 distinct roadmap enhancements for `ha-google-home-bt-proxy` on dedicated feature branches, with comprehensive unit/integration test coverage, live network testing against local Google Home Minis and Cast TVs, and open GitHub PRs for each.

**Architecture:**
1. **Branch 1 (`feat/diagnostics-and-controls`)**: Provide first-class Home Assistant UI entities (`sensor`, `switch`, `button`) for each speaker proxy node to track status (idle, scanning, throttled, skipped), count advertisements, enable/disable proxying dynamically, and trigger immediate manual scans.
2. **Branch 2 (`feat/bermuda-rf-calibration`)**: Support per-speaker / global RF RSSI offset calibration (`rssi_offset` in dBm) applied to advertisements before forwarding to `_async_on_advertisement`, empowering millimeter-level Bermuda BLE triangulation, with dedicated setup and tuning documentation.
3. **Branch 3 (`feat/per-speaker-options`)**: Introduce hierarchical options flow allowing per-speaker overrides (`CONF_SPEAKER_OVERRIDES`) for scan intervals, timeouts, playback modes, skip ceilings, and RSSI thresholds that seamlessly override global defaults.
4. **Branch 4 (`feat/hardware-matrix-and-docs`)**: Live probe real local hardware (Google Home Mini, Nest Mini, Android TV/Cast TV), verify endpoint behaviors (8009 Cast V2 TLS and 8443 HTTPS), publish empirical `docs/hardware_matrix.md`, and update `README.md` with system architecture diagrams and Bermuda calibration guides.

**Tech Stack:** Python 3.12+, Home Assistant core (`homeassistant.components.{sensor, switch, button, bluetooth, zeroconf}`), `aiohttp`, `pychromecast`, `pytest`, `pytest-asyncio`, `ruff`, `mypy`.

## Global Constraints

- Repository: `/drives/nfs/repos/ha-google-home-bt-proxy`
- Separate Git branches and distinct GitHub PRs for each of the 4 features:
  - Branch 1: `feat/diagnostics-and-controls`
  - Branch 2: `feat/bermuda-rf-calibration`
  - Branch 3: `feat/per-speaker-options`
  - Branch 4: `feat/hardware-matrix-and-docs`
- 100% standalone operation: zero runtime dependencies on Home Assistant `cast` integration or `media_player` entities.
- Full test coverage ($\ge 80\%$, target $\ge 95\%$).
- 4-stage quality gates pass on every branch:
  1. `uv run ruff check .`
  2. `uv run ruff format --check .`
  3. `uv run mypy --explicit-package-bases custom_components/google_home_bt_proxy`
  4. `uv run pytest --cov`

---

## Part 1: Feature Branch `feat/diagnostics-and-controls`

### Task 1.1: Models and Shared Runtime State
**Files:**
- Modify: `custom_components/google_home_bt_proxy/models.py`
- Modify: `custom_components/google_home_bt_proxy/const.py`
- Test: `tests/test_models.py`

**Interfaces:**
- Produces in `models.py`:
  - `SpeakerProxyState`: Dataclass tracking live metrics per speaker:
    - `status: str = "idle"` (states: `"idle"`, `"scanning"`, `"playback_throttled"`, `"playback_skipped"`, `"unavailable"`)
    - `total_advertisements: int = 0`
    - `last_scan_count: int = 0`
    - `last_scan_duration: float = 0.0`
    - `last_scan_timestamp: float | None = None`
    - `enabled: bool = True`
    - `trigger_scan_event: asyncio.Event = field(default_factory=asyncio.Event)`
    - `callbacks: list[Callable[[], None]] = field(default_factory=list)`
    - `def register_callback(self, cb: Callable[[], None]) -> Callable[[], None]: ...`
    - `def notify_callbacks(self) -> None: ...`

- [ ] **Step 1: Write failing test in `tests/test_models.py`**
- [ ] **Step 2: Run test to verify failure**
- [ ] **Step 3: Implement `SpeakerProxyState` in `models.py`**
- [ ] **Step 4: Run test to verify pass**

### Task 1.2: Sensor Platform (`sensor.py`)
**Files:**
- Create: `custom_components/google_home_bt_proxy/sensor.py`
- Modify: `custom_components/google_home_bt_proxy/strings.json`
- Test: `tests/test_sensor.py`

**Interfaces:**
- Produces:
  - `GoogleHomeBtProxyStatusSensor(Entity)`:
    - `device_info`: Attached to `(DOMAIN, speaker.device_id)`
    - `unique_id`: `f"{speaker.device_id}_proxy_status"`
    - `native_value`: Current state from `SpeakerProxyState.status`
    - `extra_state_attributes`: `last_scan_count`, `last_scan_duration`, `last_scan_timestamp`
  - `GoogleHomeBtProxyAdvertisementsSensor(Entity)`:
    - `device_info`: Attached to `(DOMAIN, speaker.device_id)`
    - `unique_id`: `f"{speaker.device_id}_advertisements_total"`
    - `state_class`: `SensorStateClass.TOTAL_INCREASING`
    - `native_value`: Current `SpeakerProxyState.total_advertisements`
    - `extra_state_attributes`: `last_scan_count`

- [ ] **Step 1: Write failing tests in `tests/test_sensor.py`**
- [ ] **Step 2: Run test to verify failure**
- [ ] **Step 3: Implement `sensor.py`**
- [ ] **Step 4: Run test to verify pass**

### Task 1.3: Switch Platform (`switch.py`)
**Files:**
- Create: `custom_components/google_home_bt_proxy/switch.py`
- Modify: `custom_components/google_home_bt_proxy/strings.json`
- Test: `tests/test_switch.py`

**Interfaces:**
- Produces:
  - `GoogleHomeBtProxyScannerSwitch(SwitchEntity)`:
    - `device_info`: Attached to `(DOMAIN, speaker.device_id)`
    - `unique_id`: `f"{speaker.device_id}_scanner_switch"`
    - `is_on`: Returns `SpeakerProxyState.enabled`
    - `async_turn_on()`: Sets `state.enabled = True`, notifies callbacks, updates options or signals loop.
    - `async_turn_off()`: Sets `state.enabled = False`, notifies callbacks.

- [ ] **Step 1: Write failing tests in `tests/test_switch.py`**
- [ ] **Step 2: Run test to verify failure**
- [ ] **Step 3: Implement `switch.py`**
- [ ] **Step 4: Run test to verify pass**

### Task 1.4: Button Platform (`button.py`)
**Files:**
- Create: `custom_components/google_home_bt_proxy/button.py`
- Modify: `custom_components/google_home_bt_proxy/strings.json`
- Test: `tests/test_button.py`

**Interfaces:**
- Produces:
  - `GoogleHomeBtProxyScanButton(ButtonEntity)`:
    - `device_info`: Attached to `(DOMAIN, speaker.device_id)`
    - `unique_id`: `f"{speaker.device_id}_trigger_scan"`
    - `async_press()`: Sets `SpeakerProxyState.trigger_scan_event.set()` to trigger immediate scan in worker loop.

- [ ] **Step 1: Write failing tests in `tests/test_button.py`**
- [ ] **Step 2: Run test to verify failure**
- [ ] **Step 3: Implement `button.py`**
- [ ] **Step 4: Run test to verify pass**

### Task 1.5: Platform Registration & Worker Loop Integration in `__init__.py`
**Files:**
- Modify: `custom_components/google_home_bt_proxy/__init__.py`
- Test: `tests/test_init.py`

- [ ] **Step 1: Write integration tests in `tests/test_init.py` covering sensor, switch, and button entity updates**
- [ ] **Step 2: Update `async_setup_entry` to instantiate `SpeakerProxyState`, forward setups to `["sensor", "switch", "button"]`, update scan loop to publish status and count advertisements, and listen to `trigger_scan_event`**
- [ ] **Step 3: Verify all tests pass, run full test suite with coverage**
- [ ] **Step 4: Run linter, typecheck, commit, push branch `feat/diagnostics-and-controls`, create PR**

---

## Part 2: Feature Branch `feat/bermuda-rf-calibration`

### Task 2.1: RSSI Offset Constant and Scanner Calculation
**Files:**
- Modify: `custom_components/google_home_bt_proxy/const.py`
- Modify: `custom_components/google_home_bt_proxy/scanner.py`
- Test: `tests/test_scanner.py`
- Test: `tests/test_models.py`

**Interfaces:**
- `const.py`:
  - `CONF_RSSI_OFFSET: Final = "rssi_offset"`
  - `DEFAULT_RSSI_OFFSET: Final = 0`
- `scanner.py`:
  - `GoogleHomeRemoteScanner.__init__(..., rssi_offset: int = 0)`
  - `process_scan_results`: applies `calibrated_rssi = max(-127, min(0, device.rssi + self._rssi_offset))` before injecting into `_async_on_advertisement`.

- [ ] **Step 1: Write failing tests in `tests/test_scanner.py` for RSSI offset application**
- [ ] **Step 2: Run test to verify failure**
- [ ] **Step 3: Implement `rssi_offset` in `scanner.py` and `const.py`**
- [ ] **Step 4: Run test to verify pass**

### Task 2.2: Options Flow Support for RSSI Offset
**Files:**
- Modify: `custom_components/google_home_bt_proxy/config_flow.py`
- Modify: `custom_components/google_home_bt_proxy/strings.json`
- Test: `tests/test_config_flow.py`

- [ ] **Step 1: Write failing tests in `tests/test_config_flow.py` for `CONF_RSSI_OFFSET` input and validation**
- [ ] **Step 2: Implement RSSI offset number/slider in options flow schema**
- [ ] **Step 3: Run test to verify pass**

### Task 2.3: Bermuda BLE Triangulation & Calibration Documentation
**Files:**
- Create: `docs/bermuda_calibration.md`

- [ ] **Step 1: Write `docs/bermuda_calibration.md` detailing Bermuda architecture, RSSI calibration methodology, empirical baseline offsets for Minis and TVs, and step-by-step setup in Home Assistant**
- [ ] **Step 2: Run linter, typecheck, pytest with coverage**
- [ ] **Step 3: Commit, push branch `feat/bermuda-rf-calibration`, create PR**

---

## Part 3: Feature Branch `feat/per-speaker-options`

### Task 3.1: Hierarchical Speaker Overrides Configuration
**Files:**
- Modify: `custom_components/google_home_bt_proxy/const.py`
- Modify: `custom_components/google_home_bt_proxy/config_flow.py`
- Modify: `custom_components/google_home_bt_proxy/strings.json`
- Test: `tests/test_config_flow.py`

**Interfaces:**
- `const.py`:
  - `CONF_SPEAKER_OVERRIDES: Final = "speaker_overrides"`
- `config_flow.py`:
  - Options flow step menu: "Configure Global Settings" or "Configure Specific Speaker"
  - Speaker-specific step allows overriding: `scan_interval`, `scan_timeout`, `playback_mode`, `playing_scan_interval`, `playing_scan_timeout`, `max_playing_skip_duration`, `rssi_threshold`, `rssi_offset`.
  - Also option to "Reset to global defaults".

- [ ] **Step 1: Write failing tests in `tests/test_config_flow.py` for hierarchical options flow**
- [ ] **Step 2: Implement multi-step options flow in `config_flow.py`**
- [ ] **Step 3: Run test to verify pass**

### Task 3.2: Worker Loop Per-Speaker Option Resolution
**Files:**
- Modify: `custom_components/google_home_bt_proxy/__init__.py`
- Test: `tests/test_init.py`

**Interfaces:**
- Helper in `__init__.py`:
  - `def _get_speaker_setting(entry: ConfigEntry, speaker_id: str, key: str, default: Any) -> Any:`
    Checks `entry.options.get(CONF_SPEAKER_OVERRIDES, {}).get(speaker_id, {}).get(key)` first, falls back to `entry.options.get(key, default)`.

- [ ] **Step 1: Write failing tests in `tests/test_init.py` verifying per-speaker override takes precedence over global entry options**
- [ ] **Step 2: Integrate `_get_speaker_setting` into `_speaker_scan_loop`**
- [ ] **Step 3: Run test to verify pass**
- [ ] **Step 4: Run linter, typecheck, pytest with coverage**
- [ ] **Step 5: Commit, push branch `feat/per-speaker-options`, create PR**

---

## Part 4: Feature Branch `feat/hardware-matrix-and-docs`

### Task 4.1: Empirical Hardware Testing & Verification
**Files:**
- Create / Run: `scripts/probe_hardware.py`
- Test live local devices (Google Home Minis, Nest Minis, Cast TVs) on the network.

- [ ] **Step 1: Probe local devices via Cast V2 TLS (8009) and HTTPS (8443) to catalog response codes, supported endpoints, and TLS behaviors**
- [ ] **Step 2: Verify playback detection and remote scan execution against accessible devices**

### Task 4.2: Hardware Matrix & Architectural Documentation
**Files:**
- Create: `docs/hardware_matrix.md`
- Modify: `README.md`

- [ ] **Step 1: Write `docs/hardware_matrix.md` with tested device profiles, hardware quirks, and capability matrices for Minis and Cast TVs**
- [ ] **Step 2: Update `README.md` with complete architecture diagram, Bermuda calibration instructions, entity documentation, and compatibility table**
- [ ] **Step 3: Run linter, typecheck, pytest**
- [ ] **Step 4: Commit, push branch `feat/hardware-matrix-and-docs`, create PR**
