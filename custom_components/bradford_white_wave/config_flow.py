"""Config flow for Bradford White Wave integration."""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any

import voluptuous as vol
from bradford_white_wave_client import (
    BradfordWhiteAuthError,
    BradfordWhiteClient,
    BradfordWhiteConnectError,
)
from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

from .const import CONF_REFRESH_TOKEN, DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_EMAIL): TextSelector(
            TextSelectorConfig(
                type=TextSelectorType.EMAIL,
                autocomplete="username",
            )
        ),
        vol.Required(CONF_PASSWORD): TextSelector(
            TextSelectorConfig(
                type=TextSelectorType.PASSWORD,
                autocomplete="current-password",
            )
        ),
    }
)


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Bradford White Wave."""

    VERSION = 1

    async def _async_authenticate(
        self, email: str, password: str
    ) -> tuple[BradfordWhiteClient | None, dict[str, str]]:
        """Validate credentials and return the authenticated client or error map."""
        errors: dict[str, str] = {}
        client = BradfordWhiteClient(session=async_get_clientsession(self.hass))
        try:
            await client.authenticate_with_credentials(email, password)
        except BradfordWhiteAuthError as err:
            _LOGGER.warning("Authentication failed: %s", err)
            errors["base"] = "invalid_auth"
        except BradfordWhiteConnectError as err:
            _LOGGER.error("Connection error during authentication: %s", err)
            errors["base"] = "cannot_connect"
        except Exception:
            _LOGGER.exception("Unexpected exception during authentication")
            errors["base"] = "unknown"
        finally:
            await client.close()

        if errors:
            return None, errors
        return client, errors

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle initial configuration via email and password."""
        errors: dict[str, str] = {}

        if user_input is not None:
            email = user_input[CONF_EMAIL].strip()
            password = user_input[CONF_PASSWORD]
            client, errors = await self._async_authenticate(email, password)

            if client is not None:
                entry_data = {
                    CONF_EMAIL: email,
                    CONF_PASSWORD: password,
                    CONF_REFRESH_TOKEN: client.refresh_token,
                }
                if client.account_id:
                    await self.async_set_unique_id(client.account_id)
                    self._abort_if_unique_id_configured(updates=entry_data)

                return self.async_create_entry(
                    title=f"Bradford White Wave ({email})",
                    data=entry_data,
                )

        schema = STEP_USER_DATA_SCHEMA
        if user_input is not None:
            schema = self.add_suggested_values_to_schema(
                schema, {CONF_EMAIL: user_input.get(CONF_EMAIL, "")}
            )

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_reauth(self, entry_data: Mapping[str, Any]) -> ConfigFlowResult:
        """Handle reauthentication."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm reauthentication with updated credentials."""
        errors: dict[str, str] = {}
        reauth_entry = self._get_reauth_entry()

        if user_input is not None:
            email = user_input[CONF_EMAIL].strip()
            password = user_input[CONF_PASSWORD]
            client, errors = await self._async_authenticate(email, password)

            if client is not None:
                if client.account_id:
                    await self.async_set_unique_id(client.account_id)
                    if reauth_entry.unique_id is not None:
                        self._abort_if_unique_id_mismatch(reason="wrong_account")

                return self.async_update_reload_and_abort(
                    reauth_entry,
                    data={
                        CONF_EMAIL: email,
                        CONF_PASSWORD: password,
                        CONF_REFRESH_TOKEN: client.refresh_token,
                    },
                )

        suggested_email = (
            user_input.get(CONF_EMAIL)
            if user_input is not None
            else reauth_entry.data.get(CONF_EMAIL, "")
        )
        schema = self.add_suggested_values_to_schema(
            STEP_USER_DATA_SCHEMA,
            {CONF_EMAIL: suggested_email},
        )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle reconfiguration of stored Bradford White Wave credentials."""
        errors: dict[str, str] = {}
        reconfigure_entry = self._get_reconfigure_entry()

        if user_input is not None:
            email = user_input[CONF_EMAIL].strip()
            password = user_input[CONF_PASSWORD]
            client, errors = await self._async_authenticate(email, password)

            if client is not None:
                if client.account_id:
                    await self.async_set_unique_id(client.account_id)
                    if reconfigure_entry.unique_id is not None:
                        self._abort_if_unique_id_mismatch(reason="wrong_account")

                return self.async_update_reload_and_abort(
                    reconfigure_entry,
                    data={
                        CONF_EMAIL: email,
                        CONF_PASSWORD: password,
                        CONF_REFRESH_TOKEN: client.refresh_token,
                    },
                )

        suggested_email = (
            user_input.get(CONF_EMAIL)
            if user_input is not None
            else reconfigure_entry.data.get(CONF_EMAIL, "")
        )
        schema = self.add_suggested_values_to_schema(
            STEP_USER_DATA_SCHEMA,
            {CONF_EMAIL: suggested_email},
        )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=schema,
            errors=errors,
        )
