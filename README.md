# 安吉尔净水器 — Home Assistant 自定义组件

> 通过安吉尔 IoT 云平台 API 在 Home Assistant 中监测你的安吉尔（Angel）净水器。

---

## 工作原理

通过 HTTPS 调用 **安吉尔 IoT 云平台** (`iot.angelgroup.com.cn`) 获取净水器实时数据。

基于对安吉尔微信小程序的抓包逆向，已验证的 API 端点：

```http
GET /iotmp-openapi/v1/device-info/device-detail?sn={SN}&dataType=1
```

设备型号: **J3402-ROB90（防伪款）** / **M5 600**

## 传感器实体（16个）

| 实体 ID | 描述 | 单位 | API 字段 |
|---------|------|------|----------|
| `sensor.tds_in` | 进水 TDS | ppm | `tdsIn` |
| `sensor.tds_out` | 出水 TDS | ppm | `tdsOut` |
| `sensor.tds_rejection_rate` | 脱盐率 | % | 由 TDS 计算 |
| `sensor.flow_rate` | 当前流量 | L/min | `instantFlowRate` |
| `sensor.total_water_usage` | 累计纯水量 | L | `totalUsedPureWater` |
| `sensor.total_water_in` | 累计总用水量 | L | `totalUsedWater` |
| `sensor.today_pure_water` | 今日纯水量 | L | `pureWater` |
| `sensor.today_total_water` | 今日总用水量 | L | `totalWater` |
| `sensor.water_pressure` | 水压 | MPa | `waterPressure` |
| `sensor.filter_pcr_remaining` | PCR 滤芯寿命 | % | `filterElements[].life` |
| `sensor.working_status` | 工作状态 | — | `deviceState` |
| `sensor.error_code` | 故障代码 | — | `warnCode` |
| `sensor.error_message` | 故障信息 | — | `warnMsg` |
| `sensor.device_name` | 设备名称 | — | `deviceName` |
| `sensor.refresh_time` | 最后刷新 | — | `refreshTime` |

## 二进制传感器（8个）

| 实体 ID | 描述 | API 字段 |
|---------|------|----------|
| `binary_sensor.online_state` | 在线状态 | `onlineState` |
| `binary_sensor.is_open` | 开关 | `isOpen` |
| `binary_sensor.is_flushing` | 冲洗中 | `washState` |
| `binary_sensor.hot_water_outlet` | 热水出水 | `hotWaterOutletState` |
| `binary_sensor.is_working` | 运行中 | `deviceState == "1"` |
| `binary_sensor.filter_change_required` | 需要更换滤芯 | 滤芯 < 5% |
| `binary_sensor.leak_detected` | 漏水检测 | `warnCode == "E1"` |
| `binary_sensor.water_quality_warning` | 水质警告 | TDS > 50ppm |

---

## 安装

### 手动安装

```bash
cp -r custom_components/angel_water_purifier /path/to/ha/config/custom_components/
```

重启 HA，然后 **设置 → 设备与服务 → 添加集成**，搜索 "Angel Water Purifier"。

### 配置参数

| 参数 | 说明 | 获取方式 |
|------|------|----------|
| **SN** | 设备序列号 | 微信小程序抓包 URL 参数 `sn=` |
| **Bearer Token** | 访问令牌 | 请求头 `Authorization: Bearer xxx` |
| **User ID** | 用户 ID | 请求头 `User-Id` |
| **wxOpenId** | 微信 OpenID | URL 参数 `wxOpenId=`（可选） |

> 💡 使用 Proxyman / Charles / Whistle 等工具对微信小程序进行 HTTPS 抓包即可获取以上信息。

---

## 开发

```bash
custom_components/angel_water_purifier/
├── __init__.py        # 组件入口 & 生命周期
├── api.py             # ⭐ Angel IoT 云 API 客户端
├── const.py           # 常量 & 传感器定义
├── config_flow.py     # UI 配置流
├── coordinator.py     # 数据轮询协调器
├── diagnostics.py     # HA 诊断面板
├── sensor.py          # 15 个传感器实体
├── binary_sensor.py   # 8 个二进制传感器实体
├── services.yaml      # 服务定义
└── strings.json       # 中文字符串
```
