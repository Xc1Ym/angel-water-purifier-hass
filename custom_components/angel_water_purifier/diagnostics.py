"""Diagnostics support for Angel Water Purifier.

Helps debug the API field mapping by showing raw response data.
"""
from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for a config entry.

    返回诊断信息，方便排查 API 字段映射问题。
    """
    data = hass.data.get(DOMAIN, {})
    entry_data = data.get(entry.entry_id, {})

    coordinator = entry_data.get("coordinator")
    device_api = entry_data.get("device_api")

    diagnostics = {
        "config_entry": {
            "title": entry.title,
            "data": {
                "sn": entry.data.get("sn", ""),
                "user_id": entry.data.get("user_id", ""),
                "wx_open_id": entry.data.get("wx_open_id", ""),
                # Token 不输出完整值，仅标记是否已配置
                "access_token_configured": bool(entry.data.get("access_token")),
            },
            "options": dict(entry.options),
        },
        "device_api": {
            "connected": device_api.connected if device_api else None,
            "sn": device_api.sn if hasattr(device_api, "sn") else None,
            "device_info": device_api.device_info if hasattr(device_api, "device_info") else None,
        },
        "coordinator": {
            "last_update_success": coordinator.last_update_success if coordinator else None,
            "data_available": coordinator.data is not None if coordinator else None,
            "sensor_count": len(coordinator.data) if coordinator and coordinator.data else 0,
        },
        "sensor_data": dict(coordinator.data) if coordinator and coordinator.data else None,
    }

    return diagnostics
