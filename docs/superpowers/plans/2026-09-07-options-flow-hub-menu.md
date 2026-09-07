# Options Flow Hub Menu & Adaptive Bermuda Mode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task.

**Goal:** Transform the single flat 20+ field Options Flow form into a clean categorized Hub Menu (`async_show_menu`) that dynamically adapts to hide bypassed RF/signal processing settings when Bermuda Mode is enabled.

**Tech Stack:** Python 3.12+, Home Assistant 2026.1.0+, Voluptuous, Pytest, Ruff.

---

### Task 1: UI Strings & Translations
**Files:**
- Modify: `custom_components/google_home_bt_proxy/strings.json`
- Modify: `custom_components/google_home_bt_proxy/translations/en.json`

- [ ] Add menu options dictionary under `options.step.init.menu_options`:
  - `scanning`: "⏱️ Scanning & Bermuda Mode"
  - `playback`: "🎵 Media Playback Handling"
  - `signal_processing`: "📡 Signal Processing & RF (Standalone)"
  - `filtering`: "🔒 Target Filtering & IRK Resolvers"
  - `speaker_overrides`: "🔊 Speaker-Specific Overrides"
- [ ] Add titles, descriptions, and data keys for each dedicated step:
  - `step.scanning`
  - `step.playback`
  - `step.signal_processing`
  - `step.filtering`
  - `step.speaker_overrides`
- [ ] Add `bermuda_notice` description explaining Bermuda Mode passthrough.
- [ ] Synchronize `strings.json` and `translations/en.json`.

---

### Task 2: Options Flow Hub Menu & Category Handlers
**Files:**
- Modify: `custom_components/google_home_bt_proxy/config_flow.py`

- [ ] Update `GoogleHomeBtProxyOptionsFlowHandler`:
  - Update `async_step_init`:
    - Display menu via `self.async_show_menu(step_id="init", menu_options=["scanning", "playback", "signal_processing", "filtering", "speaker_overrides"])`.
  - Implement `async_step_scanning`:
    - Schema: `CONF_BERMUDA_MODE`, `CONF_FILTER_PEER_PROXIES`, `CONF_ORCHESTRATION_MODE`, `CONF_SCAN_TIMEOUT`, `CONF_SCAN_INTERVAL`.
    - Updates options and redirects to `async_step_init` or creates entry.
  - Implement `async_step_playback`:
    - Schema: `CONF_PLAYBACK_MODE`, `CONF_PLAYING_SCAN_TIMEOUT`, `CONF_PLAYING_SCAN_INTERVAL`, `CONF_MAX_PLAYING_SKIP_DURATION`.
  - Implement `async_step_signal_processing`:
    - Check if `bermuda_mode` is enabled (from options or speaker overrides).
    - If `bermuda_mode` is True: render informational acknowledgement step without editable RF fields.
    - If `bermuda_mode` is False: render editable fields (`CONF_RSSI_OFFSET`, `CONF_ENABLE_RSSI_SMOOTHING`, `CONF_RSSI_FILTER_MODE`, `CONF_RSSI_FILTER_WINDOW`, `CONF_ENABLE_DISTANCE_ESTIMATION`, `CONF_MAX_DISTANCE`, `CONF_REF_POWER`, `CONF_PATH_LOSS_EXPONENT`).
  - Implement `async_step_filtering`:
    - Schema: `CONF_FILTER_MODE`, `CONF_TRACKED_DEVICES`, `CONF_RSSI_THRESHOLD`, `CONF_KNOWN_IRKS`.
  - Implement `async_step_speaker_overrides`:
    - Dropdown to select a speaker, then sub-menu or tailored form for speaker-level overrides.

---

### Task 3: Test Suite Updates & Validation
**Files:**
- Modify: `tests/test_config_flow.py`
- Modify: `tests/test_bermuda_compatibility.py`

- [ ] Test `async_step_init` menu generation.
- [ ] Test `async_step_scanning` save and options update.
- [ ] Test `async_step_playback` save.
- [ ] Test `async_step_signal_processing`:
  - Bermuda Mode enabled -> informational notice rendered, RF inputs omitted.
  - Bermuda Mode disabled -> editable RF inputs presented and saved.
- [ ] Test `async_step_filtering` save.
- [ ] Test `async_step_speaker_overrides` flow.
- [ ] Run full pytest suite with `--cov-fail-under=80`.

---

### Task 4: Git Commit, Push & Pull Request Creation
- [ ] Run `python3 scripts/verify_release.py`.
- [ ] Run `uv run ruff check .` and `uv run ruff format --check .`.
- [ ] Run `uv run pytest`.
- [ ] Commit all changes atomically.
- [ ] Push branch `feature/options-menu-bermuda-ux` to origin.
- [ ] Create Pull Request using `gh pr create` (Do NOT merge yet, per user instruction).
