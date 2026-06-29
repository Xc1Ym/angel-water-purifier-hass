"""Config flow for the Angel Water Purifier integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .const import (
    CONF_ACCESS_TOKEN,
    CONF_SN,
    CONF_USER_ID,
    CONF_WX_OPEN_ID,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class AngelWaterPurifierConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Angel Water Purifier."""

    VERSION = 1
    MINOR_VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial configuration step.

        Configuration is based on reverse-engineered Angel IoT Cloud API
        (iot.angelgroup.com.cn) used by the WeChat mini-program.
        """
        errors: dict[str, str] = {}

        if user_input is not None:
            return self.async_create_entry(
                title=user_input.get(
                    CONF_NAME,
                    f"安吉尔净水器 (SN: {user_input[CONF_SN]})",
                ),
                data={
                    CONF_SN: user_input[CONF_SN],
                    CONF_ACCESS_TOKEN: user_input.get(CONF_ACCESS_TOKEN, ""),
                    CONF_USER_ID: user_input.get(CONF_USER_ID, ""),
                    CONF_WX_OPEN_ID: user_input.get(CONF_WX_OPEN_ID, ""),
                    CONF_SCAN_INTERVAL: user_input.get(
                        CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                    ),
                },
            )

        data_schema = vol.Schema({
            vol.Required(CONF_SN): str,
            vol.Optional(CONF_ACCESS_TOKEN, default=""): str,
            vol.Optional(CONF_USER_ID, default=""): str,
            vol.Optional(CONF_WX_OPEN_ID, default=""): str,
            vol.Optional(
                CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL
            ): vol.All(vol.Coerce(int), vol.Range(min=30, max=3600)),
        })

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
            description_placeholders={
                "api_base": "iot.angelgroup.com.cn",
            },
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Create the options flow."""
        return AngelWaterPurifierOptionsFlow(config_entry)


class AngelWaterPurifierOptionsFlow(config_entries.OptionsFlow):
    """Handle options."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Optional(
                    CONF_SCAN_INTERVAL,
                    default=self.config_entry.options.get(
                        CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                    ),
                ): vol.All(vol.Coerce(int), vol.Range(min=30, max=3600)),
            }),
        )
