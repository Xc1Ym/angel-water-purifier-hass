"""Binary sensor platform for the Angel Water Purifier integration."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, FILTER_KEYS
from .coordinator import AngelWaterPurifierCoordinator

_LOGGER = logging.getLogger(__name__)

BINARY_SENSOR_TYPES: dict[str, dict[str, Any]] = {
    # 在线状态 (API 直接提供)
    "online_state": {
        "name": "在线状态",
        "device_class": BinarySensorDeviceClass.CONNECTIVITY,
        "icon": "mdi:wifi",
        "entity_category": "diagnostic",
    },
    # 开关状态
    "is_open": {
        "name": "开关",
        "device_class": BinarySensorDeviceClass.POWER,
        "icon": "mdi:power",
        "entity_category": "diagnostic",
    },
    # 冲洗中
    "is_flushing": {
        "name": "冲洗中",
        "device_class": BinarySensorDeviceClass.RUNNING,
        "icon": "mdi:water-sync",
        "entity_category": "diagnostic",
    },
    # 热水出水口
    "hot_water_outlet": {
        "name": "热水出水",
        "device_class": BinarySensorDeviceClass.HEAT,
        "icon": "mdi:water-thermometer",
        "entity_category": "diagnostic",
    },
    # 工作状态 (衍生: deviceState == "1")
    "is_working": {
        "name": "运行中",
        "device_class": BinarySensorDeviceClass.RUNNING,
        "icon": "mdi:water-pump",
        "entity_category": "diagnostic",
    },
    # 滤芯更换提醒
    "filter_change_required": {
        "name": "需要更换滤芯",
        "device_class": BinarySensorDeviceClass.PROBLEM,
        "icon": "mdi:filter-remove",
        "entity_category": "diagnostic",
    },
    # 漏水检测 (从故障码衍生)
    "leak_detected": {
        "name": "漏水检测",
        "device_class": BinarySensorDeviceClass.MOISTURE,
        "icon": "mdi:water-alert",
        "entity_category": "diagnostic",
    },
    # 水质警告
    "water_quality_warning": {
        "name": "水质警告",
        "device_class": BinarySensorDeviceClass.PROBLEM,
        "icon": "mdi:water-alert",
        "entity_category": "diagnostic",
    },
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Angel Water Purifier binary sensors."""
    coordinator: AngelWaterPurifierCoordinator = hass.data[DOMAIN][entry.entry_id][
        "coordinator"
    ]

    entities: list[AngelWaterPurifierBinarySensor] = []

    for sensor_key, sensor_config in BINARY_SENSOR_TYPES.items():
        entities.append(
            AngelWaterPurifierBinarySensor(
                coordinator=coordinator,
                entry=entry,
                sensor_key=sensor_key,
                description=BinarySensorEntityDescription(
                    key=sensor_key,
                    name=sensor_config["name"],
                    device_class=sensor_config.get("device_class"),
                    icon=sensor_config.get("icon"),
                    entity_category=sensor_config.get("entity_category"),
                    translation_key=sensor_key,
                ),
            )
        )

    async_add_entities(entities)


class AngelWaterPurifierBinarySensor(
    CoordinatorEntity[AngelWaterPurifierCoordinator],
    BinarySensorEntity,
):
    """Representation of an Angel Water Purifier binary sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: AngelWaterPurifierCoordinator,
        entry: ConfigEntry,
        sensor_key: str,
        description: BinarySensorEntityDescription,
    ) -> None:
        """Initialize the binary sensor."""
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
            self._attr_available = False
            self._attr_is_on = None
            self.async_write_ha_state()
            return

        is_on = self._derive_state(data)
        self._attr_is_on = is_on
        self._attr_available = is_on is not None
        self.async_write_ha_state()

    @property
    def is_on(self) -> bool | None:
        """Return true if the binary sensor is on."""
        data = self.coordinator.data
        if data is None:
            return None
        return self._derive_state(data)

    def _derive_state(self, data: dict[str, Any]) -> bool | None:
        """Derive binary state from coordinator data."""
        if self._sensor_key == "online_state":
            val = data.get("online_state")
            if isinstance(val, bool):
                return val
            if isinstance(val, str):
                return val.lower() == "true"
            return None

        if self._sensor_key == "is_open":
            val = data.get("is_open")
            if isinstance(val, str):
                return val == "1"
            if isinstance(val, (int, float)):
                return bool(val)
            return None

        if self._sensor_key == "is_flushing":
            val = data.get("is_flushing")
            if isinstance(val, (int, float)):
                return bool(val)
            return None

        if self._sensor_key == "hot_water_outlet":
            val = data.get("hot_water_outlet")
            if isinstance(val, (int, float)):
                return bool(val)
            return None

        if self._sensor_key == "is_working":
            status = data.get("working_status")
            # working_status 在传感器中已被转为字符串 "working"/"standby"
            if isinstance(status, str):
                return status in ("working", "working (1)")
            return None

        if self._sensor_key == "filter_change_required":
            # 检查 PCR 滤芯是否低于阈值
            for key in FILTER_KEYS:
                val = data.get(key)
                if val is not None:
                    try:
                        if float(val) <= 5:
                            return True
                    except (ValueError, TypeError):
                        pass
            return False

        if self._sensor_key == "leak_detected":
            warn = data.get("error_code", "")
            return str(warn) == "E1"

        if self._sensor_key == "water_quality_warning":
            tds_out = data.get("tds_out")
            if tds_out is not None:
                try:
                    return float(tds_out) > 50
                except (ValueError, TypeError):
                    pass
            return None

        return None
