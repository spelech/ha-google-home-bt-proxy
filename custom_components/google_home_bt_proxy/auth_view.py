"""HTTP API Auth Callback View for Google Home Bluetooth Proxy."""

from __future__ import annotations

import logging

import gpsoauth
from aiohttp import web
from glocaltokens.client import GLocalAuthenticationTokens
from homeassistant.components.http import HomeAssistantView
from homeassistant.components.http.const import KEY_HASS
from homeassistant.core import HomeAssistant

from .const import CONF_ANDROID_ID, CONF_MASTER_TOKEN, CONF_USERNAME

_LOGGER = logging.getLogger(__name__)


class GoogleHomeBtProxyAuthCallbackView(HomeAssistantView):
    """View to handle auth callbacks from Web-Helper and external tools."""

    url = "/api/google_home_bt_proxy/auth_callback"
    name = "api:google_home_bt_proxy:auth_callback"
    requires_auth = False
    cors_allowed = True

    async def post(self, request: web.Request) -> web.Response:
        """Handle POST request with OAuth token."""
        try:
            data = await request.json()
        except Exception:
            return web.json_response({"error": "missing_parameters"}, status=400)

        if not isinstance(data, dict):
            return web.json_response({"error": "missing_parameters"}, status=400)

        oauth_token = data.get("oauth_token")
        email = data.get("email") or data.get("username")
        flow_id = data.get("flow_id")
        android_id = data.get("android_id") or GLocalAuthenticationTokens._generate_android_id()

        if not oauth_token or not email:
            return web.json_response({"error": "missing_parameters"}, status=400)

        hass: HomeAssistant | None = request.app.get("hass")
        if hass is None and KEY_HASS in request.app:
            hass = request.app[KEY_HASS]

        if hass is None:
            return web.json_response({"error": "server_error"}, status=500)

        try:
            result = await hass.async_add_executor_job(
                gpsoauth.exchange_token, email, oauth_token, android_id
            )
        except Exception as err:
            _LOGGER.error("Error exchanging OAuth token: %s", err)
            return web.json_response(
                {"error": "invalid_oauth_token", "details": str(err)}, status=401
            )

        if not isinstance(result, dict) or "Token" not in result:
            return web.json_response(
                {"error": "invalid_oauth_token", "details": result}, status=401
            )

        master_token = result["Token"]

        if flow_id:
            try:
                await hass.config_entries.flow.async_configure(
                    flow_id,
                    user_input={
                        CONF_USERNAME: email,
                        CONF_MASTER_TOKEN: master_token,
                        CONF_ANDROID_ID: android_id,
                    },
                )
            except Exception as err:
                _LOGGER.warning("Could not advance config flow %s: %s", flow_id, err)

        return web.json_response({"status": "success", "master_token_acquired": True})

    async def get(self, request: web.Request) -> web.Response:
        """Handle GET request with OAuth token in query string."""
        oauth_token = request.query.get("oauth_token")
        email = request.query.get("email") or request.query.get("username")
        flow_id = request.query.get("flow_id")
        android_id = (
            request.query.get("android_id") or GLocalAuthenticationTokens._generate_android_id()
        )

        if not oauth_token or not email:
            return web.Response(
                text="<h1>Error: Missing oauth_token or email</h1>",
                status=400,
                content_type="text/html",
            )

        hass: HomeAssistant | None = request.app.get("hass")
        if hass is None and KEY_HASS in request.app:
            hass = request.app[KEY_HASS]

        if hass is None:
            return web.Response(
                text="<h1>Error: Server Error</h1>",
                status=500,
                content_type="text/html",
            )

        try:
            result = await hass.async_add_executor_job(
                gpsoauth.exchange_token, email, oauth_token, android_id
            )
        except Exception as err:
            _LOGGER.error("Error exchanging OAuth token: %s", err)
            result = {"Error": str(err)}

        if not isinstance(result, dict) or "Token" not in result:
            return web.Response(
                text="<h1>Authentication Failed</h1><p>Invalid or expired OAuth token.</p>",
                status=401,
                content_type="text/html",
            )

        master_token = result["Token"]

        if flow_id:
            try:
                await hass.config_entries.flow.async_configure(
                    flow_id,
                    user_input={
                        CONF_USERNAME: email,
                        CONF_MASTER_TOKEN: master_token,
                        CONF_ANDROID_ID: android_id,
                    },
                )
            except Exception as err:
                _LOGGER.warning("Could not advance config flow %s: %s", flow_id, err)

        success_html = (
            "<!DOCTYPE html><html>"
            "<body style='font-family:sans-serif;text-align:center;padding:50px;'>"
            "<h2>Authentication Successful!</h2>"
            "<p>You can close this window and return to Home Assistant.</p>"
            "</body></html>"
        )
        return web.Response(
            text=success_html,
            status=200,
            content_type="text/html",
        )
