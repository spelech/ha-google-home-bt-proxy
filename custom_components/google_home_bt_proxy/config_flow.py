"""Config flow and options flow for Google Home Bluetooth Proxy."""

from __future__ import annotations

import inspect
import logging
from collections.abc import Mapping
from typing import Any

import glocaltokens.client
import gpsoauth
import voluptuous as vol
from glocaltokens.client import GLocalAuthenticationTokens
from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.core import callback

from .const import (
    CONF_ANDROID_ID,
    CONF_CUSTOM_SETTINGS,
    CONF_KNOWN_IRKS,
    CONF_MASTER_TOKEN,
    CONF_MAX_PLAYING_SKIP_DURATION,
    CONF_OAUTH_TOKEN,
    CONF_PASSWORD,
    CONF_PLAYBACK_MODE,
    CONF_PLAYING_SCAN_INTERVAL,
    CONF_PLAYING_SCAN_TIMEOUT,
    CONF_RSSI_THRESHOLD,
    CONF_SCAN_INTERVAL,
    CONF_SCAN_TIMEOUT,
    CONF_SELECTED_SPEAKER,
    CONF_SPEAKER_OVERRIDES,
    CONF_USERNAME,
    DEFAULT_MAX_PLAYING_SKIP_DURATION,
    DEFAULT_PLAYBACK_MODE,
    DEFAULT_PLAYING_SCAN_INTERVAL,
    DEFAULT_PLAYING_SCAN_TIMEOUT,
    DEFAULT_RSSI_THRESHOLD,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SCAN_TIMEOUT,
    DOMAIN,
    GLOBAL_SETTINGS,
    MODE_IGNORE,
    MODE_SKIP_CEILING,
    MODE_THROTTLE,
    NAME,
)

if not hasattr(glocaltokens.client, "get_android_id"):
    glocaltokens.client.get_android_id = (  # type: ignore[attr-defined]
        GLocalAuthenticationTokens._generate_android_id
    )

_LOGGER = logging.getLogger(__name__)


class GoogleHomeBtProxyConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Google Home Bluetooth Proxy."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize config flow."""
        super().__init__()
        self._imported_data: dict[str, Any] | None = None
        self._import_checked: bool = False

    async def _validate_credentials(self, user_input: dict[str, Any]) -> bool:
        """Verify the provided credentials or master token."""
        if user_input.get(CONF_MASTER_TOKEN):
            return True

        if user_input.get(CONF_OAUTH_TOKEN):
            if not user_input.get(CONF_USERNAME):
                return False
            from glocaltokens.client import get_android_id  # type: ignore[attr-defined]

            android_id = user_input.get(CONF_ANDROID_ID) or get_android_id()
            username = user_input.get(CONF_USERNAME, "")
            oauth_token = user_input.get(CONF_OAUTH_TOKEN, "")

            def _exchange() -> dict[str, Any]:
                return gpsoauth.exchange_token(username, oauth_token, android_id)

            res = await self.hass.async_add_executor_job(_exchange)
            if "Token" in res:
                user_input[CONF_MASTER_TOKEN] = res["Token"]
                user_input[CONF_ANDROID_ID] = android_id
                user_input.pop(CONF_OAUTH_TOKEN, None)
                return True
            _LOGGER.warning("OAuth token exchange failed: %s", res)
            return False

        client = GLocalAuthenticationTokens(
            username=user_input.get(CONF_USERNAME),
            password=user_input.get(CONF_PASSWORD),
            master_token=user_input.get(CONF_MASTER_TOKEN),
            android_id=user_input.get(CONF_ANDROID_ID),
        )
        token = await self.hass.async_add_executor_job(client.get_master_token)
        return bool(token)

    def _show_config_form(self, errors: dict[str, str] | None = None) -> ConfigFlowResult:
        """Show configuration form for manual input."""
        schema = vol.Schema(
            {
                vol.Optional(CONF_USERNAME, default=""): str,
                vol.Optional(CONF_PASSWORD, default=""): str,
                vol.Optional(CONF_MASTER_TOKEN, default=""): str,
                vol.Optional(CONF_OAUTH_TOKEN, default=""): str,
                vol.Optional(CONF_ANDROID_ID, default=""): str,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors or {})

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
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
            return self._show_config_form(errors=errors)

        if not self._import_checked:
            self._import_checked = True
            if hasattr(self, "hass") and self.hass is not None:
                entries = self.hass.config_entries.async_entries("google_home")
                if inspect.isawaitable(entries):
                    entries = await entries

                if isinstance(entries, (list, tuple)):
                    for entry in entries:
                        data = (
                            entry.data
                            if hasattr(entry, "data")
                            else (entry.get("data") if isinstance(entry, dict) else None)
                        )
                        if isinstance(data, Mapping) and (
                            data.get(CONF_MASTER_TOKEN)
                            or (data.get(CONF_USERNAME) and data.get(CONF_PASSWORD))
                        ):
                            self._imported_data = dict(data)
                            return await self.async_step_import_existing()

        return self._show_config_form(errors=errors)

    async def async_step_import_existing(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle importing credentials from existing google_home integration."""
        if user_input is not None:
            if user_input.get("import_credentials", True):
                imported_data = self._imported_data or {}
                try:
                    valid = await self._validate_credentials(imported_data)
                    if valid:
                        return self.async_create_entry(
                            title=f"{NAME} (Imported)",
                            data=imported_data,
                        )
                    errors = {"base": "invalid_auth"}
                except Exception:
                    _LOGGER.exception("Unexpected exception during credential validation")
                    errors = {"base": "cannot_connect"}
                return self._show_config_form(errors=errors)
            return self._show_config_form()

        imported_data = self._imported_data or {}
        username = imported_data.get(CONF_USERNAME) or "Google Home"
        schema = vol.Schema(
            {
                vol.Required("import_credentials", default=True): bool,
            }
        )
        return self.async_show_form(
            step_id="import_existing",
            data_schema=schema,
            description_placeholders={"username": username},
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> GoogleHomeBtProxyOptionsFlowHandler:
        """Get the options flow handler."""
        return GoogleHomeBtProxyOptionsFlowHandler(config_entry)


class GoogleHomeBtProxyOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options flow for Google Home Bluetooth Proxy."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self._config_entry = config_entry
        self._selected_speaker: str = GLOBAL_SETTINGS

    @property
    def config_entry(self) -> config_entries.ConfigEntry:
        """Return the config entry."""
        if hasattr(self, "_config_entry") and self._config_entry is not None:
            return self._config_entry
        return super().config_entry

    def _get_speaker_choices(self) -> dict[str, str]:
        """Return mapping of target choice keys to labels."""
        choices = {GLOBAL_SETTINGS: "Global Settings (Default for All Speakers)"}
        if hasattr(self, "hass") and self.hass is not None:
            entry_data = self.hass.data.get(DOMAIN, {}).get(self.config_entry.entry_id, {})
            coord = entry_data.get("coordinator")
            if coord and hasattr(coord, "speakers"):
                for spk_id, spk in coord.speakers.items():
                    choices[spk_id] = f"{spk.name} ({spk.hardware})"
        return choices

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Manage the options."""
        speaker_choices = self._get_speaker_choices()

        if user_input is not None:
            selected = user_input.get(CONF_SELECTED_SPEAKER, GLOBAL_SETTINGS)
            if selected != GLOBAL_SETTINGS:
                self._selected_speaker = selected
                return await self.async_step_speaker_settings()

            cleaned_input = {
                k: v
                for k, v in user_input.items()
                if k not in (CONF_SELECTED_SPEAKER, CONF_CUSTOM_SETTINGS)
            }
            new_options = dict(self.config_entry.options)
            new_options.update(cleaned_input)
            return self.async_create_entry(title="", data=new_options)

        options = self.config_entry.options
        schema = vol.Schema(
            {
                vol.Optional(
                    CONF_SELECTED_SPEAKER,
                    default=GLOBAL_SETTINGS,
                ): vol.In(speaker_choices),
                vol.Optional(
                    CONF_PLAYBACK_MODE,
                    default=options.get(CONF_PLAYBACK_MODE, DEFAULT_PLAYBACK_MODE),
                ): vol.In([MODE_THROTTLE, MODE_SKIP_CEILING, MODE_IGNORE]),
                vol.Optional(
                    CONF_SCAN_TIMEOUT,
                    default=options.get(CONF_SCAN_TIMEOUT, DEFAULT_SCAN_TIMEOUT),
                ): vol.All(vol.Coerce(int), vol.Range(min=2, max=15)),
                vol.Optional(
                    CONF_SCAN_INTERVAL,
                    default=options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                ): vol.All(vol.Coerce(int), vol.Range(min=5, max=60)),
                vol.Optional(
                    CONF_PLAYING_SCAN_TIMEOUT,
                    default=options.get(CONF_PLAYING_SCAN_TIMEOUT, DEFAULT_PLAYING_SCAN_TIMEOUT),
                ): vol.All(vol.Coerce(int), vol.Range(min=1, max=10)),
                vol.Optional(
                    CONF_PLAYING_SCAN_INTERVAL,
                    default=options.get(CONF_PLAYING_SCAN_INTERVAL, DEFAULT_PLAYING_SCAN_INTERVAL),
                ): vol.All(vol.Coerce(int), vol.Range(min=10, max=300)),
                vol.Optional(
                    CONF_MAX_PLAYING_SKIP_DURATION,
                    default=options.get(
                        CONF_MAX_PLAYING_SKIP_DURATION, DEFAULT_MAX_PLAYING_SKIP_DURATION
                    ),
                ): vol.All(vol.Coerce(int), vol.Range(min=30, max=900)),
                vol.Optional(
                    CONF_RSSI_THRESHOLD,
                    default=options.get(CONF_RSSI_THRESHOLD, DEFAULT_RSSI_THRESHOLD),
                ): vol.All(vol.Coerce(int), vol.Range(min=-100, max=-40)),
                vol.Optional(
                    CONF_KNOWN_IRKS,
                    default=options.get(CONF_KNOWN_IRKS, ""),
                ): str,
            }
        )

        return self.async_show_form(step_id="init", data_schema=schema)

    async def async_step_speaker_settings(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage overrides for a specific speaker."""
        options = self.config_entry.options
        existing_overrides: dict[str, Any] = options.get(CONF_SPEAKER_OVERRIDES, {}).get(
            self._selected_speaker, {}
        )

        if user_input is not None:
            new_options = dict(options)
            all_overrides = dict(new_options.get(CONF_SPEAKER_OVERRIDES, {}))

            if user_input.get(CONF_CUSTOM_SETTINGS, True):
                override_data = {k: v for k, v in user_input.items() if k != CONF_CUSTOM_SETTINGS}
                all_overrides[self._selected_speaker] = override_data
            else:
                all_overrides.pop(self._selected_speaker, None)

            new_options[CONF_SPEAKER_OVERRIDES] = all_overrides
            return self.async_create_entry(title="", data=new_options)

        has_custom = bool(existing_overrides)
        speaker_schema = vol.Schema(
            {
                vol.Optional(
                    CONF_CUSTOM_SETTINGS,
                    default=has_custom,
                ): bool,
                vol.Optional(
                    CONF_PLAYBACK_MODE,
                    default=existing_overrides.get(
                        CONF_PLAYBACK_MODE,
                        options.get(CONF_PLAYBACK_MODE, DEFAULT_PLAYBACK_MODE),
                    ),
                ): vol.In([MODE_THROTTLE, MODE_SKIP_CEILING, MODE_IGNORE]),
                vol.Optional(
                    CONF_SCAN_TIMEOUT,
                    default=existing_overrides.get(
                        CONF_SCAN_TIMEOUT,
                        options.get(CONF_SCAN_TIMEOUT, DEFAULT_SCAN_TIMEOUT),
                    ),
                ): vol.All(vol.Coerce(int), vol.Range(min=2, max=15)),
                vol.Optional(
                    CONF_SCAN_INTERVAL,
                    default=existing_overrides.get(
                        CONF_SCAN_INTERVAL,
                        options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                    ),
                ): vol.All(vol.Coerce(int), vol.Range(min=5, max=60)),
                vol.Optional(
                    CONF_PLAYING_SCAN_TIMEOUT,
                    default=existing_overrides.get(
                        CONF_PLAYING_SCAN_TIMEOUT,
                        options.get(CONF_PLAYING_SCAN_TIMEOUT, DEFAULT_PLAYING_SCAN_TIMEOUT),
                    ),
                ): vol.All(vol.Coerce(int), vol.Range(min=1, max=10)),
                vol.Optional(
                    CONF_PLAYING_SCAN_INTERVAL,
                    default=existing_overrides.get(
                        CONF_PLAYING_SCAN_INTERVAL,
                        options.get(CONF_PLAYING_SCAN_INTERVAL, DEFAULT_PLAYING_SCAN_INTERVAL),
                    ),
                ): vol.All(vol.Coerce(int), vol.Range(min=10, max=300)),
                vol.Optional(
                    CONF_MAX_PLAYING_SKIP_DURATION,
                    default=existing_overrides.get(
                        CONF_MAX_PLAYING_SKIP_DURATION,
                        options.get(
                            CONF_MAX_PLAYING_SKIP_DURATION, DEFAULT_MAX_PLAYING_SKIP_DURATION
                        ),
                    ),
                ): vol.All(vol.Coerce(int), vol.Range(min=30, max=900)),
                vol.Optional(
                    CONF_RSSI_THRESHOLD,
                    default=existing_overrides.get(
                        CONF_RSSI_THRESHOLD,
                        options.get(CONF_RSSI_THRESHOLD, DEFAULT_RSSI_THRESHOLD),
                    ),
                ): vol.All(vol.Coerce(int), vol.Range(min=-100, max=-40)),
            }
        )

        return self.async_show_form(
            step_id="speaker_settings",
            data_schema=speaker_schema,
            description_placeholders={"speaker": self._selected_speaker},
        )
