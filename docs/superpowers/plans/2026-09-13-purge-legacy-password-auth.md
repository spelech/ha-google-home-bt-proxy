# Purge Legacy Password Plumbing & Harden Master Token Auth Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminate obsolete password plumbing and dead fallbacks across the integration, harden `GLocalAuthenticationTokens` instantiation with `password=""` to work around upstream `glocaltokens` defects, clean up legacy config entry data, and add comprehensive unit test coverage.

**Architecture:** Remove `password` arguments from `GoogleHomeProxyCoordinator`, hardcode `password=""` when constructing `GLocalAuthenticationTokens` in `coordinator.py` and `scripts/auth_helper.py`, remove dead password branches from `config_flow.py`, and automatically prune `CONF_PASSWORD` from existing config entries during `async_setup_entry`.

**Tech Stack:** Python 3.12+, Home Assistant core components, `glocaltokens>=0.7.6`, `gpsoauth`, `pytest`, `pytest-asyncio`, `ruff`.

## Global Constraints

- Never break or alter the two working auth methods (Auto-Import from `ha-google-home` and `EmbeddedSetup` cookie exchange).
- `GLocalAuthenticationTokens` must always receive `password=""` (not `None` or omitted) to bypass `glocaltokens`'s early exit in `get_master_token()`.
- Maintain $\ge 80\%$ test coverage across `custom_components/google_home_bt_proxy`.
- Pass all 4 CI quality gates (Manifest & link integrity, Ruff lint & format, Pytest coverage $\ge 80\%$, CodeQL security).

---

### Task 1: Harden Coordinator and Eliminate Password Parameter

**Files:**
- Modify: `custom_components/google_home_bt_proxy/coordinator.py:95-118`
- Test: `tests/test_coordinator.py`

**Interfaces:**
- Consumes: `hass: HomeAssistant`, `username: str | None`, `master_token: str | None`, `android_id: str | None`, `zeroconf_instance: Zeroconf | None`.
- Produces: `GoogleHomeProxyCoordinator.__init__` signature without `password` parameter; initializes `GLocalAuthenticationTokens` with `password=""`.

- [ ] **Step 1: Write the failing unit tests in `tests/test_coordinator.py`**

```python
def test_coordinator_initializes_glocaltokens_with_empty_password_and_master_token():
    """Verify coordinator passes empty string password to glocaltokens to work around upstream check."""
    mock_hass = MagicMock()
    coordinator = GoogleHomeProxyCoordinator(
        hass=mock_hass,
        username="test@example.com",
        master_token="aas_et/test_valid_master_token_format_1234567890",
        android_id="android_id_123",
    )

    assert coordinator._client.username == "test@example.com"
    assert coordinator._client.password == ""
    assert coordinator._client.master_token == "aas_et/test_valid_master_token_format_1234567890"
    # Verify glocaltokens get_master_token returns master_token without "Username and password are not set" error
    assert coordinator._client.get_master_token() == "aas_et/test_valid_master_token_format_1234567890"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_coordinator.py -k "test_coordinator_initializes_glocaltokens_with_empty_password_and_master_token" -v`  
Expected: FAIL with `AssertionError: assert None == ""` (or `get_master_token() == None`).

- [ ] **Step 3: Modify `coordinator.py`**

Remove `password` from `GoogleHomeProxyCoordinator.__init__`, remove `self._password`, and set `password=""` when initializing `GLocalAuthenticationTokens`:

```python
    def __init__(
        self,
        hass: HomeAssistant,
        username: str | None = None,
        master_token: str | None = None,
        android_id: str | None = None,
        zeroconf_instance: Zeroconf | None = None,
    ) -> None:
        """Initialize coordinator."""
        self.hass = hass
        self._username = username
        self._master_token = master_token
        self._android_id = android_id
        self._zeroconf = zeroconf_instance
        # glocaltokens requires a non-None password string to avoid aborting early with
        # "Username and password are not set" in get_master_token(), even when master_token is present.
        self._client = GLocalAuthenticationTokens(
            username=username,
            password="",
            master_token=master_token,
            android_id=android_id,
            verbose=False,
        )
        self.speakers: dict[str, SpeakerNode] = {}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_coordinator.py -k "test_coordinator_initializes_glocaltokens_with_empty_password_and_master_token" -v`  
Expected: PASS.

- [ ] **Step 5: Commit changes**

```bash
git add custom_components/google_home_bt_proxy/coordinator.py tests/test_coordinator.py
git commit -m "fix(auth): normalize glocaltokens password to empty string and remove coordinator password param"
```

---

### Task 2: Update Setup Entry & Migrate Legacy Config Entries

**Files:**
- Modify: `custom_components/google_home_bt_proxy/__init__.py:108-118`
- Test: `tests/test_init.py`

**Interfaces:**
- Consumes: `entry: ConfigEntry`, `hass: HomeAssistant`.
- Produces: `async_setup_entry` cleans legacy `CONF_PASSWORD` from `entry.data` and instantiates `GoogleHomeProxyCoordinator` without `password`.

- [ ] **Step 1: Write the failing unit test in `tests/test_init.py`**

```python
@pytest.mark.asyncio
async def test_setup_entry_strips_legacy_password():
    """Verify that async_setup_entry strips CONF_PASSWORD from existing stored config entry data."""
    hass = MagicMock()
    entry = MagicMock()
    entry.data = {
        CONF_USERNAME: "user@example.com",
        CONF_PASSWORD: "legacy_secret_password",
        CONF_MASTER_TOKEN: "aas_et/valid_token",
        CONF_ANDROID_ID: "android_123",
    }
    entry.options = {}
    hass.config_entries.async_update_entry = MagicMock()

    # Stub dependencies
    with (
        patch("custom_components.google_home_bt_proxy.zeroconf.async_get_instance"),
        patch("custom_components.google_home_bt_proxy.GoogleHomeProxyCoordinator") as mock_coord_cls,
        patch("custom_components.google_home_bt_proxy.GoogleHomeApiClient"),
        patch("custom_components.google_home_bt_proxy.SpeakerPlaybackDetector"),
        patch("custom_components.google_home_bt_proxy.async_track_time_interval"),
    ):
        mock_coord = mock_coord_cls.return_value
        mock_coord.async_get_speakers = AsyncMock(return_value=[])

        from custom_components.google_home_bt_proxy import async_setup_entry
        res = await async_setup_entry(hass, entry)
        assert res is True

        # Verify entry.data was updated to strip CONF_PASSWORD
        hass.config_entries.async_update_entry.assert_called_once()
        updated_data = hass.config_entries.async_update_entry.call_args[1]["data"]
        assert CONF_PASSWORD not in updated_data

        # Verify coordinator was called without password
        call_kwargs = mock_coord_cls.call_args.kwargs
        assert "password" not in call_kwargs
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_init.py -k "test_setup_entry_strips_legacy_password" -v`  
Expected: FAIL.

- [ ] **Step 3: Update `custom_components/google_home_bt_proxy/__init__.py`**

In `async_setup_entry`:
1. Check if `CONF_PASSWORD in entry.data`. If so, copy `entry.data`, delete `CONF_PASSWORD`, and call `hass.config_entries.async_update_entry(entry, data=cleaned_data)`.
2. Remove `password=entry.data.get(CONF_PASSWORD)` from `GoogleHomeProxyCoordinator(...)`.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_init.py -k "test_setup_entry_strips_legacy_password" -v`  
Expected: PASS.

- [ ] **Step 5: Commit changes**

```bash
git add custom_components/google_home_bt_proxy/__init__.py tests/test_init.py
git commit -m "refactor(auth): strip legacy passwords on setup and drop coordinator password argument"
```

---

### Task 3: Remove Dead Password Handlers from Config Flow

**Files:**
- Modify: `custom_components/google_home_bt_proxy/config_flow.py`
- Test: `tests/test_config_flow.py`

**Interfaces:**
- Consumes: `user_input: dict[str, Any]`.
- Produces: `_validate_credentials` accepts only `oauth_token` (for exchange) or `master_token`; rejects credential sets without a token.

- [ ] **Step 1: Write failing/updated tests in `tests/test_config_flow.py`**

Replace legacy password-login test with:
```python
@pytest.mark.asyncio
async def test_validate_credentials_rejects_password_only_without_token():
    """Verify that supplying only username and password without a master or oauth token fails."""
    hass = MagicMock()
    flow = GoogleHomeProxyConfigFlow()
    flow.hass = hass

    user_input = {
        CONF_USERNAME: "user@example.com",
        CONF_PASSWORD: "secret_password",
    }
    valid = await flow._validate_credentials(user_input)
    assert valid is False
    assert CONF_MASTER_TOKEN not in user_input
```

- [ ] **Step 2: Run test to verify it fails or needs refactoring**

Run: `uv run pytest tests/test_config_flow.py -k "test_validate_credentials" -v`

- [ ] **Step 3: Modify `custom_components/google_home_bt_proxy/config_flow.py`**

1. Remove `clean_password` function.
2. In `_validate_credentials`:
   - Remove `clean_password` calls.
   - Remove `if username and password:` block that calls `client.get_master_token()`.
   - Ensure the only valid routes are `oauth_token` exchange via `gpsoauth.exchange_token` or direct `master_token`.
3. In `async_step_user`: if `CONF_PASSWORD` is somehow provided, pop it immediately.

- [ ] **Step 4: Run config flow tests to verify everything passes**

Run: `uv run pytest tests/test_config_flow.py -v`  
Expected: All tests pass.

- [ ] **Step 5: Commit changes**

```bash
git add custom_components/google_home_bt_proxy/config_flow.py tests/test_config_flow.py
git commit -m "refactor(config_flow): purge dead password login fallback and clean up token validation"
```

---

### Task 4: Fix `auth_helper.py` Standalone CLI

**Files:**
- Modify: `scripts/auth_helper.py:136-141`
- Test: `tests/test_auth_helper.py`

**Interfaces:**
- Consumes: CLI arguments `--email`, `--master-token`, `--android-id`.
- Produces: Constructs `GLocalAuthenticationTokens` with `password=""` to avoid upstream `glocaltokens` failure.

- [ ] **Step 1: Write failing unit test in `tests/test_auth_helper.py`**

```python
def test_verify_passes_empty_password_to_glocaltokens():
    """Verify that handle_verify initializes GLocalAuthenticationTokens with password=''."""
    with patch("scripts.auth_helper.GLocalAuthenticationTokens") as mock_auth_cls:
        mock_client = mock_auth_cls.return_value
        mock_client.get_access_token.return_value = "valid_token"
        mock_client.get_google_devices.return_value = []

        code = main(
            [
                "verify",
                "--email",
                "user@example.com",
                "--master-token",
                "aas_et/valid_token",
            ]
        )

        assert code == 0
        mock_auth_cls.assert_called_once_with(
            username="user@example.com",
            password="",
            master_token="aas_et/valid_token",
            android_id=mock_auth_cls.call_args.kwargs["android_id"],
        )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_auth_helper.py -k "test_verify_passes_empty_password" -v`  
Expected: FAIL because `password` is not in `mock_auth_cls.call_args.kwargs`.

- [ ] **Step 3: Modify `scripts/auth_helper.py`**

In `handle_verify`:
```python
        client = GLocalAuthenticationTokens(
            username=email,
            password="",  # glocaltokens requires a non-None password string to avoid aborting early
            master_token=master_token,
            android_id=android_id,
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_auth_helper.py -k "test_verify_passes_empty_password" -v`  
Expected: PASS.

- [ ] **Step 5: Commit changes**

```bash
git add scripts/auth_helper.py tests/test_auth_helper.py
git commit -m "fix(auth_helper): pass empty string password to glocaltokens during token verification"
```

---

### Task 5: Comprehensive Quality Gates & PR #16 Acknowledgement

**Files:**
- Test: Full repository test suite and linters

- [ ] **Step 1: Run Gate 1 (Release & Link Integrity)**
Run: `python3 scripts/verify_release.py --skip-tests --ci`  
Expected: SUCCESS.

- [ ] **Step 2: Run Gate 2 (Ruff Lint & Format)**
Run: `uv run ruff check . && uv run ruff format --check .`  
Expected: All checks pass.

- [ ] **Step 3: Run Gate 3 (Pytest Suite & Coverage $\ge 80\%$)**
Run: `uv run pytest --cov=custom_components/google_home_bt_proxy --cov-fail-under=80 -v`  
Expected: All 170+ tests pass with $\ge 80\%$ code coverage.

- [ ] **Step 4: Empirical Verification of Master Token Login with Real `glocaltokens`**
Run a standalone Python one-liner creating `coordinator._client` with a mock master token and asserting `coordinator._client.get_master_token()` returns the token without error logs.

- [ ] **Step 5: Review Comment on PR #16**
Post a review comment on PR #16 acknowledging `@rafal83`'s accurate diagnosis and linking the branch.
