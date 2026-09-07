import pathlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.config_entries import SOURCE_USER, ConfigEntries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.loader import async_setup as async_setup_loader

from custom_components.google_home_bt_proxy.config_flow import (
    GoogleHomeBtProxyConfigFlow,
    GoogleHomeBtProxyOptionsFlowHandler,
)
from custom_components.google_home_bt_proxy.const import (
    CONF_ANDROID_ID,
    CONF_MASTER_TOKEN,
    CONF_OAUTH_TOKEN,
    CONF_PASSWORD,
    CONF_RSSI_THRESHOLD,
    CONF_SCAN_INTERVAL,
    CONF_SCAN_TIMEOUT,
    CONF_USERNAME,
    DOMAIN,
)


@pytest.mark.asyncio
async def test_config_flow_success():
    flow = GoogleHomeBtProxyConfigFlow()
    flow.hass = AsyncMock()

    user_input = {
        CONF_MASTER_TOKEN: "valid-master-token",
        CONF_ANDROID_ID: "valid-android-id",
    }

    with patch.object(flow, "_validate_credentials", return_value=True):
        result = await flow.async_step_user(user_input)
        assert result["type"] == "create_entry"
        assert result["title"] == "Google Home Bluetooth Proxy"
        assert result["data"][CONF_MASTER_TOKEN] == "valid-master-token"


@pytest.mark.asyncio
async def test_config_flow_show_form():
    flow = GoogleHomeBtProxyConfigFlow()
    flow.hass = AsyncMock()

    result = await flow.async_step_user(None)
    assert result["type"] == "form"
    assert result["step_id"] == "user"


@pytest.mark.asyncio
async def test_config_flow_invalid_auth():
    flow = GoogleHomeBtProxyConfigFlow()
    flow.hass = AsyncMock()

    user_input = {
        CONF_MASTER_TOKEN: "invalid-token",
        CONF_ANDROID_ID: "invalid-android-id",
    }

    with patch.object(flow, "_validate_credentials", return_value=False):
        result = await flow.async_step_user(user_input)
        assert result["type"] == "form"
        assert result["step_id"] == "token"
        assert result["errors"] == {"base": "invalid_auth"}


@pytest.mark.asyncio
async def test_config_flow_exception():
    flow = GoogleHomeBtProxyConfigFlow()
    flow.hass = AsyncMock()

    user_input = {
        CONF_MASTER_TOKEN: "token",
        CONF_ANDROID_ID: "aid",
    }

    with patch.object(flow, "_validate_credentials", side_effect=RuntimeError("Connection failed")):
        result = await flow.async_step_user(user_input)
        assert result["type"] == "form"
        assert result["step_id"] == "user"
        assert result["errors"] == {"base": "cannot_connect"}


@pytest.mark.asyncio
async def test_validate_credentials_with_master_token():
    flow = GoogleHomeBtProxyConfigFlow()
    flow.hass = AsyncMock()

    user_input = {
        CONF_MASTER_TOKEN: "existing-master-token",
        CONF_ANDROID_ID: "aid",
    }
    assert await flow._validate_credentials(user_input) is True


@pytest.mark.asyncio
async def test_validate_credentials_with_credentials_success():
    flow = GoogleHomeBtProxyConfigFlow()
    mock_hass = MagicMock()
    mock_hass.async_add_executor_job = AsyncMock(return_value="obtained-master-token")
    flow.hass = mock_hass

    user_input = {
        CONF_USERNAME: "user@example.com",
        CONF_PASSWORD: "secret-password",
        CONF_ANDROID_ID: "aid",
    }
    patch_path = "custom_components.google_home_bt_proxy.config_flow.GLocalAuthenticationTokens"
    with patch(patch_path) as mock_tokens_cls:
        tokens_inst = mock_tokens_cls.return_value
        tokens_inst.get_master_token = MagicMock()
        assert await flow._validate_credentials(user_input) is True
        assert user_input[CONF_MASTER_TOKEN] == "obtained-master-token"
        assert CONF_PASSWORD not in user_input


@pytest.mark.asyncio
async def test_validate_credentials_with_credentials_failure():
    flow = GoogleHomeBtProxyConfigFlow()
    mock_hass = MagicMock()
    mock_hass.async_add_executor_job = AsyncMock(return_value=None)
    flow.hass = mock_hass

    user_input = {
        CONF_USERNAME: "user@example.com",
        CONF_PASSWORD: "wrong-password",
    }
    assert await flow._validate_credentials(user_input) is False


@pytest.mark.asyncio
async def test_options_flow():
    mock_entry = MagicMock()
    mock_entry.options = {
        CONF_SCAN_TIMEOUT: 5,
        CONF_SCAN_INTERVAL: 10,
        CONF_RSSI_THRESHOLD: -90,
    }

    options_flow = GoogleHomeBtProxyConfigFlow.async_get_options_flow(mock_entry)
    assert isinstance(options_flow, GoogleHomeBtProxyOptionsFlowHandler)

    # Show form
    form_result = await options_flow.async_step_init(None)
    assert form_result["type"] == "form"
    assert form_result["step_id"] == "init"

    # Submit form
    user_input = {
        CONF_SCAN_TIMEOUT: 10,
        CONF_SCAN_INTERVAL: 20,
        CONF_RSSI_THRESHOLD: -75,
    }
    create_result = await options_flow.async_step_init(user_input)
    assert create_result["type"] == "create_entry"
    assert create_result["data"] == user_input


@pytest.mark.asyncio
async def test_options_flow_with_playback_settings():
    """Verify options flow accepts playback mode and timing settings."""
    from custom_components.google_home_bt_proxy.const import (
        CONF_MAX_PLAYING_SKIP_DURATION,
        CONF_PLAYBACK_MODE,
        CONF_PLAYING_SCAN_INTERVAL,
        CONF_PLAYING_SCAN_TIMEOUT,
        CONF_RSSI_OFFSET,
        MODE_SKIP_CEILING,
    )

    mock_entry = MagicMock()
    mock_entry.options = {}
    handler = GoogleHomeBtProxyOptionsFlowHandler(mock_entry)

    # Show form and verify schema includes new fields
    form_result = await handler.async_step_init(None)
    assert form_result["type"] == "form"
    schema_keys = [k.schema for k in form_result["data_schema"].schema.keys()]
    assert CONF_PLAYBACK_MODE in schema_keys
    assert CONF_PLAYING_SCAN_TIMEOUT in schema_keys
    assert CONF_PLAYING_SCAN_INTERVAL in schema_keys
    assert CONF_MAX_PLAYING_SKIP_DURATION in schema_keys
    assert CONF_RSSI_OFFSET in schema_keys

    # Submit form
    user_input = {
        CONF_PLAYBACK_MODE: MODE_SKIP_CEILING,
        CONF_PLAYING_SCAN_TIMEOUT: 3,
        CONF_PLAYING_SCAN_INTERVAL: 45,
        CONF_MAX_PLAYING_SKIP_DURATION: 180,
        CONF_RSSI_OFFSET: 4,
    }
    create_result = await handler.async_step_init(user_input)
    assert create_result["type"] == "create_entry"
    assert create_result["data"][CONF_PLAYBACK_MODE] == MODE_SKIP_CEILING
    assert create_result["data"][CONF_PLAYING_SCAN_TIMEOUT] == 3
    assert create_result["data"][CONF_PLAYING_SCAN_INTERVAL] == 45
    assert create_result["data"][CONF_MAX_PLAYING_SKIP_DURATION] == 180
    assert create_result["data"][CONF_RSSI_OFFSET] == 4


@pytest.mark.asyncio
async def test_options_flow_fallback_config_entry():
    handler = GoogleHomeBtProxyOptionsFlowHandler.__new__(GoogleHomeBtProxyOptionsFlowHandler)
    mock_entry = MagicMock()
    mock_hass = MagicMock()
    mock_hass.config_entries.async_get_known_entry.return_value = mock_entry
    handler.hass = mock_hass
    handler.handler = "test-entry-id"
    assert handler.config_entry == mock_entry


@pytest.mark.asyncio
async def test_config_flow_auto_import_existing_google_home_success():
    """Test auto-importing credentials from existing google_home integration."""
    repo_root = str(pathlib.Path(__file__).parent.parent)
    hass = HomeAssistant(repo_root)
    async_setup_loader(hass)
    hass.config_entries = ConfigEntries(hass, {})

    mock_entry = MagicMock()
    mock_entry.domain = "google_home"
    mock_entry.data = {
        CONF_MASTER_TOKEN: "aas_et/test",
        CONF_USERNAME: "test@gmail.com",
        CONF_ANDROID_ID: "12345",
    }
    hass.config_entries.async_entries = MagicMock(return_value=[mock_entry])

    with (
        patch("homeassistant.config_entries.async_process_deps_reqs", AsyncMock(return_value=True)),
        patch.object(hass.config_entries, "async_setup", return_value=True),
    ):
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "import_existing"
        assert result["description_placeholders"] == {"username": "test@gmail.com"}

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"import_credentials": True},
        )
        assert result2["type"] == FlowResultType.CREATE_ENTRY
        assert result2["title"] == "Google Home Bluetooth Proxy (Imported)"
        assert result2["data"] == mock_entry.data


@pytest.mark.asyncio
async def test_config_flow_auto_import_declined_falls_back_to_manual():
    """Test declining auto-import falls back to the manual user form."""
    repo_root = str(pathlib.Path(__file__).parent.parent)
    hass = HomeAssistant(repo_root)
    async_setup_loader(hass)
    hass.config_entries = ConfigEntries(hass, {})

    mock_entry = MagicMock()
    mock_entry.domain = "google_home"
    mock_entry.data = {
        CONF_MASTER_TOKEN: "aas_et/test",
        CONF_USERNAME: "test@gmail.com",
        CONF_ANDROID_ID: "12345",
    }
    hass.config_entries.async_entries = MagicMock(return_value=[mock_entry])

    with (
        patch("homeassistant.config_entries.async_process_deps_reqs", AsyncMock(return_value=True)),
        patch.object(hass.config_entries, "async_setup", return_value=True),
    ):
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "import_existing"

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"import_credentials": False},
        )
        assert result2["type"] == FlowResultType.FORM
        assert result2["step_id"] == "user"


@pytest.mark.asyncio
async def test_config_flow_auto_import_invalid_auth_falls_back_to_manual():
    """Test invalid credentials during auto-import falls back to manual form with error."""
    flow = GoogleHomeBtProxyConfigFlow()
    flow.hass = MagicMock()

    mock_entry = MagicMock()
    mock_entry.domain = "google_home"
    mock_entry.data = {
        CONF_MASTER_TOKEN: "aas_et/test",
        CONF_USERNAME: "test@gmail.com",
        CONF_ANDROID_ID: "12345",
    }
    flow.hass.config_entries.async_entries = MagicMock(return_value=[mock_entry])

    result = await flow.async_step_user(None)
    assert result["type"] == "form"
    assert result["step_id"] == "import_existing"

    with patch.object(flow, "_validate_credentials", return_value=False):
        result2 = await flow.async_step_import_existing({"import_credentials": True})
        assert result2["type"] == "form"
        assert result2["step_id"] == "user"
        assert result2["errors"] == {"base": "invalid_auth"}


@pytest.mark.asyncio
async def test_config_flow_auto_import_exception_falls_back_to_manual():
    """Test exception during auto-import validation falls back to manual form with error."""
    flow = GoogleHomeBtProxyConfigFlow()
    flow.hass = MagicMock()

    mock_entry = MagicMock()
    mock_entry.domain = "google_home"
    mock_entry.data = {
        CONF_MASTER_TOKEN: "aas_et/test",
        CONF_USERNAME: "test@gmail.com",
    }
    flow.hass.config_entries.async_entries = MagicMock(return_value=[mock_entry])

    result = await flow.async_step_user(None)
    assert result["type"] == "form"
    assert result["step_id"] == "import_existing"

    with patch.object(flow, "_validate_credentials", side_effect=RuntimeError("Connection failed")):
        result2 = await flow.async_step_import_existing({"import_credentials": True})
        assert result2["type"] == "form"
        assert result2["step_id"] == "user"
        assert result2["errors"] == {"base": "cannot_connect"}


@pytest.mark.asyncio
async def test_config_flow_oauth_token_exchange_success():
    """Test successful oauth token exchange into master token."""
    flow = GoogleHomeBtProxyConfigFlow()
    mock_hass = MagicMock()

    async def _mock_executor(func, *args):
        return func(*args)

    mock_hass.async_add_executor_job = AsyncMock(side_effect=_mock_executor)
    flow.hass = mock_hass

    user_input = {
        CONF_USERNAME: "user@gmail.com",
        CONF_OAUTH_TOKEN: "oauth2_4/test_token",
    }
    with patch(
        "custom_components.google_home_bt_proxy.config_flow.gpsoauth.exchange_token",
        return_value={"Token": "aas_et/generated_master_token"},
    ) as mock_exchange:
        result = await flow.async_step_user(user_input)
        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["data"][CONF_MASTER_TOKEN] == "aas_et/generated_master_token"
        assert CONF_OAUTH_TOKEN not in result["data"]
        assert result["data"][CONF_USERNAME] == "user@gmail.com"
        assert CONF_ANDROID_ID in result["data"]
        mock_exchange.assert_called_once()


@pytest.mark.asyncio
async def test_config_flow_oauth_token_in_master_token_field():
    """Test oauth token pasted into master_token field is auto-detected and exchanged."""
    flow = GoogleHomeBtProxyConfigFlow()
    mock_hass = MagicMock()

    async def _mock_executor(func, *args):
        return func(*args)

    mock_hass.async_add_executor_job = AsyncMock(side_effect=_mock_executor)
    flow.hass = mock_hass

    user_input = {
        CONF_USERNAME: "user@gmail.com",
        CONF_MASTER_TOKEN: "oauth2_4/test_token_in_master_field",
    }
    with patch(
        "custom_components.google_home_bt_proxy.config_flow.gpsoauth.exchange_token",
        return_value={"Token": "aas_et/generated_master_token"},
    ) as mock_exchange:
        result = await flow.async_step_user(user_input)
        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["data"][CONF_MASTER_TOKEN] == "aas_et/generated_master_token"
        assert CONF_OAUTH_TOKEN not in result["data"]
        assert result["data"][CONF_USERNAME] == "user@gmail.com"
        assert CONF_ANDROID_ID in result["data"]
        mock_exchange.assert_called_once()


@pytest.mark.asyncio
async def test_config_flow_oauth_token_exchange_failure():
    """Test failed oauth token exchange shows invalid_auth."""
    flow = GoogleHomeBtProxyConfigFlow()
    mock_hass = MagicMock()

    async def _mock_executor(func, *args):
        return func(*args)

    mock_hass.async_add_executor_job = AsyncMock(side_effect=_mock_executor)
    flow.hass = mock_hass

    user_input = {
        CONF_USERNAME: "user@gmail.com",
        CONF_OAUTH_TOKEN: "invalid_token",
    }
    with patch(
        "custom_components.google_home_bt_proxy.config_flow.gpsoauth.exchange_token",
        return_value={"Error": "BadAuthentication"},
    ):
        result = await flow.async_step_user(user_input)
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "token"
        assert result["errors"] == {"base": "invalid_auth"}


@pytest.mark.asyncio
async def test_config_flow_oauth_token_missing_username():
    """Test oauth token without username shows invalid_auth."""
    flow = GoogleHomeBtProxyConfigFlow()
    flow.hass = MagicMock()

    user_input = {
        CONF_OAUTH_TOKEN: "oauth2_4/test_token",
    }
    result = await flow.async_step_user(user_input)
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "token"
    assert result["errors"] == {"base": "invalid_auth"}


def test_sanitize_token_formats():
    """Test sanitize_token properly cleans various user input and cookie formats."""
    from custom_components.google_home_bt_proxy.config_flow import sanitize_token

    # Standard raw tokens
    assert sanitize_token("oauth2_4/my_clean_token") == "oauth2_4/my_clean_token"
    assert sanitize_token("aas_et/my_master_token") == "aas_et/my_master_token"

    # With surrounding quotes
    assert sanitize_token('"oauth2_4/my_clean_token"') == "oauth2_4/my_clean_token"
    assert sanitize_token("'aas_et/my_master_token'") == "aas_et/my_master_token"

    # DevTools copy formats: oauth_token:"..." or oauth_token=...
    assert (
        sanitize_token('oauth_token:"oauth2_4/0ATsMZqAKzWeCE3ZmAZYkCiTQfVOc..."')
        == "oauth2_4/0ATsMZqAKzWeCE3ZmAZYkCiTQfVOc..."
    )
    assert (
        sanitize_token('oauth_token: "oauth2_4/0ATsMZqAKzWeCE3ZmAZYkCiTQfVOc..."')
        == "oauth2_4/0ATsMZqAKzWeCE3ZmAZYkCiTQfVOc..."
    )
    assert (
        sanitize_token("oauth_token=oauth2_4/token123; path=/; domain=.google.com")
        == "oauth2_4/token123"
    )
    assert sanitize_token('master_token: "aas_et/my_token"') == "aas_et/my_token"

    # Empty / None handling
    assert sanitize_token("") == ""
    assert sanitize_token(None) == ""  # type: ignore[arg-type]


def test_clean_string_and_clean_password():
    """Test clean_string strips zero-width chars and clean_password strips App Password spacing."""
    from custom_components.google_home_bt_proxy.config_flow import (
        clean_password,
        clean_string,
    )

    # Invisible characters: \u200b (zero-width space), \ufeff (BOM), \u200e (LTR), \u200d (ZWJ)
    dirty_email = " \u200buser@gmail.com\ufeff "
    assert clean_string(dirty_email) == "user@gmail.com"

    dirty_token = "\u200eoauth2_4/my_secret_token\u200d\u2060"
    assert clean_string(dirty_token) == "oauth2_4/my_secret_token"

    # None and empty handling
    assert clean_string("") == ""
    assert clean_string(None) == ""

    # Google App Password formatting: 16 chars grouped in 4s with spaces
    app_pwd = " abcd efgh ijkl mnop "
    assert clean_password(app_pwd) == "abcdefghijklmnop"

    # App Password with zero-width spaces inside or around
    dirty_app_pwd = "\u200babcd efgh\u200b ijkl mnop\ufeff"
    assert clean_password(dirty_app_pwd) == "abcdefghijklmnop"

    # Normal password with words should NOT be stripped of internal spaces
    regular_pwd_with_spaces = "my secret password phrase"
    assert clean_password(regular_pwd_with_spaces) == "my secret password phrase"


@pytest.mark.asyncio
async def test_validate_credentials_cleans_all_inputs():
    """Verify _validate_credentials cleans whitespace, zero-width chars, and app password spaces."""
    flow = GoogleHomeBtProxyConfigFlow()
    flow.hass = MagicMock()

    user_input = {
        CONF_USERNAME: " \u200buser@gmail.com \ufeff",
        CONF_MASTER_TOKEN: ' \u200e master_token: "aas_et/secret_master" \u200d ',
        CONF_ANDROID_ID: " 0a48ee4bd1bb6222 ",
    }

    result = await flow._validate_credentials(user_input)
    assert result is True
    assert user_input[CONF_USERNAME] == "user@gmail.com"
    assert user_input[CONF_MASTER_TOKEN] == "aas_et/secret_master"
    assert user_input[CONF_ANDROID_ID] == "0a48ee4bd1bb6222"


@pytest.mark.asyncio
async def test_config_flow_step_token_success_with_devtools_format():
    """Test step_token cleans devtools format cookie and creates entry."""
    flow = GoogleHomeBtProxyConfigFlow()
    flow._email = "user@gmail.com"
    mock_hass = MagicMock()

    async def _mock_executor(func, *args):
        return func(*args)

    mock_hass.async_add_executor_job = AsyncMock(side_effect=_mock_executor)
    flow.hass = mock_hass

    user_input = {
        CONF_USERNAME: "user@gmail.com",
        CONF_MASTER_TOKEN: 'oauth_token:"oauth2_4/0ATsMZqAKzWeCE3ZmAZYkCiTQfVOc..."',
    }
    with patch(
        "custom_components.google_home_bt_proxy.config_flow.gpsoauth.exchange_token",
        return_value={"Token": "aas_et/exchanged_token"},
    ) as mock_exchange:
        result = await flow.async_step_token(user_input)
        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["data"][CONF_MASTER_TOKEN] == "aas_et/exchanged_token"
        assert result["data"][CONF_USERNAME] == "user@gmail.com"
        mock_exchange.assert_called_once_with(
            "user@gmail.com",
            "oauth2_4/0ATsMZqAKzWeCE3ZmAZYkCiTQfVOc...",
            mock_exchange.call_args[0][2],
        )


@pytest.mark.asyncio
async def test_config_flow_step_token_failure_reshows_token_step():
    """Test step_token failure re-displays the token form with errors."""
    flow = GoogleHomeBtProxyConfigFlow()
    flow._email = "user@gmail.com"
    mock_hass = MagicMock()

    async def _mock_executor(func, *args):
        return func(*args)

    mock_hass.async_add_executor_job = AsyncMock(side_effect=_mock_executor)
    flow.hass = mock_hass

    user_input = {
        CONF_USERNAME: "user@gmail.com",
        CONF_MASTER_TOKEN: "oauth2_4/bad_token",
    }
    with patch(
        "custom_components.google_home_bt_proxy.config_flow.gpsoauth.exchange_token",
        return_value={"Error": "BadAuthentication"},
    ):
        result = await flow.async_step_token(user_input)
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "token"
        assert result["errors"] == {"base": "invalid_auth"}
        # Verify schema only has username and master_token (no password)
        schema_keys = [k.schema for k in result["data_schema"].schema.keys()]
        assert CONF_USERNAME in schema_keys
        assert CONF_MASTER_TOKEN in schema_keys
        assert CONF_PASSWORD not in schema_keys


@pytest.mark.asyncio
async def test_options_flow_speaker_overrides():
    """Verify selecting a speaker advances to speaker settings and saves overrides."""
    from custom_components.google_home_bt_proxy.const import (
        CONF_CUSTOM_SETTINGS,
        CONF_SCAN_INTERVAL,
        CONF_SCAN_TIMEOUT,
        CONF_SELECTED_SPEAKER,
        CONF_SPEAKER_OVERRIDES,
        DOMAIN,
    )
    from custom_components.google_home_bt_proxy.models import SpeakerNode

    mock_entry = MagicMock()
    mock_entry.entry_id = "test-options-speakers"
    mock_entry.options = {}

    speaker1 = SpeakerNode(
        device_id="spk-office",
        name="Office Mini",
        ip_address="192.168.1.10",
        auth_token="token-1",
        hardware="Google Home Mini",
    )
    mock_coord = MagicMock()
    mock_coord.speakers = {"spk-office": speaker1}

    mock_hass = MagicMock()
    mock_hass.data = {
        DOMAIN: {
            "test-options-speakers": {
                "coordinator": mock_coord,
            }
        }
    }

    handler = GoogleHomeBtProxyOptionsFlowHandler(mock_entry)
    handler.hass = mock_hass

    # 1. Initial step lists global + discovered speakers
    init_form = await handler.async_step_init(None)
    assert init_form["type"] == "form"
    assert CONF_SELECTED_SPEAKER in [k.schema for k in init_form["data_schema"].schema.keys()]

    # 2. Select spk-office -> transitions to speaker_settings step
    select_result = await handler.async_step_init({CONF_SELECTED_SPEAKER: "spk-office"})
    assert select_result["type"] == "form"
    assert select_result["step_id"] == "speaker_settings"

    # 3. Submit custom overrides for spk-office
    speaker_input = {
        CONF_CUSTOM_SETTINGS: True,
        CONF_SCAN_INTERVAL: 45,
        CONF_SCAN_TIMEOUT: 8,
    }
    save_result = await handler.async_step_speaker_settings(speaker_input)
    assert save_result["type"] == "create_entry"
    assert CONF_SPEAKER_OVERRIDES in save_result["data"]
    assert "spk-office" in save_result["data"][CONF_SPEAKER_OVERRIDES]
    assert save_result["data"][CONF_SPEAKER_OVERRIDES]["spk-office"][CONF_SCAN_INTERVAL] == 45
    assert save_result["data"][CONF_SPEAKER_OVERRIDES]["spk-office"][CONF_SCAN_TIMEOUT] == 8

    # 4. Now test removing overrides (unchecking custom_settings)
    mock_entry.options = save_result["data"]
    handler2 = GoogleHomeBtProxyOptionsFlowHandler(mock_entry)
    handler2.hass = mock_hass
    handler2._selected_speaker = "spk-office"

    remove_input = {
        CONF_CUSTOM_SETTINGS: False,
    }
    remove_result = await handler2.async_step_speaker_settings(remove_input)
    assert remove_result["type"] == "create_entry"
    assert "spk-office" not in remove_result["data"][CONF_SPEAKER_OVERRIDES]


@pytest.mark.asyncio
async def test_options_flow_signal_processing_and_orchestration():
    """Verify options flow allows configuring signal processing and orchestration settings."""
    from custom_components.google_home_bt_proxy.const import (
        CONF_ENABLE_DISTANCE_ESTIMATION,
        CONF_ENABLE_RSSI_SMOOTHING,
        CONF_FILTER_MODE,
        CONF_MAX_DISTANCE,
        CONF_ORCHESTRATION_MODE,
        CONF_PATH_LOSS_EXPONENT,
        CONF_REF_POWER,
        CONF_RSSI_FILTER_MODE,
        CONF_RSSI_FILTER_WINDOW,
        CONF_SELECTED_SPEAKER,
        CONF_TRACKED_DEVICES,
        FILTER_MODE_WHITELIST,
        GLOBAL_SETTINGS,
        ORCHESTRATION_INDEPENDENT,
        RSSI_FILTER_EMA,
    )

    mock_entry = MagicMock()
    mock_entry.options = {}
    mock_entry.entry_id = "entry-opt-signal"

    handler = GoogleHomeBtProxyOptionsFlowHandler(mock_entry)
    mock_hass = MagicMock()
    mock_hass.data = {DOMAIN: {"entry-opt-signal": {}}}
    handler.hass = mock_hass

    # 1. Check form schema includes signal processing keys
    form = await handler.async_step_init(None)
    schema_keys = [k.schema for k in form["data_schema"].schema.keys()]
    assert CONF_ORCHESTRATION_MODE in schema_keys
    assert CONF_FILTER_MODE in schema_keys
    assert CONF_TRACKED_DEVICES in schema_keys
    assert CONF_ENABLE_RSSI_SMOOTHING in schema_keys
    assert CONF_RSSI_FILTER_MODE in schema_keys
    assert CONF_RSSI_FILTER_WINDOW in schema_keys
    assert CONF_ENABLE_DISTANCE_ESTIMATION in schema_keys
    assert CONF_MAX_DISTANCE in schema_keys
    assert CONF_REF_POWER in schema_keys
    assert CONF_PATH_LOSS_EXPONENT in schema_keys

    # 2. Save global signal options
    global_payload = {
        CONF_SELECTED_SPEAKER: GLOBAL_SETTINGS,
        CONF_ORCHESTRATION_MODE: ORCHESTRATION_INDEPENDENT,
        CONF_FILTER_MODE: FILTER_MODE_WHITELIST,
        CONF_TRACKED_DEVICES: "AA:BB:CC,Beacon",
        CONF_ENABLE_RSSI_SMOOTHING: False,
        CONF_RSSI_FILTER_MODE: RSSI_FILTER_EMA,
        CONF_RSSI_FILTER_WINDOW: 5,
        CONF_ENABLE_DISTANCE_ESTIMATION: False,
        CONF_MAX_DISTANCE: 7.5,
        CONF_REF_POWER: -62,
        CONF_PATH_LOSS_EXPONENT: 2.8,
    }
    result = await handler.async_step_init(global_payload)
    assert result["type"] == "create_entry"
    assert result["data"][CONF_ORCHESTRATION_MODE] == ORCHESTRATION_INDEPENDENT
    assert result["data"][CONF_FILTER_MODE] == FILTER_MODE_WHITELIST
    assert result["data"][CONF_TRACKED_DEVICES] == "AA:BB:CC,Beacon"
    assert result["data"][CONF_ENABLE_RSSI_SMOOTHING] is False
    assert result["data"][CONF_RSSI_FILTER_MODE] == RSSI_FILTER_EMA
    assert result["data"][CONF_RSSI_FILTER_WINDOW] == 5
    assert result["data"][CONF_ENABLE_DISTANCE_ESTIMATION] is False
    assert result["data"][CONF_MAX_DISTANCE] == 7.5
    assert result["data"][CONF_REF_POWER] == -62
    assert result["data"][CONF_PATH_LOSS_EXPONENT] == 2.8
