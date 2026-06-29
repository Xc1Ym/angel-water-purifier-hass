"""Sensor platform for the Angel Water Purifier integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    DOMAIN,
    MANUFACTURER,
    SENSOR_TYPES,
    WARN_CODE_MAP,
    WORKING_STATUS_MAP,
)
from .coordinator import AngelWaterPurifierCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Angel Water Purifier sensor entities."""
    coordinator: AngelWaterPurifierCoordinator = hass.data[DOMAIN][entry.entry_id][
        "coordinator"
    ]

    entities: list[AngelWaterPurifierSensor] = []

    for sensor_key, sensor_config in SENSOR_TYPES.items():
        entities.append(
            AngelWaterPurifierSensor(
                coordinator=coordinator,
                entry=entry,
                sensor_key=sensor_key,
                description=SensorEntityDescription(
                    key=sensor_key,
                    name=sensor_config["name"],
                    native_unit_of_measurement=sensor_config.get(
                        "native_unit_of_measurement"
                    ),
                    icon=sensor_config.get("icon"),
                    device_class=sensor_config.get("device_class"),
                    state_class=sensor_config.get("state_class"),
                    entity_category=sensor_config.get("entity_category"),
                    translation_key=sensor_key,
                ),
            )
        )

    async_add_entities(entities)


class AngelWaterPurifierSensor(CoordinatorEntity[AngelWaterPurifierCoordinator], SensorEntity):
    """Representation of an Angel Water Purifier sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: AngelWaterPurifierCoordinator,
        entry: ConfigEntry,
        sensor_key: str,
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._sensor_key = sensor_key
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_{sensor_key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer=MANUFACTURER,
            model=entry.data.get("model", "Water Purifier"),
            sw_version=entry.data.get("sw_version", ""),
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle updated data from the coordinator."""
        data = self.coordinator.data
        if data is None:
            return

        raw_value = data.get(self._sensor_key)
        if raw_value is None:
            self._attr_native_value = None
            self._attr_available = False
        else:
            processed = self._process_value(raw_value)
            if processed is not None:
                self._attr_native_value = processed
                self._attr_available = True

        self.async_write_ha_state()

    def _process_value(self, raw_value: Any):
        """Transform raw value based on sensor type."""
        if raw_value is None:
            return None

        # Working status -> human readable (deviceState is a string: "0", "1", etc.)
        if self._sensor_key == "working_status":
            return WORKING_STATUS_MAP.get(
                str(raw_value), f"unknown ({raw_value})"
            )

        # Warn code -> human readable (warnCode is a string: "", "E1", etc.)
        if self._sensor_key == "error_code":
            return WARN_CODE_MAP.get(str(raw_value), str(raw_value))

        # Error message (pass through)
        if self._sensor_key == "error_message":
            return str(raw_value) if raw_value else None

        # Device info (pass through as string)
        if self._sensor_key == "device_name":
            return str(raw_value)

        # Refresh time (pass through, device_class=timestamp will handle it)
        if self._sensor_key == "refresh_time":
            return raw_value

        # TDS (整数值)
        if self._sensor_key in ("tds_in", "tds_out"):
            return round(float(raw_value), 0)

        # 脱盐率 (百分比)
        if self._sensor_key == "tds_rejection_rate":
            return round(float(raw_value), 1)

        # 滤芯剩余 (百分比, 0-100)
        if "remaining" in self._sensor_key:
            return max(0, min(100, float(raw_value)))

        # 流量
        if self._sensor_key == "flow_rate":
            return round(float(raw_value), 2)

        # 水压
        if self._sensor_key == "water_pressure":
            return round(float(raw_value), 3)

        # 累计水量/今日用水
        if self._sensor_key in (
            "total_water_usage", "total_water_in",
            "today_pure_water", "today_total_water",
        ):
            return round(float(raw_value), 2)

        # Default numeric fallback
        try:
            return round(float(raw_value), 2)
        except (ValueError, TypeError):
            return raw_value

    @property
    def native_value(self):
        """Return the state of the sensor."""
        data = self.coordinator.data
        if data is None:
            return None

        raw_value = data.get(self._sensor_key)
        if raw_value is None:
            return None
        return self._process_value(raw_value)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        if self.coordinator.data is None:
            return False
        return self._sensor_key in self.coordinator.data
