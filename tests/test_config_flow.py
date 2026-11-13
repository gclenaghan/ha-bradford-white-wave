"""Tests for the Bradford White Wave config flow."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from bradford_white_wave_client import (
    BradfordWhiteAuthError,
    BradfordWhiteConnectError,
)
from homeassistant import config_entries
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.helpers.selector import TextSelector, TextSelectorType

from custom_components.bradford_white_wave.config_flow import (
    STEP_USER_DATA_SCHEMA,
    ConfigFlow,
)

from .conftest import FAKE_HA_SESSION, AbortFlow


def test_user_schema_uses_text_selectors() -> None:
    """Ensure the user form schema uses EMAIL and PASSWORD TextSelectors."""
    validated = STEP_USER_DATA_SCHEMA({CONF_EMAIL: "user@example.com", CONF_PASSWORD: "secret"})
    assert validated == {CONF_EMAIL: "user@example.com", CONF_PASSWORD: "secret"}

    validators = list(STEP_USER_DATA_SCHEMA.schema.values())
    assert len(validators) == 2
    assert all(isinstance(v, TextSelector) for v in validators)
    assert validators[0].config["type"] == TextSelectorType.EMAIL
    assert validators[1].config["type"] == TextSelectorType.PASSWORD


async def test_user_step_creates_entry_with_session_and_dynamic_title() -> None:
    """Test initial setup authenticates with HA session and creates entry."""
    flow = ConfigFlow()
    form = await flow.async_step_user()
    assert form["type"] == "form"
    assert form["step_id"] == "user"

    mock_client = MagicMock()
    mock_client.authenticate_with_credentials = AsyncMock()
    mock_client.close = AsyncMock()
    mock_client.account_id = "acct-123"
    mock_client.refresh_token = "rt-initial"

    with patch(
        "custom_components.bradford_white_wave.config_flow.BradfordWhiteClient",
        return_value=mock_client,
    ) as client_cls:
        result = await flow.async_step_user(
            {CONF_EMAIL: "  user@example.com  ", CONF_PASSWORD: "pw"}
        )

    client_cls.assert_called_once_with(session=FAKE_HA_SESSION)
    mock_client.authenticate_with_credentials.assert_awaited_once_with("user@example.com", "pw")
    mock_client.close.assert_awaited_once()
    assert result == {
        "type": "create_entry",
        "title": "Bradford White Wave (user@example.com)",
        "data": {
            "email": "user@example.com",
            "password": "pw",
            "refresh_token": "rt-initial",
        },
    }


async def test_user_step_aborts_if_already_configured() -> None:
    """Test duplicate account configuration aborts cleanly."""
    flow = ConfigFlow()
    flow._existing_unique_ids.add("acct-123")

    mock_client = MagicMock()
    mock_client.authenticate_with_credentials = AsyncMock()
    mock_client.close = AsyncMock()
    mock_client.account_id = "acct-123"
    mock_client.refresh_token = "rt-new"

    with (
        patch(
            "custom_components.bradford_white_wave.config_flow.BradfordWhiteClient",
            return_value=mock_client,
        ),
        pytest.raises(AbortFlow) as exc_info,
    ):
        await flow.async_step_user({CONF_EMAIL: "user@example.com", CONF_PASSWORD: "pw"})

    assert exc_info.value.reason == "already_configured"


@pytest.mark.parametrize(
    ("raised_exc", "expected_error"),
    [
        (BradfordWhiteAuthError("invalid credentials"), "invalid_auth"),
        (BradfordWhiteConnectError("network timeout"), "cannot_connect"),
        (RuntimeError("boom"), "unknown"),
    ],
)
async def test_user_step_error_mapping(raised_exc: Exception, expected_error: str) -> None:
    """Test auth, transport, and unexpected errors map to config flow error keys."""
    flow = ConfigFlow()
    mock_client = MagicMock()
    mock_client.authenticate_with_credentials = AsyncMock(side_effect=raised_exc)
    mock_client.close = AsyncMock()

    with patch(
        "custom_components.bradford_white_wave.config_flow.BradfordWhiteClient",
        return_value=mock_client,
    ):
        result = await flow.async_step_user({CONF_EMAIL: "user@example.com", CONF_PASSWORD: "pw"})

    assert result["type"] == "form"
    assert result["errors"] == {"base": expected_error}
    mock_client.close.assert_awaited_once()


async def test_reauth_and_reconfigure_flows() -> None:
    """Test reauth, legacy entry upgrade, reconfigure, and wrong-account protection."""
    flow = ConfigFlow()
    flow.source = config_entries.SOURCE_REAUTH

    form = await flow.async_step_reauth({"refresh_token": "expired"})
    assert form["step_id"] == "reauth_confirm"

    mock_client = MagicMock()
    mock_client.authenticate_with_credentials = AsyncMock()
    mock_client.close = AsyncMock()
    mock_client.account_id = "acct-123"
    mock_client.refresh_token = "rt-rotated"

    with patch(
        "custom_components.bradford_white_wave.config_flow.BradfordWhiteClient",
        return_value=mock_client,
    ):
        reauth_res = await flow.async_step_reauth_confirm(
            {CONF_EMAIL: "u@example.com", CONF_PASSWORD: "updated"}
        )

    assert reauth_res == {
        "type": "abort",
        "reason": "reauth_successful",
        "data": {
            "email": "u@example.com",
            "password": "updated",
            "refresh_token": "rt-rotated",
        },
    }

    # Wrong account during reconfigure must abort
    flow_mismatch = ConfigFlow()
    flow_mismatch.source = config_entries.SOURCE_RECONFIGURE
    mock_client.account_id = "acct-other"
    with (
        patch(
            "custom_components.bradford_white_wave.config_flow.BradfordWhiteClient",
            return_value=mock_client,
        ),
        pytest.raises(AbortFlow) as exc_info,
    ):
        await flow_mismatch.async_step_reconfigure(
            {CONF_EMAIL: "other@example.com", CONF_PASSWORD: "pw"}
        )
    assert exc_info.value.reason == "wrong_account"

    # Matching account during reconfigure reloads entry
    flow_reconf = ConfigFlow()
    flow_reconf.source = config_entries.SOURCE_RECONFIGURE
    mock_client.account_id = "acct-123"
    with patch(
        "custom_components.bradford_white_wave.config_flow.BradfordWhiteClient",
        return_value=mock_client,
    ):
        reconf_res = await flow_reconf.async_step_reconfigure(
            {CONF_EMAIL: "u@example.com", CONF_PASSWORD: "pw2"}
        )
    assert reconf_res["reason"] == "reconfigure_successful"
    assert reconf_res["data"]["password"] == "pw2"
