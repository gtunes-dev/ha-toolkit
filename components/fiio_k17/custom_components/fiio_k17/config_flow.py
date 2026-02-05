"""Config flow for FiiO K17 integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.helpers import selector

from .client import FiiOK17Client
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "FiiO K17"

STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
    }
)


class FiiOK17ConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for FiiO K17."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._host: str | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the initial step - get IP and test connection."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST]

            # Check if already configured
            await self.async_set_unique_id(host)
            self._abort_if_unique_id_configured()

            # Test connection
            client = FiiOK17Client(host)
            try:
                await client.connect()
                await client.disconnect()
            except ConnectionError:
                errors["base"] = "cannot_connect"
            except Exception:
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                # Connection successful, proceed to name/area step
                self._host = host
                return await self.async_step_configure()

        return self.async_show_form(
            step_id="user",
            data_schema=STEP_USER_DATA_SCHEMA,
            errors=errors,
        )

    async def async_step_configure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the configuration step - get name and area."""
        if user_input is not None:
            name = user_input.get(CONF_NAME, DEFAULT_NAME)
            data = {CONF_HOST: self._host}
            # Store area if provided
            if area := user_input.get("area"):
                data["area"] = area
            # Title becomes the device name (accessed via entry.title)
            return self.async_create_entry(
                title=name,
                data=data,
            )

        return self.async_show_form(
            step_id="configure",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_NAME, default=DEFAULT_NAME): str,
                    vol.Optional("area"): selector.AreaSelector(),
                }
            ),
        )
