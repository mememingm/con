# 本次报告判据与实现边界

2026-09-21，本地文件核验。下列版本是文档及既有回包版本，不表示本次重新部署或查询。

| 依据 | SHA-256 / 原文位置 | 用途 |
|---|---|---|
| `C:/Users/27792/Desktop/wiki/24-MQ接口测试清单.md` | `f963fde99e9f9d3eea58b2fac3c4f6a2bc2a80df2ec7e303bef6c00ebb8bd685` | 68项原文判据、执行纪律、14行矩阵 |
| `C:/Users/27792/Desktop/cardpool-design-docs-main/docs/server-node-mqtt-v1.md` | `af5cdbb2a8bfadae86f8f6f3fa4657d162d68ab077a9a36332e513b5dae2e04a`；74、192、361、1982–1983行 | 期限差异、硬件通道、node_type、幂等冲突事件 |
| `D:/esim/tasks/templates/mqtt-test-report-template.md` | `a52bb0bc82d10139bd5764590c487510b43bd27715807308cdb7f71f76d35495` | 输出格式；不作为结果证据 |

1. 正常信封统一携带 `id/action/time/expires_at/params`。T-16采用清单要求“所有命令必须有expires_at”；开发文档允许describe/task.get省略，这是已登记口径差异，不能悄悄混用。
2. `inventory.get` 的 `source=registry/profiles_complete=false` 按T-48记录为已知实现差异。T-47的硬件新采集判据不覆盖这一例外。当前未执行这些查询。
3. `node_type` 开发文档为 `ec20_edge / mdd_cloud`；两批既有回包是 `vocat_ec20`。保留差异，不自定义错误码，不宣称完整schema验收通过。
4. 幂等冲突可能从 `event` 里的 `alarm.raised` 返回，`data.code=IDEMPOTENCY_CONFLICT`、`details.command=原任务ID`，同时回放原task。当前describe探针只订阅task，不能直接用它执行T-02/T-03后因未见task错误就判失败。后续事件证据必须保留原事件ID及原任务关联。
5. `node.describe/task.get` 不占卡片通道；T-19/T-20需要隔离的硬件查询排队/慢执行场景，不能把普通describe耗时当作硬件出队检查。
6. `No matching subscribers` 是Broker对ACK发布的MQTT提示，不是节点错误码。传输确认与业务确认分开；没有节点处理证据时，业务ACK状态是“未验证”。
7. 单个T项可能含多个子场景，如T-17的早于/等于、T-32两种uncertain、T-33错误分类、T-41三类卡状态。只完成一部分不能把整个T项标通过；该情况需另附子场景证据，完整T项仍待判定。
8. 事件/接收器专属项不能凭空生成任务ID。后续事件报告须有真实关联任务及事件原文，无法关联则保留证据缺口。当前离线导出器没有事件验收导入接口。

本次工具的边界是“用例登记、既有describe证据自洽复核、保守导出”。它不是完整68项执行器、通用协议验证器或持久业务接收器。
