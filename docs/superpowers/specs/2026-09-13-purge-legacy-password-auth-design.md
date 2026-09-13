# Design Specification: Purge Legacy Password Plumbing & Harden Master Token Auth

**Date:** 2026-09-13  
**Status:** Approved  
**Author:** Pair programmed (Steven & Antigravity)  
**Branch:** `refactor/purge-legacy-password-auth`  

---

## 1. Context & Motivation

Google deprecated and blocked password/App Password based automated OAuth authentication (`gpsoauth` master login) years ago, resulting in `BadAuthentication` errors for automated tools.

In this integration, only two authentication methods are supported:
1. **Auto-Import**: Importing existing `master_token` (`aas_et/...`) and `username` from an existing `ha-google-home` installation.
2. **EmbeddedSetup Cookie Extraction**: Extracting a one-time `oauth_token` (`oauth2_4/...`) from `https://accounts.google.com/EmbeddedSetup` and exchanging it via `gpsoauth.exchange_token` for an `aas_et/...` master token.

Neither flow requires, prompts for, or persists a password. The configuration flow UI schema only prompts for `CONF_USERNAME` and `CONF_MASTER_TOKEN`.

However, obsolete password plumbing remained throughout `coordinator.py`, `__init__.py`, `config_flow.py`, and `scripts/auth_helper.py`. When `password=None` is passed down, an upstream defect in `glocaltokens.client.GLocalAuthenticationTokens.get_master_token()` triggers:
```python
if self.username is None or self.password is None:
    LOGGER.error("Username and password are not set.")
    return None
```
Because `self.password is None` is evaluated before checking whether `self.master_token` is already provided, `get_master_token()` returns `None`, breaking token retrieval and speaker discovery. Furthermore, `scripts/auth_helper.py` omits `password`, causing the exact same defect when validating master tokens.

External contributor `@rafal83` submitted PR #16 proposing `password=password or ""` in `coordinator.py`. Rather than simply patching one line while retaining dead code, we are completely purging legacy password plumbing, hardening master token instantiation, updating tests, and crediting PR #16.

---

## 2. Goals & Non-Goals

### Goals
- Completely remove dead password parameters, fields, and login fallbacks across the integration runtime.
- Guarantee that `GLocalAuthenticationTokens` receives `password=""` across all instantiation sites (`coordinator.py` and `scripts/auth_helper.py`) with documented rationales for the upstream workaround.
- Automatically strip any legacy `CONF_PASSWORD` from existing stored Home Assistant config entries on setup.
- Add regression unit tests verifying master token initialization without passwords.
- Maintain $\ge 80\%$ test coverage and pass all 4 CI Quality Gates.
- Acknowledge and credit PR #16 author.

### Non-Goals
- Modifying the external `glocaltokens` library directly inside this repository (an upstream issue/PR can be tracked separately).
- Changing the EmbeddedSetup token exchange workflow.

---

## 3. Detailed Technical Architecture

### 3.1 Coordinator (`custom_components/google_home_bt_proxy/coordinator.py`)
- Remove `password: str | None = None` parameter from `GoogleHomeProxyCoordinator.__init__`.
- Remove `self._password` instance variable.
- Instantiate `GLocalAuthenticationTokens` with `password=""`:
  ```python
  self._client = GLocalAuthenticationTokens(
      username=username,
      password="",  # Upstream glocaltokens requires a non-None password string to bypass early exit in get_master_token()
      master_token=master_token,
      android_id=android_id,
      verbose=False,
  )
  ```

### 3.2 Integration Setup & Storage Migration (`custom_components/google_home_bt_proxy/__init__.py`)
- In `async_setup_entry`:
  - Check if `CONF_PASSWORD` exists in `entry.data`. If present, update `entry.data` via `hass.config_entries.async_update_entry` to strip it out permanently.
  - Instantiate `GoogleHomeProxyCoordinator` without the `password` argument:
    ```python
    coordinator = GoogleHomeProxyCoordinator(
        hass=hass,
        username=entry.data.get(CONF_USERNAME),
        master_token=entry.data.get(CONF_MASTER_TOKEN),
        android_id=entry.data.get(CONF_ANDROID_ID),
        zeroconf_instance=zc,
    )
    ```

### 3.3 Config Flow (`custom_components/google_home_bt_proxy/config_flow.py`)
- In `_validate_credentials`:
  - Remove dead `if username and password:` block and `GLocalAuthenticationTokens` password-login fallback.
  - Require valid `oauth_token` (for exchange) or `master_token`. If only username/password is submitted without a token, reject credentials immediately.
  - Remove unused `clean_password` function.
- In `CONF_PASSWORD` references:
  - Keep `CONF_PASSWORD` in `const.py` for legacy entry data sanitization and migration checks.

### 3.4 Standalone Auth CLI (`scripts/auth_helper.py`)
- In `handle_verify`:
  - Instantiate `GLocalAuthenticationTokens` with `password=""`:
    ```python
    client = GLocalAuthenticationTokens(
        username=email,
        password="",  # glocaltokens requires non-None password to avoid 'Username and password are not set'
        master_token=master_token,
        android_id=android_id,
    )
    ```

### 3.5 Test Suite Updates
- `tests/test_coordinator.py`:
  - Verify `GoogleHomeProxyCoordinator` initializes `GLocalAuthenticationTokens` with `password=""` and succeeds in returning the master token when queried.
  - Ensure coordinator tests instantiate without `password`.
- `tests/test_config_flow.py`:
  - Remove obsolete tests that mocked password logins.
  - Add test asserting that attempting to supply only a username and password without a master/oauth token fails validation.
  - Add test verifying that legacy entries with `CONF_PASSWORD` are cleaned up on entry setup.
- `tests/test_auth_helper.py`:
  - Update tests to verify `password=""` is passed to `GLocalAuthenticationTokens` in `handle_verify`.

---

## 4. Verification Plan

1. **Gate 1 - Release & Link Integrity**: `python3 scripts/verify_release.py --skip-tests --ci`
2. **Gate 2 - Ruff Lint & Format**: `uv run ruff check .` and `uv run ruff format --check .`
3. **Gate 3 - Pytest & Coverage**: `uv run pytest --cov=custom_components/google_home_bt_proxy --cov-fail-under=80 -v`
4. **Behavioral Verification**: Verify `coordinator` and `auth_helper` against real `GLocalAuthenticationTokens` classes to prove `get_master_token()` and `get_access_token()` do not throw `Username and password are not set`.
