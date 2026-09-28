"""Coverage view for the MQ checklist: 68 catalog items merged with the latest
layer-1 MQ run, the §6 action matrix, and a Markdown export. No network access."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CATALOG = ROOT / 'cases' / 'catalog.json'
MQ_EVIDENCE = ROOT / '.local' / 'mq-layer1'

L1, L2, L3, LT = '第一层', '第二层', '第三层', '长周期'
# Three-layer plan (tasks/mqtt-test-console-three-layer-plan-20260922.md) with the review
# adjustments: T-19/T-20/T-49/T-53 need construction or restarts -> layer 3; T-60/T-61 long-run track.
LAYER = {}
for ids, layer in ((['T-01', 'T-02', 'T-03', 'T-04', 'T-05', 'T-16', 'T-17', 'T-18', 'T-21'], L1),
                   ([f'T-{i:02d}' for i in range(37, 49)] + ['T-50', 'T-51', 'T-52', 'T-55', 'T-56', 'T-57', 'T-64', 'T-66'], L1),
                   ([f'T-{i:02d}' for i in range(7, 16)] + [f'T-{i:02d}' for i in range(22, 28)] + ['T-63', 'T-65'], L2),
                   (['T-06', 'T-19', 'T-20'] + [f'T-{i:02d}' for i in range(28, 37)] + ['T-49', 'T-53', 'T-54', 'T-58', 'T-59', 'T-62', 'T-67', 'T-68'], L3),
                   (['T-60', 'T-61'], LT)):
    for i in ids:
        LAYER[i] = layer

# Why an item is not run by the layer-1 button (overrides the catalog's historical reason).
NOT_RUN = {
    L2: '第二层：需真实短信或业务 ACK 窗口，须单独授权后在“短信收发”入口执行',
    L3: '第三层：写卡/线路/重启/构造类操作，只在隔离环境执行，测试台只记录',
    LT: '长周期轨道：需挂机运行，不在单次测试中执行',
}
SPECIFIC = {
    'T-37': '构造条件：现场需有空槽（模块在位但卡上 0 个 Profile）；当前 3 模块 18 线均有 Profile，不为测试删卡',
    'T-38': '外部平台（PingCode）入库行为，按用户要求本阶段不测',
    'T-41': '构造条件：需要一个空槽和一个“未检测到 SIM 卡”的槽位作对照；当前现场均不具备，不为测试拔卡',
    'T-51': '构造条件：需要同一号码对应多个 Profile；当前 18 个号码各自唯一',
    'T-66': '构造条件：隔天用本批次留下的完整任务 ID 原内容重投（保留策略需时间跨度）',
}
# Which §6 matrix column a case fills. Anything not listed here only appears in the T detail table.
REJECT = {'T-05', 'T-16', 'T-17', 'T-18', 'T-40', 'T-43', 'T-47b', 'T-50', 'T-52', 'T-56'}
BOUNDARY = {'T-01', 'T-02', 'T-03', 'T-04', 'T-21', 'T-37', 'T-39', 'T-44', 'T-45', 'T-46', 'T-47a', 'T-48'}
LABEL = {'pass': '通过', 'fail': '失败', 'untested': '未测', 'partial': '未测（部分观察）', 'info': '通过',
         'insufficient': '证据不足'}


def load_catalog():
    return json.loads(CATALOG.read_text('utf-8'))


def stable_run():
    """Conclusion source for stage B: the newest repeat batch, restricted to runs whose environment
    probe succeeded and whose run fingerprint is the majority; the last such run is used, annotated
    with the agreeing runs. Cases a repeat never runs (T-43 is off by default) are filled from the
    newest single run that has a real verdict for them."""
    reports = sorted(MQ_EVIDENCE.glob('repeat-*/repeat_report.json'))
    if not reports:
        return latest_run()
    base = reports[-1].parent
    runs = []
    for p in sorted(base.glob('[0-9][0-9]/results.json')):
        r = json.loads(p.read_text('utf-8'))
        r['_dir'] = p.parent.name
        runs.append(r)
    ok = [r for r in runs if (r.get('preconditions') or {}).get('env_probe_ok', True)]
    fps = [r['run_fingerprint'] for r in ok]
    if not fps:
        return latest_run()
    majority = max(sorted(set(fps)), key=fps.count)
    agree = [r for r in ok if r['run_fingerprint'] == majority]
    chosen = dict(agree[-1])
    source = f"{base.name}/{chosen['_dir']}"
    code = (chosen.get('meta') or {}).get('code_sha256', '')[:16]
    chosen['conclusion_source'] = {'repeat_id': base.name, 'run': chosen['_dir'], 'run_fingerprint': majority,
                                   'agreeing_runs': [r['_dir'] for r in agree], 'runs_total': len(runs),
                                   'code_sha256': code}
    chosen['evidence_dir'] = str(base / chosen['_dir'])
    cases = []
    for rec in chosen['cases']:
        rec = dict(rec, batch=source, code=code)
        cases.append(rec)
    single = latest_run()
    if single:
        scode = (single.get('meta') or {}).get('code_sha256', '')[:16]
        cid = lambda r: r.get('id') or r.get('t')
        skipped = {cid(r) for r in cases if r['verdict'] == 'untested' and any('本次未启用' in x for x in r.get('reasons', []))}
        for rec in single.get('cases', []):
            if cid(rec) in skipped and rec['verdict'] != 'untested':
                cases = [x for x in cases if cid(x) != cid(rec)]
                cases.append(dict(rec, batch=single['run_id'], code=scode))
    chosen['cases'] = cases
    chosen['commands'] = chosen.get('commands', []) + (single or {}).get('commands', [])
    return chosen


def latest_run():
    runs = sorted(p for p in MQ_EVIDENCE.glob('2*/results.json'))  # single runs; repeat-*/NN/ are compared separately
    for path in reversed(runs):
        data = json.loads(path.read_text('utf-8'))
        if isinstance(data, dict) and 'cases' in data:
            data.setdefault('evidence_dir', str(path.parent))
            return data
    return None


def case_key(t):
    """'T-47a' / 'T-16#describe' -> 'T-47' / 'T-16'; 'slot.refresh/success@1' -> 'slot.refresh/success'."""
    if t.startswith('T-'):
        return t[:4]
    return t.split('@')[0]


def verdict_of(records):
    vs = [r['verdict'] for r in records]
    if 'fail' in vs:
        return '失败'
    if 'insufficient' in vs:
        return '证据不足'
    if all(v == 'untested' for v in vs):
        return '未测'
    if 'partial' in vs:
        return '未测（部分观察）'
    return '通过'


def coverage(run=None):
    catalog = load_catalog()
    by_t = {}
    for rec in (run or {}).get('cases', []):
        by_t.setdefault(case_key(rec.get('t') or rec['id']), []).append(rec)
    rows, counts = [], {'通过': 0, '失败': 0, '未测': 0}
    for item in catalog['cases']:
        tid = item['id']
        layer = LAYER.get(tid, L1)
        recs = by_t.get(tid, [])
        if recs:
            verdict = verdict_of(recs)
            ids = list(dict.fromkeys(i for r in recs for i in r['task_ids']))
            summary = '；'.join(r['summary'] for r in recs)
            when = recs[0]['time']
            batch = '；'.join(dict.fromkeys(f"{r.get('batch') or (run or {}).get('run_id')}（{r.get('code') or ((run or {}).get('meta') or {}).get('code_sha256', '')[:16]}）" for r in recs))
            raw = '；'.join(dict.fromkeys(x for r in recs for x in r.get('reasons', []) if not x.startswith(('✓', '✗'))))
            reason = ('；'.join(x for x in (SPECIFIC.get(tid), f'（{raw}）' if raw and SPECIFIC.get(tid) else raw) if x)
                      if verdict == '未测' else '')
            if verdict == '未测':
                summary = ''
        else:
            verdict, ids, summary, when, batch = '未测', [], '', '', ''
            reason = SPECIFIC.get(tid) or NOT_RUN.get(layer) or item.get('not_tested_reason', '')
        counts['未测' if verdict.startswith('未测') or verdict == '证据不足' else verdict] += 1
        rows.append({'id': tid, 'title': item['title'].replace('**', ''), 'criterion': item['criterion'],
                     'section': item.get('source_section'), 'layer': layer, 'verdict': verdict,
                     'task_ids': ids, 'time': when, 'summary': summary, 'reason': reason, 'batch': batch,
                     'runnable': layer == L1})
    return {'run_id': (run or {}).get('run_id'), 'started': (run or {}).get('started'),
            'finished': (run or {}).get('finished'), 'meta': (run or {}).get('meta'),
            'evidence_dir': (run or {}).get('evidence_dir'), 'counts': counts, 'rows': rows,
            'conclusion_source': (run or {}).get('conclusion_source'),
            'matrix': matrix(run, catalog['actions']), 'extras': extras(run)}


def _actions(run):
    return {c['id']: c['action'] for c in (run or {}).get('commands', [])}


def matrix(run, actions):
    cells = {a: {'success': [], 'reject': [], 'boundary': []} for a in actions}
    act = _actions(run)
    for rec in (run or {}).get('cases', []):
        t = rec.get('t') or rec['id']
        if rec.get('path') in ('success', 'reject', 'boundary'):  # declarative cases carry their column
            col = rec['path']
        elif rec.get('path') == 'none':
            continue
        elif t.endswith('/success'):
            col = 'success'
        elif t in REJECT or case_key(t) in REJECT:
            col = 'reject'
        elif t in BOUNDARY or case_key(t) in BOUNDARY:
            col = 'boundary'
        else:
            continue
        if rec['verdict'] == 'untested':
            continue
        for tid in rec['task_ids']:
            a = act.get(tid)
            if a in cells:
                entry = {'id': tid, 't': case_key(t) if t.startswith('T-') else '', 'verdict': LABEL.get(rec['verdict'], rec['verdict'])}
                if entry not in cells[a][col]:
                    cells[a][col].append(entry)
    return [{'action': a, **cells[a]} for a in actions]


def extras(run):
    """Cases whose action is outside the 14-row matrix (unknown action, sms.list)."""
    act = _actions(run)
    out = []
    for rec in (run or {}).get('cases', []):
        if case_key(rec.get('t') or rec['id']) not in ('T-27', 'T-55'):
            continue
        for tid in rec['task_ids']:
            if act.get(tid) not in cells_actions(run):
                out.append({'t': rec['t'], 'id': tid, 'action': act[tid], 'verdict': LABEL.get(rec['verdict'])})
    return out


def cells_actions(run):
    return set(load_catalog()['actions'])


def _cell(entries):
    return '<br>'.join(f"`{e['id'][:8]}`{'（' + e['t'] + '）' if e['t'] else ''}{' **失败**' if e['verdict'] == '失败' else ''}"
                       for e in entries)


def to_markdown(cov):
    esc = lambda s: str(s or '').replace('|', '\\|').replace('\n', ' ')
    c, m = cov['counts'], cov.get('meta') or {}
    lines = [
        '# MQ 接口测试清单 · 测试台导出（第一层 MQTT 只读协议）', '',
        '> 判定来源：`C:\\Users\\27792\\Desktop\\wiki\\24-MQ接口测试清单.md`。结论只有 通过 / 失败 / 未测；“未测（部分观察）”计入未测。',
        '> 本文件由测试台根据最近一次 MQ 批次自动生成；每格结论只来自该批次的真实回包。', '',
        '| 项 | 值 |', '|---|---|',
        f"| 批次 | `{cov.get('run_id') or '尚未运行'}`（{cov.get('started') or ''} – {cov.get('finished') or ''}，北京时间） |",
        f"| 连接 | `{m.get('broker', '')}`，业务端 client_id `{m.get('client_id', '')}`，节点 `{m.get('node', '')}` |",
        f"| 证据 | `{cov.get('evidence_dir') or ''}`（ICCID/IMEI/EID 打码，号码保留） |",
        *([f"| 结论来源 | 复现批次 `{cs['repeat_id']}` 第 {cs['run']} 次（与第 {'、'.join(cs['agreeing_runs'])} 次运行指纹一致 `{cs['run_fingerprint']}`，共 {cs['runs_total']} 次；代码 `{cs['code_sha256']}`） |"]
          if (cs := cov.get('conclusion_source')) else []),
        '| 纪律 | 新查询新 UUID；重投保持原 ID 与原内容；不发 /ack；只发只读与故意构造的非法命令 |', '',
        f"**68 项：通过 {c['通过']}、失败 {c['失败']}、未测 {c['未测']}。**", '',
        '## 覆盖矩阵（清单 §6）', '', '每格为任务 ID 前 8 位（完整 ID 见明细）；空格 = 未测。', '',
        '| action | 成功路径 | 拒绝路径 | 边界条件 |', '|---|---|---|---|']
    for r in cov['matrix']:
        lines.append(f"| {r['action']} | {_cell(r['success'])} | {_cell(r['reject'])} | {_cell(r['boundary'])} |")
    if cov['extras']:
        lines += ['', '矩阵外：' + '；'.join(f"{e['t']} `{e['action']}` `{e['id'][:8]}` {e['verdict']}" for e in cov['extras'])]
    lines += ['', '## T-01 – T-68 明细', '',
              '| 编号 | 层级 | 测什么 | 结论 | 批次（代码） | 任务 ID | 北京时间 | 关键回包 | 未测原因 / 构造条件 |',
              '|---|---|---|---|---|---|---|---|---|']
    for r in cov['rows']:
        lines.append(f"| {r['id']} | {r['layer']} | {esc(r['title'])} | **{r['verdict']}** | {esc(r.get('batch'))} | {'<br>'.join(r['task_ids'])} | "
                     f"{r['time']} | {esc(r['summary'])} | {esc(r['reason'])} |")
    return '\n'.join(lines) + '\n'
