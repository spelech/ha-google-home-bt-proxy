"""Tests for config_flow."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.google_home_bt_proxy.config_flow import (
    GoogleHomeBtProxyConfigFlow,
    GoogleHomeBtProxyOptionsFlowHandler,
)
from custom_components.google_home_bt_proxy.const import (
    CONF_ANDROID_ID,
    CONF_MASTER_TOKEN,
    CONF_PASSWORD,
    CONF_RSSI_THRESHOLD,
    CONF_SCAN_INTERVAL,
    CONF_SCAN_TIMEOUT,
    CONF_USERNAME,
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
        assert result["step_id"] == "user"
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
async def test_options_flow_fallback_config_entry():
    handler = GoogleHomeBtProxyOptionsFlowHandler.__new__(GoogleHomeBtProxyOptionsFlowHandler)
    mock_entry = MagicMock()
    mock_hass = MagicMock()
    mock_hass.config_entries.async_get_known_entry.return_value = mock_entry
    handler.hass = mock_hass
    handler.handler = "test-entry-id"
    assert handler.config_entry == mock_entry
