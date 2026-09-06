"""Tests for the Google Home Bluetooth Proxy HTTP Auth Callback View."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiohttp import web
from homeassistant.components.http.const import KEY_HASS
from homeassistant.core import HomeAssistant

from custom_components.google_home_bt_proxy import async_setup
from custom_components.google_home_bt_proxy.auth_view import GoogleHomeBtProxyAuthCallbackView
from custom_components.google_home_bt_proxy.const import (
    CONF_ANDROID_ID,
    CONF_MASTER_TOKEN,
    CONF_USERNAME,
)


@pytest.fixture
def mock_hass() -> MagicMock:
    """Mock Home Assistant instance."""
    hass = MagicMock(spec=HomeAssistant)
    hass.is_stopping = False
    hass.async_add_executor_job = AsyncMock(side_effect=lambda func, *args: func(*args))
    hass.config_entries = MagicMock()
    hass.config_entries.flow = MagicMock()
    hass.config_entries.flow.async_configure = AsyncMock()
    return hass


@pytest.fixture
async def auth_client(mock_hass: MagicMock, aiohttp_client: MagicMock) -> MagicMock:
    """Fixture providing a test client configured with GoogleHomeBtProxyAuthCallbackView."""
    app = web.Application()
    app[KEY_HASS] = mock_hass
    view = GoogleHomeBtProxyAuthCallbackView()
    view.register(mock_hass, app, app.router)
    return await aiohttp_client(app)


@pytest.mark.asyncio
async def test_post_auth_callback_success(auth_client: MagicMock, mock_hass: MagicMock) -> None:
    """Test POST auth callback with valid oauth_token and flow_id."""
    payload = {
        "oauth_token": "oauth2_4/valid_token",
        "email": "test@gmail.com",
        "flow_id": "test_flow_123",
        "android_id": "custom_android_id",
    }

    with patch(
        "custom_components.google_home_bt_proxy.auth_view.gpsoauth.exchange_token",
        return_value={"Token": "aas_et/test_master_token"},
    ) as mock_exchange:
        resp = await auth_client.post(
            "/api/google_home_bt_proxy/auth_callback",
            json=payload,
        )

        assert resp.status == 200
        data = await resp.json()
        assert data == {"status": "success", "master_token_acquired": True}

        mock_exchange.assert_called_once_with(
            "test@gmail.com", "oauth2_4/valid_token", "custom_android_id"
        )
        mock_hass.config_entries.flow.async_configure.assert_called_once_with(
            "test_flow_123",
            user_input={
                CONF_USERNAME: "test@gmail.com",
                CONF_MASTER_TOKEN: "aas_et/test_master_token",
                CONF_ANDROID_ID: "custom_android_id",
            },
        )


@pytest.mark.asyncio
async def test_post_auth_callback_with_username_and_generated_android_id(
    auth_client: MagicMock, mock_hass: MagicMock
) -> None:
    """Test POST auth callback using 'username' instead of 'email' and generated android_id."""
    payload = {
        "oauth_token": "oauth2_4/valid_token",
        "username": "user@example.com",
        "flow_id": "flow_456",
    }

    with (
        patch(
            "custom_components.google_home_bt_proxy.auth_view.GLocalAuthenticationTokens._generate_android_id",
            return_value="generated_aid_123",
        ),
        patch(
            "custom_components.google_home_bt_proxy.auth_view.gpsoauth.exchange_token",
            return_value={"Token": "aas_et/master_456"},
        ) as mock_exchange,
    ):
        resp = await auth_client.post(
            "/api/google_home_bt_proxy/auth_callback",
            json=payload,
        )

        assert resp.status == 200
        mock_exchange.assert_called_once_with(
            "user@example.com", "oauth2_4/valid_token", "generated_aid_123"
        )
        mock_hass.config_entries.flow.async_configure.assert_called_once_with(
            "flow_456",
            user_input={
                CONF_USERNAME: "user@example.com",
                CONF_MASTER_TOKEN: "aas_et/master_456",
                CONF_ANDROID_ID: "generated_aid_123",
            },
        )


@pytest.mark.asyncio
async def test_post_auth_callback_without_flow_id(
    auth_client: MagicMock, mock_hass: MagicMock
) -> None:
    """Test POST auth callback succeeds without flow_id and skips flow advancement."""
    payload = {
        "oauth_token": "oauth2_4/valid_token",
        "email": "test@gmail.com",
    }

    with patch(
        "custom_components.google_home_bt_proxy.auth_view.gpsoauth.exchange_token",
        return_value={"Token": "aas_et/master_token"},
    ):
        resp = await auth_client.post(
            "/api/google_home_bt_proxy/auth_callback",
            json=payload,
        )

        assert resp.status == 200
        data = await resp.json()
        assert data["status"] == "success"
        mock_hass.config_entries.flow.async_configure.assert_not_called()


@pytest.mark.asyncio
async def test_post_auth_callback_missing_parameters(auth_client: MagicMock) -> None:
    """Test POST auth callback missing required fields."""
    # Missing email
    resp1 = await auth_client.post(
        "/api/google_home_bt_proxy/auth_callback",
        json={"oauth_token": "token"},
    )
    assert resp1.status == 400
    assert (await resp1.json()) == {"error": "missing_parameters"}

    # Missing oauth_token
    resp2 = await auth_client.post(
        "/api/google_home_bt_proxy/auth_callback",
        json={"email": "test@gmail.com"},
    )
    assert resp2.status == 400
    assert (await resp2.json()) == {"error": "missing_parameters"}

    # Empty payload
    resp3 = await auth_client.post(
        "/api/google_home_bt_proxy/auth_callback",
        json={},
    )
    assert resp3.status == 400
    assert (await resp3.json()) == {"error": "missing_parameters"}

    # Non-json payload
    resp4 = await auth_client.post(
        "/api/google_home_bt_proxy/auth_callback",
        data="invalid-raw-body",
        headers={"Content-Type": "application/json"},
    )
    assert resp4.status == 400
    assert (await resp4.json()) == {"error": "missing_parameters"}


@pytest.mark.asyncio
async def test_post_auth_callback_invalid_token_response(auth_client: MagicMock) -> None:
    """Test POST auth callback when gpsoauth returns error dictionary."""
    payload = {
        "oauth_token": "oauth2_4/bad_token",
        "email": "test@gmail.com",
    }

    with patch(
        "custom_components.google_home_bt_proxy.auth_view.gpsoauth.exchange_token",
        return_value={"Error": "BadAuthentication"},
    ):
        resp = await auth_client.post(
            "/api/google_home_bt_proxy/auth_callback",
            json=payload,
        )

        assert resp.status == 401
        data = await resp.json()
        assert data["error"] == "invalid_oauth_token"
        assert data["details"] == {"Error": "BadAuthentication"}


@pytest.mark.asyncio
async def test_post_auth_callback_exchange_exception(auth_client: MagicMock) -> None:
    """Test POST auth callback when gpsoauth raises an exception."""
    payload = {
        "oauth_token": "oauth2_4/bad_token",
        "email": "test@gmail.com",
    }

    with patch(
        "custom_components.google_home_bt_proxy.auth_view.gpsoauth.exchange_token",
        side_effect=RuntimeError("Network error"),
    ):
        resp = await auth_client.post(
            "/api/google_home_bt_proxy/auth_callback",
            json=payload,
        )

        assert resp.status == 401
        data = await resp.json()
        assert data["error"] == "invalid_oauth_token"
        assert "Network error" in data["details"]


@pytest.mark.asyncio
async def test_post_auth_callback_config_flow_error_handled(
    auth_client: MagicMock, mock_hass: MagicMock
) -> None:
    """Test POST auth callback when async_configure raises an exception."""
    payload = {
        "oauth_token": "oauth2_4/valid_token",
        "email": "test@gmail.com",
        "flow_id": "stale_flow",
    }
    mock_hass.config_entries.flow.async_configure.side_effect = RuntimeError("Flow expired")

    with patch(
        "custom_components.google_home_bt_proxy.auth_view.gpsoauth.exchange_token",
        return_value={"Token": "aas_et/test_master_token"},
    ):
        resp = await auth_client.post(
            "/api/google_home_bt_proxy/auth_callback",
            json=payload,
        )

        assert resp.status == 200
        data = await resp.json()
        assert data == {"status": "success", "master_token_acquired": True}


@pytest.mark.asyncio
async def test_get_auth_callback_success(auth_client: MagicMock, mock_hass: MagicMock) -> None:
    """Test GET auth callback with query parameters."""
    with patch(
        "custom_components.google_home_bt_proxy.auth_view.gpsoauth.exchange_token",
        return_value={"Token": "aas_et/test_master_token"},
    ) as mock_exchange:
        resp = await auth_client.get(
            "/api/google_home_bt_proxy/auth_callback?oauth_token=oauth2_4/abc&email=test@gmail.com&flow_id=flow_789&android_id=my_aid"
        )

        assert resp.status == 200
        assert resp.content_type == "text/html"
        body = await resp.text()
        assert "Authentication Successful!" in body
        assert "You can close this window" in body

        mock_exchange.assert_called_once_with("test@gmail.com", "oauth2_4/abc", "my_aid")
        mock_hass.config_entries.flow.async_configure.assert_called_once_with(
            "flow_789",
            user_input={
                CONF_USERNAME: "test@gmail.com",
                CONF_MASTER_TOKEN: "aas_et/test_master_token",
                CONF_ANDROID_ID: "my_aid",
            },
        )


@pytest.mark.asyncio
async def test_get_auth_callback_with_username(
    auth_client: MagicMock, mock_hass: MagicMock
) -> None:
    """Test GET auth callback using 'username' parameter."""
    with (
        patch(
            "custom_components.google_home_bt_proxy.auth_view.GLocalAuthenticationTokens._generate_android_id",
            return_value="generated_aid_get",
        ),
        patch(
            "custom_components.google_home_bt_proxy.auth_view.gpsoauth.exchange_token",
            return_value={"Token": "aas_et/master_get"},
        ) as mock_exchange,
    ):
        resp = await auth_client.get(
            "/api/google_home_bt_proxy/auth_callback?oauth_token=oauth2_4/abc&username=test@gmail.com"
        )

        assert resp.status == 200
        mock_exchange.assert_called_once_with("test@gmail.com", "oauth2_4/abc", "generated_aid_get")
        mock_hass.config_entries.flow.async_configure.assert_not_called()


@pytest.mark.asyncio
async def test_get_auth_callback_missing_parameters(auth_client: MagicMock) -> None:
    """Test GET auth callback missing parameters."""
    # Missing email
    resp1 = await auth_client.get(
        "/api/google_home_bt_proxy/auth_callback?oauth_token=oauth2_4/abc"
    )
    assert resp1.status == 400
    assert "Missing oauth_token or email" in await resp1.text()

    # Missing oauth_token
    resp2 = await auth_client.get("/api/google_home_bt_proxy/auth_callback?email=test@gmail.com")
    assert resp2.status == 400
    assert "Missing oauth_token or email" in await resp2.text()


@pytest.mark.asyncio
async def test_get_auth_callback_invalid_token(auth_client: MagicMock) -> None:
    """Test GET auth callback invalid token."""
    with patch(
        "custom_components.google_home_bt_proxy.auth_view.gpsoauth.exchange_token",
        return_value={"Error": "BadAuthentication"},
    ):
        resp = await auth_client.get(
            "/api/google_home_bt_proxy/auth_callback?oauth_token=invalid&email=test@gmail.com"
        )
        assert resp.status == 401
        assert "Authentication Failed" in await resp.text()


@pytest.mark.asyncio
async def test_get_auth_callback_exchange_exception(auth_client: MagicMock) -> None:
    """Test GET auth callback when exchange raises exception."""
    with patch(
        "custom_components.google_home_bt_proxy.auth_view.gpsoauth.exchange_token",
        side_effect=Exception("Timeout"),
    ):
        resp = await auth_client.get(
            "/api/google_home_bt_proxy/auth_callback?oauth_token=invalid&email=test@gmail.com"
        )
        assert resp.status == 401
        assert "Authentication Failed" in await resp.text()


@pytest.mark.asyncio
async def test_get_auth_callback_flow_configure_error_handled(
    auth_client: MagicMock, mock_hass: MagicMock
) -> None:
    """Test GET auth callback when flow configuration fails."""
    mock_hass.config_entries.flow.async_configure.side_effect = RuntimeError("Flow dead")

    with patch(
        "custom_components.google_home_bt_proxy.auth_view.gpsoauth.exchange_token",
        return_value={"Token": "aas_et/master"},
    ):
        resp = await auth_client.get(
            "/api/google_home_bt_proxy/auth_callback?oauth_token=valid&email=test@gmail.com&flow_id=expired_flow"
        )
        assert resp.status == 200
        assert "Authentication Successful!" in await resp.text()


@pytest.mark.asyncio
async def test_missing_hass_instance(aiohttp_client: MagicMock) -> None:
    """Test response when hass is not in request.app."""
    app = web.Application()
    # No app["hass"]
    view = GoogleHomeBtProxyAuthCallbackView()
    # Register with dummy hass
    dummy_hass = MagicMock(spec=HomeAssistant)
    dummy_hass.is_stopping = False
    view.register(dummy_hass, app, app.router)
    client = await aiohttp_client(app)

    # POST returns 500
    post_resp = await client.post(
        "/api/google_home_bt_proxy/auth_callback",
        json={"oauth_token": "token", "email": "test@gmail.com"},
    )
    assert post_resp.status == 500

    # GET returns 500
    get_resp = await client.get(
        "/api/google_home_bt_proxy/auth_callback?oauth_token=token&email=test@gmail.com"
    )
    assert get_resp.status == 500


@pytest.mark.asyncio
async def test_async_setup_registers_view() -> None:
    """Test that component async_setup registers GoogleHomeBtProxyAuthCallbackView."""
    mock_hass = MagicMock(spec=HomeAssistant)
    mock_hass.http = MagicMock()

    result = await async_setup(mock_hass, {})

    assert result is True
    mock_hass.http.register_view.assert_called_once_with(GoogleHomeBtProxyAuthCallbackView)
