"""Integration for Angel (安吉尔) Water Purifier."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .api import AngelCloudAPI
from .const import (
    CONF_ACCESS_TOKEN,
    CONF_SN,
    CONF_USER_ID,
    CONF_WX_OPEN_ID,
    CONF_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MANUFACTURER,
)
from .coordinator import AngelWaterPurifierCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.BINARY_SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Angel Water Purifier from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    config = {**entry.data, **entry.options}

    # Instantiate the Angel IoT cloud API
    device_api = AngelCloudAPI(
        hass=hass,
        config=config,
        sn=config.get(CONF_SN, ""),
        token=config.get(CONF_ACCESS_TOKEN, ""),
        user_id=config.get(CONF_USER_ID, ""),
        wx_open_id=config.get(CONF_WX_OPEN_ID, ""),
    )

    # Validate connection
    connected = await device_api.async_connect()
    if not connected:
        _LOGGER.warning(
            "Failed to connect to Angel IoT cloud for device SN: %s",
            config.get(CONF_SN, "unknown"),
        )

    # Create coordinator
    scan_interval = config.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    coordinator = AngelWaterPurifierCoordinator(
        hass=hass,
        device_api=device_api,
        scan_interval=scan_interval,
    )

    # Fetch first data
    await coordinator.async_config_entry_first_refresh()

    # Store coordinator for platforms
    hass.data[DOMAIN][entry.entry_id] = {
        "coordinator": coordinator,
        "device_api": device_api,
    }

    # Register device with actual model info from API
    _register_device(hass, entry, device_api)

    # Set up platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Reload handler
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        device_api = hass.data[DOMAIN][entry.entry_id].get("device_api")
        if device_api:
            await device_api.async_disconnect()
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload a config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate config entry to a newer version."""
    _LOGGER.debug(
        "Migrating Angel Water Purifier config entry from version %s",
        entry.version
    )
    return True


def _register_device(
    hass: HomeAssistant,
    entry: ConfigEntry,
    device_api: AngelCloudAPI | None = None,
) -> None:
    """Register the device in the device registry."""
    model = "Water Purifier"
    sw_version = ""

    if device_api is not None:
        dev_info = device_api.device_info
        model = dev_info.get("model", model)
        sw_version = dev_info.get("sw_version", sw_version)

    device_registry = dr.async_get(hass)
    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id)},
        name=entry.title,
        manufacturer=MANUFACTURER,
        model=model,
        sw_version=sw_version,
    )
