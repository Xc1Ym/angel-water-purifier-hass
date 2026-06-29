"""Constants for the Angel Water Purifier integration."""
from __future__ import annotations

import logging
from enum import Enum
from typing import Final

DOMAIN: Final = "angel_water_purifier"
LOGGER = logging.getLogger(__package__)
MANUFACTURER: Final = "Angel (安吉尔)"

# Configuration keys
CONF_SN: Final = "sn"
CONF_ACCESS_TOKEN: Final = "access_token"
CONF_USER_ID: Final = "user_id"
CONF_WX_OPEN_ID: Final = "wx_open_id"
CONF_SCAN_INTERVAL: Final = "scan_interval"

DEFAULT_SCAN_INTERVAL: Final = 120

# Max number of filter elements to handle
MAX_FILTERS: Final = 4

# Filter key prefixes
FILTER_PREFIXES: list[str] = [f"filter_{i + 1}" for i in range(MAX_FILTERS)]


# --------------------------------------------------------------------------- #
#  SENSOR TYPE CATEGORIES
# --------------------------------------------------------------------------- #

class SensorGroup(str, Enum):
    """Sensor display groups."""

    WATER_QUALITY = "water_quality"
    FILTER = "filter"
    FLOW = "flow"
    USAGE = "usage"
    PRESSURE = "pressure"
    STATUS = "status"
    TIME = "time"
    CONFIG = "config"
    PRODUCT = "product"
    ALARM = "alarm"


# --------------------------------------------------------------------------- #
#  SENSOR DEFINITIONS
#  (static sensors that appear in every device)
# --------------------------------------------------------------------------- #

BULK_SENSORS: dict[str, dict] = {
    # ========== 水质 ==========
    "tds_in": {
        "name": "进水 TDS",
        "unit": "ppm", "icon": "mdi:water",
        "device_class": None, "state_class": "measurement",
        "group": SensorGroup.WATER_QUALITY, "cat": None,
    },
    "tds_out": {
        "name": "出水 TDS",
        "unit": "ppm", "icon": "mdi:water-check",
        "device_class": None, "state_class": "measurement",
        "group": SensorGroup.WATER_QUALITY, "cat": None,
    },
    "tds_rejection_rate": {
        "name": "脱盐率",
        "unit": "%", "icon": "mdi:percent",
        "device_class": None, "state_class": "measurement",
        "group": SensorGroup.WATER_QUALITY, "cat": "diagnostic",
    },
    # ========== 流量 & 水压 ==========
    "flow_rate": {
        "name": "当前流量",
        "unit": "L/min", "icon": "mdi:water-pump",
        "device_class": None, "state_class": "measurement",
        "group": SensorGroup.FLOW, "cat": None,
    },
    "water_pressure": {
        "name": "水压",
        "unit": "MPa", "icon": "mdi:gauge",
        "device_class": "pressure", "state_class": "measurement",
        "group": SensorGroup.PRESSURE, "cat": "diagnostic",
    },
    # ========== 累计水量 ==========
    "total_water_usage": {
        "name": "累计纯水量",
        "unit": "L", "icon": "mdi:water",
        "device_class": None, "state_class": "total_increasing",
        "group": SensorGroup.USAGE, "cat": "diagnostic",
    },
    "total_water_in": {
        "name": "累计总用水量",
        "unit": "L", "icon": "mdi:water",
        "device_class": None, "state_class": "total_increasing",
        "group": SensorGroup.USAGE, "cat": "diagnostic",
    },
    # ========== 今日用水 ==========
    "today_pure_water": {
        "name": "今日纯水量",
        "unit": "L", "icon": "mdi:chart-bell-curve",
        "device_class": None, "state_class": "total_increasing",
        "group": SensorGroup.USAGE, "cat": "diagnostic",
    },
    "today_total_water": {
        "name": "今日总用水量",
        "unit": "L", "icon": "mdi:chart-bell-curve",
        "device_class": None, "state_class": "total_increasing",
        "group": SensorGroup.USAGE, "cat": "diagnostic",
    },
    "total_target_water": {
        "name": "目标水量",
        "unit": "L", "icon": "mdi:target",
        "device_class": None, "state_class": "measurement",
        "group": SensorGroup.USAGE, "cat": "diagnostic",
    },
    "mineral_water_total": {
        "name": "矿物质水总量",
        "unit": "L", "icon": "mdi:water-plus",
        "device_class": None, "state_class": "total_increasing",
        "group": SensorGroup.USAGE, "cat": "diagnostic",
    },
    # ========== 工作状态 ==========
    "working_status": {
        "name": "工作状态",
        "unit": None, "icon": "mdi:state-machine",
        "device_class": None, "state_class": None,
        "group": SensorGroup.STATUS, "cat": "diagnostic",
    },
    "wash_state": {
        "name": "冲洗状态",
        "unit": None, "icon": "mdi:water-sync",
        "device_class": None, "state_class": None,
        "group": SensorGroup.STATUS, "cat": "diagnostic",
    },
    "is_open": {
        "name": "开关",
        "unit": None, "icon": "mdi:power",
        "device_class": None, "state_class": None,
        "group": SensorGroup.STATUS, "cat": "diagnostic",
    },
    "online_state": {
        "name": "在线状态",
        "unit": None, "icon": "mdi:wifi",
        "device_class": None, "state_class": None,
        "group": SensorGroup.STATUS, "cat": "diagnostic",
    },
    "hot_water_outlet": {
        "name": "热水出水",
        "unit": None, "icon": "mdi:water-thermometer",
        "device_class": None, "state_class": None,
        "group": SensorGroup.STATUS, "cat": "diagnostic",
    },
    "regeneration_step": {
        "name": "再生步骤",
        "unit": None, "icon": "mdi:refresh",
        "device_class": None, "state_class": None,
        "group": SensorGroup.STATUS, "cat": "diagnostic",
    },
    "bind_type": {
        "name": "绑定类型",
        "unit": None, "icon": "mdi:link-variant",
        "device_class": None, "state_class": None,
        "group": SensorGroup.STATUS, "cat": "diagnostic",
    },
    # ========== 故障 ==========
    "error_code": {
        "name": "故障代码",
        "unit": None, "icon": "mdi:alert-circle",
        "device_class": None, "state_class": None,
        "group": SensorGroup.ALARM, "cat": "diagnostic",
    },
    "error_message": {
        "name": "故障信息",
        "unit": None, "icon": "mdi:alert-circle-outline",
        "device_class": None, "state_class": None,
        "group": SensorGroup.ALARM, "cat": "diagnostic",
    },
    # ========== 时间 ==========
    "refresh_time": {
        "name": "数据刷新时间",
        "unit": None, "icon": "mdi:clock-time-three",
        "device_class": "timestamp", "state_class": None,
        "group": SensorGroup.TIME, "cat": "diagnostic",
    },
    "active_time": {
        "name": "最后活跃时间",
        "unit": None, "icon": "mdi:clock-outline",
        "device_class": "timestamp", "state_class": None,
        "group": SensorGroup.TIME, "cat": "diagnostic",
    },
    # ========== 推送设置 ==========
    "reminder_push": {
        "name": "提醒推送",
        "unit": None, "icon": "mdi:bell-ring",
        "device_class": None, "state_class": None,
        "group": SensorGroup.CONFIG, "cat": "diagnostic",
    },
    "water_intake_push": {
        "name": "饮水提醒推送",
        "unit": None, "icon": "mdi:bell-ring-outline",
        "device_class": None, "state_class": None,
        "group": SensorGroup.CONFIG, "cat": "diagnostic",
    },
    "machine_failure_push": {
        "name": "故障推送",
        "unit": None, "icon": "mdi:bell-alert",
        "device_class": None, "state_class": None,
        "group": SensorGroup.CONFIG, "cat": "diagnostic",
    },
    "salinity_push": {
        "name": "盐度推送",
        "unit": None, "icon": "mdi:bell-check",
        "device_class": None, "state_class": None,
        "group": SensorGroup.CONFIG, "cat": "diagnostic",
    },
    "receive_water_usage_month": {
        "name": "月度用水报告",
        "unit": None, "icon": "mdi:calendar-month",
        "device_class": None, "state_class": None,
        "group": SensorGroup.CONFIG, "cat": "diagnostic",
    },
    "receive_filter_replace": {
        "name": "滤芯更换通知",
        "unit": None, "icon": "mdi:email-newsletter",
        "device_class": None, "state_class": None,
        "group": SensorGroup.CONFIG, "cat": "diagnostic",
    },
    "target_switch": {
        "name": "目标水量开关",
        "unit": None, "icon": "mdi:toggle-switch",
        "device_class": None, "state_class": None,
        "group": SensorGroup.CONFIG, "cat": "diagnostic",
    },
    # ========== 设备信息 ==========
    "device_name": {
        "name": "设备名称",
        "unit": None, "icon": "mdi:label",
        "device_class": None, "state_class": None,
        "group": SensorGroup.PRODUCT, "cat": "diagnostic",
    },
    "serial_number": {
        "name": "序列号",
        "unit": None, "icon": "mdi:numeric",
        "device_class": None, "state_class": None,
        "group": SensorGroup.PRODUCT, "cat": "diagnostic",
    },
    "product_model": {
        "name": "产品型号",
        "unit": None, "icon": "mdi:chip",
        "device_class": None, "state_class": None,
        "group": SensorGroup.PRODUCT, "cat": "diagnostic",
    },
    "product_name": {
        "name": "产品名称",
        "unit": None, "icon": "mdi:tag",
        "device_class": None, "state_class": None,
        "group": SensorGroup.PRODUCT, "cat": "diagnostic",
    },
    "product_code": {
        "name": "产品代码",
        "unit": None, "icon": "mdi:qrcode",
        "device_class": None, "state_class": None,
        "group": SensorGroup.PRODUCT, "cat": "diagnostic",
    },
}

# --------------------------------------------------------------------------- #
#  FILTER SENSOR DEFINITIONS (generated for each filter element)
# --------------------------------------------------------------------------- #

FILTER_SENSOR_DEFS: dict[str, dict] = {
    "name": {
        "name_suffix": "名称",
        "unit": None, "icon": "mdi:filter-variant",
        "group": SensorGroup.FILTER, "cat": "diagnostic",
    },
    "code": {
        "name_suffix": "代码",
        "unit": None, "icon": "mdi:qrcode",
        "group": SensorGroup.FILTER, "cat": "diagnostic",
    },
    "remaining_pct": {
        "name_suffix": "剩余寿命",
        "unit": "%", "icon": "mdi:percent",
        "group": SensorGroup.FILTER, "cat": "diagnostic",
    },
    "used_days": {
        "name_suffix": "已用天数",
        "unit": "天", "icon": "mdi:calendar-arrow-right",
        "group": SensorGroup.FILTER, "cat": "diagnostic",
    },
    "remaining_days": {
        "name_suffix": "剩余天数",
        "unit": "天", "icon": "mdi:calendar-check",
        "group": SensorGroup.FILTER, "cat": "diagnostic",
    },
    "total_days": {
        "name_suffix": "总天数",
        "unit": "天", "icon": "mdi:calendar-range",
        "group": SensorGroup.FILTER, "cat": "diagnostic",
    },
    "used_hours": {
        "name_suffix": "已用小时",
        "unit": "h", "icon": "mdi:clock-arrow-right",
        "group": SensorGroup.FILTER, "cat": "diagnostic",
    },
    "remaining_hours": {
        "name_suffix": "剩余小时",
        "unit": "h", "icon": "mdi:clock-check",
        "group": SensorGroup.FILTER, "cat": "diagnostic",
    },
    "max_hours": {
        "name_suffix": "最大小时",
        "unit": "h", "icon": "mdi:clock-range",
        "group": SensorGroup.FILTER, "cat": "diagnostic",
    },
    "remaining_hours_pct": {
        "name_suffix": "小时剩余率",
        "unit": "%", "icon": "mdi:clock-percent",
        "group": SensorGroup.FILTER, "cat": "diagnostic",
    },
    "life_style": {
        "name_suffix": "寿命模式",
        "unit": None, "icon": "mdi:tune",
        "group": SensorGroup.FILTER, "cat": "diagnostic",
    },
}

# --------------------------------------------------------------------------- #
#  WORKING STATUS / WARN CODE MAPPINGS
# --------------------------------------------------------------------------- #

WORKING_STATUS_MAP: dict[str, str] = {
    "0": "standby", "1": "working", "2": "flushing",
    "3": "heating", "4": "filtering", "5": "error", "6": "idle",
}

WARN_CODE_MAP: dict[str, str] = {
    "": "正常",
    "E1": "漏水保护", "E2": "进水异常", "E3": "出水异常",
    "E4": "滤芯寿命到期", "E5": "水泵故障", "E6": "水质传感器故障",
    "E7": "温度传感器故障", "E8": "通讯故障", "E9": "压力罐故障",
}
