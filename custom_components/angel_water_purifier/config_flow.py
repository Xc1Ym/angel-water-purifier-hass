"""Config flow for the Angel Water Purifier integration."""
from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .api import AngelCloudAPI
from .const import (
    CONF_ACCESS_TOKEN,
    CONF_REFRESH_TOKEN,
    CONF_SN,
    CONF_USER_ID,
    CONF_WX_OPEN_ID,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""


class AngelWaterPurifierConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Angel Water Purifier."""

    VERSION = 1
    MINOR_VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._pending_input: dict[str, Any] = {}
        self._discovered_devices: list[dict[str, str]] = []

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial configuration step.

        Configuration is based on reverse-engineered Angel IoT Cloud API
        (iot.angelgroup.com.cn) used by the WeChat mini-program.

        SN 可留空：填写 wxOpenId 后自动发现账号绑定的设备；
        多台设备时进入选择步骤。
        """
        errors: dict[str, str] = {}

        if user_input is not None:
            sn = str(user_input.get(CONF_SN, "")).strip()

            if sn:
                # 手动填了 SN：直接验证
                if await self._try_validate(user_input, errors):
                    return await self._create_entry(user_input)
            else:
                # 未填 SN：自动发现
                try:
                    devices = await self._discover_devices(user_input)
                except InvalidAuth:
                    errors["base"] = "invalid_auth"
                except CannotConnect:
                    errors["base"] = "cannot_connect"
                else:
                    if devices is None:
                        errors["base"] = "need_wxopenid"
                    elif not devices:
                        errors["base"] = "no_devices"
                    elif len(devices) == 1:
                        # 单台设备：直接采用并验证
                        user_input = {**user_input, CONF_SN: devices[0]["sn"]}
                        if await self._try_validate(user_input, errors):
                            return await self._create_entry(user_input)
                    else:
                        # 多台设备：进入选择步骤
                        self._pending_input = user_input
                        self._discovered_devices = devices
                        return await self.async_step_select_device()

        data_schema = vol.Schema({
            vol.Optional(CONF_SN, default=""): str,
            vol.Optional(CONF_ACCESS_TOKEN, default=""): str,
            vol.Optional(CONF_REFRESH_TOKEN, default=""): str,
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

    async def async_step_select_device(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the device selection step (multiple devices found)."""
        errors: dict[str, str] = {}

        if user_input is not None:
            data = {**self._pending_input, CONF_SN: user_input[CONF_SN]}
            if await self._try_validate(data, errors):
                return await self._create_entry(data)

        options = {
            d["sn"]: f"{d['name']} ({d['sn']})" for d in self._discovered_devices
        }
        return self.async_show_form(
            step_id="select_device",
            data_schema=vol.Schema({
                vol.Required(CONF_SN): vol.In(options),
            }),
            errors=errors,
        )

    async def _try_validate(
        self, user_input: dict[str, Any], errors: dict[str, str]
    ) -> bool:
        """验证凭证，失败时填充错误信息."""
        try:
            await self._validate_input(user_input)
        except CannotConnect:
            errors["base"] = "cannot_connect"
            return False
        except InvalidAuth:
            errors["base"] = "invalid_auth"
            return False
        except Exception:  # noqa: BLE001 - 未知错误统一提示
            _LOGGER.exception("Unexpected error during validation")
            errors["base"] = "unknown"
            return False
        return True

    async def _validate_input(self, user_input: dict[str, Any]) -> None:
        """验证凭证：真实请求一次 API，无效则抛出对应错误.

        配置了 refresh_token 时会先刷新换取最新 token 再验证。
        """
        api = AngelCloudAPI(
            hass=self.hass,
            config=user_input,
            sn=user_input[CONF_SN],
            token=user_input.get(CONF_ACCESS_TOKEN, ""),
            refresh_token=user_input.get(CONF_REFRESH_TOKEN, ""),
            user_id=user_input.get(CONF_USER_ID, ""),
            wx_open_id=user_input.get(CONF_WX_OPEN_ID, ""),
        )
        connected = await api.async_connect()
        await api.async_disconnect()

        if not connected:
            if api.last_error == "invalid_auth":
                raise InvalidAuth
            raise CannotConnect

    async def _discover_devices(
        self, user_input: dict[str, Any]
    ) -> list[dict[str, str]] | None:
        """调用账号接口发现绑定设备列表（SN 留空时使用）."""
        api = AngelCloudAPI(
            hass=self.hass,
            config=user_input,
            sn="",
            token=user_input.get(CONF_ACCESS_TOKEN, ""),
            refresh_token=user_input.get(CONF_REFRESH_TOKEN, ""),
            user_id=user_input.get(CONF_USER_ID, ""),
            wx_open_id=user_input.get(CONF_WX_OPEN_ID, ""),
        )
        try:
            return await api.async_discover_devices()
        finally:
            await api.async_disconnect()

    async def _create_entry(self, user_input: dict[str, Any]) -> FlowResult:
        """创建配置条目（SN 已确定）."""
        sn = user_input[CONF_SN]

        await self.async_set_unique_id(sn)
        self._abort_if_unique_id_configured()

        return self.async_create_entry(
            title=user_input.get(
                CONF_NAME,
                f"安吉尔净水器 (SN: {sn})",
            ),
            data={
                CONF_SN: sn,
                CONF_ACCESS_TOKEN: user_input.get(CONF_ACCESS_TOKEN, ""),
                CONF_REFRESH_TOKEN: user_input.get(CONF_REFRESH_TOKEN, ""),
                CONF_USER_ID: user_input.get(CONF_USER_ID, ""),
                CONF_WX_OPEN_ID: user_input.get(CONF_WX_OPEN_ID, ""),
                CONF_SCAN_INTERVAL: user_input.get(
                    CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                ),
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

        current = {
            **self.config_entry.data,
            **self.config_entry.options,
        }
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema({
                vol.Optional(
                    CONF_SCAN_INTERVAL,
                    default=current.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                ): vol.All(vol.Coerce(int), vol.Range(min=30, max=3600)),
                # refresh_token 可选：填写后 access_token 过期自动续期，无需手动更新
                vol.Optional(
                    CONF_REFRESH_TOKEN,
                    default=current.get(CONF_REFRESH_TOKEN, ""),
                ): str,
            }),
        )
