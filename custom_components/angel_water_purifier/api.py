"""Angel IoT Cloud API — 安吉尔净水器云平台 HTTP 客户端."""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from aiohttp import ClientConnectorError, ClientError, ClientTimeout, ContentTypeError
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client

from .coordinator import AngelDeviceAPI

_LOGGER = logging.getLogger(__name__)

API_BASE = "https://iot.angelgroup.com.cn"
REQUEST_TIMEOUT = 30
MAX_RETRIES = 2

WECHAT_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/132.0.0.0 Safari/537.36 "
    "MicroMessenger/7.0.20.1781(0x6700143B) "
    "NetType/WIFI MiniProgramEnv/Mac "
    "MacWechat/WMPF MacWechat/3.8.7(0x13080712) "
    "UnifiedPCMacWechat(0xf2641b15) XWEB/20008"
)

# Map of API response keys → internal sensor keys
RESPONSE_FIELD_MAP: dict[str, str] = {
    "tdsIn": "tds_in",
    "tdsOut": "tds_out",
    "instantFlowRate": "flow_rate",
    "totalUsedPureWater": "total_water_usage",
    "totalUsedWater": "total_water_in",
    "pureWater": "today_pure_water",
    "totalWater": "today_total_water",
    "totalTargetWater": "total_target_water",
    "mineralWaterTotal": "mineral_water_total",
    "waterPressure": "water_pressure",
    "deviceState": "working_status",
    "washState": "wash_state",
    "isOpen": "is_open",
    "onlineState": "online_state",
    "hotWaterOutletState": "hot_water_outlet",
    "regenerationStep": "regeneration_step",
    "bindType": "bind_type",
    "warnCode": "error_code",
    "warnMsg": "error_message",
    "refreshTime": "refresh_time",
    "activeTime": "active_time",
    "deviceName": "device_name",
    "sn": "serial_number",
    "reminderPush": "reminder_push",
    "waterIntakePush": "water_intake_push",
    "machineFailurePush": "machine_failure_push",
    "salinityPush": "salinity_push",
    "receiveWaterUsageMonth": "receive_water_usage_month",
    "receiveFilterReplace": "receive_filter_replace",
    "targetSwitch": "target_switch",
}


class AngelCloudAPI(AngelDeviceAPI):
    """安吉尔 IoT 云平台 API 客户端."""

    def __init__(
        self,
        hass: HomeAssistant,
        config: dict[str, Any],
        sn: str,
        token: str = "",
        user_id: str = "",
        wx_open_id: str = "",
    ) -> None:
        super().__init__(hass, config)
        self._sn = sn
        self._token = token
        self._user_id = user_id
        self._wx_open_id = wx_open_id
        self._session = None
        self._device_info: dict[str, Any] = {}

    @property
    def device_info(self) -> dict[str, Any]:
        return self._device_info

    # ------------------------------------------------------------------ #
    #  Lifecycle
    # ------------------------------------------------------------------ #

    async def async_connect(self) -> bool:
        self._session = aiohttp_client.async_get_clientsession(self.hass)

        if not self._sn:
            _LOGGER.error("❌ 未配置 SN")
            return False
        if not self._token:
            _LOGGER.error("❌ 未配置 Token")
            return False

        try:
            raw = await self._request_device_detail(data_type=0)
        except (ClientError, asyncio.TimeoutError) as exc:
            _LOGGER.error("❌ 连接失败: %s", exc)
            return False

        if raw is None:
            _LOGGER.warning("⚠️ SN=%s 无响应 (Token 可能过期)", self._sn)
            return False

        payload = self._unwrap_response(raw)
        if isinstance(payload, dict):
            self._extract_device_info(payload)

        self._connected = True
        _LOGGER.info(
            "✅ 连接成功 | SN=%s | 型号=%s",
            self._sn, self._device_info.get("model", "?"),
        )
        return True

    async def async_disconnect(self) -> None:
        self._session = None
        self._connected = False

    # ------------------------------------------------------------------ #
    #  Data fetching
    # ------------------------------------------------------------------ #

    async def async_fetch_data(self) -> dict[str, Any]:
        if not self._connected:
            return {}

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                raw = await self._request_device_detail(data_type=1)
            except (ClientError, asyncio.TimeoutError) as exc:
                _LOGGER.warning("⚠️ 第 %d/%d 次失败: %s", attempt, MAX_RETRIES, exc)
                if attempt < MAX_RETRIES:
                    await asyncio.sleep(2**attempt)
                continue

            if raw is None:
                if attempt < MAX_RETRIES:
                    await asyncio.sleep(2**attempt)
                continue

            result = self._parse_all(raw)
            _LOGGER.debug("📊 解析到 %d 个传感器", len(result))
            return result

        return {}

    async def async_set(self, key: str, value: Any) -> bool:
        _LOGGER.warning("⏳ 设备控制未实现: %s=%s", key, value)
        return False

    # ------------------------------------------------------------------ #
    #  HTTP
    # ------------------------------------------------------------------ #

    def _build_headers(self) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self._token}",
            "User-Id": self._user_id,
            "Content-Type": "application/json;charset=UTF-8",
            "Accept": "*/*",
            "User-Agent": WECHAT_UA,
            "Xweb_xhr": "1",
            "Sec-Fetch-Site": "cross-site",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Dest": "empty",
            "Accept-Language": "zh-CN,zh;q=0.9",
        }
        if self._wx_open_id:
            headers["Referer"] = (
                "https://servicewechat.com/wx2145ac10e603bc5c/153/page-frame.html"
            )
        return headers

    async def _request(
        self, method: str, path: str,
        json_data: dict | None = None,
        params: dict[str, str] | None = None,
    ) -> dict | None:
        if self._session is None:
            self._session = aiohttp_client.async_get_clientsession(self.hass)

        url = f"{API_BASE}{path}"
        headers = self._build_headers()

        try:
            async with self._session.request(
                method=method, url=url, headers=headers,
                json=json_data, params=params,
                timeout=ClientTimeout(total=REQUEST_TIMEOUT),
                ssl=True,
            ) as resp:
                if resp.status != 200:
                    body = (await resp.read())[:200] if resp.status >= 400 else b""
                    _LOGGER.warning("⚠️ HTTP %d %s %s", resp.status, method, path)
                    return None
                try:
                    return await resp.json()
                except ContentTypeError:
                    return None
        except (ClientConnectorError, asyncio.TimeoutError) as exc:
            _LOGGER.warning("⚠️ 请求失败 %s %s: %s", method, path, exc)
            return None

    async def _request_device_detail(self, data_type: int = 0) -> dict | None:
        params = {"sn": self._sn, "dataType": str(data_type)}
        if data_type == 0:
            params["noLoading"] = "false"
            params["noToast"] = "false"
        else:
            params["noLoading"] = "true"
            params["noToast"] = "true"
        if self._wx_open_id:
            params["wxOpenId"] = self._wx_open_id
        return await self._request(
            method="GET",
            path="/iotmp-openapi/v1/device-info/device-detail",
            params=params,
        )

    # ------------------------------------------------------------------ #
    #  Response parsing
    # ------------------------------------------------------------------ #

    @staticmethod
    def _unwrap_response(raw: dict) -> dict | None:
        if not isinstance(raw, dict):
            return None
        code = raw.get("retCode")
        if code is not None and str(code) in ("0", "200"):
            payload = raw.get("data")
            if isinstance(payload, dict):
                return payload
            return None
        for key in ("data", "result"):
            if key in raw and isinstance(raw[key], dict):
                return raw[key]
        return raw

    def _parse_all(self, raw: dict) -> dict[str, Any]:
        """Parse the full API response into a flat sensor dict."""
        result: dict[str, Any] = {}

        payload = self._unwrap_response(raw)
        if not isinstance(payload, dict):
            return result

        # Log raw field names for debugging
        _LOGGER.debug("📦 API 原始字段: %s", list(payload.keys()))

        # 1. Direct field mapping
        for api_key, sensor_key in RESPONSE_FIELD_MAP.items():
            val = payload.get(api_key)
            if val is not None and val != "":
                result[sensor_key] = val

        # 2. Product info (nested)
        product = payload.get("product")
        if isinstance(product, dict):
            for api_key, sensor_key in {
                "productModel": "product_model",
                "productName": "product_name",
                "productCode": "product_code",
            }.items():
                val = product.get(api_key)
                if val:
                    result[sensor_key] = val
                    self._device_info.setdefault("model", str(product.get("productModel", "?")))
                    self._device_info.setdefault("product_code", str(product.get("productCode", "")))

        # 3. Filter elements → multiple sensors per filter
        filters = payload.get("filterElements", [])
        if isinstance(filters, list):
            for idx, f in enumerate(filters):
                if not isinstance(f, dict):
                    continue
                prefix = f"filter_{idx + 1}"

                # Basic info
                result[f"{prefix}_name"] = f.get("name", f"Filter {idx + 1}")
                if f.get("filterCode"):
                    result[f"{prefix}_code"] = f["filterCode"]

                # Days-based life
                life = f.get("life") or f.get("lifeDay")
                life_all = f.get("lifeAll") or f.get("maxLifeDay")
                if life is not None and life_all is not None:
                    life, life_all = int(life), int(life_all)
                    if life_all > 0:
                        result[f"{prefix}_used_days"] = life
                        result[f"{prefix}_total_days"] = life_all
                        result[f"{prefix}_remaining_days"] = max(0, life_all - life)
                        result[f"{prefix}_remaining_pct"] = round(
                            (life_all - life) / life_all * 100, 1
                        )

                # Hours-based life
                hour = f.get("hour")
                max_hour = f.get("maxHour")
                if hour is not None and max_hour is not None:
                    hour, max_hour = int(hour), int(max_hour)
                    if max_hour > 0:
                        result[f"{prefix}_used_hours"] = hour
                        result[f"{prefix}_max_hours"] = max_hour
                        result[f"{prefix}_remaining_hours"] = max(0, max_hour - hour)
                        result[f"{prefix}_remaining_hours_pct"] = round(
                            (max_hour - hour) / max_hour * 100, 1
                        )

                # Life style
                if f.get("lifeStyle") is not None:
                    result[f"{prefix}_life_style"] = f["lifeStyle"]

        # 4. TDS rejection rate (derived)
        tds_in = result.get("tds_in")
        tds_out = result.get("tds_out")
        if tds_in is not None and tds_out is not None:
            tds_in_f, tds_out_f = float(tds_in), float(tds_out)
            if tds_in_f > 0:
                result["tds_rejection_rate"] = round(
                    (1 - tds_out_f / tds_in_f) * 100, 1
                )

        # 5. Device info (for registry)
        self._extract_device_info(payload)

        _LOGGER.debug("✅ 解析完成: %d 个传感器", len(result))
        return result

    def _extract_device_info(self, payload: dict) -> None:
        product = payload.get("product")
        if isinstance(product, dict):
            model = product.get("productModel") or product.get("productName")
            if model:
                self._device_info["model"] = str(model)
        if "deviceName" in payload:
            self._device_info.setdefault("name", str(payload["deviceName"]))
        if "sn" in payload:
            self._device_info["sn"] = str(payload["sn"])
