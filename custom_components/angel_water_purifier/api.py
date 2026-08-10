"""Angel IoT Cloud API — 安吉尔净水器云平台 HTTP 客户端."""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from aiohttp import ClientConnectorError, ClientError, ClientTimeout, ContentTypeError
from homeassistant.core import HomeAssistant
from homeassistant.helpers import aiohttp_client

from .coordinator import AngelDeviceAPI

_LOGGER = logging.getLogger(__name__)

API_BASE = "https://iot.angelgroup.com.cn"
REQUEST_TIMEOUT = 30
MAX_RETRIES = 2

# OAuth2 客户端凭证（微信小程序内固定值）
OAUTH_CLIENT_ID = "angelWebApi"
OAUTH_CLIENT_SECRET = "caebe54dac9f4e51addd5d0a4a6f289a"
OAUTH_TOKEN_URL = f"{API_BASE}/iotmp-openauth/oauth/token"

# access_token 剩余有效期低于该秒数时提前刷新（access_token 有效期约 24h）
TOKEN_REFRESH_THRESHOLD = 600
# refresh_token 有效期约 30 天，每次刷新后自动旋转续期

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
        refresh_token: str = "",
    ) -> None:
        super().__init__(hass, config)
        self._sn = sn
        self._token = token
        self._user_id = user_id
        self._wx_open_id = wx_open_id
        self._refresh_token = refresh_token
        self._session = None
        self._device_info: dict[str, Any] = {}

        # Token 生命周期状态（epoch 秒）
        self._expires_at: float | None = None
        self._refresh_expires_at: float | None = None

        self._token_lock = asyncio.Lock()
        self._token_store = None

    @property
    def device_info(self) -> dict[str, Any]:
        return self._device_info

    @property
    def token_expires_at(self) -> float | None:
        """access_token 过期时间（epoch），供诊断面板使用."""
        return self._expires_at

    @property
    def has_refresh_token(self) -> bool:
        """是否配置了 refresh_token（可自动续期）."""
        return bool(self._refresh_token)

    # ------------------------------------------------------------------ #
    #  Lifecycle
    # ------------------------------------------------------------------ #

    async def async_connect(self) -> bool:
        self._session = aiohttp_client.async_get_clientsession(self.hass)
        await self._load_tokens()

        if not self._sn:
            _LOGGER.error("❌ 未配置 SN")
            return False
        if not self._token and not self._refresh_token:
            _LOGGER.error("❌ 未配置 Token 或 Refresh Token")
            return False

        # 配置了 refresh_token：启动时强制刷新一次，验证有效性并拿到最新 token
        if self._refresh_token:
            if await self._refresh_token_if_needed(force=True):
                _LOGGER.info("✅ Token 刷新成功 | SN=%s", self._sn)
            else:
                _LOGGER.error(
                    "❌ Refresh Token 无效或刷新失败，请重新从小程序抓包获取后更新配置 | SN=%s",
                    self._sn,
                )
                return False

        if not self._token:
            _LOGGER.error("❌ 无有效 Token")
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
    #  Token 管理（OAuth2 refresh_token 自动续期）
    # ------------------------------------------------------------------ #

    async def _load_tokens(self) -> None:
        """从 HA Store 加载持久化的 token 状态（按 SN 隔离）."""
        from homeassistant.helpers.storage import Store

        self._token_store = Store[dict[str, Any]](
            self.hass, version=1, key=f"angel_water_purifier_tokens_{self._sn}"
        )
        data = await self._token_store.async_load()
        if not isinstance(data, dict):
            return

        # 配置项里的 refresh_token 优先，Store 里缓存的兜底
        self._refresh_token = self._refresh_token or data.get("refresh_token", "")
        self._token = self._token or data.get("access_token", "")
        self._expires_at = data.get("expires_at")
        self._refresh_expires_at = data.get("refresh_expires_at")

    async def _save_tokens(self) -> None:
        """持久化最新 token，供重启后继续自动续期."""
        if self._token_store is None:
            return
        await self._token_store.async_save({
            "access_token": self._token,
            "refresh_token": self._refresh_token,
            "expires_at": self._expires_at,
            "refresh_expires_at": self._refresh_expires_at,
        })

    def _token_expiring(self) -> bool:
        """access_token 是否已过期或接近过期."""
        if self._expires_at is None:
            # 无过期信息（旧配置），假设有效，请求失败时由 401 兜底
            return False
        return time.time() > self._expires_at - TOKEN_REFRESH_THRESHOLD

    async def _refresh_token_if_needed(self, force: bool = False) -> bool:
        """确保 access_token 有效，需要时用 refresh_token 自动刷新.

        force=True 时跳过有效期检查直接刷新（连接时 / 401 时使用）。
        """
        async with self._token_lock:
            # token 仍有效且非强制 → 无需刷新
            if not force and self._token and not self._token_expiring():
                return True
            if not self._refresh_token:
                # 未配置 refresh_token：只能依赖现有 token
                return bool(self._token)
            return await self._do_refresh()

    async def _do_refresh(self) -> bool:
        """用 refresh_token 换取新 token（OAuth2 标准流程，返回全新 token 对）."""
        if self._session is None:
            self._session = aiohttp_client.async_get_clientsession(self.hass)

        params = {
            "client_id": OAUTH_CLIENT_ID,
            "client_secret": OAUTH_CLIENT_SECRET,
            "grant_type": "refresh_token",
            "refresh_token": self._refresh_token,
        }
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": WECHAT_UA,
            "Accept": "*/*",
        }

        try:
            async with self._session.post(
                OAUTH_TOKEN_URL, data=params, headers=headers,
                timeout=ClientTimeout(total=REQUEST_TIMEOUT),
            ) as resp:
                if resp.status != 200:
                    _LOGGER.error("❌ Token 刷新失败: HTTP %d", resp.status)
                    return False
                data = await resp.json()
        except (ClientError, asyncio.TimeoutError, ContentTypeError) as exc:
            _LOGGER.error("❌ Token 刷新请求失败: %s", exc)
            return False

        new_token = data.get("access_token")
        if not new_token:
            _LOGGER.error("❌ Token 刷新响应无效: %s", data.get("error") or data.get("retMsg") or data)
            return False

        old_refresh = self._refresh_token
        self._token = new_token
        if data.get("refresh_token"):
            self._refresh_token = data["refresh_token"]
        self._expires_at = time.time() + int(data.get("expires_in", 86399))
        self._refresh_expires_at = time.time() + int(data.get("refresh_expires_in", 2591999))

        await self._save_tokens()
        hours = (self._expires_at - time.time()) / 3600
        if old_refresh != self._refresh_token:
            _LOGGER.info("🔄 Token 已自动刷新（refresh_token 已旋转）| 有效期 %.1f 小时", hours)
        else:
            _LOGGER.info("🔄 Token 已自动刷新 | 有效期 %.1f 小时", hours)
        return True

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

        # 确保 access_token 有效（过期自动刷新）
        if not await self._refresh_token_if_needed():
            _LOGGER.error("❌ 无有效访问令牌 (%s %s)", method, path)
            return None

        for attempt in range(2):
            headers = self._build_headers()
            try:
                async with self._session.request(
                    method=method, url=url, headers=headers,
                    json=json_data, params=params,
                    timeout=ClientTimeout(total=REQUEST_TIMEOUT),
                    ssl=True,
                ) as resp:
                    if resp.status == 401:
                        # access_token 失效 → 强制刷新后重试一次
                        _LOGGER.warning("⚠️ 401 未授权，刷新 token 后重试")
                        if not await self._refresh_token_if_needed(force=True):
                            return None
                        continue
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
