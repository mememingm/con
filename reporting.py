"""Offline checklist/evidence reporting. This module never connects to MQTT."""
import argparse
import csv
import hashlib
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID

ROOT = Path(__file__).resolve().parent
BEIJING = timezone(timedelta(hours=8))
DEFAULT_SOURCE = Path('C:/Users/27792/Desktop/wiki/24-MQ接口测试清单.md')
TERMINAL = {'succeeded', 'failed', 'rejected', 'expired', 'uncertain'}


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def parse_source(path):
    cases, actions = [], []
    section = ''
    for line_number, line in enumerate(path.read_text('utf-8-sig').splitlines(), 1):
        if line.startswith('#'):
            section = line.lstrip('# ').strip()
        if re.match(r'^\| T-\d{2}\s*\|', line):
            cells = [cell.strip() for cell in line.strip('|').split('|')]
            if len(cells) != 3:
                raise ValueError(f'Unexpected case table at line {line_number}')
            cases.append(dict(id=cells[0], title=cells[1], criterion=cells[2],
                              source_line=line_number, source_section=section))
        if section.startswith('6.') and line.startswith('| '):
            action = line.split('|')[1].strip()
            if action != 'action':
                actions.append(action)
    if [case['id'] for case in cases] != [f'T-{i:02}' for i in range(1, 69)]:
        raise ValueError('Source must contain exactly T-01 through T-68 in order')
    if len(actions) != 14 or len(set(actions)) != 14:
        raise ValueError('Source must contain exactly 14 ordered actions')
    return dict(source_path=str(path.resolve()), source_sha256=sha256(path),
                actions=actions, cases=cases)


def build_catalog(source, requirements):
    catalog = parse_source(source)
    with requirements.open(encoding='utf-8-sig', newline='') as handle:
        rows = list(csv.DictReader(handle, delimiter='\t'))
    if [row['id'] for row in rows] != [c['id'] for c in catalog['cases']]:
        raise ValueError('Requirements must match all 68 source cases in order')
    catalog['schema_version'] = 1
    catalog['mapping_policy'] = 'action 映射为候选执行设计；跨接口/接收器项不自动复制到全部 action；未知 action 仅进入 T 明细。'
    catalog['global_preconditions'] = [
        '真实环境、业务身份、节点和部署版本现场核实；凭据不入报告。',
        '每个新查询用新 UUID，重投必须保持原 ID 与原始字节。',
        '只 ACK 自己任务/测试事件；业务与去重同事务提交后再 ACK。',
        '真实结论需本批次任务 ID、北京时间、原始回包及全部判据证据。',
        '硬件目标来自现场清单；公共机不做删卡、停组、重启或故障注入。',
    ]
    for case, row in zip(catalog['cases'], rows):
        case.update({k: v for k, v in row.items() if k != 'actions'})
        case['actions'] = row['actions'].split(',') if row['actions'] else []
        if not all(row.values()):
            # Empty action mapping is deliberate for receiver/event-wide cases.
            if any(not value for key, value in row.items() if key != 'actions'):
                raise ValueError(f'Missing metadata for {case["id"]}')
        case['automation'] = '可辅助构造与核验，现场判据须逐项审阅'
        case['scope'] = ('只读查询（仍有节点负载及任务/outbox写入）；当前未新执行'
                         if row['phase'] == '首版只读'
                         else '需要所列场景、日志或专项授权；当前只登记不执行')
    return catalog


def load_catalog(path, source):
    catalog = json.loads(path.read_text('utf-8'))
    original = parse_source(source)
    if catalog['source_sha256'] != original['source_sha256']:
        raise ValueError('Checklist changed: rebuild and review the catalog first')
    if catalog['actions'] != original['actions']:
        raise ValueError('Matrix action order differs from source')
    if len(catalog['cases']) != 68:
        raise ValueError('Catalog must contain 68 cases')
    for case, expected in zip(catalog['cases'], original['cases']):
        if any(case[key] != expected[key] for key in expected):
            raise ValueError('Catalog source fields changed')
    return catalog


def bj_time(value):
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError('Observation timestamps must include timezone')
    return parsed.astimezone(BEIJING).strftime('%Y-%m-%d %H:%M:%S.%f')


def audit_probe(directory):
    """Audit legacy describe trace integrity, never promote it to a T verdict."""
    trace = directory / 'trace.jsonl'
    result_path = directory / 'result.json'
    records = [json.loads(line) for line in trace.read_text('utf-8-sig').splitlines() if line]
    result = json.loads(result_path.read_text('utf-8-sig'))
    issues, findings = [], []
    environments = [r for r in records if r['kind'] == 'environment']
    commands = [(i, r) for i, r in enumerate(records, 1) if r['kind'] == 'command_intent']
    if len(environments) != 1 or len(commands) != 1:
        raise ValueError('Describe probe must contain one environment and one command')
    env = environments[0]
    command_line, command_record = commands[0]
    command = command_record['payload']
    task_id = command['id']
    try:
        UUID(task_id)
    except (ValueError, TypeError):
        issues.append('Request ID is not a UUID')
    if command['action'] != 'node.describe':
        issues.append('Not a describe probe')
    if task_id != env['task_id'] or task_id != result['task_id']:
        issues.append('Environment/request/result IDs differ')
    base = f'cardpool/v1/nodes/{env["node"]}'
    if command_record['topic'] != base + '/command':
        issues.append('Command topic does not match environment')
    if command_record.get('qos') != 1 or command_record.get('retain') is not False:
        issues.append('Unexpected command QoS/retain')
    replies, seen = [], {}
    for line, record in enumerate(records, 1):
        if record['kind'] == 'ack_intent':
            for item in record['payload'].get('items', []):
                if item.get('kind') != 'task' or item.get('id') != task_id or item.get('seq') not in seen:
                    issues.append('ACK is not for an already recorded owned task sequence')
        if record['kind'] != 'task':
            continue
        reply = json.loads(record['raw'])
        seq = reply.get('seq')
        if record.get('retained') is not False or record['topic'] != base + '/task':
            issues.append('Unexpected reply topic/retain')
        if reply.get('id') != task_id or type(seq) is not int or seq < 1:
            issues.append('Unmatched reply or invalid sequence')
        if seq in seen and seen[seq] != record['raw']:
            issues.append('Same sequence has different raw content')
        seen[seq] = record['raw']
        replies.append(dict(line=line, beijing_time=bj_time(record['observed_at']),
                            node_time=reply.get('time'), payload=reply,
                            raw_sha256=hashlib.sha256(record['raw'].encode()).hexdigest()))
    terminal = [r for r in replies if r['payload'].get('state') in TERMINAL]
    latest = max(terminal, key=lambda r: r['payload'].get('seq', 0)) if terminal else None
    if latest is None or latest['payload'] != result.get('terminal'):
        issues.append('Summary terminal does not match raw trace')
    summaries = [r for r in records if r['kind'] == 'summary']
    if len(summaries) != 1 or any(summaries[0].get(k) != v for k, v in result.items()):
        issues.append('Trace summary differs from result.json')
    if not any(r['kind'] == 'connack' and r.get('reason') == 'Success' for r in records):
        issues.append('Missing successful CONNACK')
    if not any(r['kind'] == 'suback' and r.get('reasons') == ['Granted QoS 1'] for r in records):
        issues.append('Missing successful SUBACK')
    if not any(r['kind'] == 'puback' and r.get('purpose') == 'command' and r.get('reason') == 'Success' for r in records):
        issues.append('Missing successful command PUBACK')
    ack_pubs = [r for r in records if r['kind'] == 'puback' and r.get('purpose') == 'business_ack']
    no_subscribers = sum(r.get('reason') == 'No matching subscribers' for r in ack_pubs)
    if no_subscribers:
        findings.append('ACK_NO_MATCHING_SUBSCRIBERS')
    fields = (latest['payload'].get('result') or {}) if latest else {}
    if fields.get('node_type') not in {'ec20_edge', 'mdd_cloud'}:
        findings.append('NODE_TYPE_DIFFERENCE')
    findings.extend(['NOT_A_T_CASE_EXECUTION', 'NO_TRANSACTIONAL_RECEIVER_EVIDENCE',
                     'PHYSICAL_HOST_MAPPING_UNVERIFIED', 'CLOCK_SYNC_UNVERIFIED'])
    # Only selected non-secret environment fields leave the private trace.
    return dict(batch_id=directory.name, origin='historical', evidence_directory=str(directory.resolve()),
                environment={k: env[k] for k in ('broker', 'tls', 'mqtt_version', 'node', 'client_id')},
                task_id=task_id, action=command['action'], command_line=command_line,
                command_time=command['time'], receive_time=latest['beijing_time'] if latest else None,
                node_time=latest['node_time'] if latest else None,
                states=[r['payload'].get('state') for r in replies], replies=replies,
                terminal_fields=fields, ack_no_subscribers=no_subscribers,
                business_ack_verified=False, integrity_ok=not issues, integrity_issues=issues,
                finding_codes=findings, eligible_cases=[],
                files=[dict(path=str(p.resolve()), sha256=sha256(p), bytes=p.stat().st_size)
                       for p in (trace, result_path)])


def validate_verdict(value, batch_id, environment):
    """Structural guard for reviewed records; NOT a remote case adjudicator.

    Callers must resolve raw_ref against immutable raw evidence before calling.
    The offline CLI deliberately accepts no verdict file and grants no passes.
    """
    required = ('case_id', 'action', 'category', 'verdict', 'task_id', 'batch_id',
                'environment', 'origin', 'beijing_time', 'raw_ref', 'raw_reply', 'criterion_review')
    if any(not value.get(key) for key in required):
        raise ValueError('Tested verdict requires complete traceable evidence')
    if value['origin'] != 'live' or value['batch_id'] != batch_id or value['environment'] != environment:
        raise ValueError('Wrong origin, batch or environment')
    if value['verdict'] not in {'通过', '失败'} or value['category'] not in {'成功路径', '拒绝路径', '边界条件'}:
        raise ValueError('Invalid conclusion/category')
    if not re.fullmatch(r'T-(0[1-9]|[1-5][0-9]|6[0-8])', value['case_id']):
        raise ValueError('Invalid case ID')
    try:
        UUID(value['task_id'])
        datetime.strptime(value['beijing_time'], '%Y-%m-%d %H:%M:%S')
    except (ValueError, TypeError) as exc:
        raise ValueError('Invalid task ID or Beijing time') from exc
    if not isinstance(value['raw_reply'], dict) or value['raw_reply'].get('id') != value['task_id']:
        raise ValueError('Raw reply does not match task ID')


def cell(value):
    return str(value).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('|', '&#124;').replace('\r', '').replace('\n', '<br>')


def render_report(catalog, verdicts, batch_id, environment=None):
    by_case = {}
    matrix = {action: {k: [] for k in ('成功路径', '拒绝路径', '边界条件')} for action in catalog['actions']}
    for value in verdicts:
        validate_verdict(value, batch_id, environment)
        case = next(c for c in catalog['cases'] if c['id'] == value['case_id'])
        if case['actions'] and value['action'] not in case['actions']:
            raise ValueError('Action is not mapped to this case; review mapping before export')
        if value['case_id'] in by_case:
            raise ValueError('Consolidate all subcases explicitly before exporting one T verdict')
        by_case[value['case_id']] = value
        label = value['task_id']
        if value['verdict'] == '失败':
            code = (value['raw_reply'].get('error') or {}).get('code')
            if not code:
                # Keep failure in detail; do not fabricate a node error for matrix.
                continue
            label += ' + ' + code
        if value['action'] in matrix:
            matrix[value['action']][value['category']].append(label)
    output = [f'# MQ 接口测试报告 — {batch_id}', '',
              '> 本表仅统计所选批次的完整用例。未测原因见备注，原始证据和历史观察另附；本地工具测试不计入远端通过。', '',
              '| action | 成功路径 | 拒绝路径 | 边界条件 |', '|---|---|---|---|']
    for action, paths in matrix.items():
        output.append('| ' + ' | '.join([action] + [cell('; '.join(dict.fromkeys(v))) for v in paths.values()]) + ' |')
    output.extend(['', '| 编号 | 结论（通过·失败·未测） | 任务 ID | 北京时间 | 关键回包字段 | 备注 |', '|---|---|---|---|---|---|'])
    for case in catalog['cases']:
        value = by_case.get(case['id'])
        if value is None:
            row = [case['id'], '未测', '', '', '', case['not_tested_reason']]
        else:
            note = value.get('note', '') + '；证据：' + value['raw_ref']
            if value['verdict'] == '失败' and not (value['raw_reply'].get('error') or {}).get('code'):
                note += '；证据缺口：节点未返回错误码，矩阵留空，不编造错误码'
            row = [case['id'], value['verdict'], value['task_id'], value['beijing_time'], value.get('key_fields', ''), note]
        output.append('| ' + ' | '.join(cell(v) for v in row) + ' |')
    return '\n'.join(output) + '\n'


def write_mapping(catalog, path):
    lines = ['# 68 项用例、前提与执行设计', '',
             '这是用例目录，不是测试成绩。原文判据逐字提取，候选 action 不能自动变成覆盖结果。', '',
             f'源文件 SHA-256：`{catalog["source_sha256"]}`', '',
             '接收器、事件和平台用例没有一一对应的 action，不强行塞进矩阵。T-27 与 T-55 的未知 action 只进入明细。', '',
             '| 编号 | 测试内容与原文位置 | 候选 action / 类别 | 对象 / 阶段 | 前提 | 执行动作 | 通过判据（源原文） |',
             '|---|---|---|---|---|---|---|']
    for c in catalog['cases']:
        row = [c['id'], f'{c["title"]}（第 {c["source_line"]} 行，{c["source_section"]}）',
               ', '.join(c['actions']) + ' / ' + c['category'], c['object'] + ' / ' + c['phase'],
               c['preconditions'], c['procedure'], c['criterion']]
        lines.append('| ' + ' | '.join(cell(v) for v in row) + ' |')
    path.write_text('\n'.join(lines) + '\n', encoding='utf-8')


def write_audit_notes(audits, path):
    lines = ['# 原始证据复核附件', '',
             '状态：本地证据核验已完成；远端68项验收未完成。此附件记录既有批次，不是本次重新连接所得。', '',
             '正式报告按本次离线核验批次输出：通过0、失败0、未测68。历史最小往返不回填本轮矩阵，也不抵作任何完整T项。', '',
             '自洽检查覆盖请求/环境/摘要ID、topic、seq、原始终态、摘要一致性、Broker确认、ACK归属与落盘顺序。哈希用于后续查变更，不是对原始来源的数字签名。', '']
    for a in audits:
        f = a['terminal_fields']
        lines.extend([f'## 历史批次 {a["batch_id"]}', '',
                      f'- 真实任务 ID：`{a["task_id"]}`；action：`{a["action"]}`。',
                      f'- 请求时间：{a["command_time"]}；本机收到终态：{a["receive_time"]}；节点消息 time：{a["node_time"]}（均为北京时间）。',
                      f'- 状态：{" → ".join(a["states"])}；请求在 trace.jsonl 第 {a["command_line"]} 行。',
                      f'- 环境：节点 {a["environment"]["node"]}，MQTT {a["environment"]["mqtt_version"]}，TLS={a["environment"]["tls"]}；完整 Broker/client 身份仅保留在本地 audit JSON 与原始证据。',
                      f'- software_version：`{f.get("software_version")}`；protocol_version：`{f.get("protocol_version")}`。',
                      f'- node_type：`{f.get("node_type")}`；outbox_pending：`{f.get("outbox_pending")}`；声明能力数：{len(f.get("capabilities", []))}。',
                      f'- {a["ack_no_subscribers"]} 次业务 ACK 发布收到 `No matching subscribers`；节点收到/处理 ACK 未验证。',
                      '- 证据自洽检查：通过；T用例覆盖：0。', '',
                      '| 回包所在行 | seq / state | 本机接收北京时间 | 原始消息 SHA-256 |', '|---|---|---|---|'])
        for reply in a['replies']:
            p = reply['payload']
            lines.append(f'| {reply["line"]} | {p["seq"]} / {p["state"]} | {reply["beijing_time"]} | {reply["raw_sha256"]} |')
        lines.extend(['', f'原始日志：[trace.jsonl]({Path(a["evidence_directory"]).as_posix()}/trace.jsonl)。原始回包逐字保存在该文件 raw 字段；本批次摘要：[audit JSON](audit-{a["batch_id"]}.json)。', ''])
    lines.extend(['## 发现与边界', '',
                  '1. ACK：No matching subscribers 是 Broker 的传输提示，不是节点业务错误码；不得填进矩阵充当节点错误。没有节点订阅/处理证据，原因仍未知。没有修改共享 ACK 开关或 outbox。',
                  '2. node_type：当前开发文档规定 ec20_edge / mdd_cloud，两个原始回包均为 vocat_ec20。这是协议枚举差异，未获得兼容性裁决；不据此制造节点错误码或把最小查询当完整协议通过。',
                  '3. 探针：只订阅 task；没有 event/presence/heartbeat、事务化业务库与去重库、重启恢复、分页、task.get 和正式用例执行器。每条日志 fsync 后发 ACK 只证明程序顺序，不能满足完整 T-10。',
                  '4. 两批分别使用不同 UUID；相同返回内容不能证明幂等、重投、补传或跨重启一致性。声明支持14个 action 不能证明其余13个真的测过。',
                  '5. outbox_pending=2 是查询时的单点快照；pending publish 为空只表示 Broker 的传输确认完成，不证明业务消息清零。',
                  '6. 节点消息时间约超前本机1秒；未验证时钟同步。ec20test 与本地 Ubuntu/实际硬件的对应关系未确认。', '',
                  '7. command_intent 保存的是请求对象，未保存实际发布字节及其哈希；也没有留存运行时探针源码哈希。后续严格原文重投需要冻结发布字节，不能直接重新生成时间或序列化后就宣称逐字节一致。', '',
                  '## 下一步所需输入', '',
                  '- 最小只读批次：确认目标 Broker/node 与可用业务账号、节点/机器映射及当前版本；凭据通过隐藏输入提供。建议先 node.describe / task.get 与预定义参数拒绝项，完整保留 task/event 证据。',
                  '- ACK专项：提供节点 ACK 开关和订阅/处理的只读日志；若需修改公共配置或故障注入，再限定操作范围。',
                  '- 资源用例：现场合法 target、空槽及完整分页；查询会占用硬件通道，需控制串行负载。',
                  '- 短信、写卡、删卡、隧道变更、8h/24h和故障专项：按 case-mapping.md 的场景分别取得测试资源、操作范围和授权。', '',
                  '本次未尝试远端登录或连接，故没有新的网络/认证失败证据；阻塞边界是未核实的现场条件与未取得的专项授权，不猜测账号已失效。'])
    path.write_text('\n'.join(lines) + '\n', encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['catalog', 'export'])
    parser.add_argument('--source', type=Path, default=DEFAULT_SOURCE)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--batch-id', default='offline-review-20260921')
    parser.add_argument('--evidence', action='append', type=Path, default=[])
    args = parser.parse_args()
    if args.command == 'catalog':
        catalog = build_catalog(args.source, ROOT / 'cases/requirements.tsv')
        write_json(ROOT / 'cases/catalog.json', catalog)
        write_mapping(catalog, ROOT / 'docs/case-mapping.md')
        print('68 cases and 14 actions catalogued; no remote tests executed.')
        return
    catalog = load_catalog(ROOT / 'cases/catalog.json', args.source)
    if args.output is None:
        parser.error('export requires --output (a new directory)')
    audits = [audit_probe(path.resolve()) for path in args.evidence]
    if len({a['batch_id'] for a in audits}) != len(audits):
        raise ValueError('Duplicate batch IDs would overwrite audit files')
    # Reject mixed/corrupt inputs before creating any deliverable files.
    if any(not audit['integrity_ok'] for audit in audits):
        raise ValueError('Evidence integrity check failed; no report generated')
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output / 'report.md').write_text(render_report(catalog, [], args.batch_id), encoding='utf-8')
    for audit in audits:
        write_json(args.output / ('audit-' + audit['batch_id'] + '.json'), audit)
    write_audit_notes(audits, args.output / 'evidence-review.md')
    write_json(args.output / 'report.json', dict(
        batch_id=args.batch_id, mode='offline_review', generated_at=datetime.now(BEIJING).isoformat(),
        source_sha256=catalog['source_sha256'], current_remote_executions=0,
        totals={'通过': 0, '失败': 0, '未测': 68},
        matrix=[dict(action=a, 成功路径=[], 拒绝路径=[], 边界条件=[]) for a in catalog['actions']],
        cases=[dict(case_id=c['id'], verdict='未测', task_id=None, beijing_time=None,
                    key_fields=None, note=c['not_tested_reason']) for c in catalog['cases']],
        historical_batches=[a['batch_id'] for a in audits]))
    write_json(args.output / 'manifest.json', dict(
        source=dict(path=str(args.source.resolve()), sha256=sha256(args.source)),
        catalog=dict(path=str((ROOT / 'cases/catalog.json').resolve()), sha256=sha256(ROOT / 'cases/catalog.json')),
        exporter=dict(path=str(Path(__file__).resolve()), sha256=sha256(Path(__file__))),
        inputs=[f for a in audits for f in a['files']],
        outputs=[dict(path=p.name, sha256=sha256(p), bytes=p.stat().st_size)
                 for p in sorted(args.output.iterdir()) if p.is_file()]))
    print(f'Exported {args.output.resolve()}: 0 passed, 0 failed, 68 not tested; {len(audits)} historical batches audited.')


if __name__ == '__main__':
    main()
