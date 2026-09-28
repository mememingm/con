# 68 项用例、前提与执行设计

这是用例目录，不是测试成绩。原文判据逐字提取，候选 action 不能自动变成覆盖结果。

源文件 SHA-256：`f963fde99e9f9d3eea58b2fac3c4f6a2bc2a80df2ec7e303bef6c00ebb8bd685`

接收器、事件和平台用例没有一一对应的 action，不强行塞进矩阵。T-27 与 T-55 的未知 action 只进入明细。

| 编号 | 测试内容与原文位置 | 候选 action / 类别 | 对象 / 阶段 | 前提 | 执行动作 | 通过判据（源原文） |
|---|---|---|---|---|---|---|
| T-01 | 同 ID + 完全相同内容重投一个已完成的只读任务（第 44 行，2.1 幂等与重试） | node.describe / 边界条件 | 节点幂等 / 首版只读 | 本工具已完成的只读任务及发布原文；执行计数或节点日志可取得 | 逐字节重投原请求，对比原始 seq、内容及执行计数 | 回放已有任务状态，`seq` 不递增，不重新执行 |
| T-02 | 同 ID + **只改 `expires_at`**，其余不变（第 45 行，2.1 幂等与重试） | node.describe / 拒绝路径 | 节点幂等 / 首版只读 | 本工具已有任务；订阅 task/event；保留原请求和告警原文 | 仅修改 expires_at；关联 alarm.raised 的 details.command 与 IDEMPOTENCY_CONFLICT，并确认原任务未覆盖 | 返回 `IDEMPOTENCY_CONFLICT`，不覆盖原任务 |
| T-03 | 同 ID + 改 `params` 内容（第 46 行，2.1 幂等与重试） | node.describe / 拒绝路径 | 节点幂等 / 首版只读 | 本工具已有任务；固定其余信封字段；订阅 task/event | 只修改 params，关联 IDEMPOTENCY_CONFLICT 告警与原任务回放 | 返回 `IDEMPOTENCY_CONFLICT` |
| T-04 | `task.get` 查询一个历史任务（第 47 行，2.1 幂等与重试） | task.get / 成功路径 | 节点持久状态 / 首版只读 | 本工具原任务 ID、原始状态及无重复执行的观测依据 | 新 UUID 查询 params.id 指向原任务，比较最新持久状态与执行记录 | `task.get` 自身用**新**任务 ID，`params.id` 指原任务；返回原任务最新持久状态，不重复其操作 |
| T-05 | 查询一个不存在的任务 ID（第 48 行，2.1 幂等与重试） | task.get / 拒绝路径 | 节点任务查询 / 首版只读 | 新生成且确认未投递过的任务 ID | 用新外层 UUID 查询不存在的 params.id | `TASK_NOT_FOUND` |
| T-06 | 有副作用的任务超时后**不换 ID**（第 49 行，2.1 幂等与重试） | sms.send, esim.profile.download, task.get / 边界条件 | 副作用重试 / 后续专项 | 已授权副作用任务及可控超时；保留完整原请求；隔离测试窗口 | 超时后新外层 task.get 查原任务，再按原文重投并核对无重复副作用 | 确认正确做法是 `task.get` 查原任务；记录节点对同 ID 重投的回放行为。**不要换新 ID 重发写卡或短信** |
| T-07 | ACK 去重键（第 57 行，2.2 业务 ACK 与补传） |  / 边界条件 | 业务接收器与节点 ACK / ACK专项 | 业务 ACK 开启；仅本工具消息；持久接收器和去重库；无其他消费者提前确认 | 重收同键同内容消息，对比数据库写入次数与再次 ACK | 按 **node + kind + id + seq** 去重；相同键相同内容重复消息再次确认、不重复处理 |
| T-08 | **event 的 ACK 不带 seq**（第 58 行，2.2 业务 ACK 与补传） |  / 拒绝路径 | event ACK / ACK专项 | 本工具测试事件；隔离 ACK 窗口；节点拒绝观测日志 | 分别提交不含 seq 与含 seq=0 的事件 ACK，核对节点接纳和拒绝 | 带 `seq`（包括 `seq=0`）会被节点按协议拒绝。验收脚本踩过这个坑〔timeline §52〕 |
| T-09 | task 逐 seq 确认（第 59 行，2.2 业务 ACK 与补传） |  / 边界条件 | task ACK 逐序号 / ACK专项 | 本工具生成至少 3 个 seq；ACK 开启；接收器可选择暂不确认 | 只确认 seq=3，观察 1、2 仍原样补传 | 确认 seq=3 不代表确认 1、2；只确认 3 时节点应继续补传 1、2 |
| T-10 | 先落库后 ACK（第 60 行，2.2 业务 ACK 与补传） |  / 边界条件 | 业务事务与补传 / ACK专项 | 持久接收器；可断开自己的接收连接；ACK 开启且消息归属可查 | 保存原文，断开后重连，对比未确认消息全部字段及事务提交时序 | 断开接收端再重连，未 ACK 的消息原样补传，`id`/`seq`/`time`/内容全部不变 |
| T-11 | ACK 丢失后的重复消息（第 61 行，2.2 业务 ACK 与补传） |  / 边界条件 | ACK 丢失恢复 / ACK专项 | 仅本工具消息；可选择抑制自己的 ACK；节点对应 outbox 可观测 | 落库后丢弃一次 ACK，重收再 ACK，核对无重复业务及对应项清零 | 接收端已落库但 ACK 丢失 → 重复收到时再确认一次即可；节点 outbox 对应项清零 |
| T-12 | 迟到的旧 seq（第 62 行，2.2 业务 ACK 与补传） |  / 边界条件 | 业务接收器 / ACK专项 | 本工具可重放旧 seq；数据库有较新持久状态 | 投递旧 seq，核对保存、ACK 和最新状态没有倒退 | 可以保存并确认，但**不能覆盖较新状态** |
| T-13 | 相同键但内容不同（第 63 行，2.2 业务 ACK 与补传） |  / 拒绝路径 | 业务接收器 / ACK专项 | 隔离测试输入；同键不同内容的真实关联测试消息 | 注入冲突，核对隔离记录、原状态和未发送成功 ACK | 隔离冲突，不覆盖原记录，不发成功 ACK |
| T-14 | 批量上限（第 64 行，2.2 业务 ACK 与补传） |  / 边界条件 | ACK 批量与无需 ACK 消息 / ACK专项 | 自己的 task/event；可覆盖 1、100、101 项；presence/heartbeat 观测 | 验证 1–100 项处理与超限拒绝；检查 presence/heartbeat/ACK 无业务确认 | 一次 ACK 包含 1–100 项；`presence`、`heartbeat` 和 ACK 本身不需要业务确认 |
| T-15 | 接收端进程重启（第 65 行，2.2 业务 ACK 与补传） |  / 边界条件 | 接收器重启恢复 / ACK专项 | 持久接收器与本工具未确认消息；只重启自己的接收器 | 重启接收器后比较补收、ACK、数据库去重结果 | 重启后继续补收并确认，不产生重复业务记录 |
| T-16 | 缺 `expires_at`（第 73 行，2.3 `expires_at` 的三个检查点） | node.describe, task.get / 拒绝路径 | 信封期限校验 / 首版只读 | 已确认目标环境；登记负向请求；包含两个只读 action | 分别省略 expires_at 发起查询并保存拒绝回包 | 被拒绝（含只读 action） |
| T-17 | `expires_at` 早于或等于 `time`（第 74 行，2.3 `expires_at` 的三个检查点） | node.describe / 拒绝路径 | 信封期限校验 / 首版只读 | 登记早于和等于 time 的两个只读请求 | 分别发送 expires_at 小于及等于 time 的请求 | 被拒绝 |
| T-18 | 发送时已过期（第 75 行，2.3 `expires_at` 的三个检查点） | node.describe / 拒绝路径 | 入口过期 / 首版只读 | 时钟偏差已核实；过期时间仍晚于命令 time；能证明未执行 | 发送已过期请求，核对拒绝或 expired 及执行日志 | 被拒绝 / 回 `expired`，**不执行** |
| T-19 | 收到时未过期、排队到执行前才过期（第 76 行，2.3 `expires_at` 的三个检查点） | phones.list / 边界条件 | 出队过期 / 隔离故障专项 | 隔离节点硬件查询与可控队列；记录入队及出队时刻；故障范围授权 | 制造入队时有效、访问硬件前过期，核对 COMMAND_EXPIRED 及未执行；不使用不占卡通道的 describe 冒充排队 | 出队时二次检查，回 `expired` / `COMMAND_EXPIRED`，**不执行** |
| T-20 | 已经开始执行的任务超过期限（第 77 行，2.3 `expires_at` 的三个检查点） | phones.list / 边界条件 | 执行中超期 / 隔离故障专项 | 隔离节点可控慢硬件查询；开始执行时仍有效；观测时间线 | 让已经开始的硬件查询跨过期限，观察没有被强制中断 | **不被强制中断**，也不直接判失败 |
| T-21 | 重复收到已执行完的任务（第 78 行，2.3 `expires_at` 的三个检查点） | node.describe / 边界条件 | 已完成任务重投 / 首版只读 | 本工具完整已完成请求；等待其原 expires_at 过去 | 原文重投，比较旧终态不被改写为 expired | 返回原任务状态，**不能改写成 expired** |
| T-22 | `sms.send` 的 `succeeded` 含义（第 84 行，2.4 短信语义与端到端收发） | sms.send / 成功路径 | 短信通道提交 / 短信专项 | 授权号码、对端、条数和费用；现场合法 target；持久接收器 | 发送唯一测试文本，核对 succeeded 和 result=null，仅记录提交受理 | 只代表发送通道受理 IMS 提交，**不代表对方收到**。`result` 固定为 null |
| T-23 | 送达确认（第 85 行，2.4 短信语义与端到端收发） | sms.send / 边界条件 | 短信送达事件 / 短信专项 | 本工具发送任务及可取得的真实 delivery 事件 | 关联新事件 ID、data.command 与实际 delivery_state | `sms.delivery` 是独立事件、新事件 ID，`data.command` 填原发送任务 ID，`data.delivery_state` 填实际送达状态 |
| T-24 | `sms.received` 的归属（第 86 行，2.4 短信语义与端到端收发） |  / 边界条件 | 短信接收归属 / 短信专项 | 本工具测试短信；接收隧道 ICCID 映射；必要时隔离卡状态 | 核对接收隧道归属和 phone 未知时为 null | 归属用**接收隧道的 ICCID**，不是卡片此刻启用的号码；`phone` 未知时为 null |
| T-25 | 双向实收（第 87 行，2.4 短信语义与端到端收发） | sms.send / 成功路径 | 双向真实收发 / 短信专项 | 两端可配合且有授权；唯一正文；两侧原始收件证据 | 双向各发一条，逐条匹配正文、ICCID 与双端时间 | 用**唯一正文串**发双向各一条，逐条核对事件里的 ICCID 和正文。不能只看 `registered` / `sms_ready` 就签收 |
| T-26 | 补传去重（第 88 行，2.4 短信语义与端到端收发） |  / 边界条件 | 短信事件补传 / 短信与ACK专项 | 本工具接收事件；ACK 开启；可控重复投递 | 比较事件 ID、原时间及内容，验证按键而非正文去重 | 补传复用原事件 ID、原内容和原始接收时间；**不能仅凭相同文本去重** |
| T-27 | `sms.list` 不存在（第 89 行，2.4 短信语义与端到端收发） | sms.list / 拒绝路径 | 不支持的历史短信接口 / 首版只读 | 确认目标及负向 action；只发无硬件副作用请求 | 发送 sms.list，核对 UNSUPPORTED_ACTION | 发 `sms.list` 应返回 `UNSUPPORTED_ACTION`；收码只能靠 `sms.received` 事件，没有历史拉取接口 |
| T-28 | 空槽首次写卡建组（第 104 行，3.1 写卡后自动开线（**未验项里价值最高**）） | esim.profile.download / 成功路径 | 首次写卡自动开线 / 写卡专项 | 可支配空 eUICC；slot.refresh 现场确认；激活码额度和写卡授权 | 首次写入，核对 written、sms_ready、tunnel_state，全程不调用 ensure | `succeeded` + `written=true` + `sms_ready=true` + `tunnel_state=registered`，全程不调用 `tunnel.ensure` |
| T-29 | **同卡第二个 Profile 增量开线**（第 105 行，3.1 写卡后自动开线（**未验项里价值最高**）） | esim.profile.download / 边界条件 | 第二 Profile 增量开线 / 写卡与短信专项 | 同卡已有在线 Profile；第二激活码；旧线实收配合；授权窗口 | 下载第二 Profile，记录旧线路身份与连续性，写入期间旧号实收 | 新线加入运行组、**原有线路不重建且不掉线**（写入期间对旧号发一条码验证）。这是本轮最重要的一项 |
| T-30 | `failed / TUNNEL_START_FAILED / known_failed`（第 106 行，3.1 写卡后自动开线（**未验项里价值最高**）） | esim.profile.download / 边界条件 | 已写卡但开线失败 / 隔离写卡故障专项 | 隔离测试 eUICC；授权可控开线失败；后台重试日志 | 制造明确开线失败，核对及时返回、written=true、ICCID、tunnel_error 和独立重试 | 卡已写入、线路明确失败时**及时返回**，不等满 10 分钟期限；回包保留 `written=true`、ICCID、`tunnel_error`；后台重试独立继续 |
| T-31 | **业务端处理顺序**（第 107 行，3.1 写卡后自动开线（**未验项里价值最高**）） | esim.profile.download / 边界条件 | 业务端写卡决策 / 平台专项 | 真实 failed 且 written=true 的本轮任务；业务端日志与下发账本 | 核对业务端先看 written，不因 failed 自动重新下载 | **`failed` 不等于没写卡 —— 必须先看 `result.written` 再看 `state`。** 验证业务端不会因 `failed` 就重下 |
| T-32 | `uncertain` 两类（第 108 行，3.1 写卡后自动开线（**未验项里价值最高**）） | esim.profile.download / 边界条件 | 两种 uncertain 与恢复 / 隔离写卡故障专项 | 可控配置接纳失败及超时未就绪；卡片与配置前后快照 | 分别验证两类错误的配置回滚或保存、Profile 保留和禁止自动重下 | `AUTO_TUNNEL_START_FAILED`（配置/接纳失败，配置回滚、Profile 保留）与 `TUNNEL_NOT_READY`（配置已存、期限内未确认就绪）。两者都**不可自动重下** |
| T-33 | 下载拒绝分类（第 109 行，3.1 写卡后自动开线（**未验项里价值最高**）） | esim.profile.download / 拒绝路径 | 下载错误分类 / 写卡拒绝专项 | 专用测试资源；可分别复现各上游拒绝；原始上游回包 | 逐项对照六类错误映射；只有 Refused 时不得推断激活码已使用 | `ACTIVATION_CODE_REFUSED`、`EUICC_INSUFFICIENT_MEMORY`、`EUICC_CI_INCOMPATIBLE`、`PROFILE_POOL_EMPTY`、`EUICC_AUTHENTICATION_FAILED`，兜底 `DOWNLOAD_FAILED`。上游只回 `Refused` 时不得断言激活码已被使用 |
| T-34 | `profile_state` 的含义（第 110 行，3.1 写卡后自动开线（**未验项里价值最高**）） | esim.profile.download / 边界条件 | Profile 状态与线路状态 / 写卡专项 | 已授权写卡；下载回读和多隧道状态可独立观测 | 分别核对 profile_state 与 sms_ready/tunnel_state 的业务含义 | 表示下载回读时的 Profile 状态，**不表示当前多隧道在线情况**；业务可用性看 `sms_ready` / `tunnel_state` |
| T-35 | 重投同一下载任务（第 111 行，3.1 写卡后自动开线（**未验项里价值最高**）） | esim.profile.download / 边界条件 | 下载幂等 / 写卡专项 | 本工具已授权下载原文；卡片与额度前后证据 | 同 ID 原文重投，验证回放且未再次写入或消费额度 | 保持原 ID 和内容，回放已有结果，**不会再次写卡**，不消耗第二个激活码 |
| T-36 | `tunnel.ensure` 补开旧号（第 112 行，3.1 写卡后自动开线（**未验项里价值最高**）） | tunnel.ensure / 成功路径 | 补开与增量开线 / 隧道专项 | 卡上目标 ICCID；首次、增量、已就绪及单线转组场景；授权 | 分场景 ensure；已就绪 changed=false；原在线线路保持连续 | 对卡上已存在的 ICCID 首次建组或增量加入；已就绪的号码返回 `changed=false`（幂等）；从单线转组时原在线号码不掉 |
| T-37 | 省略参数的默认行为（第 120 行，3.2 `phones.list` 默认返回空卡行） | phones.list / 成功路径 | 默认空卡行 / 首版只读 | 当前存在 slot.refresh 确认的干净空槽；完整分页 | 省略 include_empty_slots，核对空卡字段及真实 IMEI | 返回空卡行：`slot` 为真实 IMEI、`iccid=""`、`phone=null`、`available=false`、`reason="空卡，无 Profile"` |
| T-38 | **业务端对空卡行的处理**（第 121 行，3.2 `phones.list` 默认返回空卡行） | phones.list / 边界条件 | PingCode 入库 / 平台专项 | 本轮含空卡行清单；平台访问和入库、拒绝日志 | 检查整批拒收、单行拒收或入库，并记录明确实际行为 | 记录业务端是否拒收整批、拒单行还是入库。这是当前已知的平台侧不兼容点，要拿到明确结论 |
| T-39 | 显式 `include_empty_slots=false`（第 122 行，3.2 `phones.list` 默认返回空卡行） | phones.list / 成功路径 | 过滤空卡 / 首版只读 | 现场存在空卡对照；使用新查询快照完整分页 | 显式 include_empty_slots=false，核对仅有真实 Profile | 过滤空卡，只返回真实 Profile 行 |
| T-40 | 分页中途切换该选项（第 123 行，3.2 `phones.list` 默认返回空卡行） | phones.list / 拒绝路径 | 分页选项一致性 / 首版只读 | 至少两页；保存第一页 cursor 和选项 | 后续页切换 include_empty_slots，核对拒绝 | 应被拒绝；同一分页必须保持选项一致 |
| T-41 | 「空卡」与「未检测到 SIM 卡」的区别（第 124 行，3.2 `phones.list` 默认返回空卡行） | phones.list / 边界条件 | 空卡、缺卡与读卡失败 / 隔离硬件专项 | 三种可区分状态的隔离槽位；不在公共机带电插拔 | 分别采集零 Profile、SIM not inserted、其他读卡失败 | 读到 0 个 Profile = 空卡；模块明确报 SIM not inserted = 保留 IMEI、空 ICCID、`reason="未检测到 SIM 卡"`。**两者不能混为一谈，其他读卡错误也不得伪装成空卡** |
| T-42 | `available=true` 的门槛（第 125 行，3.2 `phones.list` 默认返回空卡行） | phones.list, phones.check / 边界条件 | 号码可用性四条件 / 隔离线路专项 | 绑定、注册、通信、发送通道四项可观测；可控不满足场景 | 分别破坏或恢复单一条件，核对 available、reason 和 tunnel_state | 绑定有效 + 隧道已注册 + 通信连接有效 + 发送通道能受理短信，四者全满足才为 true；否则 false 并在 `reason` 说明，`tunnel_state` 保留具体状态。**仅有进程存活或注册标志不算** |
| T-43 | 游标过期（第 131 行，3.3 分页、快照与对账） | phones.list, inventory.get / 拒绝路径 | 游标过期和重新采集 / 首版只读与平台 | 分页快照；等待超过5分钟或获准制造快照淘汰；业务端对账日志 | 提交过期 cursor，核对 CURSOR_EXPIRED 及整份丢弃重采 | 超过 5 分钟或超过 32 份快照上限被淘汰 → `CURSOR_EXPIRED`；业务端必须**整份丢弃重新从第一页采**，不能拿半份清单去删卡片 |
| T-44 | `complete=true` 才对账（第 132 行，3.3 分页、快照与对账） | phones.list, inventory.get / 边界条件 | 业务端完整性对账 / 平台专项 | 未收齐与完整快照；可读业务端资源变更账本 | 比较 complete=false/true 时的对账动作，确认未收齐不删资源 | 未收齐全部页不得据此删除资源；单页缺失不算卡片消失 |
| T-45 | 两个清单的一致性（第 133 行，3.3 分页、快照与对账） | inventory.get, phones.list / 成功路径 | 两个清单一致性 / 首版只读 | 同环境近同时完整快照；统一设备范围；时间差已记录 | 比较库存 IMEI 与号码 target.slot 的全量去重集合 | `inventory.get` 的 IMEI 集合 == `phones.list` 去重后的 `target.slot` 集合，missing/extra 均为空（09-17 实测两边均为 20，可作基线） |
| T-46 | **计数陷阱**（第 134 行，3.3 分页、快照与对账） | phones.list / 边界条件 | 跨页计数 / 首版只读与平台 | page_size=10 且有跨页重复槽位；完整同一快照 | 输出每页去重和、全量去重数及差集；平台计数另核对 | 用 `page_size=10` 分页，核对「各页各自去重数相加」与「全量去重数」的差异。历史上前者得 21、后者 19，PingCode 页面「21 卡槽」疑似由此而来，**至今未闭环** |
| T-47 | 每次新查询重新现场采集（第 135 行，3.3 分页、快照与对账） | phones.list, phones.check, slot.refresh, esim.profiles.list / 边界条件 | 现场采集和失败处理 / 只读与隔离故障 | 新 UUID 无 cursor；可观测硬件读取；mode 负向及可控读失败 | 验证新采集、source=hardware、拒绝 mode、读失败不用旧值 | 不带 cursor 的新任务必须重新读硬件，`source` 固定 `hardware`，不接受 `mode` 参数；读取失败明确返回失败，不用旧值填充 |
| T-48 | `inventory.get` 的已知差异（第 136 行，3.3 分页、快照与对账） | inventory.get / 成功路径 | 已知库存实现差异 / 首版只读 | 当前库存请求及部署版本可追溯 | 核对 source=registry、profiles_complete=false、状态 unknown，并登记差异 | 当前仍为 `source=registry`、`profiles_complete=false`、Profile 状态 unknown；完整硬件 Profile 要另查 `esim.profiles.list` / `slot.refresh`。**这是实现差异，不要当成 bug 报**〔23 §4〕 |
| T-49 | 服务刚启动、IMEI 尚未解析时查询（第 142 行，3.4 拒绝路径（比成功路径更少被测，优先补）） | phones.list / 拒绝路径 | 身份待确认 / 隔离启动专项 | 隔离节点启动窗口；IMEI 未解析；授权服务操作 | 在身份未确认窗口查询并核对 IDENTITY_PENDING | `IDENTITY_PENDING`。09-17 补过一次「自动建组模块 IMEI 快照为空」的补丁，值得回归〔timeline §54.9〕 |
| T-50 | 给一个不存在的手机号（第 143 行，3.4 拒绝路径（比成功路径更少被测，优先补）） | phones.check / 拒绝路径 | 手机号寻址 / 首版只读 | 完整号码清单；确认不存在的测试号码；禁止发送短信 | 用不存在的 phone 执行只读检查，核对 PHONE_NOT_FOUND | `PHONE_NOT_FOUND` |
| T-51 | 给一个对应多个 Profile 的手机号（第 144 行，3.4 拒绝路径（比成功路径更少被测，优先补）） | phones.check / 拒绝路径 | 手机号歧义 / 隔离数据专项 | 受控且真实对应多个 Profile 的 phone；来源清单 | 查询歧义号码并核对 PHONE_AMBIGUOUS | `PHONE_AMBIGUOUS` |
| T-52 | `phone` 与 `iccid` 给成不匹配的一对（第 145 行，3.4 拒绝路径（比成功路径更少被测，优先补）） | phones.check / 拒绝路径 | 目标不匹配 / 首版只读 | 现场查出的两个不匹配 phone/ICCID；其余 target 合法 | 只读检查提交不匹配配对，核对 TARGET_MISMATCH | `TARGET_MISMATCH` |
| T-53 | 查一个换卡后已迁走的 ICCID（第 146 行，3.4 拒绝路径（比成功路径更少被测，优先补）） | phones.check, esim.profiles.list / 边界条件 | 换卡后寻址 / 隔离换卡专项 | 授权隔离换卡；旧、新 IMEI 和 ICCID 原始映射 | 新槽查询迁移 ICCID，同时核对旧槽拒绝旧配置 | 换卡后应能在新 IMEI 下正确找到；旧槽位不得凭旧配置接受该 ICCID。历史上出过 `PROFILE_NOT_FOUND`，已修〔timeline §54.6/§54.7〕 |
| T-54 | 同一张卡上并发下两个任务（第 147 行，3.4 拒绝路径（比成功路径更少被测，优先补）） | esim.profile.download, esim.profile.delete, esim.profile.enable / 拒绝路径 | 同卡操作锁 / 隔离并发专项 | 隔离 eUICC；并发写入、删除、切换、鉴权范围授权 | 在同卡操作重叠窗口提交另一个任务，核对 SLOT_BUSY 和无额外副作用 | `SLOT_BUSY`（同卡共用一把操作锁，写入、删除、切换、鉴权互斥） |
| T-55 | 发一个不存在的 action（第 148 行，3.4 拒绝路径（比成功路径更少被测，优先补）） | __unknown_action__ / 拒绝路径 | 不支持的 action / 首版只读 | 预定义不存在的 action；完整合法信封 | 提交未知 action，核对 UNSUPPORTED_ACTION | `UNSUPPORTED_ACTION` |
| T-56 | 参数类型/格式错误（第 149 行，3.4 拒绝路径（比成功路径更少被测，优先补）） | node.describe, task.get, phones.list, phones.check / 拒绝路径 | 参数格式校验 / 首版只读 | 每种 action 登记类型和格式负向输入；固定无副作用范围 | 按类型与格式样本执行，核对 INVALID_ARGUMENT | `INVALID_ARGUMENT` |
| T-57 | 每个错误的 `certainty` 字段（第 150 行，3.4 拒绝路径（比成功路径更少被测，优先补）） |  / 边界条件 | 跨接口错误 certainty / 跨专项 | 本轮各错误真实回包；明确动作是否开始和实际结果 | 逐类核对 certainty 存在且语义正确，不能仅检查枚举 | 必有且取值正确：`not_started` / `known_failed` / `unknown` |
| T-58 | `esim.profile.enable` 对已启用的同一 Profile（第 151 行，3.4 拒绝路径（比成功路径更少被测，优先补）） | esim.profile.enable / 边界条件 | 启用幂等 / 写卡专项 | 现场确认已启用的 Profile；启用动作授权 | 再次启用同一 Profile，核对幂等成功和卡状态 | 幂等成功 |
| T-59 | `esim.profile.delete` 对在线/在用的 Profile（第 152 行，3.4 拒绝路径（比成功路径更少被测，优先补）） | esim.profile.delete / 拒绝路径 | 在用 Profile 删除保护 / 隔离删卡专项 | 隔离机在线 Profile；已核实保护条件及删除风险授权 | 提交删除，核对 PROFILE_IN_USE 和 Profile 仍存在 | 拒绝 `PROFILE_IN_USE`。**不能把这个拒绝当成删除成功** |
| T-60 | **24 小时 IKE rekey 窗口**（第 162 行，4. P2 · 长周期与稳定性） | phones.check, sms.send / 边界条件 | 24小时 rekey / 长周期短信专项 | 授权短信条数和持续观测；实际注册锚点；跨23–24小时窗口 | 持续查询及真实收码，记录可用性抖动和 uncertain 时间线 | 线路 `ready_for≈23h` 时 ePDG 要求 rekey，VoCat 不支持，**所有线同时拆掉重建，至今未处置**。在窗口内持续 `phones.check` + 真实收码，记录 `available` 抖动时长、有无任务掉进 `uncertain`〔00 §6，DEVICE-REPORT §41.4〕 |
| T-61 | **8 小时 401 重挑战**（第 163 行，4. P2 · 长周期与稳定性） | phones.check, sms.send / 边界条件 | 8小时401重挑战 / 长周期短信专项 | 各线完整注册时刻；观测覆盖分散锚点；短信授权 | 跨各线8小时窗口统计收码成功率与 tunnel_state | 锚点是各线自己上次完整注册时刻，单线停 8.6–9.4 s（偶有 24–54 s），16–20 条线锚点分散约 13 分钟。测这期间的收码成功率和 `tunnel_state` 变化〔00 §6〕 |
| T-62 | 节点重启后的一致性（第 164 行，4. P2 · 长周期与稳定性） |  / 边界条件 | 节点重启恢复 / 隔离重启专项 | 隔离节点；明确重启授权；未确认和未过期自有任务 | 记录身份验证、hello、补传、库存校准和任务恢复顺序 | 重连顺序：验证身份 → `node.hello`（含 `node_type`、`software_version`、`capabilities`、积压、设备绑定）→ 补传 → 校准库存 → 恢复未过期任务。**不能重启后直接报全部在线** |
| T-63 | seq 不倒退（第 165 行，4. P2 · 长周期与稳定性） |  / 边界条件 | 云端seq不倒退 / ACK与平台专项 | 本轮先到 seq=3 后到 seq=2；云端状态库及 ACK 记录 | 核对旧消息存档确认且最新状态不倒退 | 云端已收到 seq=3 后再收到 seq=2，不倒退状态，但仍要确认这条补传，避免节点反复重发 |
| T-64 | presence 与心跳新鲜度（第 166 行，4. P2 · 长周期与稳定性） |  / 边界条件 | presence与心跳新鲜度 / 隔离连接专项 | presence/heartbeat 订阅；QoS/retain 元数据；可控90秒无心跳 | 保留 online 同时停止心跳，核对 stale 与健康判断 | `presence` 是 QoS 1 + retained，心跳 QoS 0 默认 30 秒；**90 秒无心跳标记 stale**。验证「retained online + 陈旧心跳」不被判为健康 |
| T-65 | 补传退避（第 167 行，4. P2 · 长周期与稳定性） |  / 边界条件 | 补传退避 / ACK专项 | 本工具未确认消息；ACK开启；可观测至少至300秒及重连窗口 | 记录补传间隔抖动、原文不变与重连唤醒 | 约 10/20/40/80/160/300 秒加抖动，重连唤醒积压，重发保持原 id/seq/时间/内容 |
| T-66 | 保留策略（第 168 行，4. P2 · 长周期与稳定性） | node.describe / 边界条件 | 旧任务保留回放 / 保留策略专项 | 归属明确的很旧只读任务及原请求；保留策略和版本历史 | 原文重投，核对旧回包保留；区分旧版已删除不可重建 | 拿一个很旧的任务 ID 重投，看是否还有回包。旧版存在「去重记录还在、最后回包已被删」→ 重投无回包的问题，已修；**已被旧版删掉的回包不会重建** |
| T-67 | `uncertain` 任务的清理（第 169 行，4. P2 · 长周期与稳定性） |  / 边界条件 | uncertain保留 / 保留策略专项 | 本轮真实 uncertain 自有任务；跨保留期或授权隔离时钟方案 | 核对未自动清理和未盲目重新执行，保留状态及操作账本 | 不自动清理，过保留期也不能盲目重新执行旧任务 |
| T-68 | 存储近满（第 170 行，4. P2 · 长周期与稳定性） |  / 拒绝路径 | 存储压力保护 / 隔离存储故障专项 | 专用测试机与磁盘配额；近满及满盘注入授权；未确认数据基线 | 分阶段近满与满盘，检查告警、停止副作用接收、STORAGE_FULL 和数据保留 | 近满盘应告警并停止接收新副作用任务，满盘时明确报 `STORAGE_FULL`，不静默淘汰未确认数据（可在测试机构造） |
