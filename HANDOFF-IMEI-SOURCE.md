# IMEI 来源与 VoCat 关联交接文档

更新时间：2026-09-24（北京时间）

## 交接目标

说明当前号码测试台里的 IMEI 从哪里来、如何在 VoCat 找到、如何刷新本地缓存，以及下一会话需要注意的边界。

## 当前副本与运行状态

- 客户版副本：`D:\esim\mqtt-test-console-customer`
- 本地页面：`http://127.0.0.1:8768/#/run`
- 后端：`sms_console/server.py`
- 本地缓存：`D:\esim\mqtt-test-console-customer\.local\sms-console\numbers.json`
- 当前监听端口：8768；启动时确认 PID 的命令行包含客户版副本路径。
- 当前缓存最新结果：6 台设备、24 个号码、22 个就绪号码。
- 远程 VoCat 地址：`http://192.168.1.5:7575`

## IMEI 的真实来源

IMEI 不是本地生成的，也不是从电话号码、ICCID 或设备 ID 推导出来的。

读取链路：

```text
VoCat /api/devices
  └─ devices[].network_imei
       ↓ 优先使用
号码测试台 reader.numbers()
       ↓
本地 numbers.json 的 imei 字段
       ↓
总览、开始测试、号码列表、IMEI 识别页面
```

代码位置：

- [server.py:101](D:/esim/mqtt-test-console-customer/sms_console/server.py:101)：读取 VoCat 设备和多号码数据。
- [server.py:112](D:/esim/mqtt-test-console-customer/sms_console/server.py:112)：读取 `/devices/{id}/multisim`。
- [server.py:122](D:/esim/mqtt-test-console-customer/sms_console/server.py:122)：优先使用设备对象的 `network_imei`。
- [server.py:125](D:/esim/mqtt-test-console-customer/sms_console/server.py:125)：设备字段缺失时，从线路的 `state.network_imei` 回填。

## 在 VoCat 中查找设备 3

网页入口：

```text
http://192.168.1.5:7575/devices?device=3&tab=overview
```

人工查看步骤：

1. 打开 VoCat。
2. 选择设备 `3`。
3. 进入 `Overview / 概览`。
4. 在设备信息或网络信息区域找 `Network IMEI / 网络 IMEI`。

接口查看方式：

```text
GET http://192.168.1.5:7575/api/devices
```

在返回结果中找到：

```text
devices[].id == 3
devices[].network_imei
```

如果设备对象没有 IMEI，再查看：

```text
GET http://192.168.1.5:7575/api/devices/3/multisim
```

线路级备用字段是：

```text
state.lines[].state.network_imei
```

## 最近一次实时核对结果

通过最新凭据只读访问 VoCat 后确认：

- `/api/devices` 返回 6 台设备。
- 设备 3 的 `network_imei` 字段存在，长度为 15 位。
- `/api/devices/3/multisim` 返回 20 条线路。
- 设备 3 的线路对象包含 `state.network_imei` 字段。
- 最新结果已写入本地 `numbers.json`。
- 临时读取脚本已删除，凭据未写入项目、日志或文档。

## 重要概念边界

```text
设备 ID 3       ≠ IMEI
电话号码         ≠ IMEI
ICCID            ≠ IMEI
配置档案数量     ≠ 已识别号码数量
EC20             = 当前项目中的一个号池
```

当前程序把设备级 IMEI 复制到该设备的号码行上，方便号码列表和测试页面显示。它不代表每个号码都是一台独立设备。

如果未来发现同一设备的不同线路上报不同 `network_imei`，需要增加线路级 IMEI 展示和冲突提示，不能继续只取首个值。

## 刷新缓存

刷新时需要：

1. 使用 `C:\Users\27792\Desktop\vocatadmin.txt` 中的账号和密码登录 VoCat。
2. 只调用登录接口和 GET 读取接口。
3. 读取 `/api/devices`，再读取每台设备的 `/api/devices/{id}/multisim`。
4. 成功后整体替换 `numbers.json`，失败时保留旧缓存。
5. 不输出、提交或写入凭据、完整 IMEI、ICCID 或密码。

当前页面离线演示会读取本地缓存，因此 VoCat 临时关闭时仍能查看上一次成功读取的数据，但页面必须明确标记为离线缓存。

## 下一会话建议

- 先读取本文件和 `HANDOFF-V04.md`。
- 不要把设备 ID 当作 IMEI。
- 不要根据设备数量猜测实体 EC20 数量。
- 如要修改 IMEI 显示逻辑，先建立新的回退目录。
- 修改后至少运行：

```powershell
& D:\esim\mqtt-test-console\.venv\Scripts\python.exe -m unittest discover -s tests -q
node tests\test_sms_console_ui.cjs
node --check sms_console\static\app.js
```

