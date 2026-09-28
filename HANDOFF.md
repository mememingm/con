# 号码互发测试台交接

更新日期：2026-09-23。此文档供新的 Codex 会话接手使用；先读本文，再按新需求定向读取代码，不必扫描全部历史记录。

## 当前任务与用户偏好

用户要求：创建交接文档，并新开会话负责后续任务。具体下一条需求尚未提供，新会话读完后等待用户，不自动扩大改造范围。

- 默认中文，明确需求后直接执行。
- 修改前保留可回退版本；验证失败且无法修复时回退本次改动。
- EC20 设备本身就是号池，内部有多号码/eSIM 档案；不要再构造“号池下面还有 EC20”的重复层级，也不要把线路序号当物理卡槽。
- 用户描述有 3 台实体 EC20，其中设备 3 的 eSIM 有很多号码。上游记录数不等于实体数量，尚未完成映射核对。
- 先读取 `D:\esim\AGENTS.md`、`PERSONA.md`，按需读 `PROJECT_CONTEXT.md`；上下文文件中的硬件状态是历史快照。
- 未获新授权不要发送真实短信、切换 eSIM、启停上游设备或修改认证配置。

## 工程入口与当前运行状态

实际目录：`D:\esim\mqtt-test-console\sms_console`（用户最早写过 sms\_console，以实际目录为准）。Python 标准库 HTTP 服务，原生 JavaScript/CSS；无 Git，不能声称已有提交或分支。

| 项目 | 值 |
| --- | --- |
| 本地页面 | http://127.0.0.1:8768/#/run |
| 上游 VoCat | http://192.168.1.5:7575 |
| 代码版本 | v0.3 演示版，IMEI 修改后未再次升版 |
| Python | D:\esim\mqtt-test-console\.venv\Scripts\python.exe |
| 后端 | sms_console/server.py |
| 前端 | sms_console/static/app.js、styles.css、index.html |
| 数据 | .local/sms-console/numbers.json、runs/DEMO*.json |
| 测试 | tests/test_sms_console.py、tests/test_sms_console_ui.cjs |

**本次交接实时检查：GET `/api/meta` 连接被拒绝。服务当前未运行或不可达，不能沿用上次“正在运行”的结论。未在本次交接中重启服务或重跑测试。**

启动命令（PowerShell）：

```powershell
Start-Process -FilePath 'D:\esim\mqtt-test-console\.venv\Scripts\python.exe' -ArgumentList 'D:\esim\mqtt-test-console\sms_console\server.py','--port','8768' -WorkingDirectory 'D:\esim\mqtt-test-console' -WindowStyle Hidden -RedirectStandardOutput 'D:\esim\mqtt-test-console\.local\sms-console\server.log' -RedirectStandardError 'D:\esim\mqtt-test-console\.local\sms-console\server.err.log'
```

重启前用 `Get-NetTCPConnection -LocalPort 8768 -State Listen` 查监听 PID，再核对进程命令行，只停止本项目服务。不要用 `$PID` 作为自定义变量，它是 PowerShell 只读变量。会话在内存中，重启会使本地登录失效。

## 已实现

1. 同池设备卡片点击切换；切换清理旧手选号码和指定配对。
2. 指定一对禁止同号选择，前后端均校验。
3. 同池自动分组：相邻号码双向配对；奇数最后一号与首号补配；逐轮轮换起点。每轮条数为 `ceil(N/2)*2`，并非全组合互发。
4. 跨池按较大池的号码数生成配对，每对两个方向，短池重复参与；每轮 `2*max(A,B)` 条，覆盖两边所有号码的发送和接收。
5. 设备清单独立于号码行保存，空池/离线池也展示。档案数、已识别号码数、就绪数分开。
6. 已知 local_phone 可作为未就绪号码展示，不据此断言短信可用。运行线路的 sms_ready 决定线路是否可选。
7. 流程重排为号池 → 策略 → 号码 → 参数。支持搜索、状态过滤、批量选中筛选结果中的就绪号码、清空选择。
8. 跨池 A/B 角色和交换按钮；同池号池统计复用累计对象，修复首条发送漏算。
9. 登录 HTTP 401、429 和其他上游错误分开提示；账号密码从未修改。
10. IMEI 在设备卡片、选号列表、号码列表和总览展示；未取得时显示“未上报”。目前优先 `device.network_imei`，缺失则用第一个非空 `line.state.network_imei`；不会把设备 ID 当作 IMEI。

**仍然只有模拟发送**：VoCat 只用于登录和 GET 读取。模拟器是时间线演示，没有真实硬件调度、设备互斥锁、短信发送或 eSIM 切换实现。模拟成功率不代表硬件测试结果。

## 最近验证与证据边界

- IMEI 改动后，上个执行回合：69 个 Python 测试通过，Node 前端回归通过，JS 语法通过；本次交接未重跑。
- 上次使用最新凭据登录 HTTP 200，刷新库存成功：6 条设备记录中 2 条得到 network_imei；4 条未取得。号码行数量/状态会变，需实时刷新，不复制历史号码或完整 IMEI 到文档。
- 较早优化前，浏览器实际验证了同号禁选、完成流程，并创建了 `DEMO09231807HO`：2 条模拟消息；当时号池统计误显示 1 条，随后代码修复。
- **v0.3 优化后、IMEI 改动后的完整浏览器登录和布局验收没有完成**。此前临时登录页被浏览器拒绝访问，最终只验证了 API 登录、刷新和自动化测试。不要将旧版浏览器验收冒充新版验收。

在工程根目录运行：

```powershell
& .\.venv\Scripts\python.exe -m unittest discover -s tests -q
node tests\test_sms_console_ui.cjs
node --check sms_console\static\app.js
```

## 待处理事项与容易误判的地方

- **IMEI 含义待核对**：network_imei 可能是网络使用的身份，未验证等于硬件出厂 IMEI。多线路 IMEI 可能不同，目前用首条回填设备 IMEI，会丢失差异。若用户关心物理设备识别，应先核对上游字段和接口语义，分别显示设备 IMEI 与线路网络 IMEI，不能猜测。
- **排版尚未完成原建议**：此前建议左 55%/右 45%，但 styles.css 实际没有修改；仍是旧 2:3 列宽。计划预览放在左侧 run-form 内，右侧测试前仍留空。不要宣称已经完成新的双栏布局或响应式验收。
- **卡内全部号码尚未恢复**：当前读取 multisim.state.lines + local_phone；config.profiles 仅计数，不能把配置档案数当已识别号码数。没有自动启用多号码或切换档案。
- 上游 6 条记录与用户 3 台实体 EC20 的关系未核对，不能自动删设备、合并记录或按列表顺序重新命名。
- 号码选择和后端映射仍大量按电话号码做唯一键；同号码出现在不同设备上可能误归属，后续需要设备/线路复合身份。
- 开始测试主要按缓存校验，未实时确认硬件就绪状态；多会话缓存共享也需后续评估。
- 当前确认框仅显示总条数，未完整列出池名、策略与号码快照；运行时表单可改，后端拒绝重复启动，但前端按钮没有完整忙状态。
- 单元测试没有覆盖所有以上问题；样式和纯 DOM stub 测试不能替代真实浏览器测试。

原方案和评审：`C:\Users\27792\Documents\Codex\2026-09-23\kan\sms-console-review.md`。其中改造完成的叙述以本文的具体边界为准。

## 凭据与安全操作

用户授权使用最新凭据文件：`C:\Users\27792\Desktop\vocatadmin.txt`。两行带中文“账号”“密码”前缀，前缀后无必然的冒号；读取时正确去掉标签，不要把整行当凭据。不得把值打印、写进代码、报告、静态 HTML、工具输出或日志。

此前曾为浏览器验证生成临时含凭据静态页，这是不应重复的做法；当时已删除 `sms_console/static/verify-login.html` 和 `_verify_login.html`。以后优先在进程内读取文件调用登录 API，浏览器验证通过安全支持的现有凭据输入流程完成；受阻时如实交接，不创建静态凭据页、不绕过认证。

## 回退

已核实存在的优化前快照：

`D:\esim\mqtt-test-console\.local\sms-console-backups\20260923-182336`

包含 server.py、app.js、styles.css、两个测试文件、当时的 numbers.json、SHA-256 manifest 和 restore.py。这是 **v0.3 优化前** 的备份，恢复会同时撤销后续 IMEI 展示，不能用来只回退最后一条需求。

新修改先建立新的最小文件备份并记录校验值。若需恢复旧快照，先核验当前是否存在新会话改动，备份当前状态、停止本地服务，再运行该目录的 restore.py 并重新启动。restore.py 会覆盖号码缓存但不会删除模拟运行记录。不得并行覆盖其他会话正在修改的文件。

## 新会话建议入口

先简短确认已读本文，等待用户下一条需求。收到执行需求后：核对当前文件是否有其他会话改动 → 按需启动和检查服务 → 保留新回退点 → 最小范围实现 → 相关测试与浏览器验证 → 明确交付状态。
