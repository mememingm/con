"""Layer-1 read-only MQTT protocol suite (24-MQ接口测试清单).

One MQTT connection with the dedicated tester client_id from the desktop
Broker file. Only read-only actions and deliberately invalid commands are
sent. Never publishes /ack. Evidence is written masked (ICCID/IMEI/EID/IMSI)
to .local/mq-layer1/<run>/; the password is never printed or saved.
"""
import glob
import json
import re
import sys
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import paho.mqtt.client as mqtt
from paho.mqtt.packettypes import PacketTypes
from paho.mqtt.properties import Properties

CST = timezone(timedelta(hours=8))
ROOT = Path(__file__).resolve().parents[1]
TERMINAL = {'succeeded', 'failed', 'rejected', 'expired', 'uncertain'}
CERTAINTY = {'not_started', 'known_failed', 'unknown'}
MASK_KEYS = {'iccid', 'current_iccid', 'eid', 'imsi', 'slot', 'modem_imei', 'imei'}


def load_cred():
    path = glob.glob(r'C:\Users\27792\Desktop\Broker*.txt')[0]
    f = {}
    for line in Path(path).read_text('utf-8-sig').splitlines():
        parts = re.split(r'[:\uff1a]', line, maxsplit=1)
        if len(parts) == 2:
            f[parts[0].strip().lower()] = parts[1].strip()
    host, port = re.search(r'([\d.]+):(\d+)', f['broker']).groups()
    user, pw = [s.strip() for s in f['\u8d26\u53f7'].split('/', 1)]
    return host, int(port), user, pw, f['client id'], f['\u8282\u70b9\u7f16\u53f7']


def ts(dt=None):
    return (dt or datetime.now(CST)).strftime('%Y-%m-%d %H:%M:%S')


def mask_value(v):
    if isinstance(v, str) and re.fullmatch(r'\d{10,}', v):
        return v[:4] + '*' * (len(v) - 8) + v[-4:]
    return v


def mask(o):
    if isinstance(o, dict):
        return {k: (mask_value(v) if k in MASK_KEYS else mask(v)) for k, v in o.items()}
    if isinstance(o, list):
        return [mask(x) for x in o]
    return o


class Node:
    def __init__(self):
        host, port, user, self.pw, cid, node = load_cred()
        self.prefix = f'cardpool/v1/nodes/{node}'
        self.meta = {'broker': f'{host}:{port}', 'client_id': cid, 'node': node}
        self.lock = threading.Lock()
        self.tasks, self.alarms, self.other_events, self.heartbeats, self.presence = {}, [], [], [], []
        self.cond = threading.Condition(self.lock)
        self.connected = threading.Event()
        self.c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=cid, protocol=mqtt.MQTTv5)
        self.c.username_pw_set(user, self.pw)
        self.c.on_connect = lambda c, u, f, rc, p: (self.meta.update(connack=str(rc)),
                                                    None if rc.is_failure else self.connected.set())
        self.c.on_message = self.on_message
        cp = Properties(PacketTypes.CONNECT)
        cp.SessionExpiryInterval = 0
        self.c.connect(host, port, keepalive=30, clean_start=True, properties=cp)
        self.c.loop_start()
        if not self.connected.wait(15):
            raise SystemExit(f"CONNACK failed: {self.meta.get('connack')}")
        self.c.subscribe([(f'{self.prefix}/{k}', 1) for k in ('task', 'event', 'presence', 'heartbeat')])
        time.sleep(2)

    def on_message(self, c, u, m):
        kind = m.topic.rsplit('/', 1)[-1]
        try:
            body = json.loads(m.payload.decode('utf-8'))
        except Exception:
            body = {'_raw': m.payload.decode('utf-8', 'replace')[:500]}
        rec = {'rx': ts(), 'rx_mono': time.monotonic(), 'payload': body}
        with self.cond:
            if kind == 'task':
                self.tasks.setdefault(body.get('id'), []).append(rec)
            elif kind == 'event':
                if body.get('event') == 'alarm.raised':
                    self.alarms.append(rec)
                else:  # other people's traffic: keep only type/id, never content
                    self.other_events.append({'rx': rec['rx'], 'event': body.get('event'), 'id': body.get('id')})
            elif kind == 'heartbeat':
                self.heartbeats.append(rec)
            elif kind == 'presence':
                self.presence.append(rec)
            self.cond.notify_all()

    def send(self, action, params=None, target=None, cid=None, t=None, expires=120, omit_expires=False, extra=None):
        cid = cid or str(uuid.uuid4())
        t = t or datetime.now(CST)
        cmd = {'id': cid, 'action': action, 'time': ts(t)}
        if not omit_expires:
            cmd['expires_at'] = ts(t + timedelta(seconds=expires)) if isinstance(expires, (int, float)) else expires
        if target is not None:
            cmd['target'] = target
        cmd['params'] = {} if params is None else params
        if extra:
            cmd.update(extra)
        self.publish(cmd)
        return cmd

    def publish(self, cmd):
        with self.cond:
            self.tasks.setdefault(cmd['id'], [])
        self.c.publish(f'{self.prefix}/command', json.dumps(cmd, ensure_ascii=False), qos=1)

    def final(self, cid, timeout=75):
        end = time.monotonic() + timeout
        with self.cond:
            while True:
                for r in self.tasks.get(cid, []):
                    if r['payload'].get('state') in TERMINAL:
                        return r['payload']
                left = end - time.monotonic()
                if left <= 0:
                    return None
                self.cond.wait(left)

    def msgs_since(self, cid, mono):
        with self.lock:
            return [r['payload'] for r in self.tasks.get(cid, []) if r['rx_mono'] >= mono]

    def alarms_since(self, mono):
        with self.lock:
            return [r['payload'] for r in self.alarms if r['rx_mono'] >= mono]

    def close(self):
        self.c.disconnect()
        self.c.loop_stop()


def run():
    n = Node()
    started = datetime.now(CST)
    run_id = started.strftime('%Y%m%d-%H%M%S') + '-' + uuid.uuid4().hex[:6]
    ev = ROOT / '.local' / 'mq-layer1' / run_id
    ev.mkdir(parents=True, exist_ok=True)
    cases, commands = [], []

    def log(s):
        print(f'{ts()} {s}', flush=True)

    def record(t_ids, verdict, summary, task_ids, detail=None):
        cases.append({'t': t_ids, 'verdict': verdict, 'summary': summary, 'task_ids': task_ids,
                      'time': ts(), 'detail': mask(detail) if detail is not None else None})
        log(f'[{verdict}] {t_ids}: {summary} ids={task_ids}')

    def call(action, params=None, target=None, timeout=75, **kw):
        cmd = n.send(action, params, target, **kw)
        commands.append(cmd)
        return cmd, n.final(cmd['id'], timeout)

    def err(f):
        return (f or {}).get('error') or {}

    def paginate(action, params):
        pages, items = [], []
        cursor = None
        for _ in range(40):
            p = dict(params)
            if cursor:
                p['cursor'] = cursor
            cmd, f = call(action, p)
            pages.append({'id': cmd['id'], 'final': f})
            if not f or f.get('state') != 'succeeded':
                break
            r = f.get('result') or {}
            items.extend(r.get('items') or [])
            if r.get('complete'):
                break
            cursor = r.get('cursor')
            if not cursor:
                break
        return pages, items

    # ---------- baseline ----------
    base_cmd, base = call('node.describe', expires=30)
    caps = (base or {}).get('result', {}).get('capabilities') or []
    record('node.describe/success', 'pass' if base and base.get('state') == 'succeeded' else 'fail',
           f"state={(base or {}).get('state')} caps={len(caps)} version={(base or {}).get('result', {}).get('software_version')}",
           [base_cmd['id']], base)
    base_final_seq = (base or {}).get('seq')

    # T-43 cursor taken early, used after >5 min
    c43, f43 = call('phones.list', {'page_size': 10})
    cursor43 = ((f43 or {}).get('result') or {}).get('cursor')
    t43 = time.monotonic()

    inv_pages, inv_items = paginate('inventory.get', {'page_size': 100})
    inv_last = (inv_pages[-1]['final'] or {}).get('result') or {}
    inv_imeis = {i.get('slot') for i in inv_items}
    inv_ok = all((p['final'] or {}).get('state') == 'succeeded' for p in inv_pages) and inv_last.get('complete') is True
    record('inventory.get/success', 'pass' if inv_ok else 'fail',
           f'pages={len(inv_pages)} items={len(inv_items)} distinct_imei={len(inv_imeis)} complete={inv_last.get("complete")}',
           [p['id'] for p in inv_pages], {'first_item': inv_items[:1]})
    src = {i.get('source') for i in [inv_last]}
    pc = sorted({str(i.get('profiles_complete')) for i in inv_items})
    record('T-48', 'pass' if inv_last.get('source') == 'registry' else 'info',
           f"inventory.get source={inv_last.get('source')} profiles_complete值={pc}（清单记为已知实现差异）",
           [p['id'] for p in inv_pages])

    pl_pages, pl_items = paginate('phones.list', {'page_size': 100})
    pl_ok = all((p['final'] or {}).get('state') == 'succeeded' for p in pl_pages)
    pl_last = (pl_pages[-1]['final'] or {}).get('result') or {}
    empty = [i for i in pl_items if (i.get('target') or {}).get('iccid') in ('', None)]
    real = [i for i in pl_items if (i.get('target') or {}).get('iccid')]
    record('phones.list/success', 'pass' if pl_ok and pl_last.get('complete') else 'fail',
           f'items={len(pl_items)} real={len(real)} empty={len(empty)} source={pl_last.get("source")} complete={pl_last.get("complete")}',
           [p['id'] for p in pl_pages])
    bad_empty = [i for i in empty if not (i['target'].get('slot') and i['target'].get('phone') is None
                                          and i.get('available') is False and i.get('reason') == '空卡，无 Profile')]
    other_reason = sorted({i.get('reason') for i in empty})
    if not empty:
        record('T-37', 'untested', '默认 phones.list 未返回空卡行（现场无空卡可供验证）', [p['id'] for p in pl_pages])
    else:
        record('T-37', 'pass' if not bad_empty else 'fail',
               f'空卡行 {len(empty)} 条，格式不符 {len(bad_empty)} 条；reason 取值={other_reason}',
               [p['id'] for p in pl_pages], {'sample_empty': empty[:2], 'bad': bad_empty[:3]})

    ne_pages, ne_items = paginate('phones.list', {'page_size': 100, 'include_empty_slots': False})
    ne_empty = [i for i in ne_items if not (i.get('target') or {}).get('iccid')]
    ne_ok = all((p['final'] or {}).get('state') == 'succeeded' for p in ne_pages)
    record('T-39', 'pass' if ne_ok and not ne_empty and len(ne_items) == len(real) else 'fail',
           f'include_empty_slots=false 返回 {len(ne_items)} 条，其中空卡 {len(ne_empty)}；默认查询真实行 {len(real)}',
           [p['id'] for p in ne_pages])

    p10_pages, p10_items = paginate('phones.list', {'page_size': 10})
    per_page = []
    for p in p10_pages:
        r = (p['final'] or {}).get('result') or {}
        per_page.append({'id': p['id'], 'n': len(r.get('items') or []), 'complete': r.get('complete'),
                         'cursor_null': r.get('cursor') is None, 'source': r.get('source'),
                         'distinct_slot': len({(i.get('target') or {}).get('slot') for i in r.get('items') or []})})
    mid_ok = all(pp['complete'] is False and not pp['cursor_null'] for pp in per_page[:-1])
    last_ok = per_page and per_page[-1]['complete'] is True and per_page[-1]['cursor_null']
    record('T-44', 'pass' if mid_ok and last_ok else 'fail',
           f'page_size=10 共 {len(per_page)} 页；中间页 complete=false 且 cursor 非空={mid_ok}；末页 complete=true 且 cursor=null={bool(last_ok)}',
           [pp['id'] for pp in per_page], per_page)
    sum_distinct = sum(pp['distinct_slot'] for pp in per_page)
    all_distinct = len({(i.get('target') or {}).get('slot') for i in p10_items})
    record('T-46', 'pass', f'各页去重 slot 数相加={sum_distinct}，全量去重={all_distinct}，差={sum_distinct - all_distinct}（记录用，判据是两种口径必须区分）',
           [pp['id'] for pp in per_page])
    pl_slots = {(i.get('target') or {}).get('slot') for i in pl_items}
    missing, extra = inv_imeis - pl_slots, pl_slots - inv_imeis
    record('T-45', 'pass' if inv_ok and pl_ok and not missing and not extra else 'fail',
           f'inventory IMEI={len(inv_imeis)} phones.list 去重 slot={len(pl_slots)} missing={len(missing)} extra={len(extra)}',
           [p['id'] for p in inv_pages] + [p['id'] for p in pl_pages],
           {'missing': sorted(missing), 'extra': sorted(extra)})
    srcs = {pp['source'] for pp in per_page} | {pl_last.get('source')}
    record('T-47a', 'pass' if srcs == {'hardware'} else 'fail', f'新查询 source 取值={sorted(map(str, srcs))}',
           [pp['id'] for pp in per_page])
    m_cmd, m = call('phones.list', {'page_size': 10, 'mode': 'cache'})
    record('T-47b', 'pass' if m and m.get('state') == 'rejected' and err(m).get('code') == 'INVALID_ARGUMENT' else 'fail',
           f"带 mode 参数 → state={(m or {}).get('state')} code={err(m).get('code')}", [m_cmd['id']], m)

    # T-40: switch include_empty_slots mid-pagination
    a_cmd, a = call('phones.list', {'page_size': 10})
    cur = ((a or {}).get('result') or {}).get('cursor')
    if cur:
        b_cmd, b = call('phones.list', {'page_size': 10, 'cursor': cur, 'include_empty_slots': False})
        record('T-40', 'pass' if b and b.get('state') == 'rejected' else 'fail',
               f"分页中途改 include_empty_slots → state={(b or {}).get('state')} code={err(b).get('code')}",
               [a_cmd['id'], b_cmd['id']], b)
    else:
        record('T-40', 'untested', '首页无 cursor（总条数 ≤10），无法测分页切换', [a_cmd['id']])

    # ---------- idempotency ----------
    mono = time.monotonic()
    n.publish(dict(base_cmd))
    time.sleep(8)
    replay = n.msgs_since(base_cmd['id'], mono)
    seqs = [r.get('seq') for r in replay]
    rerun = [r for r in replay if r.get('state') in ('accepted', 'running')]
    grew = [s for s in seqs if isinstance(s, int) and base_final_seq and s > base_final_seq]
    record('T-01', 'pass' if replay and not rerun and not grew else 'fail',
           f'同 ID 同内容重投 → 收到 {len(replay)} 条回放 seq={seqs} states={[r.get("state") for r in replay]}（原最终 seq={base_final_seq}）',
           [base_cmd['id']], replay)

    def conflict_case(tid, orig, changed, what):
        mono = time.monotonic()
        n.publish(changed)
        time.sleep(8)
        al = [a for a in n.alarms_since(mono) if ((a.get('data') or {}).get('details') or {}).get('command') == orig['id']]
        codes = [(a.get('data') or {}).get('code') for a in al]
        after = n.msgs_since(orig['id'], mono)
        polluted = [r for r in after if r.get('state') in ('accepted', 'running')]
        ok = 'IDEMPOTENCY_CONFLICT' in codes and not polluted
        record(tid, 'pass' if ok else 'fail',
               f'同 ID 仅改{what} → alarm codes={codes}；原任务随后回传 {len(after)} 条 states={[r.get("state") for r in after]}',
               [orig['id']], {'alarms': al, 'task_msgs_after': after})

    changed = dict(base_cmd)
    changed['expires_at'] = ts(datetime.strptime(base_cmd['expires_at'], '%Y-%m-%d %H:%M:%S') + timedelta(hours=1))
    conflict_case('T-02', base_cmd, changed, ' expires_at')
    ne_first = [c for c in commands if c['id'] == ne_pages[0]['id']][0]
    changed = json.loads(json.dumps(ne_first))
    changed['params']['page_size'] = 50
    conflict_case('T-03', ne_first, changed, ' params.page_size')

    g_cmd, g = call('task.get', {'id': base_cmd['id']})
    gt = ((g or {}).get('result') or {}).get('task') or {}
    ok = g and g.get('state') == 'succeeded' and gt.get('id') == base_cmd['id'] and gt.get('state') == 'succeeded'
    record('T-04', 'pass' if ok else 'fail',
           f"task.get(新 ID) 查原任务 → state={(g or {}).get('state')} 原任务 id 匹配={gt.get('id') == base_cmd['id']} 原任务 state={gt.get('state')} seq={gt.get('seq')}",
           [g_cmd['id'], base_cmd['id']], g)
    x_cmd, x = call('task.get', {'id': str(uuid.uuid4())})
    record('T-05', 'pass' if x and err(x).get('code') == 'TASK_NOT_FOUND' else 'fail',
           f"查不存在的任务 → state={(x or {}).get('state')} code={err(x).get('code')}", [x_cmd['id']], x)

    # ---------- expires_at ----------
    for action, params in (('node.describe', {}), ('phones.list', {'page_size': 1})):
        c, f = call(action, params, omit_expires=True, timeout=30)
        record('T-16', 'pass' if f and f.get('state') == 'rejected' else ('fail' if f else 'fail'),
               f"{action} 缺 expires_at → state={(f or {}).get('state')} code={err(f).get('code')}", [c['id']], f)
    now = datetime.now(CST)
    c, f = call('node.describe', t=now, expires=ts(now), timeout=30)
    record('T-17', 'pass' if f and f.get('state') == 'rejected' else 'fail',
           f"expires_at == time → state={(f or {}).get('state')} code={err(f).get('code')}", [c['id']], f)
    past = datetime.now(CST) - timedelta(minutes=10)
    c, f = call('phones.list', {'page_size': 1}, t=past, expires=ts(past + timedelta(minutes=5)), timeout=30)
    ok = f and f.get('state') in ('rejected', 'expired') and f.get('result') is None
    record('T-18', 'pass' if ok else 'fail',
           f"发送时已过期 → state={(f or {}).get('state')} code={err(f).get('code')} certainty={err(f).get('certainty')} result 为空={(f or {}).get('result') is None}",
           [c['id']], f)

    # ---------- rejection paths ----------
    rows_phone = [i for i in real if (i.get('target') or {}).get('phone')]
    if rows_phone:
        t0 = dict(rows_phone[0]['target'])
        c, f = call('phones.check', {}, {k: t0[k] for k in ('device', 'slot', 'phone', 'binding_version') if k in t0})
        record('phones.check/success', 'pass' if f and f.get('state') == 'succeeded' else 'fail',
               f"state={(f or {}).get('state')} available={((f or {}).get('result') or {}).get('available')} tunnel_state={((f or {}).get('result') or {}).get('tunnel_state')}",
               [c['id']], f)
        tgt = {k: t0[k] for k in ('device', 'slot', 'binding_version') if k in t0}
        tgt['phone'] = '+10000000000'
        c, f = call('phones.check', {}, tgt)
        record('T-50', 'pass' if err(f).get('code') == 'PHONE_NOT_FOUND' else 'fail',
               f"不存在的手机号 → state={(f or {}).get('state')} code={err(f).get('code')}", [c['id']], f)
        same_slot = [i for i in real if i['target'].get('slot') == t0.get('slot') and i['target'].get('iccid') != t0.get('iccid')]
        other = (same_slot or [i for i in real if i['target'].get('iccid') != t0.get('iccid')])
        if other:
            tgt = {k: t0[k] for k in ('device', 'slot', 'phone', 'binding_version') if k in t0}
            tgt['iccid'] = other[0]['target']['iccid']
            c, f = call('phones.check', {}, tgt)
            record('T-52', 'pass' if err(f).get('code') == 'TARGET_MISMATCH' else 'fail',
                   f"phone 与 iccid 不匹配（{'同槽' if same_slot else '跨槽'}另一 ICCID）→ state={(f or {}).get('state')} code={err(f).get('code')}",
                   [c['id']], f)
        else:
            record('T-52', 'untested', '只有一个真实 ICCID，无法构造不匹配对', [])
        slot_t = {k: t0[k] for k in ('device', 'slot') if k in t0}
        c, f = call('slot.refresh', {}, slot_t, timeout=90)
        record('slot.refresh/success', 'pass' if f and f.get('state') == 'succeeded' else 'fail',
               f"state={(f or {}).get('state')} slot.state={(((f or {}).get('result') or {}).get('slot') or {}).get('state')} profiles={len((((f or {}).get('result') or {}).get('slot') or {}).get('profiles') or [])}",
               [c['id']], f)
        c, f = call('esim.profiles.list', {}, slot_t, timeout=90)
        r = (f or {}).get('result') or {}
        record('esim.profiles.list/success', 'pass' if f and f.get('state') == 'succeeded' and r.get('complete') is True else 'fail',
               f"state={(f or {}).get('state')} profiles={len(r.get('profiles') or [])} complete={r.get('complete')}", [c['id']], f)
    else:
        for tid in ('phones.check/success', 'T-50', 'T-52', 'slot.refresh/success', 'esim.profiles.list/success'):
            record(tid, 'untested', 'phones.list 中没有带号码的行', [])

    phones = [i['target'].get('phone') for i in real if i['target'].get('phone')]
    dups = sorted({p for p in phones if phones.count(p) > 1})
    record('T-51', 'untested' if not dups else 'info',
           '现场没有对应多个 Profile 的手机号，无法构造' if not dups else f'存在重复号码 {len(dups)} 个，待单独测试', [])

    c, f = call('foo.bar', {}, timeout=30)
    record('T-55', 'pass' if err(f).get('code') == 'UNSUPPORTED_ACTION' else 'fail',
           f"未知 action → state={(f or {}).get('state')} code={err(f).get('code')}", [c['id']], f)
    c, f = call('sms.list', {}, timeout=30)
    record('T-27', 'pass' if err(f).get('code') == 'UNSUPPORTED_ACTION' else 'fail',
           f"sms.list → state={(f or {}).get('state')} code={err(f).get('code')}", [c['id']], f)
    for bad in ({'page_size': 'abc'}, {'page_size': 0}, {'page_size': 101}, {'page_sise': 10}):
        c, f = call('phones.list', bad, timeout=30)
        record('T-56', 'pass' if err(f).get('code') == 'INVALID_ARGUMENT' else 'fail',
               f"params={bad} → state={(f or {}).get('state')} code={err(f).get('code')}", [c['id']], f)

    # T-42 consistency observation
    inconsistent = [i for i in pl_items if (i.get('available') is True and (i.get('tunnel_state') != 'registered' or i.get('reason')))
                    or (i.get('available') is False and not i.get('reason'))]
    avail = sum(1 for i in pl_items if i.get('available') is True)
    record('T-42', 'partial', f'available=true {avail} 条；字段一致性违例 {len(inconsistent)} 条（仅验一致性，四项门槛内部状态未独立核实）',
           [p['id'] for p in pl_pages], inconsistent[:3])

    # ---------- T-21 after base expires ----------
    exp = datetime.strptime(base_cmd['expires_at'], '%Y-%m-%d %H:%M:%S').replace(tzinfo=CST)
    wait = (exp - datetime.now(CST)).total_seconds() + 3
    if wait > 0:
        time.sleep(wait)
    mono = time.monotonic()
    n.publish(dict(base_cmd))
    time.sleep(8)
    rp = n.msgs_since(base_cmd['id'], mono)
    ok = rp and all(r.get('state') == 'succeeded' for r in rp)
    record('T-21', 'pass' if ok else 'fail',
           f'原任务 expires_at 已过后同 ID 同内容重投 → states={[r.get("state") for r in rp]}', [base_cmd['id']], rp)

    # ---------- T-43 cursor expiry ----------
    if cursor43:
        wait = 310 - (time.monotonic() - t43)
        if wait > 0:
            log(f'waiting {int(wait)}s for T-43 cursor expiry')
            time.sleep(wait)
        c, f = call('phones.list', {'page_size': 10, 'cursor': cursor43}, timeout=30)
        record('T-43', 'pass' if err(f).get('code') == 'CURSOR_EXPIRED' else 'fail',
               f"游标取得 {int(time.monotonic() - t43)}s 后使用 → state={(f or {}).get('state')} code={err(f).get('code')}",
               [c43['id'], c['id']], f)
    else:
        record('T-43', 'untested', '首页没有 cursor', [c43['id']])

    # ---------- T-57 certainty over all error replies ----------
    with n.lock:
        errs = [(tid, r['payload']) for tid, rs in n.tasks.items() for r in rs if r['payload'].get('error')]
    bad = [(tid, p['error']) for tid, p in errs if (p['error'] or {}).get('certainty') not in CERTAINTY]
    record('T-57', 'pass' if errs and not bad else 'fail',
           f'全部 {len(errs)} 条带 error 的回包中 certainty 缺失/非法 {len(bad)} 条；取值={sorted({(p["error"] or {}).get("certainty") for _, p in errs}, key=str)}',
           sorted({tid for tid, _ in errs}), bad[:5])

    # ---------- T-64 heartbeat observation ----------
    hb = [r for r in n.heartbeats]
    gaps = [round(b['rx_mono'] - a['rx_mono'], 1) for a, b in zip(hb, hb[1:])]
    record('T-64', 'partial', f'心跳 {len(hb)} 条，间隔秒={gaps[:12]}；presence retained={[p["payload"].get("online") for p in n.presence]}（90s stale 判定属业务端逻辑，未测）',
           [], {'last_heartbeat': hb[-1]['payload'] if hb else None})

    n.close()
    out = {'run_id': run_id, 'started': ts(started), 'finished': ts(), 'meta': n.meta,
           'cases': cases, 'commands': mask(commands),
           'task_messages': mask({k: [r['payload'] for r in v] for k, v in n.tasks.items()}),
           'alarms': mask([r['payload'] for r in n.alarms]), 'other_events': n.other_events,
           'phones_list_default': mask(pl_items), 'inventory': mask(inv_items)}
    text = json.dumps(out, ensure_ascii=False, indent=2)
    assert n.pw not in text
    (ev / 'results.json').write_text(text, 'utf-8')
    log(f'evidence: {ev}\\results.json')
    return 0


if __name__ == '__main__':
    sys.exit(run())
