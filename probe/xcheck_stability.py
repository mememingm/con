"""独立的"稳定性交叉核对"工具（只读，不碰 Broker、不改测试台代码）。

用途：读多次 MQ 第一层运行的 results.json，独立比出"哪些用例每次结论一致（稳定）、
哪些翻转"，用来复核代码会话 --repeat 的结论，而不是照抄它的判定。

独立性：对每条用例，用它的 normalized（已去易变字段的语义结果）自己重算指纹，并顺带
校验它自己写的 fingerprint 是否与 normalized 相符（不符=它的哈希逻辑有问题）。还会独立
重算 run_fingerprint（只含 deterministic 用例）与它顶层的值比对。

角色分工（execution-plan §2）：本工具属"交叉核对"，由 codex thread retrieval 会话维护。

用法：
  python xcheck_stability.py                         # 自动取最近一个 repeat-* 批次的各次运行
  python xcheck_stability.py repeat-20260922-160153  # 指定 repeat 批次目录（自动展开 01..NN）
  python xcheck_stability.py <run1> <run2> …         # 指定若干运行目录名或 results.json
"""
import glob
import hashlib
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

BJ = timezone(timedelta(hours=8))
ROOT = Path(__file__).resolve().parents[1]
MQ = ROOT / '.local' / 'mq-layer1'
OUT = ROOT / '.local' / 'pool-console'


def fp(obj):
    return hashlib.sha1(json.dumps(obj, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:12]


def normalize_old(case):
    det = case.get('detail')
    det = det[-1] if isinstance(det, list) and det else (det if isinstance(det, dict) else {})
    err = det.get('error') or {}
    result = det.get('result')
    return {'verdict': case.get('verdict'), 'state': det.get('state'),
            'error_code': err.get('code') if isinstance(err, dict) else None,
            'error_certainty': err.get('certainty') if isinstance(err, dict) else None,
            'result_keys': sorted(result.keys()) if isinstance(result, dict) else None}


def load_run(path):
    data = json.loads(Path(path).read_text('utf-8'))
    if not isinstance(data, dict) or 'cases' not in data:
        return None
    meta = data.get('meta') or {}
    code = meta.get('code_sha256')
    code = str(code)[:16] if code else None
    cases = {}
    schema = 'old'
    for c in data['cases']:
        cid = c.get('id') or c.get('t')
        if cid is None:
            continue
        if 'normalized' in c:  # 新结构
            schema = 'new'
            norm = c.get('normalized')
            entry = dict(verdict=c.get('verdict'), stability=c.get('stability'),
                         normalized=norm, their_fp=c.get('fingerprint'),
                         my_fp=fp(norm))
        else:  # 旧结构
            norm = normalize_old(c)
            entry = dict(verdict=c.get('verdict'), stability=None,
                         normalized=norm, their_fp=None, my_fp=fp(norm))
        cases.setdefault(cid, entry)
    return dict(run_id=data.get('run_id', os.path.basename(os.path.dirname(str(path)))),
                path=str(path), code=code, schema=schema,
                run_fp=data.get('run_fingerprint'),
                env_id=data.get('environment_snapshot_id'), cases=cases)


def expand(args):
    paths = []
    for a in args:
        p = Path(a if os.path.isabs(a) or os.path.exists(a) else str(MQ / a))
        if p.is_dir():
            nested = sorted(glob.glob(str(p / '**' / 'results.json'), recursive=True))
            paths.extend(nested or [str(p / 'results.json')])
        else:
            paths.append(str(p))
    return paths


def main():
    args = sys.argv[1:]
    if args:
        paths = expand(args)
    else:  # 自动：最近一个 repeat-* 批次
        batches = sorted(glob.glob(str(MQ / 'repeat-*')), key=os.path.getmtime)
        if batches:
            paths = sorted(glob.glob(os.path.join(batches[-1], '**', 'results.json'), recursive=True))
            print(f'自动选取最近批次: {os.path.basename(batches[-1])}')
        else:
            paths = sorted(glob.glob(str(MQ / '*' / 'results.json')), key=os.path.getmtime)[-5:]

    runs = []
    for p in paths:
        try:
            r = load_run(p)
            if r:
                runs.append(r)
            else:
                print(f'跳过（非全量结构）: {p}')
        except Exception as e:
            print(f'读取失败 {p}: {e}')
    if len(runs) < 2:
        print('可比较的运行少于 2 个，无法比对。')
        return 1

    # 按代码哈希分组，只比同版代码
    codes = {r['code'] for r in runs}
    print(f'参与比对的运行（{len(runs)}）: {", ".join(r["run_id"] for r in runs)}')
    if codes == {None}:
        print('[!] 警告：未记录 code_sha256，无法保证同版代码；结论仅供参考。')
    elif len(codes) > 1:
        groups = {}
        for r in runs:
            groups.setdefault(r['code'], []).append(r)
        biggest = max(groups.values(), key=len)
        print(f'[!] 混入多个代码版本 {codes}；只比最大同版组（{biggest[0]["code"]}，{len(biggest)} 次），其余忽略。')
        runs = biggest
        if len(runs) < 2:
            print('同版代码运行少于 2 个，无法比对。')
            return 1
    else:
        print(f'代码哈希一致: {codes.pop()} (OK)')

    # 环境快照一致性
    env_ids = {r['env_id'] for r in runs}
    print(f'environment_snapshot_id: {"一致 "+list(env_ids)[0] if len(env_ids)==1 else "不一致 "+str(env_ids)+"（号池/节点可能变了，环境类差异按此归因）"}')

    # 每用例稳定性
    all_ids = sorted(set().union(*[set(r['cases']) for r in runs]))
    stable, flap_det, flap_other, partial, disagree = [], [], [], [], []
    for cid in all_ids:
        present = [r for r in runs if cid in r['cases']]
        if len(present) < len(runs):
            partial.append(cid)
        entries = [r['cases'][cid] for r in present]
        # 我用 normalized 独立重算的指纹（不依赖它的 fingerprint 字段）判稳定
        myfps = {e['my_fp'] for e in entries}
        my_stable = len(myfps) == 1
        # 顺带看它自己的 fingerprint 跨次是否也稳定；若与我的判断相反，说明两边指纹口径需对齐
        theirfps = {e['their_fp'] for e in entries if e.get('their_fp')}
        their_stable = (len(theirfps) == 1) if theirfps else my_stable
        if my_stable != their_stable:
            disagree.append(cid)
        if my_stable:
            stable.append(cid)
        else:
            stab = entries[0].get('stability')
            (flap_det if stab == 'deterministic' else flap_other).append(cid)

    print(f'\n用例 {len(all_ids)}  稳定 {len(stable)}  翻转 {len(flap_det)+len(flap_other)}'
          f'（其中 deterministic 翻转 {len(flap_det)}）  非全覆盖 {len(partial)}')

    # run_fingerprint 一致性（它的 + 我独立重算）
    their_runfps = {r['run_fp'] for r in runs}
    my_runfps = set()
    for r in runs:
        det = {cid: e['my_fp'] for cid, e in r['cases'].items() if e.get('stability') == 'deterministic'}
        my_runfps.add(fp(det))
    print(f"run_fingerprint（它）: {'一致 '+str(list(their_runfps)[0]) if len(their_runfps)==1 else '不一致 '+str(their_runfps)}")
    print(f"run_fingerprint（我独立重算 deterministic）: {'一致 '+str(list(my_runfps)[0]) if len(my_runfps)==1 else '不一致 '+str(my_runfps)}")

    if flap_det:
        print('\n[关键] deterministic 用例翻转（说明流程未固定，需按 §4.6 定因）:')
        for cid in flap_det:
            vs = ['/'.join(str(x) for x in (r['cases'][cid]['verdict'], r['cases'][cid]['normalized'].get('state') if isinstance(r['cases'][cid]['normalized'],dict) else None)) for r in runs if cid in r['cases']]
            print(f'  {cid}: ' + '  |  '.join(vs))
    if flap_other:
        print(f'\n非 deterministic 翻转（多为 environmental/volatile，需确认分类）: {", ".join(flap_other)}')
    if disagree:
        print(f'\n[注] 我与它对"是否稳定"判断不一致的用例 {len(disagree)} 个（指纹口径需对齐，非谁对谁错）: {", ".join(disagree)}')

    verdict = '流程已固定（deterministic 全稳）' if not flap_det else '流程未固定：有 deterministic 用例翻转'
    print(f'\n结论: {verdict}')

    OUT.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(BJ).strftime('%Y%m%d-%H%M%S')
    report = dict(generated_at=datetime.now(BJ).isoformat(),
                  runs=[r['run_id'] for r in runs], code=sorted(c for c in codes if c) or None,
                  env_ids=sorted(x for x in env_ids if x),
                  their_run_fingerprint=sorted(x for x in their_runfps if x),
                  my_run_fingerprint=sorted(my_runfps),
                  total=len(all_ids), stable=len(stable),
                  flapping_deterministic=flap_det, flapping_other=flap_other,
                  partial=partial, fingerprint_disagreement=disagree, verdict=verdict)
    path = OUT / f'xcheck-{ts}.json'
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'报告: {path}')
    return 0 if not flap_det else 2


if __name__ == '__main__':
    sys.exit(main())
