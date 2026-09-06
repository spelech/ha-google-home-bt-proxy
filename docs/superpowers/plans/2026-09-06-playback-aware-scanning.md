# Standalone Playback-Aware Scanning Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement standalone playback-aware Bluetooth scanning with configurable intervals, durations, and skip ceilings in `ha-google-home-bt-proxy` without any dependency on Home Assistant's `cast` component or `media_player` entities.

**Architecture:** A standalone `SpeakerPlaybackDetector` queries the speaker directly via Cast V2 TLS (port 8009) and local Bluetooth status HTTPS (port 8443). The worker scan loop in `_speaker_scan_loop` adapts between idle cadence, throttled cadence, or skip-with-ceiling based on the active playback mode and configurable timing options.

**Tech Stack:** Python 3.12+, `aiohttp`, `pychromecast`, `homeassistant`, `pytest`, `pytest-asyncio`, `ruff`, `mypy`.

## Global Constraints

- Repository: `/drives/nfs/repos/ha-google-home-bt-proxy`
- Branch: `feat/playback-aware-scanning`
- Zero external runtime daemons or Home Assistant `cast` component coupling; 100% standalone direct speaker communication.
- Adhere strictly to Steven T. Pelech's `AgenticEngineeringToolbelt` standards: SOLID, role-based naming, $\ge$ 80% test coverage, 4-stage quality gates.

---

### Task 1: Constants and Configuration Keys (`const.py`, `strings.json`)

**Files:**
- Modify: `custom_components/google_home_bt_proxy/const.py`
- Modify: `custom_components/google_home_bt_proxy/strings.json`
- Test: `tests/test_models.py`

**Interfaces:**
- Produces in `const.py`:
  - `CONF_PLAYBACK_MODE: Final = "playback_mode"`
  - `MODE_THROTTLE: Final = "throttle"`
  - `MODE_SKIP_CEILING: Final = "skip_ceiling"`
  - `MODE_IGNORE: Final = "ignore"`
  - `CONF_PLAYING_SCAN_TIMEOUT: Final = "playing_scan_timeout"`
  - `CONF_PLAYING_SCAN_INTERVAL: Final = "playing_scan_interval"`
  - `CONF_MAX_PLAYING_SKIP_DURATION: Final = "max_playing_skip_duration"`
  - `DEFAULT_PLAYBACK_MODE: Final = MODE_THROTTLE`
  - `DEFAULT_PLAYING_SCAN_TIMEOUT: Final = 2`
  - `DEFAULT_PLAYING_SCAN_INTERVAL: Final = 30`
  - `DEFAULT_MAX_PLAYING_SKIP_DURATION: Final = 120`

- [ ] **Step 1: Write failing constants test**

Add to `tests/test_models.py`:
```python
def test_playback_constants():
    from custom_components.google_home_bt_proxy.const import (
        CONF_MAX_PLAYING_SKIP_DURATION,
        CONF_PLAYBACK_MODE,
        CONF_PLAYING_SCAN_INTERVAL,
        CONF_PLAYING_SCAN_TIMEOUT,
        DEFAULT_MAX_PLAYING_SKIP_DURATION,
        DEFAULT_PLAYBACK_MODE,
        DEFAULT_PLAYING_SCAN_INTERVAL,
        DEFAULT_PLAYING_SCAN_TIMEOUT,
        MODE_IGNORE,
        MODE_SKIP_CEILING,
        MODE_THROTTLE,
    )

    assert CONF_PLAYBACK_MODE == "playback_mode"
    assert MODE_THROTTLE == "throttle"
    assert MODE_SKIP_CEILING == "skip_ceiling"
    assert MODE_IGNORE == "ignore"
    assert DEFAULT_PLAYBACK_MODE == MODE_THROTTLE
    assert DEFAULT_PLAYING_SCAN_TIMEOUT == 2
    assert DEFAULT_PLAYING_SCAN_INTERVAL == 30
    assert DEFAULT_MAX_PLAYING_SKIP_DURATION == 120
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_models.py -k test_playback_constants -v`
Expected: FAIL with `ImportError`

- [ ] **Step 3: Implement constants in `const.py` and labels in `strings.json`**

Update `custom_components/google_home_bt_proxy/const.py` with the constants.
Update `custom_components/google_home_bt_proxy/strings.json` with field descriptions and options titles.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_models.py -k test_playback_constants -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add custom_components/google_home_bt_proxy/const.py custom_components/google_home_bt_proxy/strings.json tests/test_models.py
git commit -m "feat(const): add playback awareness configuration constants and options strings"
```

---

### Task 2: API Client Bluetooth Status Query (`api.py`)

**Files:**
- Modify: `custom_components/google_home_bt_proxy/api.py`
- Test: `tests/test_api.py`

**Interfaces:**
- Produces in `GoogleHomeApiClient`:
  - `async def get_bluetooth_status(self, speaker: SpeakerNode) -> dict[str, Any]`

- [ ] **Step 1: Write failing test for `get_bluetooth_status`**

Add to `tests/test_api.py`:
```python
@pytest.mark.asyncio
async def test_get_bluetooth_status(aiohttp_client):
    async def handle_status(request):
        assert request.headers.get("cast-local-authorization-token") == "test-token"
        return web.json_response(
            {
                "connected_devices": [
                    {"mac_address": "11:22:33:44:55:66", "name": "Phone", "device_class": 5898764}
                ]
            }
        )

    app = web.Application()
    app.router.add_get("/setup/bluetooth/status", handle_status)
    client = await aiohttp_client(app)
    api_client = GoogleHomeApiClient(client.session, port=client.server.port, use_ssl=False)

    speaker = SpeakerNode(
        device_id="test-spk",
        name="Test Speaker",
        ip_address=str(client.server.host),
        auth_token="test-token",
    )

    status = await api_client.get_bluetooth_status(speaker)
    assert "connected_devices" in status
    assert len(status["connected_devices"]) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_api.py -k test_get_bluetooth_status -v`
Expected: FAIL with `AttributeError: 'GoogleHomeApiClient' object has no attribute 'get_bluetooth_status'`

- [ ] **Step 3: Implement `get_bluetooth_status` in `api.py`**

Add `get_bluetooth_status` to `GoogleHomeApiClient` using `ENDPOINT_BLUETOOTH_STATUS`.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_api.py -k test_get_bluetooth_status -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add custom_components/google_home_bt_proxy/api.py tests/test_api.py
git commit -m "feat(api): add get_bluetooth_status endpoint query method"
```

---

### Task 3: Standalone Playback Detector (`playback.py`)

**Files:**
- Create: `custom_components/google_home_bt_proxy/playback.py`
- Test: `tests/test_playback.py`

**Interfaces:**
- Consumes: `SpeakerNode`, `GoogleHomeApiClient`.
- Produces in `playback.py`:
  - `class SpeakerPlaybackDetector`:
    - `def __init__(self, api_client: GoogleHomeApiClient, cast_timeout: float = 3.0) -> None`
    - `async def async_is_playing(self, speaker: SpeakerNode) -> bool`
    - `async def _check_cast_playing(self, host: str) -> bool`
    - `async def _check_bluetooth_streaming(self, speaker: SpeakerNode) -> bool`

- [ ] **Step 1: Write failing playback detector tests**

Create `tests/test_playback.py` testing:
1. `test_is_playing_cast_active`: Mock pychromecast returning `player_state = "PLAYING"` -> returns `True`.
2. `test_is_playing_bluetooth_a2dp`: Cast returns `False`, but `/setup/bluetooth/status` returns connected devices with device class or connection -> returns `True`.
3. `test_is_playing_idle`: Both Cast and BT status report idle -> returns `False`.
4. `test_is_playing_error_resilience`: Cast socket timeout and BT connection error -> gracefully returns `False`.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_playback.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement `playback.py`**

Implement `SpeakerPlaybackDetector` with direct socket/pychromecast queries and `api_client.get_bluetooth_status` checks, wrapped in safe timeouts (`asyncio.timeout` / executor).

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_playback.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add custom_components/google_home_bt_proxy/playback.py tests/test_playback.py
git commit -m "feat(playback): implement standalone SpeakerPlaybackDetector for Cast and Bluetooth audio"
```

---

### Task 4: Options Flow Playback Configuration (`config_flow.py`)

**Files:**
- Modify: `custom_components/google_home_bt_proxy/config_flow.py`
- Test: `tests/test_config_flow.py`

**Interfaces:**
- Produces: Updated `GoogleHomeBtProxyOptionsFlowHandler` supporting `playback_mode`, `scan_timeout`, `scan_interval`, `playing_scan_timeout`, `playing_scan_interval`, `max_playing_skip_duration`, and `rssi_threshold`.

- [ ] **Step 1: Write failing options flow test**

Add to `tests/test_config_flow.py`:
```python
@pytest.mark.asyncio
async def test_options_flow_with_playback_settings():
    from custom_components.google_home_bt_proxy.const import (
        CONF_PLAYBACK_MODE,
        CONF_PLAYING_SCAN_INTERVAL,
        CONF_PLAYING_SCAN_TIMEOUT,
        CONF_MAX_PLAYING_SKIP_DURATION,
        MODE_SKIP_CEILING,
    )

    entry = MagicMock()
    entry.options = {}
    handler = GoogleHomeBtProxyOptionsFlowHandler(entry)

    user_input = {
        CONF_PLAYBACK_MODE: MODE_SKIP_CEILING,
        CONF_PLAYING_SCAN_TIMEOUT: 3,
        CONF_PLAYING_SCAN_INTERVAL: 45,
        CONF_MAX_PLAYING_SKIP_DURATION: 180,
    }
    result = await handler.async_step_init(user_input)
    assert result["type"] == "create_entry"
    assert result["data"][CONF_PLAYBACK_MODE] == MODE_SKIP_CEILING
    assert result["data"][CONF_PLAYING_SCAN_TIMEOUT] == 3
    assert result["data"][CONF_PLAYING_SCAN_INTERVAL] == 45
    assert result["data"][CONF_MAX_PLAYING_SKIP_DURATION] == 180
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_config_flow.py -k test_options_flow_with_playback_settings -v`
Expected: FAIL

- [ ] **Step 3: Update `config_flow.py` options schema**

Add `vol.Optional(CONF_PLAYBACK_MODE, default=...)`, `CONF_PLAYING_SCAN_TIMEOUT`, `CONF_PLAYING_SCAN_INTERVAL`, `CONF_MAX_PLAYING_SKIP_DURATION` with validation ranges.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_config_flow.py -k test_options_flow_with_playback_settings -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add custom_components/google_home_bt_proxy/config_flow.py tests/test_config_flow.py
git commit -m "feat(flow): add playback mode, playing timings, and skip ceiling to options flow"
```

---

### Task 5: Adaptive Playback Scan Loop & State Machine (`__init__.py`)

**Files:**
- Modify: `custom_components/google_home_bt_proxy/__init__.py`
- Test: `tests/test_init.py`

**Interfaces:**
- Consumes: `SpeakerPlaybackDetector`, `CONF_PLAYBACK_MODE`, `CONF_PLAYING_SCAN_INTERVAL`, `CONF_PLAYING_SCAN_TIMEOUT`, `CONF_MAX_PLAYING_SKIP_DURATION`.
- Modifies: `_speaker_scan_loop` in `__init__.py`.

- [ ] **Step 1: Write failing tests for adaptive scan loop**

Add tests to `tests/test_init.py`:
1. `test_scan_loop_throttles_when_playing`: When `playback_mode == "throttle"` and `async_is_playing` is True, verify scan timeout is 2s and interval is 30s.
2. `test_scan_loop_skips_until_ceiling`: When `playback_mode == "skip_ceiling"` and `async_is_playing` is True, skips scan while duration < ceiling, and triggers scan once duration $\ge$ ceiling.
3. `test_scan_loop_ignores_playback_in_ignore_mode`: When `playback_mode == "ignore"`, scans with normal idle timeout and interval regardless of playback state.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_init.py -k "playback or throttle or ceiling" -v`
Expected: FAIL

- [ ] **Step 3: Implement adaptive scan loop in `__init__.py`**

Wire `SpeakerPlaybackDetector` into `_speaker_scan_loop`, calculate active timeout/interval dynamically, track continuous playback skip duration, and enforce the mode policy.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_init.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add custom_components/google_home_bt_proxy/__init__.py tests/test_init.py
git commit -m "feat(worker): implement adaptive scan loop with playback throttling and skip ceiling"
```

---

### Task 6: Full Suite Verification, Quality Gates & Pull Request

**Files:**
- All modified files

- [ ] **Step 1: Run Ruff linter and formatter**

Run: `uv run ruff check . && uv run ruff format --check .`

- [ ] **Step 2: Run Mypy type checker**

Run: `uv run mypy custom_components/ tests/`

- [ ] **Step 3: Run Pytest test suite with code coverage**

Run: `uv run pytest --cov=custom_components.google_home_bt_proxy --cov-report=term-missing`
Expected: 100% pass, coverage $\ge$ 80%

- [ ] **Step 4: Push branch and create Pull Request**

Run:
```bash
git push -u origin feat/playback-aware-scanning
gh pr create --title "feat: standalone playback-aware Bluetooth scanning with configurable intervals" --body "..."
```
