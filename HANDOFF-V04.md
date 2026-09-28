# eSIM 设备与短信测试台 v0.4 交接

更新时间：2026-09-23（北京时间）

## 新会话目标
继续在 `D:\esim\mqtt-test-console-customer` 完成客户可交付级的界面与交互打磨，重点验收：离线演示、IMEI 识别与 EC20 关联、开始测试流程和响应式布局。

## 当前工作副本
- 原项目：`D:\esim\mqtt-test-console`
- 当前副本：`D:\esim\mqtt-test-console-customer`
- 回退点：`D:\esim\mqtt-test-console-customer\.local\rollback-pre-redesign`
- 本副本无 Git，不要声称有 commit/branch。
- 服务当前启动在 `http://127.0.0.1:8768`，启动命令：
  `D:\esim\mqtt-test-console\.venv\Scripts\python.exe D:\esim\mqtt-test-console-customer\sms_console\server.py --port 8768`

## 已完成
1. 复制代码并把本地 `numbers.json`、演示 runs 复制到副本；未复制 `.venv`、凭据和原 `.local` 全量目录。
2. 后端版本改为 `v0.4 设备识别与测试台`。
3. 增加 `/api/demo-session`：远程 VoCat 关闭时进入离线演示，`/api/numbers` 返回本地缓存并标注离线警告；正常登录仍走原 VoCat。
4. 增加 `/api/imei`：分组创建、批量导入（每批最多 100）、删除、持久化到 `.local/sms-console/imei-groups.json`。
5. IMEI 状态：15 位数字 + Luhn、重复、TAC、本地 TAC 示例数据集命中/未收录、完整 IMEI 精确关联缓存设备；冲突不自动合并。
6. 前端增加 `IMEI识别` 导航页：分组、批量粘贴、从缓存 EC20 导入、状态筛选、搜索、详情展开、删除、CSV 导出、关联 EC20 跳转到开始测试。
7. 顶部显示“离线演示 · 本地缓存”；总览增加设备/号池库存卡片（IMEI、在线状态、号码数、就绪数、配置档案数）。
8. 样式做了客户交付向的视觉升级：深色侧栏、清晰状态层级、IMEI 双栏布局、响应式断点、sticky 执行区。

## 验证证据
- `node --check sms_console/static/app.js` 通过。
- `node tests/test_sms_console_ui.cjs` 通过。
- `D:\esim\mqtt-test-console\.venv\Scripts\python.exe -m unittest discover -s tests -q`：71 个测试通过。
- 实际 HTTP 验证通过：离线 session 200、`/api/me` 返回 `offline=true`、`/api/overview` 返回 6 台缓存设备、`/api/imei` 200、离线号码读取 200。
- 实际 HTTP 验证通过：离线模式选择缓存中 2 个就绪号码启动两两互发，返回批次并可停止。
- CUA 浏览器库存/连接失败，尚未完成真实浏览器截图和点击验收；不要把 API 验证当成视觉验收。

## 关键边界
- 远程 VoCat 当前关闭；本地演示只读缓存，不发送真实短信。
- IMEI 型号查询当前为本地示例 TAC 映射；未命中明确显示“数据源未收录”，没有伪造型号。
- 不把设备 ID 当 IMEI；`network_imei` 只能作为当前上游上报字段，不能直接断言出厂硬件 IMEI。
- 不把配置档案数当已识别号码数；EC20 本身就是号池。
- 不读写或回显 `C:\Users\27792\Desktop\vocatadmin.txt` 的凭据。

## 继续任务建议
1. 先检查 8768 监听 PID 是否仍属于副本服务；若不是，只停对应进程后重启。
2. 用真实浏览器验收 `#/` 离线登录 → `#/overview` → `#/imei` → 导入 → 筛选/详情/导出 → `#/run`。
3. 如发现视觉/交互问题，先备份当前 v0.4 文件到新的 `.local/rollback-*`，再按薄切片改动；每片都重跑 71 个 Python、Node UI 和 JS syntax checks。
4. 继续补 IMEI API 测试：分组创建、导入上限、删除、冲突关联、刷新持久化。
5. 可考虑把本地 TAC 映射移到单独 JSON 数据集，并增加“数据源更新时间/来源”显示；不要在无授权时调用第三方 API 发送完整 IMEI。
6. 最终交付要明确区分：已验证完成、部分完成、建议未执行、浏览器验收阻塞。
