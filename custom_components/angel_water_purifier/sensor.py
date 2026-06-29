"""Sensor platform for the Angel Water Purifier integration."""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    BULK_SENSORS,
    DOMAIN,
    FILTER_SENSOR_DEFS,
    MANUFACTURER,
    MAX_FILTERS,
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

    # ---- Bulk sensors (always present) ----
    for sensor_key, cfg in BULK_SENSORS.items():
        entities.append(
            _make_sensor(coordinator, entry, sensor_key, cfg)
        )

    # ---- Filter sensors (0..MAX_FILTERS per device) ----
    for idx in range(1, MAX_FILTERS + 1):
        prefix = f"filter_{idx}"
        for sub_key, sub_cfg in FILTER_SENSOR_DEFS.items():
            sensor_key = f"{prefix}_{sub_key}"
            # Build name: "滤芯 1 剩余寿命"
            filter_name = f"滤芯 {idx}"
            name = f"{filter_name} {sub_cfg['name_suffix']}"
            entities.append(
                _make_filter_sensor(
                    coordinator, entry, sensor_key, name, sub_cfg
                )
            )

    _LOGGER.debug("📋 创建 %d 个传感器实体", len(entities))
    async_add_entities(entities)


def _resolve_category(cat: str | None) -> EntityCategory | None:
    """Convert category string to EntityCategory enum."""
    if cat == "diagnostic":
        return EntityCategory.DIAGNOSTIC
    if cat == "config":
        return EntityCategory.CONFIG
    return None


def _make_sensor(
    coordinator: AngelWaterPurifierCoordinator,
    entry: ConfigEntry,
    sensor_key: str,
    cfg: dict,
) -> AngelWaterPurifierSensor:
    """Create a bulk sensor entity."""
    return AngelWaterPurifierSensor(
        coordinator=coordinator,
        entry=entry,
        sensor_key=sensor_key,
        description=SensorEntityDescription(
            key=sensor_key,
            name=cfg["name"],
            native_unit_of_measurement=cfg.get("unit"),
            icon=cfg.get("icon"),
            device_class=cfg.get("device_class"),
            state_class=cfg.get("state_class"),
            entity_category=_resolve_category(cfg.get("cat")),
            translation_key=sensor_key,
        ),
    )


def _make_filter_sensor(
    coordinator: AngelWaterPurifierCoordinator,
    entry: ConfigEntry,
    sensor_key: str,
    display_name: str,
    cfg: dict,
) -> AngelWaterPurifierSensor:
    """Create a filter sensor entity."""
    return AngelWaterPurifierSensor(
        coordinator=coordinator,
        entry=entry,
        sensor_key=sensor_key,
        description=SensorEntityDescription(
            key=sensor_key,
            name=display_name,
            native_unit_of_measurement=cfg.get("unit"),
            icon=cfg.get("icon"),
            device_class=None,
            state_class=cfg.get("state_class", "measurement" if cfg.get("unit") else None),
            entity_category=_resolve_category(cfg.get("cat")),
            translation_key=sensor_key,
        ),
    )


class AngelWaterPurifierSensor(
    CoordinatorEntity[AngelWaterPurifierCoordinator],
    SensorEntity,
):
    """Representation of an Angel Water Purifier sensor."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: AngelWaterPurifierCoordinator,
        entry: ConfigEntry,
        sensor_key: str,
        description: SensorEntityDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._sensor_key = sensor_key
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_{sensor_key}"
        # 显式设置图标，确保 entity_description.icon 生效
        if description.icon:
            self._attr_icon = description.icon
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=entry.title,
            manufacturer=MANUFACTURER,
            model=entry.data.get("model", "Water Purifier"),
            sw_version=entry.data.get("sw_version", ""),
        )

    @callback
    def _handle_coordinator_update(self) -> None:
        data = self.coordinator.data
        if data is None:
            self._attr_available = False
            self._attr_native_value = None
            self.async_write_ha_state()
            return

        raw = data.get(self._sensor_key)
        if raw is None:
            self._attr_available = False
            self._attr_native_value = None
        else:
            processed = self._apply_transform(raw)
            self._attr_native_value = processed
            self._attr_available = processed is not None

        self.async_write_ha_state()

    @property
    def native_value(self):
        data = self.coordinator.data
        if data is None:
            return None
        raw = data.get(self._sensor_key)
        if raw is None:
            return None
        return self._apply_transform(raw)

    @property
    def available(self) -> bool:
        if self.coordinator.data is None:
            return False
        return self._sensor_key in self.coordinator.data

    # ------------------------------------------------------------------ #
    #  Value transformation
    # ------------------------------------------------------------------ #

    def _apply_transform(self, raw: Any) -> Any:
        """Convert raw value to display value."""
        if raw is None:
            return None

        key = self._sensor_key

        # ---- Strings ----
        if key == "working_status":
            return WORKING_STATUS_MAP.get(str(raw), f"unknown ({raw})")

        if key in ("error_code", "warn_code"):
            return WARN_CODE_MAP.get(str(raw), str(raw))

        if key in ("error_message", "warn_msg"):
            return str(raw) if raw else None

        if key in ("device_name", "serial_number", "product_model",
                    "product_name", "product_code"):
            return str(raw)

        # ---- Timestamps ----
        if key in ("refresh_time", "active_time"):
            # Format: "2026-06-29 10:35:29"
            if isinstance(raw, str) and raw:
                try:
                    return datetime.fromisoformat(raw)
                except (ValueError, TypeError):
                    return raw
            return raw

        # ---- Booleans / Switches (0/1/"0"/"1") ----
        if key in ("is_open", "online_state", "wash_state", "hot_water_outlet",
                    "reminder_push", "water_intake_push", "machine_failure_push",
                    "salinity_push", "receive_water_usage_month",
                    "receive_filter_replace", "target_switch",
                    "regeneration_step", "bind_type",
                    *[f"filter_{i}_life_style" for i in range(1, MAX_FILTERS + 1)]):
            if isinstance(raw, bool):
                return raw
            if isinstance(raw, str):
                return raw
            try:
                return int(raw)
            except (ValueError, TypeError):
                return raw

        # ---- Percentages ----
        if "_pct" in key or "_rate" in key:
            try:
                return min(100.0, max(0.0, round(float(raw), 1)))
            except (ValueError, TypeError):
                return raw

        # ---- TDS (整数) ----
        if key in ("tds_in", "tds_out"):
            try:
                return round(float(raw))
            except (ValueError, TypeError):
                return raw

        # ---- Flow rate (2位小数) ----
        if key == "flow_rate":
            try:
                return round(float(raw), 2)
            except (ValueError, TypeError):
                return raw

        # ---- Water pressure (3位小数) ----
        if key == "water_pressure":
            try:
                return round(float(raw), 3)
            except (ValueError, TypeError):
                return raw

        # ---- Water volumes (2位小数) ----
        if any(k in key for k in ("water", "total_", "today_", "mineral_", "target_water")):
            try:
                return round(float(raw), 2)
            except (ValueError, TypeError):
                return raw

        # ---- Filter numbers (int) ----
        if key.startswith("filter_") and any(k in key for k in ("days", "hours", "life")):
            try:
                return int(raw)
            except (ValueError, TypeError):
                return raw

        # ---- Filter name / code (string) ----
        if key.startswith("filter_") and any(k in key for k in ("name", "code")):
            return str(raw)

        # ---- Numeric fallback ----
        try:
            return round(float(raw), 2)
        except (ValueError, TypeError):
            return str(raw) if raw is not None else None
