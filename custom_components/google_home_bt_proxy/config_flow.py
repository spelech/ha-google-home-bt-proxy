"""Config flow and options flow for Google Home Bluetooth Proxy."""

from __future__ import annotations

import inspect
import logging
import re
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
    CONF_ENABLE_DISTANCE_ESTIMATION,
    CONF_ENABLE_RSSI_SMOOTHING,
    CONF_FILTER_MODE,
    CONF_KNOWN_IRKS,
    CONF_MASTER_TOKEN,
    CONF_MAX_DISTANCE,
    CONF_MAX_PLAYING_SKIP_DURATION,
    CONF_OAUTH_TOKEN,
    CONF_ORCHESTRATION_MODE,
    CONF_PASSWORD,
    CONF_PATH_LOSS_EXPONENT,
    CONF_PLAYBACK_MODE,
    CONF_PLAYING_SCAN_INTERVAL,
    CONF_PLAYING_SCAN_TIMEOUT,
    CONF_REF_POWER,
    CONF_RSSI_FILTER_MODE,
    CONF_RSSI_FILTER_WINDOW,
    CONF_RSSI_OFFSET,
    CONF_RSSI_THRESHOLD,
    CONF_SCAN_INTERVAL,
    CONF_SCAN_TIMEOUT,
    CONF_SELECTED_SPEAKER,
    CONF_SPEAKER_OVERRIDES,
    CONF_TRACKED_DEVICES,
    CONF_USERNAME,
    DEFAULT_ENABLE_DISTANCE_ESTIMATION,
    DEFAULT_ENABLE_RSSI_SMOOTHING,
    DEFAULT_FILTER_MODE,
    DEFAULT_MAX_DISTANCE,
    DEFAULT_MAX_PLAYING_SKIP_DURATION,
    DEFAULT_ORCHESTRATION_MODE,
    DEFAULT_PATH_LOSS_EXPONENT,
    DEFAULT_PLAYBACK_MODE,
    DEFAULT_PLAYING_SCAN_INTERVAL,
    DEFAULT_PLAYING_SCAN_TIMEOUT,
    DEFAULT_REF_POWER,
    DEFAULT_RSSI_FILTER_MODE,
    DEFAULT_RSSI_FILTER_WINDOW,
    DEFAULT_RSSI_OFFSET,
    DEFAULT_RSSI_THRESHOLD,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_SCAN_TIMEOUT,
    DOMAIN,
    FILTER_MODE_ALL,
    FILTER_MODE_KNOWN_ONLY,
    FILTER_MODE_WHITELIST,
    GLOBAL_SETTINGS,
    MODE_IGNORE,
    MODE_SKIP_CEILING,
    MODE_THROTTLE,
    NAME,
    ORCHESTRATION_INDEPENDENT,
    ORCHESTRATION_ROUND_ROBIN,
    RSSI_FILTER_EMA,
    RSSI_FILTER_MEDIAN,
    RSSI_FILTER_NONE,
)

if not hasattr(glocaltokens.client, "get_android_id"):
    glocaltokens.client.get_android_id = (  # type: ignore[attr-defined]
        GLocalAuthenticationTokens._generate_android_id
    )

_LOGGER = logging.getLogger(__name__)


def sanitize_token(token: str) -> str:
    """Extract and sanitize token from raw strings, cookie headers, or devtools copies."""
    if not token or not isinstance(token, str):
        return ""
    token = token.strip()
    # Check for oauth2_4 token embedded in cookie string or key-value pair
    match_oauth = re.search(r"(oauth2_4/[^\s\"';,]+)", token)
    if match_oauth:
        return match_oauth.group(1)
    # Check for aas_et / oauth2_rt master token
    match_master = re.search(r"((?:aas_et|oauth2_rt)/[^\s\"';,]+)", token)
    if match_master:
        return match_master.group(1)
    # Fallback stripping of common key prefixes and surrounding quotes
    token = re.sub(r"^(?:oauth_token|master_token)\s*[:=]\s*", "", token, flags=re.IGNORECASE)
    token = token.strip().strip("\"'").strip(";").strip()
    return token


class GoogleHomeBtProxyConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Google Home Bluetooth Proxy."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize config flow."""
        super().__init__()
        self._imported_data: dict[str, Any] | None = None
        self._import_checked: bool = False
        self._email: str = ""

    async def _validate_credentials(self, user_input: dict[str, Any]) -> bool:
        """Verify the provided credentials or master token."""
        for key in (
            CONF_USERNAME,
            CONF_PASSWORD,
            CONF_MASTER_TOKEN,
            CONF_OAUTH_TOKEN,
            CONF_ANDROID_ID,
        ):
            if key in user_input and isinstance(user_input[key], str):
                user_input[key] = user_input[key].strip()

        from glocaltokens.client import get_android_id  # type: ignore[attr-defined]

        android_id = user_input.get(CONF_ANDROID_ID) or get_android_id()
        user_input[CONF_ANDROID_ID] = android_id

        master_token = sanitize_token(user_input.get(CONF_MASTER_TOKEN, ""))
        oauth_token = sanitize_token(user_input.get(CONF_OAUTH_TOKEN, ""))
        username = user_input.get(CONF_USERNAME, "")
        password = user_input.get(CONF_PASSWORD, "")

        # Auto-detect if user entered an oauth token into master_token field
        if master_token.startswith("oauth2_4/"):
            oauth_token = master_token
            master_token = ""

        if oauth_token:
            if not username:
                return False

            def _exchange() -> dict[str, Any]:
                return gpsoauth.exchange_token(username, oauth_token, android_id)

            res = await self.hass.async_add_executor_job(_exchange)
            if isinstance(res, dict) and "Token" in res:
                user_input[CONF_MASTER_TOKEN] = res["Token"]
                user_input.pop(CONF_OAUTH_TOKEN, None)
                return True
            _LOGGER.warning("OAuth token exchange failed: %s", res)
            return False

        if master_token:
            user_input[CONF_MASTER_TOKEN] = master_token
            return True

        if username and password:
            client = GLocalAuthenticationTokens(
                username=username,
                password=password,
                master_token=None,
                android_id=android_id,
            )
            token = await self.hass.async_add_executor_job(client.get_master_token)
            if token:
                user_input[CONF_MASTER_TOKEN] = token
                return True
            return False

        return False

    def _show_config_form(self, errors: dict[str, str] | None = None) -> ConfigFlowResult:
        """Show configuration form for manual input."""
        schema = vol.Schema(
            {
                vol.Optional(CONF_USERNAME, default=""): str,
                vol.Optional(CONF_PASSWORD, default=""): str,
                vol.Optional(CONF_MASTER_TOKEN, default=""): str,
            }
        )
        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors or {},
            description_placeholders={"flow_id": getattr(self, "flow_id", "") or ""},
        )

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._email = user_input.get(CONF_USERNAME, "").strip()
            try:
                valid = await self._validate_credentials(user_input)
                if valid:
                    return self.async_create_entry(title=NAME, data=user_input)
                errors["base"] = "invalid_auth"
                # If password authentication failed, transition to token step
                # so the user is not asked for the password again!
                return await self.async_step_token(errors=errors)
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

    async def async_step_token(
        self,
        user_input: dict[str, Any] | None = None,
        errors: dict[str, str] | None = None,
    ) -> ConfigFlowResult:
        """Handle token input step when password auth failed or token is used directly."""
        step_errors = dict(errors or {})

        if user_input is not None:
            if not user_input.get(CONF_USERNAME) and self._email:
                user_input[CONF_USERNAME] = self._email
            elif user_input.get(CONF_USERNAME):
                self._email = user_input[CONF_USERNAME].strip()

            try:
                valid = await self._validate_credentials(user_input)
                if valid:
                    return self.async_create_entry(title=NAME, data=user_input)
                step_errors["base"] = "invalid_auth"
            except Exception:
                _LOGGER.exception("Unexpected exception in token config flow")
                step_errors["base"] = "cannot_connect"

        schema = vol.Schema(
            {
                vol.Required(CONF_USERNAME, default=self._email): str,
                vol.Required(CONF_MASTER_TOKEN): str,
            }
        )
        return self.async_show_form(
            step_id="token",
            data_schema=schema,
            errors=step_errors,
            description_placeholders={"email": self._email or "your Google account"},
        )

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
                    CONF_ORCHESTRATION_MODE,
                    default=options.get(CONF_ORCHESTRATION_MODE, DEFAULT_ORCHESTRATION_MODE),
                ): vol.In([ORCHESTRATION_ROUND_ROBIN, ORCHESTRATION_INDEPENDENT]),
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
                    CONF_RSSI_OFFSET,
                    default=options.get(CONF_RSSI_OFFSET, DEFAULT_RSSI_OFFSET),
                ): vol.All(vol.Coerce(int), vol.Range(min=-30, max=30)),
                vol.Optional(
                    CONF_FILTER_MODE,
                    default=options.get(CONF_FILTER_MODE, DEFAULT_FILTER_MODE),
                ): vol.In([FILTER_MODE_ALL, FILTER_MODE_KNOWN_ONLY, FILTER_MODE_WHITELIST]),
                vol.Optional(
                    CONF_TRACKED_DEVICES,
                    default=options.get(CONF_TRACKED_DEVICES, ""),
                ): str,
                vol.Optional(
                    CONF_ENABLE_RSSI_SMOOTHING,
                    default=options.get(CONF_ENABLE_RSSI_SMOOTHING, DEFAULT_ENABLE_RSSI_SMOOTHING),
                ): bool,
                vol.Optional(
                    CONF_RSSI_FILTER_MODE,
                    default=options.get(CONF_RSSI_FILTER_MODE, DEFAULT_RSSI_FILTER_MODE),
                ): vol.In([RSSI_FILTER_NONE, RSSI_FILTER_MEDIAN, RSSI_FILTER_EMA]),
                vol.Optional(
                    CONF_RSSI_FILTER_WINDOW,
                    default=options.get(CONF_RSSI_FILTER_WINDOW, DEFAULT_RSSI_FILTER_WINDOW),
                ): vol.All(vol.Coerce(int), vol.Range(min=1, max=10)),
                vol.Optional(
                    CONF_ENABLE_DISTANCE_ESTIMATION,
                    default=options.get(
                        CONF_ENABLE_DISTANCE_ESTIMATION, DEFAULT_ENABLE_DISTANCE_ESTIMATION
                    ),
                ): bool,
                vol.Optional(
                    CONF_MAX_DISTANCE,
                    default=float(options.get(CONF_MAX_DISTANCE, DEFAULT_MAX_DISTANCE)),
                ): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=50.0)),
                vol.Optional(
                    CONF_REF_POWER,
                    default=options.get(CONF_REF_POWER, DEFAULT_REF_POWER),
                ): vol.All(vol.Coerce(int), vol.Range(min=-100, max=-30)),
                vol.Optional(
                    CONF_PATH_LOSS_EXPONENT,
                    default=float(options.get(CONF_PATH_LOSS_EXPONENT, DEFAULT_PATH_LOSS_EXPONENT)),
                ): vol.All(vol.Coerce(float), vol.Range(min=1.0, max=5.0)),
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
                vol.Optional(
                    CONF_RSSI_OFFSET,
                    default=existing_overrides.get(
                        CONF_RSSI_OFFSET,
                        options.get(CONF_RSSI_OFFSET, DEFAULT_RSSI_OFFSET),
                    ),
                ): vol.All(vol.Coerce(int), vol.Range(min=-30, max=30)),
                vol.Optional(
                    CONF_FILTER_MODE,
                    default=existing_overrides.get(
                        CONF_FILTER_MODE,
                        options.get(CONF_FILTER_MODE, DEFAULT_FILTER_MODE),
                    ),
                ): vol.In([FILTER_MODE_ALL, FILTER_MODE_KNOWN_ONLY, FILTER_MODE_WHITELIST]),
                vol.Optional(
                    CONF_TRACKED_DEVICES,
                    default=existing_overrides.get(
                        CONF_TRACKED_DEVICES,
                        options.get(CONF_TRACKED_DEVICES, ""),
                    ),
                ): str,
                vol.Optional(
                    CONF_ENABLE_RSSI_SMOOTHING,
                    default=existing_overrides.get(
                        CONF_ENABLE_RSSI_SMOOTHING,
                        options.get(CONF_ENABLE_RSSI_SMOOTHING, DEFAULT_ENABLE_RSSI_SMOOTHING),
                    ),
                ): bool,
                vol.Optional(
                    CONF_RSSI_FILTER_MODE,
                    default=existing_overrides.get(
                        CONF_RSSI_FILTER_MODE,
                        options.get(CONF_RSSI_FILTER_MODE, DEFAULT_RSSI_FILTER_MODE),
                    ),
                ): vol.In([RSSI_FILTER_NONE, RSSI_FILTER_MEDIAN, RSSI_FILTER_EMA]),
                vol.Optional(
                    CONF_RSSI_FILTER_WINDOW,
                    default=existing_overrides.get(
                        CONF_RSSI_FILTER_WINDOW,
                        options.get(CONF_RSSI_FILTER_WINDOW, DEFAULT_RSSI_FILTER_WINDOW),
                    ),
                ): vol.All(vol.Coerce(int), vol.Range(min=1, max=10)),
                vol.Optional(
                    CONF_ENABLE_DISTANCE_ESTIMATION,
                    default=existing_overrides.get(
                        CONF_ENABLE_DISTANCE_ESTIMATION,
                        options.get(
                            CONF_ENABLE_DISTANCE_ESTIMATION, DEFAULT_ENABLE_DISTANCE_ESTIMATION
                        ),
                    ),
                ): bool,
                vol.Optional(
                    CONF_MAX_DISTANCE,
                    default=float(
                        existing_overrides.get(
                            CONF_MAX_DISTANCE,
                            options.get(CONF_MAX_DISTANCE, DEFAULT_MAX_DISTANCE),
                        )
                    ),
                ): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=50.0)),
                vol.Optional(
                    CONF_REF_POWER,
                    default=existing_overrides.get(
                        CONF_REF_POWER,
                        options.get(CONF_REF_POWER, DEFAULT_REF_POWER),
                    ),
                ): vol.All(vol.Coerce(int), vol.Range(min=-100, max=-30)),
                vol.Optional(
                    CONF_PATH_LOSS_EXPONENT,
                    default=float(
                        existing_overrides.get(
                            CONF_PATH_LOSS_EXPONENT,
                            options.get(CONF_PATH_LOSS_EXPONENT, DEFAULT_PATH_LOSS_EXPONENT),
                        )
                    ),
                ): vol.All(vol.Coerce(float), vol.Range(min=1.0, max=5.0)),
            }
        )

        return self.async_show_form(
            step_id="speaker_settings",
            data_schema=speaker_schema,
            description_placeholders={"speaker": self._selected_speaker},
        )
