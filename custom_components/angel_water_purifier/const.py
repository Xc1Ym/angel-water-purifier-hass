"""Constants for the Angel Water Purifier integration."""
from __future__ import annotations

import logging
from enum import Enum
from typing import Final

DOMAIN: Final = "angel_water_purifier"
LOGGER = logging.getLogger(__package__)
MANUFACTURER: Final = "Angel (安吉尔)"

# Configuration keys (Angel IoT Cloud API)
CONF_SN: Final = "sn"                    # Device serial number
CONF_ACCESS_TOKEN: Final = "access_token"  # Bearer JWT token
CONF_USER_ID: Final = "user_id"           # Angel IoT user ID
CONF_WX_OPEN_ID: Final = "wx_open_id"     # WeChat OpenID (optional)
CONF_SCAN_INTERVAL: Final = "scan_interval"

DEFAULT_SCAN_INTERVAL: Final = 120  # seconds (cloud API rate limiting)


# Sensor types
class SensorType(str, Enum):
    """Categories of sensors."""

    WATER_QUALITY = "water_quality"
    FILTER = "filter"
    TEMPERATURE = "temperature"
    FLOW = "flow"
    STATUS = "status"
    CONSUMPTION = "consumption"
    PRESSURE = "pressure"


# Sensor metadata definitions
# 基于实际 API 响应分析确定（设备型号: J3402-ROB90 / M5 600）
SENSOR_TYPES: dict[str, dict] = {
    # ======== 水质 ========
    "tds_in": {
        "name": "进水 TDS",
        "native_unit_of_measurement": "ppm",
        "icon": "mdi:water",
        "device_class": None,
        "state_class": "measurement",
        "sensor_type": SensorType.WATER_QUALITY,
        "entity_category": None,
    },
    "tds_out": {
        "name": "出水 TDS",
        "native_unit_of_measurement": "ppm",
        "icon": "mdi:water-check",
        "device_class": None,
        "state_class": "measurement",
        "sensor_type": SensorType.WATER_QUALITY,
        "entity_category": None,
    },
    "tds_rejection_rate": {
        "name": "脱盐率",
        "native_unit_of_measurement": "%",
        "icon": "mdi:percent",
        "device_class": None,
        "state_class": "measurement",
        "sensor_type": SensorType.WATER_QUALITY,
        "entity_category": "diagnostic",
    },
    # ======== 流量 ========
    "flow_rate": {
        "name": "当前流量",
        "native_unit_of_measurement": "L/min",
        "icon": "mdi:water-pump",
        "device_class": None,
        "state_class": "measurement",
        "sensor_type": SensorType.FLOW,
        "entity_category": None,
    },
    # ======== 累计水量 ========
    "total_water_usage": {
        "name": "累计纯水量",
        "native_unit_of_measurement": "L",
        "icon": "mdi:water",
        "device_class": None,
        "state_class": "total_increasing",
        "sensor_type": SensorType.CONSUMPTION,
        "entity_category": "diagnostic",
    },
    "total_water_in": {
        "name": "累计总用水量",
        "native_unit_of_measurement": "L",
        "icon": "mdi:water",
        "device_class": None,
        "state_class": "total_increasing",
        "sensor_type": SensorType.CONSUMPTION,
        "entity_category": "diagnostic",
    },
    # ======== 今日用水 ========
    "today_pure_water": {
        "name": "今日纯水量",
        "native_unit_of_measurement": "L",
        "icon": "mdi:chart-bell-curve",
        "device_class": None,
        "state_class": "total_increasing",
        "sensor_type": SensorType.CONSUMPTION,
        "entity_category": "diagnostic",
    },
    "today_total_water": {
        "name": "今日总用水量",
        "native_unit_of_measurement": "L",
        "icon": "mdi:chart-bell-curve",
        "device_class": None,
        "state_class": "total_increasing",
        "sensor_type": SensorType.CONSUMPTION,
        "entity_category": "diagnostic",
    },
    # ======== 水压 ========
    "water_pressure": {
        "name": "水压",
        "native_unit_of_measurement": "MPa",
        "icon": "mdi:gauge",
        "device_class": "pressure",
        "state_class": "measurement",
        "sensor_type": SensorType.PRESSURE,
        "entity_category": "diagnostic",
    },
    # ======== 滤芯寿命 ========
    "filter_pcr_remaining": {
        "name": "PCR 滤芯寿命",
        "native_unit_of_measurement": "%",
        "icon": "mdi:filter-variant",
        "device_class": None,
        "state_class": "measurement",
        "sensor_type": SensorType.FILTER,
        "entity_category": "diagnostic",
    },
    # ======== 工作状态 ========
    "working_status": {
        "name": "工作状态",
        "native_unit_of_measurement": None,
        "icon": "mdi:state-machine",
        "device_class": None,
        "state_class": None,
        "sensor_type": SensorType.STATUS,
        "entity_category": "diagnostic",
    },
    # ======== 故障 ========
    "error_code": {
        "name": "故障代码",
        "native_unit_of_measurement": None,
        "icon": "mdi:alert-circle",
        "device_class": None,
        "state_class": None,
        "sensor_type": SensorType.STATUS,
        "entity_category": "diagnostic",
    },
    "error_message": {
        "name": "故障信息",
        "native_unit_of_measurement": None,
        "icon": "mdi:alert-circle-outline",
        "device_class": None,
        "state_class": None,
        "sensor_type": SensorType.STATUS,
        "entity_category": "diagnostic",
    },
    # ======== 设备信息 ========
    "device_name": {
        "name": "设备名称",
        "native_unit_of_measurement": None,
        "icon": "mdi:label",
        "device_class": None,
        "state_class": None,
        "sensor_type": SensorType.STATUS,
        "entity_category": "diagnostic",
    },
    "refresh_time": {
        "name": "最后刷新",
        "native_unit_of_measurement": None,
        "icon": "mdi:clock-time-three",
        "device_class": "timestamp",
        "state_class": None,
        "sensor_type": SensorType.STATUS,
        "entity_category": "diagnostic",
    },
}

# Working status mapping (deviceState: "0"=待机, "1"=运行中, 等)
WORKING_STATUS_MAP: dict[str, str] = {
    "0": "standby",
    "1": "working",
    "2": "flushing",
    "3": "heating",
    "4": "filtering",
    "5": "error",
    "6": "idle",
}

# WarnCode 映射 (warnCode 字段, "" = 正常)
WARN_CODE_MAP: dict[str, str] = {
    "": "正常",
    "E1": "漏水保护",
    "E2": "进水异常",
    "E3": "出水异常",
    "E4": "滤芯寿命到期",
    "E5": "水泵故障",
    "E6": "水质传感器故障",
    "E7": "温度传感器故障",
    "E8": "通讯故障",
    "E9": "压力罐故障",
}

# Filter keys for sensor iteration
FILTER_KEYS: list[str] = [
    "filter_pcr_remaining",
]
