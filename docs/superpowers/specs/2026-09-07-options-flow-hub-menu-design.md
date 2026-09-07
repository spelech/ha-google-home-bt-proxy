# Options Flow Hub Menu & Adaptive Bermuda Mode Design Specification

## Overview
This specification details the transition of the `ha-google-home-bt-proxy` Home Assistant Options Flow from a single 20+ field flat form into a structured, categorized Hub Menu (`async_show_menu`), combined with dynamic adaptive schema rules that automatically hide or annotate bypassed signal processing and RF calibration parameters when Bermuda Mode is enabled.

---

## 1. Requirements

### 1.1 Architectural & Flow Requirements
1. **Hub Menu Router (`async_step_init`)**:
   - When the user opens the integration options, render a clean Hub Menu:
     - `menu_options`:
       - `scanning`: ⏱️ Scanning & Bermuda Mode
       - `playback`: 🎵 Media Playback Handling
       - `signal_processing`: 📡 Signal Processing & RF (Adaptive)
       - `filtering`: 🔒 Target Filtering & IRK Resolvers
       - `speaker_overrides`: 🔊 Speaker-Specific Overrides
2. **Adaptive Bermuda Mode Handling (`async_step_signal_processing`)**:
   - When `bermuda_mode` is **True**:
     - Do NOT display editable fields for `rssi_offset`, `enable_rssi_smoothing`, `rssi_filter_mode`, `rssi_filter_window`, `enable_distance_estimation`, `max_distance`, `ref_power`, or `path_loss_exponent`.
     - Render an informational step with description text explaining:
       > "Bermuda Optimization Mode is active. Signal smoothing, hardware RSSI offsets, and distance modeling are managed natively by Bermuda to preserve peak velocity tracking. To configure antenna offsets, use Bermuda's Configure Scanner Offsets menu."
     - Form provides a single button / acknowledgement to return cleanly to the Hub Menu.
   - When `bermuda_mode` is **False**:
     - Render editable fields for standalone signal filtering and RF modeling.
3. **Dedicated Category Steps**:
   - `async_step_scanning`: Mode toggles (`bermuda_mode`, `filter_peer_proxies`, `orchestration_mode`), idle scan durations (`scan_timeout`, `scan_interval`).
   - `async_step_playback`: Mode (`playback_mode`), playing scan timings (`playing_scan_timeout`, `playing_scan_interval`, `max_playing_skip_duration`).
   - `async_step_filtering`: Whitelist modes (`filter_mode`, `tracked_devices`), RSSI cutoff (`rssi_threshold`), and `known_irks`.
   - `async_step_speaker_overrides`: Dropdown to select a speaker or reset overrides, then presents speaker-specific categorized settings.
4. **Data Persistence**:
   - Every category submission updates `config_entry.options` and redirects back to the menu router (`async_step_init`), allowing users to make multi-category adjustments without exiting or losing context.
5. **Localization / UI Text**:
   - Add all menu titles, step titles, field descriptions, and Bermuda informational notices to `custom_components/google_home_bt_proxy/strings.json` and `translations/en.json`.
6. **Testing & Quality**:
   - Maintain >= 90% test coverage on `config_flow.py`.
   - All 4 CI Quality Gates passing.
