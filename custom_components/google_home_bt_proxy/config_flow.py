"""Config flow and options flow for Google Home Bluetooth Proxy."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol
from glocaltokens.client import GLocalAuthenticationTokens
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .const import (
    CONF_ANDROID_ID,
    CONF_MASTER_TOKEN,
    CONF_PASSWORD,
    CONF_RSSI_THRESHOLD,
    CONF_SCAN_INTERVAL,
    CONF_SCAN_TIMEOUT,
    CONF_USERNAME,
    DEFAULT_RSSI_THRESHOLD,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SCAN_TIMEOUT,
    DOMAIN,
    NAME,
)

_LOGGER = logging.getLogger(__name__)


class GoogleHomeBtProxyConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Google Home Bluetooth Proxy."""

    VERSION = 1

    async def _validate_credentials(self, user_input: dict[str, Any]) -> bool:
        """Verify the provided credentials or master token."""
        client = GLocalAuthenticationTokens(
            username=user_input.get(CONF_USERNAME),
            password=user_input.get(CONF_PASSWORD),
            master_token=user_input.get(CONF_MASTER_TOKEN),
            android_id=user_input.get(CONF_ANDROID_ID),
        )
        if user_input.get(CONF_MASTER_TOKEN):
            return True

        token = await self.hass.async_add_executor_job(client.get_master_token)
        return bool(token)

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                valid = await self._validate_credentials(user_input)
                if valid:
                    return self.async_create_entry(title=NAME, data=user_input)
                errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception in config flow")
                errors["base"] = "cannot_connect"

        schema = vol.Schema(
            {
                vol.Optional(CONF_USERNAME, default=""): str,
                vol.Optional(CONF_PASSWORD, default=""): str,
                vol.Optional(CONF_MASTER_TOKEN, default=""): str,
                vol.Optional(CONF_ANDROID_ID, default=""): str,
            }
        )

        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Return options flow handler."""
        return GoogleHomeBtProxyOptionsFlowHandler(config_entry)


class GoogleHomeBtProxyOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options for Google Home Bluetooth Proxy."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._config_entry = config_entry

    @property
    def config_entry(self) -> config_entries.ConfigEntry:
        """Return the config entry."""
        if hasattr(self, "_config_entry") and self._config_entry is not None:
            return self._config_entry
        return super().config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        options = self.config_entry.options
        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_SCAN_TIMEOUT,
                    default=options.get(CONF_SCAN_TIMEOUT, DEFAULT_SCAN_TIMEOUT),
                ): vol.All(vol.Coerce(int), vol.Range(min=3, max=15)),
                vol.Optional(
                    CONF_SCAN_INTERVAL,
                    default=options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                ): vol.All(vol.Coerce(int), vol.Range(min=5, max=60)),
                vol.Optional(
                    CONF_RSSI_THRESHOLD,
                    default=options.get(CONF_RSSI_THRESHOLD, DEFAULT_RSSI_THRESHOLD),
                ): vol.All(vol.Coerce(int), vol.Range(min=-100, max=-40)),
            }
        )

        return self.async_show_form(step_id="init", data_schema=schema)
