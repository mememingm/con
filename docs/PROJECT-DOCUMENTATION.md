# eSIM 设备与短信测试台项目文档

更新时间：2026-09-28（北京时间）  
项目路径：`D:\esim\mqtt-test-console-customer\sms_console`

## 1. 项目简介

这是一个运行在本机的 eSIM/EC20 设备与短信测试台。它提供三类能力：

1. 读取 VoCat 的设备、号池和号码状态；
2. 识别和管理 IMEI，并使用本地 TAC 数据集查询厂商/型号；
3. 在本地演示模式下模拟号码互发、查看测试记录并导出 CSV。

当前版本是 `v0.4 设备识别与测试台`。**当前的短信测试是本地模拟，不会通过本项目发送真实短信。** VoCat 连接也只允许登录和只读 GET 查询。

```text
浏览器
  ↓ HTTP
server.py（本机 127.0.0.1:8768）
  ├─ 离线缓存：.local/sms-console/numbers.json
  ├─ IMEI/TAC：本地 imei-groups.json + tac_full.csv
  ├─ 演示测试：本地生成测试批次和消息状态
  └─ 在线只读：VoCat /api/devices、/api/devices/{id}/multisim
```

## 2. 目录结构

```text
mqtt-test-console-customer/
├─ sms_console/
│  ├─ server.py                 Python HTTP 后端、会话、API、模拟测试
│  ├─ tac_catalog.py            TAC CSV 加载、索引和查询
│  └─ static/
│     ├─ index.html             单页入口
│     ├─ app.js                 原生 JavaScript 前端和页面路由
│     └─ styles.css             页面样式和响应式布局
├─ tests/
│  ├─ test_sms_console.py       后端、会话、号码和模拟测试
│  ├─ test_tac_catalog.py       TAC 数据加载和查询
│  ├─ test_sms_console_ui.cjs   前端静态检查
│  ├─ test_mq_coverage.py       MQTT 用例覆盖工具测试
│  ├─ test_mq_layer1.py         MQTT 第一层测试工具测试
│  ├─ test_readonly_inbox.py    只读证据处理测试
│  └─ test_reporting.py         报告导出工具测试
├─ docs/
│  ├─ PROJECT-DOCUMENTATION.md  本文档
│  ├─ case-mapping.md           MQTT 用例和前提映射
│  ├─ protocol-baseline.md      MQTT 判据和协议差异
│  └─ validation-20260921.txt   历史验证记录
├─ .local/sms-console/          本机运行数据，不应提交到公共仓库
│  ├─ numbers.json              VoCat 号码快照
│  ├─ settings.json             演示参数
│  ├─ imei-groups.json          IMEI 分组和保存记录
│  └─ runs/*.json               模拟测试批次
└─ README.md                    旧版 MQTT 清单整理工具说明
```

## 3. 启动项目

在 PowerShell 中执行：

```powershell
cd D:\esim\mqtt-test-console-customer

& 'D:\esim\mqtt-test-console\.venv\Scripts\python.exe' `
  'D:\esim\mqtt-test-console-customer\sms_console\server.py' `
  --port 8768
```

启动成功时，终端会显示：

```text
号码互发测试台（演示版）: http://127.0.0.1:8768
```

浏览器访问：

```text
http://127.0.0.1:8768/
```

可选参数：

```powershell
& 'D:\esim\mqtt-test-console\.venv\Scripts\python.exe' `
  'D:\esim\mqtt-test-console-customer\sms_console\server.py' `
  --port 8769 `
  --vocat http://192.168.1.5:7575
```

`--vocat` 用于指定 VoCat 地址；默认值是 `http://192.168.1.5:7575`。服务只监听 `127.0.0.1`，默认不对局域网开放。

## 4. 前端页面

登录或进入离线演示后，前端使用 hash 路由：

| 路由 | 页面 | 作用 |
|---|---|---|
| `#/overview` | 总览 | 查看整体成功率、设备和最近测试情况 |
| `#/run` | 开始测试 | 选择号池和号码，启动本地模拟互发 |
| `#/imei` | IMEI 识别 | 查询设备 IMEI、TAC 型号、分组和关联关系 |
| `#/records` | 测试记录 | 查看历史模拟批次 |
| `#/records/{batch}` | 记录详情 | 查看单个批次并导出 CSV |
| `#/numbers` | 号码状态 | 查看号码、设备、号池和就绪状态 |
| `#/settings` | 系统设置 | 调整演示失败比例和模拟延迟 |

## 5. 后端职责和数据流

### 5.1 `server.py`

`server.py` 使用 Python 标准库的 `ThreadingHTTPServer`，不依赖 Flask、FastAPI 或其他 Web 框架。主要职责：

- 提供静态文件和 JSON API；
- 管理内存会话，默认有效期 12 小时；
- 调用 VoCat 登录和只读接口；
- 读写本地 JSON 快照和测试批次；
- 校验 IMEI、查询 TAC；
- 规划并生成本地模拟测试消息；
- 返回总览、明细和 CSV。

### 5.2 VoCat 只读边界

`VoCatReader` 只允许：

- `POST /api/auth/login`：登录验证；
- `GET /api/devices`：读取设备；
- `GET /api/devices/{id}/multisim`：读取设备号池和线路。

除登录外的带请求体写操作会被拒绝。当前 console 没有通过 VoCat 发送短信、写卡、改 Profile 或修改设备配置的代码。

设备 IMEI 的读取优先级：

```text
设备对象 network_imei
  ↓ 缺失时
线路 state.network_imei
  ↓
保存为本地设备/号码快照
```

注意：`network_imei` 是 VoCat 当前上报的网络设备身份，不能仅凭此字段断言物理模块的出厂 IMEI。

### 5.3 在线和离线模式

在线登录后，`/api/numbers?refresh=1` 或首次读取会从 VoCat 拉取设备和号码，并写入：

```text
.local/sms-console/numbers.json
```

离线演示通过 `POST /api/demo-session` 创建，不访问 VoCat，直接读取本地缓存。响应会带有：

- `source=cache`；
- `stale=true`；
- `warning`；
- `fetched_at`。

因此离线缓存只能用于演示和查看历史状态，不能当作当前实时设备状态。

## 6. IMEI 和 TAC 功能

### 6.1 IMEI 校验

系统要求 IMEI 为 15 位 ASCII 数字，并执行 Luhn 校验。Luhn 只能证明输入格式自洽，不能证明设备真实存在。

手动查询流程：

```text
输入完整 IMEI
  ↓
15 位数字检查
  ↓
Luhn 校验
  ↓
取前 8 位 TAC
  ↓
查询本地 TAC 索引
```

### 6.2 TAC 数据源

默认数据源：

```text
D:\esim\前端\tac-database-main\tac_full.csv
```

启动时由 `tac_catalog.py` 读取一次并建立内存索引，运行中的请求不会重复解析 CSV，也不会读取 XLSX。

支持的环境变量：

| 环境变量 | 作用 |
|---|---|
| `TAC_CSV` | 替换默认 TAC CSV 路径 |
| `TAC_SOURCE` | 返回结果中的数据源名称 |
| `TAC_DATA_UPDATED_AT` | 数据更新时间元信息 |
| `TAC_DATA_COVERAGE_THROUGH` | 数据覆盖截止时间，默认 `2025-12` |

查询状态：

- `matched`：一个唯一候选；
- `ambiguous`：同一 TAC 有多个不同候选；
- `unknown`：数据集中没有候选。

系统不会根据品牌经验猜测未收录型号。

### 6.3 IMEI 分组保存

IMEI 分组保存于：

```text
.local/sms-console/imei-groups.json
```

支持创建分组、批量导入、删除和批量查询。批量导入最多处理 100 条；批量 TAC 查询最多 500 条。记录再次展示时会根据当前缓存设备重新计算关联状态：

- `linked`：精确关联到一台设备；
- `unlinked`：没有找到设备；
- `conflict`：同一 IMEI 找到多台设备，不能自动合并。

## 7. 模拟短信测试

### 7.1 测试模式

当前设置被代码强制锁定为：

```text
send_mode = demo
```

可调参数：

- `fail_rate`：提交失败比例，范围 0～50%；
- `undelivered_rate`：未到达比例，范围 0～50%；
- `latency_min` / `latency_max`：模拟到达延迟，范围 0.5～60 秒。

### 7.2 互发方式

支持四种模式：

- `relay`：接力互发；
- `pairs`：两两互发；
- `pair`：指定一对号码；
- `cross_pool`：两个不同号池之间轮询互发。

测试只允许选择缓存中标记为 `ready` 的号码。轮数范围是 1～5，间隔范围是 0.1～10 秒，单批最多生成 2000 条消息。

批次文件写入：

```text
.local/sms-console/runs/{batch}.json
```

记录中的“已到达”等状态是模拟结果，不是运营商 delivery report，也不是实际短信送达证据。

## 8. API 参考

### 8.1 通用规则

- GET API 需要有效的 `smsc_session` Cookie（`/api/meta`、静态文件除外）；
- POST API 必须带请求头 `X-Requested-With: sms-console`；
- 请求和响应主体主要使用 JSON；
- 所有响应设置 `Cache-Control: no-store`；
- 会话保存在进程内，服务重启后需要重新登录；
- 当前没有正式 `/api/v1` 版本前缀。

### 8.2 无需登录的接口

| 方法 | 路径 | 作用 |
|---|---|---|
| `GET` | `/`、`/index.html` | 返回前端入口 |
| `GET` | `/static/{file}` | 返回前端静态资源 |
| `GET` | `/api/meta` | 返回版本和 VoCat 地址 |
| `POST` | `/api/login` | 使用 VoCat 账号登录，不保存密码 |
| `POST` | `/api/demo-session` | 创建离线演示会话 |

### 8.3 登录后 GET 接口

| 方法 | 路径 | 作用 |
|---|---|---|
| `GET` | `/api/me` | 当前用户和 offline 状态 |
| `GET` | `/api/numbers` | 读取缓存号码；在线会话可加 `?refresh=1` |
| `GET` | `/api/overview` | 总览统计、设备和最近测试 |
| `GET` | `/api/imei/devices` | 实时或缓存设备 IMEI 列表 |
| `GET` | `/api/imei/lookup?imei=...` | 查询单个 IMEI/TAC |
| `GET` | `/api/imei` | 读取 IMEI 分组和记录 |
| `GET` | `/api/settings` | 读取演示参数 |
| `GET` | `/api/runs` | 读取测试批次列表 |
| `GET` | `/api/runs/current` | 读取当前测试状态 |
| `GET` | `/api/runs/{batch}` | 读取批次详情 |
| `GET` | `/api/runs/{batch}.csv` | 导出批次 CSV |
| `GET` | `/api/real` | 读取历史真实结果目录的只读汇总 |

### 8.4 登录后 POST 接口

| 方法 | 路径 | 作用 |
|---|---|---|
| `POST` | `/api/logout` | 注销当前会话 |
| `POST` | `/api/settings` | 保存演示参数，拒绝真实发送模式 |
| `POST` | `/api/imei/batch-lookup` | 批量查询 IMEI/TAC，最多 500 条 |
| `POST` | `/api/imei/save-results` | 保存批量查询记录 |
| `POST` | `/api/imei` | 创建分组、导入或删除 IMEI |
| `POST` | `/api/runs` | 创建本地模拟测试批次 |
| `POST` | `/api/runs/current/stop` | 停止当前模拟批次 |

## 9. 测试和验证

在项目根目录执行：

```powershell
cd D:\esim\mqtt-test-console-customer

& 'D:\esim\mqtt-test-console\.venv\Scripts\python.exe' -m unittest discover -s tests -q
node tests\test_sms_console_ui.cjs
node --check sms_console\static\app.js
```

这些测试验证本地代码、TAC 查询、报告工具和前端静态结构，**不等于真实 MQTT、真实短信或真实运营商送达验收**。

建议的手工冒烟流程：

1. 启动服务；
2. 打开首页；
3. 点击“离线演示”；
4. 检查总览和号码状态；
5. 在 IMEI 页面导入、搜索、查看详情并导出 CSV；
6. 选择两个就绪号码启动两两互发；
7. 查看测试记录并导出批次 CSV；
8. 用 390px 左右窄窗口检查横向溢出和浏览器控制台错误。

## 10. 安全和数据边界

- 不要把 VoCat 密码、API key、SIM 激活码、完整 ICCID/IMSI/EID 或短信正文写入项目文档；
- `/api/login` 只把账号密码转发给 VoCat，不在本项目持久化密码；
- 会话 Cookie 设置了 `HttpOnly` 和 `SameSite=Strict`，但当前服务没有 HTTPS，适合本机演示，不适合直接暴露公网；
- `.local` 下的缓存、IMEI 记录和测试批次可能包含敏感业务数据，不应提交或外发；
- 本地 TAC CSV 是静态参考数据，不是运营商权威设备身份数据库；
- 设备 ID、手机号、ICCID、配置档案数和 `network_imei` 不能互相替代。

## 11. 当前限制和后续工作

### 已实现但仍需持续验证

- 客户版页面和 IMEI/TAC 功能；
- 离线缓存和模拟短信测试；
- 本地测试记录和 CSV 导出。

### 当前未实现

- 真实短信发送；
- 真实 MQTT Broker、TLS、ACL 和业务 ACK；
- 真实硬件 adapter 的端到端接入；
- 多用户、持久化数据库和生产级会话管理；
- 正式的 `/api/v1` API 契约和版本迁移机制。

### 进入真实联调前的前提

需要先明确并提供隔离环境中的 Broker、TLS/ACL、云端入库入口、节点身份、硬件 adapter 和真实短信证据规则。没有这些条件，不能把本地模拟结果写成 MQTT 已部署或短信已送达。

## 12. 常见问题

### 页面打不开

确认服务仍在运行，并检查端口：

```powershell
Get-NetTCPConnection -LocalPort 8768 -State Listen
```

如果端口已被占用，可以换端口启动，例如 `--port 8769`，然后访问对应地址。

### 显示 VoCat 连接失败

可先点击“离线演示”继续查看本地缓存。离线页面显示的是历史快照，不能当作实时设备状态。

### TAC 查询全部是 unknown

检查 `TAC_CSV` 是否指向存在的 CSV 文件，并确认 CSV 包含 `brand`、`tac`、`specs` 三个字段。服务只在启动时加载 TAC 数据，修改数据文件后需要重启服务。

### 为什么测试成功但没有真实短信

因为当前版本固定为 `send_mode=demo`。测试结果只表示本地模拟流程完成，不会调用运营商或 VoCat 的短信发送接口。

## 13. 相关文档

- [`README.md`](../README.md)：旧版 MQTT 清单整理和离线报告工具说明；
- [`case-mapping.md`](case-mapping.md)：MQTT 测试用例映射；
- [`protocol-baseline.md`](protocol-baseline.md)：MQTT 判据、协议差异和证据边界；
- [`HANDOFF-V04.md`](../HANDOFF-V04.md)：客户版 v0.4 交接说明；
- [`HANDOFF-SCAN-20260924.md`](../HANDOFF-SCAN-20260924.md)：IMEI/TAC/EC20 功能交接说明。
