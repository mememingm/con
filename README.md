# MQ 清单本地整理与报告工具

当前已实现：T-01—T-68结构化目录、两批既有describe证据核验、规定格式的Markdown/JSON报告和SHA-256清单。

当前交付为**部分完成**：本地工作已完成；68项远端验收仍未测。没有连接Broker，也没有发送新的command或ACK。原有 `probe/describe_once.py` 是有限诊断探针，不是完整测试台；此次没有改写其原始证据或源任务文档。

数据怎么走：

```text
上司清单（只读） + 逐项前提
               ↓
       68项用例目录
               ↓
既有原始日志 → 自洽核验 → 独立历史证据附件
               ↓
       14行矩阵 + 68行明细
```

## 已生成交付

- [正式报告](../tasks/records/mqtt-console/offline-review-20260921/report.md)：严格保留两张主表；本批次0通过、0失败、68未测，逐项注明原因。
- [证据复核附件](../tasks/records/mqtt-console/offline-review-20260921/evidence-review.md)：两批真实ID、双时钟时间、回包行号、ACK限制与后续输入。
- [用例与前提](docs/case-mapping.md) / [机器可读目录](cases/catalog.json)。
- [协议判据边界](docs/protocol-baseline.md)。

## 本地复现

在PowerShell中进入 `D:\esim\mqtt-test-console`。使用现有Python 3.12环境；报告工具仅使用标准库，不需要MQTT账号或新安装依赖。

先运行工具测试，成功时应显示13项通过。这些是本地工具测试，不计入真实MQ验收：

```powershell
& '.\.venv\Scripts\python.exe' -m unittest discover -s tests -v
```

重新提取目录时，下列命令读取上司源文件，将判据与 `cases/requirements.tsv` 的前提/执行设计合并，生成JSON和说明。源清单改变后必须重新人工核对元数据；不允许仅凭重新生成就认可新判据。

```powershell
& '.\.venv\Scripts\python.exe' reporting.py catalog
```

导出报告时必须使用**新目录**，防止覆盖前一次交付。下面会复核两批原始日志；成功时输出0通过、0失败、68未测及2批历史证据：

```powershell
& '.\.venv\Scripts\python.exe' reporting.py export `
  --batch-id offline-review-rerun `
  --output '..\tasks\records\mqtt-console\offline-review-rerun' `
  --evidence '.\evidence\20260921-103246-afdf0c9d' `
  --evidence '.\evidence\20260921-103558-a2a9aaf5'
```

输出包括 `report.md`、`report.json`、`evidence-review.md`、逐批 `audit-*.json` 和 `manifest.json`。manifest包含输入/输出哈希；原始回包仍引用原来的trace.jsonl，不改写。JSON附件含完整环境标识，只用于本地核验，外发前另做脱敏副本。

## 工具限制

- `export` 是离线复核命令，不接收“通过结果文件”，不根据 `succeeded` 或 `capabilities` 自动给T项打勾。
- 渲染层针对经过人工判据审阅的记录有格式/批次/环境检查及本地测试。它不是原始证据认证接口，不能把任意JSON标为live后当真实成绩导入。接入未来执行器前，需实现原文定位、关联任务/事件和全部子场景核验。
- 失败但无节点错误码时，T明细可记录失败与证据缺口，矩阵保守留空。`TIMEOUT` 等工具诊断不能伪装成节点回包错误码。
- T-27的 `sms.list`、T-55的未知action不在14行矩阵；只写T明细。事件、接收器、平台项不机械复制到所有action。
- 本地目录不是Git仓库；本次没有初始化仓库、创建提交或发布远端变更。全局记忆未修改。

## 对既有实施规划的进展

| 项 | 本次状态 |
|---|---|
| MC-01 用例登记 | 已完成68项目录、原文定位、判据、候选action、前提、范围和执行设计 |
| MC-02 协议与证据基线 | 部分完成：本次离线报告口径和重要差异已登记；五接口完整契约待实现 |
| MC-03—MC-10 页面、持久接收器与真实执行 | 未完成；原describe探针不能替代这些功能 |
| MC-11 报告导出 | 部分完成：离线两张主表、JSON、哈希和历史审计已完成；远端判定导入和结果页面截图未实现 |
| MC-12 交付与复现 | 本地报告流程已验证；完整测试台与远端验收未完成 |

后续最小只读批次及专项输入见证据附件。不要直接运行全部68项；短信、卡片变更、公共配置改动与故障注入需对应范围的资源和授权。
