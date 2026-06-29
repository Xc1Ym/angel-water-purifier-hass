"""Data update coordinator for the Angel Water Purifier integration."""
from __future__ import annotations

from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, DEFAULT_SCAN_INTERVAL, LOGGER as _LOGGER


class AngelWaterPurifierCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator to manage fetching water purifier data."""

    def __init__(
        self,
        hass: HomeAssistant,
        device_api: AngelDeviceAPI,
        scan_interval: int = DEFAULT_SCAN_INTERVAL,
    ) -> None:
        """Initialize coordinator."""
        super().__init__(
            hass=hass,
            logger=_LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
        )
        self.device_api = device_api

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch data from the device."""
        try:
            data = await self.device_api.async_fetch_data()
            if data is None:
                raise UpdateFailed("Failed to fetch data from device: no data returned")
            return data
        except Exception as err:
            raise UpdateFailed(f"Error communicating with device: {err}") from err


class AngelDeviceAPI:
    """Abstraction layer for communicating with Angel water purifiers.

    This base class defines the interface. Subclasses implement protocol-specific
    communication (local TCP/UDP, Tuya, MiHome, etc.).
    """

    def __init__(self, hass: HomeAssistant, config: dict[str, Any]) -> None:
        """Initialize the device API."""
        self.hass = hass
        self.config = config
        self._connected = False

    @property
    def connected(self) -> bool:
        """Return whether the device is connected."""
        return self._connected

    async def async_connect(self) -> bool:
        """Establish connection to the device."""
        raise NotImplementedError

    async def async_disconnect(self) -> None:
        """Disconnect from the device."""
        raise NotImplementedError

    async def async_fetch_data(self) -> dict[str, Any]:
        """Fetch the full device state.

        Returns a dict with keys matching SENSOR_TYPES in const.py.
        """
        raise NotImplementedError

    async def async_set(self, key: str, value: Any) -> bool:
        """Send a command to the device."""
        raise NotImplementedError
