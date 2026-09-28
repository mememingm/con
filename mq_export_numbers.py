"""Export the layer-1 candidate numbers for layer 2 (pool-internal SMS).

Source: the stable run chosen by mq_coverage.stable_run() (newest repeat batch, environment probe
OK, majority fingerprint). A number is a layer-1 pass when, in that run, its phones.list row is
available=true, tunnel_state=registered, reason empty, and (with --check) a fresh read-only
phones.check on it succeeds with available=true. Module read-failure counts across all saved
repeat runs are attached so layer 2 can prefer stable modules.

  python mq_export_numbers.py --check --out ..\\tasks\\records\\mqtt-console\\layer1-numbers-20260922
Read-only; never sends SMS or /ack. ICCID/IMEI stay masked; phone numbers are kept (pool identity).
"""
import argparse
import json
import re
import time
from collections import Counter
from pathlib import Path

import mq_coverage
import mq_layer1

FAIL_RE = re.compile(r'读取模块 (\d{4}\*+\d{4}) 的 Profile 失败')


def module_failures(evidence=mq_coverage.MQ_EVIDENCE):
    """Per masked module: in how many saved repeat runs it had a read failure."""
    counts, total = Counter(), 0
    for p in sorted(evidence.glob('repeat-*/[0-9][0-9]/results.json')):
        total += 1
        text = p.read_text('utf-8')
        mods = set(FAIL_RE.findall(text))
        data = json.loads(text)
        for c in data.get('cases', []):  # registry fallback with slot.state=error (F-8) counts too
            fin = (c.get('evidence') or {}).get('final') or {}
            slot = (fin.get('result') or {}).get('slot') or {}
            if slot.get('state') == 'error' and slot.get('slot'):
                mods.add(slot['slot'])
        counts.update(mods)
    return counts, total


def candidates(run):
    rows = run.get('environment_rows')
    if rows is None:  # runs before environment_rows existed: take the setup phones.list reply
        rows = []
        for tid in run.get('setup_task_ids', [])[1:2]:
            fin = [m for m in run.get('task_messages', {}).get(tid, []) if m.get('state') == 'succeeded']
            rows = ((fin[-1].get('result') or {}).get('items') or []) if fin else []
    out = []
    for r in rows:
        t = r.get('target') or {}
        if not t.get('phone'):
            continue
        ok = r.get('available') is True and r.get('tunnel_state') == 'registered' and not r.get('reason')
        out.append({'phone': t['phone'], 'device': str(t.get('device')), 'module': t.get('slot'), 'iccid': t.get('iccid'),
                    'available': r.get('available'), 'tunnel_state': r.get('tunnel_state'), 'reason': r.get('reason'),
                    'stable_run_ok': ok})
    return sorted(out, key=lambda x: (x['device'], x['module'] or '', x['phone']))


def live_check(rows, evidence_dir, progress=print):
    """One read-only phones.check per number; target taken from a fresh phones.list (unmasked).
    Each check is appended to the number's history; raw replies are saved masked."""
    node = mq_layer1.Node()
    ctx = mq_layer1.Ctx(node, {})
    raw = []
    try:
        pages, items = ctx.paginate('phones.list', {'page_size': 100})
        by_phone = {i['target']['phone']: i['target'] for i in items if (i.get('target') or {}).get('phone')}
        for row in rows:
            t = by_phone.get(row['phone'])
            if not t:
                row.setdefault('checks', []).append({'state': 'not_in_fresh_list', 'time': mq_layer1.ts()})
                continue
            cmd = ctx.command('phones.check', {}, {k: t[k] for k in ('device', 'slot', 'phone', 'binding_version')})
            f = ctx.send(cmd, 60) or {}
            res, err = f.get('result') or {}, f.get('error') or {}
            row.setdefault('checks', []).append({
                'task_id': cmd['id'], 'time': f.get('time') or mq_layer1.ts(), 'state': f.get('state'),
                'available': res.get('available'), 'tunnel_state': res.get('tunnel_state'),
                'error_code': err.get('code'), 'error_message': mq_layer1.mask_text(err.get('message') or '')})
            raw.append({'command': mq_layer1.mask(cmd), 'final': mq_layer1.mask(f)})
            progress(f"{row['phone']}: {f.get('state')} available={res.get('available')} {err.get('code') or ''}")
            time.sleep(0.5)
    finally:
        node.close()
    ev = Path(evidence_dir) / f"checks-{time.strftime('%Y%m%d-%H%M%S')}.json"
    ev.write_text(json.dumps(raw, ensure_ascii=False, indent=2), 'utf-8')
    return rows


def check_ok(c):
    return c.get('state') == 'succeeded' and c.get('available') is True


def decide(rows, failures, total):
    """Pass = stable run OK and (no live checks yet, or at least one live check succeeded).
    Live-check failures are shown, never hidden, and count against the module."""
    live_fail = Counter(r['module'] for r in rows for c in r.get('checks', []) if not check_ok(c))
    for r in rows:
        n = failures.get(r['module'], 0)
        r['module_read_failures'] = f'{n}/{total}' + (f'；实时复核失败 {live_fail[r["module"]]} 次' if live_fail[r['module']] else '')
        checks = r.get('checks', [])
        ok = sum(check_ok(c) for c in checks)
        r['live_checks'] = f'{ok}/{len(checks)}' if checks else '—'
        r['layer1_pass'] = bool(r['stable_run_ok'] and (not checks or ok >= 1))
        bad = [c for c in checks if not check_ok(c)]
        if not r['layer1_pass']:
            r['recommendation'] = '不进入第二层'
        elif n == 0 and not live_fail[r['module']]:
            r['recommendation'] = '首选'
        else:
            notes = [f'所在模块读卡偶发 {n}/{total}'] if n else []
            notes += [f"本号实时复核失败 {len(bad)} 次（{', '.join(sorted({c.get('error_code') or c.get('state') for c in bad}))}）"] if bad else []
            notes += ['同模块其他号码实时复核失败'] if live_fail[r['module']] and not bad else []
            r['recommendation'] = '可用；' + '，'.join(notes) + '，建议不作首选'
    return rows


def to_markdown(meta, rows):
    lines = ['# 第一层通过的号码清单（第二层候选）', '',
             f"- 来源：复现批次 `{meta['source']}`（与第 {'、'.join(meta['agreeing_runs'])} 次指纹一致 `{meta['run_fingerprint']}`；代码 `{meta['code_sha256']}`）",
             f"- 实时复核：{meta['live_check']}",
             '- 判据：稳定次 phones.list 中 available=true、tunnel_state=registered、reason 为空；且实时复核至少一次 phones.check succeeded + available=true。失败次数照实列出，不以重试掩盖',
             f"- 模块读卡偶发统计：已保存的 {meta['repeat_runs']} 次复现运行",
             f"- 结果：{sum(r['layer1_pass'] for r in rows)}/{len(rows)} 个号码通过第一层；首选 {sum(r['recommendation'] == '首选' for r in rows)} 个",
             '- 只读导出：未发送短信或 ACK；ICCID/IMEI 打码，号码保留', '',
             '| 号码 | 设备 | 模块 IMEI | ICCID | 稳定次 | 实时复核（成功/次数；各次任务 ID） | 模块读卡偶发 | 第一层 | 建议 |',
             '|---|---|---|---|---|---|---|---|---|']
    for r in rows:
        ids = ' '.join(f"`{(c.get('task_id') or '')[:8]}`{'✓' if check_ok(c) else '✗' + (c.get('error_code') or '')}"
                       for c in r.get('checks', []))
        lines.append(f"| {r['phone']} | {r['device']} | {r['module']} | {r['iccid']} | "
                     f"{'✓' if r['stable_run_ok'] else '✗'} {r['tunnel_state']} | {r['live_checks']} {ids} | {r['module_read_failures']} | "
                     f"{'通过' if r['layer1_pass'] else '不通过'} | {r['recommendation']} |")
    return '\n'.join(lines) + '\n'


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--check', action='store_true', help='对每个号码实时发一次只读 phones.check')
    ap.add_argument('--out', required=True)
    a = ap.parse_args()
    run = mq_coverage.stable_run()
    cs = run.get('conclusion_source') or {}
    rows = candidates(run)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    prev = {}
    if (out / 'numbers.json').exists():  # keep earlier live checks: history is appended, never replaced
        for r in json.loads((out / 'numbers.json').read_text('utf-8')).get('numbers', []):
            hist = r.get('checks') or ([{'task_id': r.get('check_task_id'), 'time': r.get('check_time'), 'state': r.get('check_state'),
                                         'available': r.get('check_available'), 'error_code': r.get('check_error')}]
                                       if r.get('check_state') else [])
            prev[r['phone']] = hist
    for r in rows:
        r['checks'] = list(prev.get(r['phone'], []))
    if a.check:
        rows = live_check(rows, out)
    failures, total = module_failures()
    rows = decide(rows, failures, total)
    meta = {'source': f"{cs.get('repeat_id')}/{cs.get('run')}", 'agreeing_runs': cs.get('agreeing_runs', []),
            'run_fingerprint': cs.get('run_fingerprint'), 'code_sha256': cs.get('code_sha256'),
            'live_check': f"累计 {max((len(r.get('checks', [])) for r in rows), default=0)} 轮 phones.check（最近一轮 {time.strftime('%Y-%m-%d %H:%M:%S')}）；各次原始回包在同目录 checks-*.json",
            'repeat_runs': total, 'module_failures': dict(failures)}
    (out / 'numbers.json').write_text(json.dumps({'meta': meta, 'numbers': rows}, ensure_ascii=False, indent=2), 'utf-8')
    (out / 'numbers.md').write_text(to_markdown(meta, rows), 'utf-8')
    print(f"{sum(r['layer1_pass'] for r in rows)}/{len(rows)} 通过；输出 {out}")


if __name__ == '__main__':
    main()
