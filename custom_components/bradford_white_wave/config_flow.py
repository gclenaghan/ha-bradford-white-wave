"""Config flow for Bradford White Wave integration."""

from __future__ import annotations

import logging
from typing import Any

from bradford_white_wave_client import BradfordWhiteClient
from bradford_white_wave_client.exceptions import BradfordWhiteConnectError, BradfordWhiteAuthError
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult
import voluptuous as vol

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

STEP_USER_DATA_Schema = vol.Schema(
    {
        vol.Required("url"): str,
    }
)

class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Bradford White Wave."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}
        
        # We need a client instance to generate the auth url
        client = BradfordWhiteClient()
        auth_url = client.get_authorization_url()
        
        if user_input is not None:
            url = user_input["url"]
            
            try:
                await client.authenticate_with_code(url)
            except (BradfordWhiteConnectError, BradfordWhiteAuthError) as err:
                 _LOGGER.error("Auth failed: %s", err)
                 errors["base"] = "invalid_auth"
            except Exception:
                 _LOGGER.exception("Unexpected exception during auth")
                 errors["base"] = "unknown"
            finally:
                 await client.close()

            if not errors:
                if client._account_id:
                     await self.async_set_unique_id(client._account_id)
                     self._abort_if_unique_id_configured(
                         updates={"refresh_token": client._refresh_token}
                     )
                
                return self.async_create_entry(
                    title="Bradford White Wave",
                    data={
                        "refresh_token": client._refresh_token
                    },
                )

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_Schema,
            errors=errors,
            description_placeholders={
                "auth_url": auth_url
            }
        )

    async def async_step_reauth(
        self, entry_data: dict[str, Any]
    ) -> FlowResult:
        """Handle reauthentication."""
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Confirm reauthentication."""
        errors: dict[str, str] = {}
        client = BradfordWhiteClient()
        auth_url = client.get_authorization_url()

        if user_input is not None:
            url = user_input["url"]
            try:
                await client.authenticate_with_code(url)
                
                if client._account_id:
                     await self.async_set_unique_id(client._account_id)
                     self._abort_if_unique_id_mismatch(reason="wrong_account")
                
                return self.async_update_reload_and_abort(
                     self._get_reauth_entry(),
                     data={"refresh_token": client._refresh_token},
                )
            except (BradfordWhiteConnectError, BradfordWhiteAuthError) as err:
                 _LOGGER.error("Auth failed: %s", err)
                 errors["base"] = "invalid_auth"
            except Exception:
                 _LOGGER.exception("Unexpected exception during auth")
                 errors["base"] = "unknown"
            finally:
                 await client.close()

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=STEP_USER_DATA_Schema,
            errors=errors,
            description_placeholders={
                "auth_url": auth_url
            }
        )
