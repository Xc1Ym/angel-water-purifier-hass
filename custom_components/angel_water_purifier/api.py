"""Angel IoT Cloud API — 安吉尔净水器云平台 HTTP 客户端.

基于安吉尔微信小程序 (wx2145ac10e603bc5c) 抓包逆向:
  API Base:  https://iot.angelgroup.com.cn
  鉴权方式:  Bearer JWT token (从微信小程序登录获取)
  设备标识:  SN (序列号)

抓包捕获的端点:
  GET  /iotmp-openapi/v1/device-info/device-detail    ← 主数据源
  POST /iotmp-openapi/api/device/getHistory.do         ← 历史数据
  POST /iotmp-openapi/api/device/getDeviceConfigBySn.do ← 设备配置
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from aiohttp import ClientConnectorError, ClientError, ClientTimeout, ContentTypeError
from homeassistant.core import HomeAssistant

from .coordinator import AngelDeviceAPI

_LOGGER = logging.getLogger(__name__)

API_BASE = "https://iot.angelgroup.com.cn"
REQUEST_TIMEOUT = 30  # seconds
MAX_RETRIES = 2

# 微信小程序 User-Agent (从抓包原样复制)
WECHAT_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/132.0.0.0 Safari/537.36 "
    "MicroMessenger/7.0.20.1781(0x6700143B) "
    "NetType/WIFI MiniProgramEnv/Mac "
    "MacWechat/WMPF MacWechat/3.8.7(0x13080712) "
    "UnifiedPCMacWechat(0xf2641b15) XWEB/20008"
)


class AngelCloudAPI(AngelDeviceAPI):
    """安吉尔 IoT 云平台 API 客户端.

    通过 HTTPS 调用 iot.angelgroup.com.cn 获取净水器实时数据。
    """

    def __init__(
        self,
        hass: HomeAssistant,
        config: dict[str, Any],
        sn: str,
        token: str = "",
        user_id: str = "",
        wx_open_id: str = "",
    ) -> None:
        """初始化 API 客户端."""
        super().__init__(hass, config)
        self._sn = sn
        self._token = token
        self._user_id = user_id
        self._wx_open_id = wx_open_id
        self._session = None
        self._device_info: dict[str, Any] = {}
        self._field_map: dict[str, str] = {}  # API field -> internal key

    # ------------------------------------------------------------------ #
    #  属性
    # ------------------------------------------------------------------ #

    @property
    def device_info(self) -> dict[str, Any]:
        """返回设备信息 (model, sw_version 等)."""
        return self._device_info

    @property
    def sn(self) -> str:
        """设备序列号."""
        return self._sn

    # ------------------------------------------------------------------ #
    #  生命周期
    # ------------------------------------------------------------------ #

    async def async_connect(self) -> bool:
        """连接测试：调用 device-detail?dataType=0 验证凭证有效性."""
        self._session = self.hass.helpers.aiohttp_client.async_get_clientsession()

        if not self._sn:
            _LOGGER.error("❌ 未配置设备 SN")
            return False

        if not self._token:
            _LOGGER.error("❌ 未配置 Access Token")
            return False

        try:
            raw = await self._request_device_detail(data_type=0)
        except (ClientError, asyncio.TimeoutError) as exc:
            _LOGGER.error("❌ 连接安吉尔云平台失败: %s", exc)
            return False

        if raw is None:
            _LOGGER.warning(
                "⚠️ 设备 SN=%s 无响应或未找到 (Token 可能已过期)", self._sn
            )
            return False

        # 尝试提取设备信息
        info = self._unwrap_response(raw)
        if isinstance(info, dict):
            _LOGGER.debug("📦 dataType=0 原始响应字段: %s", list(info.keys()))
            self._extract_device_info(info)

        self._connected = True
        _LOGGER.info(
            "✅ 安吉尔云平台连接成功 | SN=%s | 型号=%s | 版本=%s",
            self._sn,
            self._device_info.get("model", "?"),
            self._device_info.get("sw_version", "?"),
        )
        return True

    async def async_disconnect(self) -> None:
        """断开连接（清理 session）."""
        self._session = None
        self._connected = False

    # ------------------------------------------------------------------ #
    #  数据获取
    # ------------------------------------------------------------------ #

    async def async_fetch_data(self) -> dict[str, Any]:
        """获取净水器实时数据.

        调用 GET device-detail?dataType=1，解析返回的 JSON 为传感器数值。
        """
        if not self._connected:
            _LOGGER.warning("⚠️ 未连接到安吉尔云平台")
            return {}

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                raw = await self._request_device_detail(data_type=1)
            except (ClientError, asyncio.TimeoutError) as exc:
                _LOGGER.warning(
                    "⚠️ 第 %d/%d 次请求失败: %s", attempt, MAX_RETRIES, exc
                )
                if attempt < MAX_RETRIES:
                    await asyncio.sleep(2**attempt)
                continue

            if raw is None:
                _LOGGER.warning("⚠️ 第 %d/%d 次请求返回空", attempt, MAX_RETRIES)
                if attempt < MAX_RETRIES:
                    await asyncio.sleep(2**attempt)
                continue

            # 解析数据
            result = self._parse_device_detail(raw)

            if result:
                _LOGGER.debug(
                    "📊 净水器数据: TDS_in=%s TDS_out=%s 水温=%s°C 状态=%s",
                    result.get("tds_in"),
                    result.get("tds_out"),
                    result.get("water_temperature"),
                    result.get("working_status"),
                )
            else:
                _LOGGER.warning("⚠️ 数据解析为空，可能需要更新字段映射")

            return result

        _LOGGER.error("❌ %d 次重试后仍然失败", MAX_RETRIES)
        return {}

    async def async_set(self, key: str, value: Any) -> bool:
        """发送命令到设备 (尚未实现).

        TODO: 需要逆向安吉尔小程序的控制接口.
        """
        _LOGGER.warning("⏳ 设备控制尚未实现: %s=%s", key, value)
        return False

    # ------------------------------------------------------------------ #
    #  HTTP 请求
    # ------------------------------------------------------------------ #

    def _build_headers(self) -> dict[str, str]:
        """构造与抓包一致的 HTTP 请求头."""
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
        # 加上 Referer (微信小程序页面)
        if self._wx_open_id:
            headers["Referer"] = (
                "https://servicewechat.com/wx2145ac10e603bc5c/153/page-frame.html"
            )
        return headers

    async def _request(
        self,
        method: str,
        path: str,
        json_data: dict[str, Any] | None = None,
        params: dict[str, str] | None = None,
    ) -> dict[str, Any] | None:
        """执行 HTTP 请求."""
        if self._session is None:
            self._session = self.hass.helpers.aiohttp_client.async_get_clientsession()

        url = f"{API_BASE}{path}"
        headers = self._build_headers()

        try:
            async with self._session.request(
                method=method,
                url=url,
                headers=headers,
                json=json_data,
                params=params,
                timeout=ClientTimeout(total=REQUEST_TIMEOUT),
                ssl=True,
            ) as resp:
                if resp.status != 200:
                    body_preview = ""
                    try:
                        body_preview = (await resp.read())[:200]
                    except Exception:
                        pass
                    _LOGGER.warning(
                        "⚠️ HTTP %d %s %s | body=%s",
                        resp.status, method, path, body_preview,
                    )
                    return None

                try:
                    return await resp.json()
                except ContentTypeError:
                    text = await resp.text()
                    _LOGGER.warning(
                        "⚠️ 非 JSON 响应: %s %s → %s",
                        method, path, text[:200],
                    )
                    return None

        except ClientConnectorError as exc:
            _LOGGER.warning("⚠️ 连接失败 %s: %s", url, exc)
            return None
        except asyncio.TimeoutError:
            _LOGGER.warning("⚠️ 请求超时 %s %s", method, path)
            return None

    async def _request_device_detail(self, data_type: int = 0) -> dict[str, Any] | None:
        """调用 device-detail 接口.

        Args:
            data_type: 0=基础信息, 1=实时数据
        """
        params = {
            "sn": self._sn,
            "dataType": str(data_type),
        }
        # 微信小程序中的 noLoading/noToast 参数
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
    #  响应解析
    # ------------------------------------------------------------------ #

    @staticmethod
    def _unwrap_response(raw: dict[str, Any]) -> dict[str, Any] | None:
        """解包安吉尔 API 响应外壳.

        实际响应格式:
          { "retCode": 0, "retMsg": "操作成功", "data": {...} }
        """
        if not isinstance(raw, dict):
            return None

        # 安吉尔标准格式: retCode=0, data=...
        code = raw.get("retCode")
        if code is not None:
            code_str = str(code)
            if code_str in ("0", "200"):
                payload = raw.get("data")
                if isinstance(payload, dict):
                    return payload
                return None

        # 兜底: 标准外壳
        for key in ("data", "result", "info", "content"):
            if key in raw and isinstance(raw[key], dict):
                return raw[key]

        # 裸响应
        return raw

    def _parse_device_detail(self, raw: dict[str, Any]) -> dict[str, Any]:
        """解析 device-detail 响应为传感器数值字典.

        字段名已通过对真实 API 响应分析确定：
          model: J3402-ROB90（防伪款）
          data: { tdsIn, tdsOut, instantFlowRate, totalUsedPureWater, ... }
        """
        result: dict[str, Any] = {}

        payload = self._unwrap_response(raw)
        if payload is None:
            _LOGGER.warning("⚠️ 响应解析失败: retCode=%s", raw.get("retCode"))
            return result

        if not isinstance(payload, dict):
            _LOGGER.warning("⚠️ data 不是 dict: %s", type(payload).__name__)
            return result

        # ---- 🔍 调试日志 ----
        _LOGGER.debug("📦 dataType=1 字段: %s", list(payload.keys()))

        # ========== 直接字段映射 ==========
        FIELD_MAP: dict[str, str] = {
            # 内部 key → API 字段名 (已验证)
            "tds_in":               "tdsIn",
            "tds_out":              "tdsOut",
            "flow_rate":            "instantFlowRate",
            "total_water_usage":    "totalUsedPureWater",
            "total_water_in":       "totalUsedWater",
            "today_pure_water":     "pureWater",
            "today_total_water":    "totalWater",
            "water_pressure":       "waterPressure",
            "working_status":       "deviceState",
            "error_code":           "warnCode",
            "error_message":        "warnMsg",
            "online_state":         "onlineState",
            "is_open":              "isOpen",
            "is_flushing":          "washState",
            "hot_water_outlet":     "hotWaterOutletState",
            "device_name":          "deviceName",
            "refresh_time":         "refreshTime",
        }

        for sensor_key, api_field in FIELD_MAP.items():
            if api_field in payload:
                val = payload[api_field]
                if val is not None and val != "":
                    result[sensor_key] = val

        # ========== 滤芯寿命 (filterElements 数组) ==========
        filters = payload.get("filterElements", [])
        if isinstance(filters, list) and filters:
            for idx, f in enumerate(filters):
                if not isinstance(f, dict):
                    continue
                name = f.get("name", f"filter_{idx}")
                life = f.get("life")        # 已用天数
                life_all = f.get("lifeAll") # 总寿命天数
                hour = f.get("hour")        # 已用小时数
                max_hour = f.get("maxHour") # 最大小时数

                if life is not None and life_all is not None and life_all > 0:
                    remain = max(0, (life_all - int(life)) / int(life_all) * 100)
                    if name == "PCR":
                        result["filter_pcr_remaining"] = round(remain, 1)
                    else:
                        # 按 index 命名: filter_1, filter_2, ...
                        result[f"filter_{idx + 1}_remaining"] = round(remain, 1)

                # 按小时算的剩余 (部分设备有小时寿命)
                if hour is not None and max_hour is not None and max_hour > 0:
                    hour_remain = max(0, (max_hour - int(hour)) / max_hour * 100)
                    if name == "PCR":
                        result["filter_pcr_hours"] = round(hour_remain, 1)

        # ========== TDS 脱盐率 (衍生计算) ==========
        tds_in = result.get("tds_in")
        tds_out = result.get("tds_out")
        if tds_in is not None and tds_out is not None:
            tds_in_f = float(tds_in)
            tds_out_f = float(tds_out)
            if tds_in_f > 0:
                result["tds_rejection_rate"] = round(
                    (1 - tds_out_f / tds_in_f) * 100, 1
                )

        # ========== 产品信息 (嵌套在 product 对象中) ==========
        product = payload.get("product")
        if isinstance(product, dict):
            model = product.get("productModel")
            pname = product.get("productName")
            if model:
                self._device_info.setdefault("model", str(model))
            if pname:
                self._device_info.setdefault("name", str(pname))
        if "deviceName" in payload:
            self._device_info.setdefault("name", str(payload["deviceName"]))

        # ---- 日志 ----
        if not result:
            _LOGGER.warning(
                "⚠️ 没有解析到任何数据！请检查响应格式: keys=%s",
                list(payload.keys()),
            )
        else:
            _LOGGER.debug("✅ 解析完成: %s", {k: v for k, v in result.items()
                                               if v is not None})

        return result

    def _extract_device_info(self, payload: dict[str, Any]) -> None:
        """从 device-detail(dataType=0/1) 响应中提取设备信息."""
        # 设备名
        name = payload.get("deviceName")
        if name:
            self._device_info["name"] = str(name)

        # 产品信息 (嵌套)
        product = payload.get("product")
        if isinstance(product, dict):
            model = product.get("productModel")
            pname = product.get("productName")
            version = product.get("productCode")
            if model:
                self._device_info["model"] = str(model)
            if pname:
                self._device_info.setdefault("name", str(pname))
            if version:
                self._device_info["sw_version"] = str(version)

        # 设备SN
        sn = payload.get("sn")
        if sn:
            self._device_info["sn"] = str(sn)

    # ------------------------------------------------------------------ #
    #  工具方法
    # ------------------------------------------------------------------ #

    @staticmethod
    def _match_field(data: dict, candidates: list[str]) -> Any:
        """从 data 中依次尝试候选字段名，返回第一个匹配的值."""
        for key in candidates:
            if key in data:
                val = data[key]
                if val is not None and val != "" and val != "null":
                    return val
        return None
