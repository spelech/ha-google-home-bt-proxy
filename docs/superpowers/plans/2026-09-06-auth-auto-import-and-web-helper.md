# Authentication Auto-Import and Web-Helper Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement zero-click auto-import from existing `ha-google-home` installations and automated Web-Helper browser integration for standalone users to eliminate manual DevTools token handling.

**Architecture:**
1. **Auto-Import**: Config flow checks `hass.config_entries.async_entries("google_home")` for existing `master_token` / `username` / `android_id` and offers 1-click import.
2. **OAuth Exchange Engine**: Built-in support for exchanging single-use `oauth_token` (`oauth2_4/...`) into permanent `master_token` (`aas_et/...`) via `gpsoauth.exchange_token()`.
3. **Web-Helper HA Callback API**: HTTP endpoint at `/api/google_home_bt_proxy/auth_callback` that accepts tokens from browser extensions or web helpers and auto-advances active config flows.
4. **Browser Extension Web-Helper**: Lightweight Manifest V3 extension to intercept `HttpOnly` `oauth_token` on `accounts.google.com/EmbeddedSetup` and post it to Home Assistant automatically.
5. **Standalone Auth Helper CLI**: Script in `scripts/auth_helper.py` for token verification and manual exchange outside HA.

**Tech Stack:** Python 3.14, Home Assistant Core (`config_entries`, `http.HomeAssistantView`), `gpsoauth`, `glocaltokens`, Chrome Manifest V3 Extension.

---

### Task 1: Auto-Import from Existing ha-google-home Integration
**Files:**
- Modify: `custom_components/google_home_bt_proxy/config_flow.py`
- Modify: `tests/test_config_flow.py`

- [ ] **Step 1: Write tests for auto-import detection and import flow**
- [ ] **Step 2: Implement `async_step_user` check for `google_home` entries and `async_step_import_existing`**
- [ ] **Step 3: Run pytest on `tests/test_config_flow.py` and verify all tests pass**
- [ ] **Step 4: Commit as `feat(auth): add auto-import from existing ha-google-home integration`**

---

### Task 2: In-Integration OAuth Token Exchange
**Files:**
- Modify: `custom_components/google_home_bt_proxy/const.py`
- Modify: `custom_components/google_home_bt_proxy/config_flow.py`
- Modify: `tests/test_config_flow.py`

- [ ] **Step 1: Write tests for exchanging `oauth_token` via `gpsoauth.exchange_token`**
- [ ] **Step 2: Add `CONF_OAUTH_TOKEN` and exchange logic in `_validate_credentials`**
- [ ] **Step 3: Run pytest and verify token exchange flow**
- [ ] **Step 4: Commit as `feat(auth): support direct oauth_token exchange in config flow`**

---

### Task 3: Home Assistant Auth Callback View
**Files:**
- Create: `custom_components/google_home_bt_proxy/auth_view.py`
- Modify: `custom_components/google_home_bt_proxy/__init__.py`
- Create: `tests/test_auth_view.py`

- [x] **Step 1: Write tests for `/api/google_home_bt_proxy/auth_callback` POST and GET handling**
- [x] **Step 2: Implement `GoogleHomeBtProxyAuthCallbackView` registering in `__init__.py`**
- [x] **Step 3: Run pytest on `tests/test_auth_view.py`**
- [x] **Step 4: Commit as `feat(auth): add HTTP callback view for automated web-helper auth`**

---

### Task 4: Web-Helper Browser Extension
**Files:**
- Create: `extensions/google_home_auth_extension/manifest.json`
- Create: `extensions/google_home_auth_extension/background.js`
- Create: `extensions/google_home_auth_extension/popup.html`
- Create: `extensions/google_home_auth_extension/popup.js`
- Create: `extensions/google_home_auth_extension/README.md`

- [x] **Step 1: Create Manifest V3 extension structure with cookies and host permissions**
- [x] **Step 2: Implement cookie listener for `oauth_token` on `accounts.google.com`**
- [x] **Step 3: Implement popup UI for configuring HA URL and Flow ID**
- [x] **Step 4: Commit as `feat(extension): add Manifest V3 web-helper browser extension`**

---

### Task 5: Standalone Auth Helper CLI
**Files:**
- Create: `scripts/auth_helper.py`
- Create: `tests/test_auth_helper.py`

- [x] **Step 1: Write tests for `scripts/auth_helper.py`**
- [x] **Step 2: Implement CLI with `exchange` and `verify` commands**
- [x] **Step 3: Run pytest on `tests/test_auth_helper.py`**
- [x] **Step 4: Commit as `feat(scripts): add standalone auth_helper CLI`**

---

### Task 6: Full Quality Gate & PR Creation
- [ ] **Step 1: Run `uv run ruff check .` and `uv run ruff format --check .`**
- [ ] **Step 2: Run `uv run mypy custom_components`**
- [ ] **Step 3: Run `uv run pytest` across entire suite**
- [ ] **Step 4: Push branch to `origin/feat/auth-auto-import-and-web-helper`**
- [ ] **Step 5: Create Pull Request with GitHub CLI (`gh pr create`)**
