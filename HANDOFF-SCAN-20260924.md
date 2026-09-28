# 会话扫描交接：IMEI / TAC / EC20 测试台

更新时间：2026-09-24（北京时间）

这份文档压缩了以下会话的有效上下文，供下一位 agent 继续执行：

- `01a0d18e-31a2-7713-acec-d284097634b4`：IMEI 查询页、VoCat IMEI 来源、号池分组优化
- `01a0cef2-4192-7ec0-b5cc-de811bfb140d`：v0.4 客户版浏览器验收与 API 边界测试
- `01a0ceda-346e-7e10-bc46-73e714d9610d`：客户版副本启动、继续验收、关机安排
- `01a0d163-4f0b-7640-9190-b18db4552df1`：TAC 数据集接入、浏览器错误修复、数据质量分析
- `01a0cdf3-fff1-7f20-93df-61bdffca93e3`：EC25 / SIM / ePDG / IMS / 隧道概念说明
- `01a0d1cf-8043-7f91-ba70-7c2b14301bb5`：本次扫描会话

## 1. 交接目标

继续维护并验证客户版短信测试台：

```text
VoCat / 本地缓存
        ↓
设备与 IMEI 读取
        ↓
TAC 本地数据集查询
        ↓
IMEI 识别、EC20/号池关联、短信测试入口
```

本轮优先目标是确认当前代码真实可运行、TAC 查询真实可用、浏览器页面没有回归，然后再决定是否需要继续改代码。不要从头重做 v0.4。

## 2. 工作区与边界

- 客户版副本：`D:\esim\mqtt-test-console-customer`
- 原项目：`D:\esim\mqtt-test-console`
- 客户版没有 Git；不要声称存在 commit、branch 或已提交 PR。
- 现有项目交接文档：
  - `D:\esim\mqtt-test-console-customer\HANDOFF-V04.md`
  - `D:\esim\mqtt-test-console-customer\HANDOFF-IMEI-SOURCE.md`
- 现有服务端口：`127.0.0.1:8768`。每次使用前确认监听 PID 的命令行确实指向客户版副本。
- 原有启动解释器：`D:\esim\mqtt-test-console\.venv\Scripts\python.exe`

启动命令：

```powershell
& 'D:\esim\mqtt-test-console\.venv\Scripts\python.exe' `
  'D:\esim\mqtt-test-console-customer\sms_console\server.py' --port 8768
```

## 3. 会话中已实现的功能

以下是会话最后报告过的实现结果，仍需按第 6 节重新复核：

### 客户版 v0.4 / 离线演示

- `/api/demo-session` 支持 VoCat 不可用时进入离线演示。
- 本地缓存用于展示设备、号码和 IMEI；页面应明确显示“离线缓存”，不得伪装成实时状态。
- IMEI 分组支持创建、批量导入、删除、持久化和冲突关联。
- 批量导入上限为 100 条。
- IMEI 页支持搜索、状态筛选、详情展开、从缓存 EC20 导入和 CSV 导出。

### IMEI 查询与 VoCat 来源

- 页面导航和路由：`#/imei-query`（旧版本交接文档也称 `#/imei`，以当前 `app.js` 路由为准）。
- 只读接口：
  - `GET /api/imei/devices`
  - `GET /api/imei/lookup?imei=...`
- IMEI 来源优先级：

```text
VoCat /api/devices[].network_imei
        ↓ 缺失时
/api/devices/{id}/multisim -> lines[].state.network_imei
        ↓
本地 numbers.json
        ↓
总览、开始测试、IMEI 页面
```

- 实时查询成功后会刷新本地号码快照；VoCat 暂时不可用时返回最近缓存，并携带 `source=cache`、缓存时间和过期提示。
- 设备级 IMEI 复制到该设备的号码行，便于显示；这不表示每个号码都是独立设备。
- 设备 ID、电话号码、ICCID、配置档案数都不能当成 IMEI。

### 号池与前端展示

- 开始测试的号码选择区已按 `A 号池` / `B 号池` 分组。
- 每组显示设备名、就绪数、已选数；每个号码行重复显示所属号池和设备。
- `1`、`2`、`3`、`dd` 等是设备 ID/名称，不是硬件 IMEI。
- EC20 在当前业务中代表一个设备号池；号码是号池成员。

### TAC 本地数据集

- 数据目录：`D:\esim\前端\tac-database-main`
- 运行时主源：`tac_full.csv`
- `tac_full.xlsx` 只作为人工复核/备选输入，不应在每次请求时解析。
- 新增模块：`sms_console/tac_catalog.py`。
- 支持 `TAC_CSV` 环境变量替换默认数据路径。
- 服务启动时加载一次并建立内存索引。
- TAC 必须按字符串处理，保留前导零。
- 查询状态：`matched`、`ambiguous`、`unknown`。
- 返回结果中包含候选型号、数据来源和数据集版本/哈希等元信息（以当前代码为准）。
- `lookup_imei()` 已从早期硬编码示例映射改为读取 CSV 的实现（会话报告已完成，需重新运行测试确认）。

数据质量检查的会话结论：

- CSV 约 255,002 行；约 248,378 行是标准 8 位 TAC；约 6,624 行为空、非 8 位或其他异常值。
- 存在重复 TAC；一个 TAC 不能假设只对应一个型号。
- CSV 与 XLSX 存在少量差异，因此不要同时导入并互相覆盖。
- 不要把 6 位 TAC 自动补齐；7 位 TAC 是否补零必须有来源依据。建议保留 `tac_raw` 与 `tac_normalized` 的区别。

## 4. 会话报告过的验证结果

这些结果来自不同时间点，不等于当前工作区已经重新验收：

- 客户版浏览器验收：离线登录 → 总览 → IMEI 导入/详情/搜索/状态筛选/CSV 导出 → 开始测试。
- 390px 窄屏无横向溢出，导航自动隐藏，浏览器控制台无 error/warn。
- 离线模拟批次 `DEMO09232350HM` 报告为 2/2 成功到达。
- 服务报告为 `127.0.0.1:8768`，某次 PID 为 23652；PID 必须现场重新确认。
- Python 测试曾报告 71、72、77 项通过，数字对应不同改动阶段；不能直接沿用，必须重新运行当前副本。
- Node UI 测试和 `node --check sms_console\static\app.js` 曾通过。
- 浏览器错误 `tacResultHtml is not defined` 已修复：`app.js` 增加了唯一匹配、多候选、未收录三种渲染分支。
- 远程 VoCat 只读检查曾确认：`192.168.1.5:7575` 可达，`/api/health` 正常，6 台设备中 5 台 ready，设备 `2` 曾为 missing，设备 `3` 曾有 20/20 条线路 ready。SSH 登录因用户/凭据不匹配未能进入系统层面查看 vocat 进程。

## 5. 必须遵守的边界

- 不读取、回显、提交或写入密码、API key、SIM 激活码、完整 ICCID/IMSI/EID 或短信正文。
- 不把缓存结果写成实时 VoCat 结果。
- 不把设备 ID、电话号码或 `network_imei` 直接断言为出厂硬件 IMEI。
- 不调用第三方接口发送完整 IMEI；TAC 查询优先本地完成。
- Osmocom `http://tacdb.osmocom.org/query` 会话测试结论是：它返回 HTML/CSRF，提交后提示“不支持查询接口”，不应作为在线 API 接入。若需要使用其数据，应下载后本地查询。
- 远程 VoCat 的 GET 检查可以做，但不要修改设备、发送短信或改变服务配置。
- 修改前先在 `.local` 建立新的 `rollback-*` 目录；不要覆盖其他 agent 正在验证的文件。
- 真实设备实验、真实 MQTT Broker、TLS/ACL、硬件 adapter 和端到端联调仍未由这些会话证明。

## 6. 下一位 agent 的执行顺序

### A. 先核对当前现场

1. 读取 `PROJECT_CONTEXT.md`、本文件、`HANDOFF-V04.md`、`HANDOFF-IMEI-SOURCE.md`。
2. 检查 `8768` 监听 PID、命令行和当前工作区修改时间。
3. 确认没有其他 agent 正在写 `server.py`、`tac_catalog.py`、`static/app.js`、`static/styles.css` 或 `tests`。

### B. 重新跑自动化检查

在 `D:\esim\mqtt-test-console-customer` 执行：

```powershell
& 'D:\esim\mqtt-test-console\.venv\Scripts\python.exe' -m unittest discover -s tests -q
node tests\test_sms_console_ui.cjs
node --check sms_console\static\app.js
```

记录实际测试数量和失败输出，不引用上面历史数字。

### C. 做 API 冒烟检查

1. 使用 `POST /api/demo-session` 创建离线会话，保留 session cookie。
2. 检查未登录访问返回 401，且缺少 `X-Requested-With` 时不会绕过认证。
3. 调用 `/api/imei/devices`，确认缓存来源、设备数和 IMEI 字段。
4. 调用 `/api/imei/lookup` 覆盖：
   - 合法且唯一匹配的 IMEI；
   - 同 TAC 多候选的 `ambiguous`；
   - 合法但未收录的 `unknown`；
   - Luhn 错误；
   - 前导零 TAC；
   - 空值、非数字、长度错误。
5. 确认返回中不泄露凭据或不必要的完整敏感字段。

### D. 浏览器验收（浏览器工具可用时）

验证：离线登录 → IMEI 页面 → 导入/粘贴 → TAC 状态和候选型号 → 设备/号池关联 → 搜索/筛选 → 详情 → CSV 导出 → 开始测试入口；再检查 390px 窄屏和 console error/warn。

### E. 只有发现真实失败才改代码

- TAC 映射仍不应猜型号；未收录就显示 `unknown`。
- 若数据量导致启动时间或内存不可接受，再评估预清洗 SQLite/JSON；不要为了“看起来更完整”同时运行时加载 CSV 和 XLSX。
- 若同一设备线路出现不同 `network_imei`，增加线路级展示和冲突提示，不能继续静默取首个值。

## 7. 交付格式

最终报告必须分开写：

- **已验证完成**：本轮实际命令、接口和浏览器结果。
- **部分完成**：代码存在但本轮没有证据的内容。
- **建议但未执行**：例如拆分 TAC 数据文件、增加来源更新时间、预清洗 SQLite。
- **无法完成/阻塞**：例如浏览器工具不可用、SSH 凭据不匹配、远程 VoCat 不可达。

不要把历史会话的测试数、用户口述成功或实现代码存在，直接写成当前轮次通过。
