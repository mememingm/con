"""MQ layer-1 read-only protocol tests (24-MQ接口测试清单), declarative and repeatable.

Cases live in cases/mq_layer1_cases.json. This module only reads cases, executes them
through a small set of generic procedures, collects each case's own replies, and hands
the observation to judge(). Adding or removing a case does not touch this code as long
as it uses an existing procedure.

One MQTT connection with the dedicated tester client_id (desktop Broker file). Only
read-only actions and deliberately invalid commands are sent; /ack is never published.
Evidence is masked (ICCID/IMEI/EID) and written to .local/mq-layer1/; the password is
never printed or saved.

  python mq_layer1.py [--skip-t43]            one run
  python mq_layer1.py --repeat 5 [--interval 10] [--include-t43]
"""
import argparse
import copy
import glob
import hashlib
import json
import os
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
ROOT = Path(__file__).resolve().parent
CASES_FILE = ROOT / 'cases' / 'mq_layer1_cases.json'
EVIDENCE = ROOT / '.local' / 'mq-layer1'
BROKER_CREDENTIALS = os.environ.get('MQ_BROKER_CREDENTIALS', r'C:\Users\27792\Desktop\Broker*.txt')
TERMINAL = {'succeeded', 'failed', 'rejected', 'expired', 'uncertain'}
CERTAINTY = {'not_started', 'known_failed', 'unknown'}
MASK_KEYS = {'iccid', 'current_iccid', 'eid', 'imsi', 'slot', 'modem_imei', 'imei'}
STABILITY = {'deterministic', 'environmental', 'volatile'}
PROCEDURES = {}
VERDICTS = ('pass', 'fail', 'untested', 'insufficient', 'partial')


# ---------------------------------------------------------------- helpers
def ts(dt=None):
    return (dt or datetime.now(CST)).strftime('%Y-%m-%d %H:%M:%S')


def parse_ts(s):
    return datetime.strptime(s, '%Y-%m-%d %H:%M:%S').replace(tzinfo=CST)


def mask_value(v):
    if isinstance(v, str) and re.fullmatch(r'\d{10,}', v):
        return v[:4] + '*' * (len(v) - 8) + v[-4:]
    return v


def mask_text(s):
    return re.sub(r'(?<![\d+])(\d{4})(\d{6,})(\d{4})(?!\d)', lambda m: m[1] + '*' * len(m[2]) + m[3], s)


def mask(o):
    if isinstance(o, str):
        return mask_text(o)
    if isinstance(o, dict):  # recurse first: result.slot is itself a record holding IMEI/ICCID
        return {k: (mask_value(v) if k in MASK_KEYS and not isinstance(v, (dict, list)) else mask(v)) for k, v in o.items()}
    if isinstance(o, list):
        return [mask(x) for x in o]
    return o


def sha(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def code_sha256():
    parts = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (Path(__file__).resolve(), CASES_FILE)}
    combined = sha(''.join(parts[k] for k in sorted(parts)))
    return combined, parts


def dig(obj, path):
    """'result.slot.state' -> nested value, or None."""
    cur = obj
    for part in path.split('.'):
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    return cur


def load_cases(path=CASES_FILE):
    data = json.loads(Path(path).read_text('utf-8'))
    return data['cases']


def validate_cases(cases):
    """Return a list of problems; empty means the case file is well-formed."""
    problems, seen = [], set()
    for c in cases:
        cid = c.get('id', '?')
        for key in ('id', 'layer', 'action', 'procedure', 'path', 'expect', 'stability'):
            if key not in c:
                problems.append(f'{cid}: missing {key}')
        if cid in seen:
            problems.append(f'{cid}: duplicate id')
        seen.add(cid)
        if c.get('stability') not in STABILITY:
            problems.append(f'{cid}: bad stability {c.get("stability")}')
        if c.get('depends_on'):
            problems.append(f'{cid}: depends_on must be empty')
        if c.get('procedure') not in PROCEDURES:
            problems.append(f'{cid}: unknown procedure {c.get("procedure")}')
        if 'target' in c and c['target'].get('binding_version') != 1:
            problems.append(f'{cid}: target without binding_version=1')
        if c.get('path') not in ('success', 'reject', 'boundary', 'none'):
            problems.append(f'{cid}: bad path {c.get("path")}')
    return problems


def load_cred():
    matches = glob.glob(BROKER_CREDENTIALS)
    if not matches:
        raise RuntimeError(f'找不到业务端 MQTT 凭据文件：{BROKER_CREDENTIALS}')
    f = {}
    for line in Path(matches[0]).read_text('utf-8-sig').splitlines():
        parts = re.split(r'[:\uff1a]', line, maxsplit=1)
        if len(parts) == 2:
            f[parts[0].strip().lower()] = parts[1].strip()
    host, port = re.search(r'([\d.]+):(\d+)', f['broker']).groups()
    user, pw = [s.strip() for s in f['\u8d26\u53f7'].split('/', 1)]
    return host, int(port), user, pw, f['client id'], f['\u8282\u70b9\u7f16\u53f7']


# ---------------------------------------------------------------- MQTT node
class Node:
    def __init__(self):
        host, port, user, self.pw, cid, node = load_cred()
        self.prefix = f'cardpool/v1/nodes/{node}'
        self.meta = {'broker': f'{host}:{port}', 'client_id': cid, 'node': node}
        self.lock = threading.Lock()
        self.cond = threading.Condition(self.lock)
        self.tasks, self.alarms, self.other_events, self.heartbeats, self.presence = {}, [], [], [], []
        self.own_ids = set()
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
            self.c.loop_stop()
            raise RuntimeError(f"MQTT 连接失败：CONNACK={self.meta.get('connack')}")
        self.c.subscribe([(f'{self.prefix}/{k}', 1) for k in ('task', 'event', 'presence', 'heartbeat')])
        time.sleep(2)

    def on_message(self, c, u, m):
        kind = m.topic.rsplit('/', 1)[-1]
        try:
            body = json.loads(m.payload.decode('utf-8'))
        except Exception:
            body = {'_raw': m.payload.decode('utf-8', 'replace')[:500]}
        rec = {'rx': ts(), 'mono': time.monotonic(), 'retain': m.retain, 'payload': body}
        with self.cond:
            if kind == 'task':
                self.tasks.setdefault(body.get('id'), []).append(rec)
            elif kind == 'event' and body.get('event') == 'alarm.raised':
                self.alarms.append(rec)
            elif kind == 'event':  # other traffic: type/id only, never content
                self.other_events.append({'rx': rec['rx'], 'event': body.get('event'), 'id': body.get('id')})
            elif kind == 'heartbeat':
                self.heartbeats.append(rec)
            elif kind == 'presence':
                self.presence.append(rec)
            self.cond.notify_all()

    def publish(self, cmd):
        with self.cond:
            self.tasks.setdefault(cmd['id'], [])
            self.own_ids.add(cmd['id'])
        self.c.publish(f'{self.prefix}/command', json.dumps(cmd, ensure_ascii=False), qos=1)

    def final(self, cid, timeout):
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

    def since(self, cid, mono):
        with self.lock:
            return [r['payload'] for r in self.tasks.get(cid, []) if r['mono'] >= mono]

    def alarms_since(self, mono):
        with self.lock:
            return [r['payload'] for r in self.alarms if r['mono'] >= mono]

    def close(self):
        self.c.disconnect()
        self.c.loop_stop()


# ---------------------------------------------------------------- run context
class Ctx:
    """Everything a procedure needs: the node, deterministic targets and a command log."""

    def __init__(self, node, options):
        self.n, self.options, self.commands, self.vars, self.env = node, options, [], {}, {}

    def command(self, action, params=None, target=None, cid=None, time_offset_s=0, expires_offset_s=120,
                omit_expires=False):
        t = datetime.now(CST) + timedelta(seconds=time_offset_s)
        cmd = {'id': cid or str(uuid.uuid4()), 'action': action, 'time': ts(t)}
        if not omit_expires:
            cmd['expires_at'] = ts(t + timedelta(seconds=expires_offset_s))
        if target is not None:
            cmd['target'] = target
        cmd['params'] = {} if params is None else params
        return cmd

    def send(self, cmd, timeout=75):
        self.commands.append(cmd)
        self.n.publish(cmd)
        return self.n.final(cmd['id'], timeout)

    def resolve(self, value, slot=None):
        """Replace '$row.phone', '$slot.device', '$new_uuid' ... inside templates."""
        if isinstance(value, dict):
            return {k: self.resolve(v, slot) for k, v in value.items()}
        if isinstance(value, list):
            return [self.resolve(v, slot) for v in value]
        if isinstance(value, str) and value.startswith('$'):
            if value == '$new_uuid':
                return str(uuid.uuid4())
            name, _, field = value[1:].partition('.')
            src = slot if name == 'slot' else self.vars.get(name)
            return (src or {}).get(field)
        return value

    def paginate(self, action, params):
        pages, items, cursor = [], [], None
        for _ in range(40):
            p = dict(params)
            if cursor:
                p['cursor'] = cursor
            cmd = self.command(action, p)
            f = self.send(cmd)
            pages.append((cmd['id'], f))
            if not f or f.get('state') != 'succeeded':
                break
            r = f.get('result') or {}
            items.extend(r.get('items') or [])
            if r.get('complete') or not r.get('cursor'):
                break
            cursor = r.get('cursor')
        return pages, items


def setup(ctx):
    """Environment probe (not a case): node online, deterministic targets, environment snapshot."""
    f = ctx.send(ctx.command('node.describe'))
    online = bool(f and f.get('state') == 'succeeded')
    desc = (f or {}).get('result') or {}
    pages, rows = ctx.paginate('phones.list', {'page_size': 100})
    inv_pages, inv = ctx.paginate('inventory.get', {'page_size': 100})
    key = lambda r: (str(r['target'].get('device')), str(r['target'].get('slot')), str(r['target'].get('iccid')))
    rows = sorted(rows, key=key)
    real = [r for r in rows if r['target'].get('iccid')]
    phone_rows = [r for r in real if r['target'].get('phone') and r.get('available') is True]
    row = phone_rows[0]['target'] if phone_rows else None
    ctx.vars['row'] = row
    other = [r['target'] for r in real if row and r['target'].get('slot') == row.get('slot')
             and r['target'].get('iccid') != row.get('iccid')]
    ctx.vars['other'] = other[0] if other else None
    phones = [r['target'].get('phone') for r in real if r['target'].get('phone')]
    dup = sorted({p for p in phones if phones.count(p) > 1})
    ctx.vars['dup'] = next((r['target'] for r in real if dup and r['target'].get('phone') == dup[0]), None)
    slots = []
    for r in real:
        s = {'device': r['target'].get('device'), 'slot': r['target'].get('slot')}
        if s not in slots:
            slots.append(s)
    ctx.vars['slots'] = slots
    ctx.env = {'rows': rows, 'real': real, 'inventory': inv}
    probe_errors = [(f or {}).get('error') for _, f in pages + inv_pages if not f or f.get('state') != 'succeeded']
    ctx.pre = {
        'node_online': online,
        'env_probe_ok': not probe_errors,
        'has_phone_row': row is not None,
        'has_same_slot_pair': bool(other),
        'has_dup_phone': bool(dup),
        'has_empty_slot': any(not r['target'].get('iccid') for r in rows),
        'multi_page': len(rows) > 10,
    }
    snapshot = {
        'software_version': desc.get('software_version'),
        'capabilities': sorted(desc.get('capabilities') or []),
        'lines': sorted((str(r['target'].get('device')), sha(str(r['target'].get('slot')))[:12],
                         sha(str(r['target'].get('iccid')))[:12], r['target'].get('phone'),
                         r.get('available'), r.get('tunnel_state')) for r in rows),
        'modules': sorted((str(i.get('device')), sha(str(i.get('slot')))[:12]) for i in inv),
    }
    summary = {'modules': len(inv), 'lines': len(rows), 'real_lines': len(real),
               'empty_slots': len(rows) - len(real), 'available': sum(1 for r in rows if r.get('available') is True),
               'software_version': desc.get('software_version')}
    return {'environment_snapshot_id': sha(json.dumps(snapshot, sort_keys=True, ensure_ascii=False))[:16],
            'environment_summary': summary,
            'selected_targets': mask({'row': row, 'other': ctx.vars['other'], 'slots': slots}),
            'preconditions': ctx.pre,
            'env_probe_errors': mask(probe_errors),
            'setup_task_ids': [f and f.get('id')] + [p[0] for p in pages + inv_pages],
            'environment_rows': mask(rows)}


# ---------------------------------------------------------------- procedures
def procedure(name):
    def deco(fn):
        PROCEDURES[name] = fn
        return fn
    return deco


def _final_obs(f, case):
    err = (f or {}).get('error') or {}
    obs = {'state': (f or {}).get('state'), 'error.code': err.get('code'), 'error.certainty': err.get('certainty'),
           'result.present': (f or {}).get('result') is not None}
    for key, spec in (case.get('observe') or {}).items():
        if spec.startswith('len:'):
            v = dig(f or {}, spec[4:])
            obs[key] = len(v) if isinstance(v, list) else None
        else:
            obs[key] = dig(f or {}, spec)
    return obs


@procedure('single')
def p_single(ctx, case, slot=None):
    cmd = ctx.command(case['action'], ctx.resolve(case.get('params', {}), slot),
                      ctx.resolve(case['target'], slot) if 'target' in case else None,
                      time_offset_s=case.get('time_offset_s', 0), expires_offset_s=case.get('expires_offset_s', 120),
                      omit_expires=case.get('omit_expires', False))
    f = ctx.send(cmd, case.get('timeout_s', 75))
    return {'observed': _final_obs(f, case), 'task_ids': [cmd['id']], 'complete': f is not None,
            'evidence': {'final': f}}


@procedure('paginate')
def p_paginate(ctx, case, slot=None):
    pages, items = ctx.paginate(case['action'], case.get('params', {}))
    finals = [f for _, f in pages]
    results = [(f or {}).get('result') or {} for f in finals]
    lines = [i for i in items if isinstance(i.get('target'), dict)]  # phones.list rows; inventory rows have no target
    empty = [i for i in lines if not i['target'].get('iccid')]
    slot_of = lambda i: (i.get('target') or {}).get('slot') or i.get('slot')
    per_page_distinct = [len({slot_of(i) for i in r.get('items') or []}) for r in results]
    obs = {
        'all_succeeded': all(f and f.get('state') == 'succeeded' for f in finals),
        'complete_last': bool(results and results[-1].get('complete') is True and results[-1].get('cursor') is None),
        'mid_pages_ok': all(r.get('complete') is False and r.get('cursor') for r in results[:-1]),
        'sources': sorted({str(r.get('source')) for r in results}),
        'empty_rows': len(empty),
        'empty_rows_format_ok': all(i['target'].get('slot') and i['target'].get('phone') is None
                                    and i.get('available') is False and i.get('reason') == '空卡，无 Profile' for i in empty),
        'row_count_matches_env': len(items) == len(ctx.env.get('real', [])),
        'availability_consistent': all(
            (i.get('available') is True and i.get('tunnel_state') == 'registered' and not i.get('reason'))
            or (i.get('available') is False and i.get('reason')) for i in items if 'available' in i),
        'profiles_complete_values': sorted({i.get('profiles_complete') for i in items if 'profiles_complete' in i}, key=str),
    }
    if 'double_count' in case.get('observe_extra', []):
        obs['double_count'] = sum(per_page_distinct) - len({slot_of(i) for i in items})
    stuck = next((f for f in finals if f and f.get('state') != 'succeeded'), None)
    if stuck:
        obs['error.code'] = ((stuck.get('error') or {}).get('code'))
    return {'observed': obs, 'task_ids': [i for i, _ in pages], 'complete': all(f is not None for f in finals),
            'evidence': {'pages': len(pages), 'items': len(items), 'first_error': (stuck or {}).get('error')}}


def _origin(ctx, case):
    o = case['origin']
    cmd = ctx.command(o['action'], o.get('params', {}), expires_offset_s=o.get('expires_offset_s', 120))
    f = ctx.send(cmd)
    if f is not None:  # let the whole original seq stream arrive before re-publishing
        end = time.monotonic() + 5
        while time.monotonic() < end and set(range(1, (f.get('seq') or 0) + 1)) - {
                r.get('seq') for r in ctx.n.since(cmd['id'], 0)}:
            time.sleep(0.2)
        time.sleep(1)
    return cmd, f


def _changed_states(ctx, cid, final, window):
    """Messages in window that are NOT a faithful retransmission: a seq beyond the original final
    seq, or an existing seq whose state/result/error differs from its first-seen content."""
    first = {}
    for r in ctx.n.since(cid, 0):
        first.setdefault(r.get('seq'), r)
    body = lambda r: json.dumps([r.get('state'), r.get('result'), r.get('error')], sort_keys=True, ensure_ascii=False)
    return [r for r in window if not isinstance(r.get('seq'), int) or r['seq'] > (final.get('seq') or 0)
            or body(r) != body(first[r['seq']])]


@procedure('replay')
def p_replay(ctx, case, slot=None):
    cmd, f = _origin(ctx, case)
    if f is None:
        return {'observed': {'origin_state': None}, 'task_ids': [cmd['id']], 'complete': False, 'evidence': {}}
    if case.get('replay_after_expiry'):
        time.sleep(max(0, (parse_ts(cmd['expires_at']) - datetime.now(CST)).total_seconds() + 3))
    mono = time.monotonic()
    ctx.n.publish(copy.deepcopy(cmd))
    time.sleep(case.get('window_s', 8))
    replay = ctx.n.since(cmd['id'], mono)
    seqs = [r.get('seq') for r in replay if isinstance(r.get('seq'), int)]
    obs = {'origin_state': f.get('state'), 'replay_received': bool(replay),
           'new_execution': bool(_changed_states(ctx, cmd['id'], f, replay)),
           'seq_grew': any(s > (f.get('seq') or 0) for s in seqs),
           'replay_states': sorted({str(r.get('state')) for r in replay})}
    return {'observed': obs, 'task_ids': [cmd['id']], 'complete': True,
            'evidence': {'replay_seqs': [(r.get('seq'), r.get('state')) for r in replay]}}


@procedure('conflict')
def p_conflict(ctx, case, slot=None):
    cmd, f = _origin(ctx, case)
    if f is None:
        return {'observed': {'origin_state': None}, 'task_ids': [cmd['id']], 'complete': False, 'evidence': {}}
    changed = copy.deepcopy(cmd)
    m = case.get('mutate', {})
    if 'expires_at_shift_s' in m:
        changed['expires_at'] = ts(parse_ts(cmd['expires_at']) + timedelta(seconds=m['expires_at_shift_s']))
    if 'params' in m:
        changed['params'].update(m['params'])
    mono = time.monotonic()
    ctx.n.publish(changed)
    time.sleep(case.get('window_s', 8))
    alarms = [a for a in ctx.n.alarms_since(mono)
              if ((a.get('data') or {}).get('details') or {}).get('command') == cmd['id']]
    after = ctx.n.since(cmd['id'], mono)
    obs = {'origin_state': f.get('state'),
           'alarm_code': (alarms[0].get('data') or {}).get('code') if alarms else None,
           'origin_polluted': bool(_changed_states(ctx, cmd['id'], f, after))}
    return {'observed': obs, 'task_ids': [cmd['id']], 'complete': True,
            'evidence': {'alarms': alarms, 'retransmitted_seqs': [(r.get('seq'), r.get('state')) for r in after]}}


@procedure('task_get')
def p_task_get(ctx, case, slot=None):
    ocmd, of = _origin(ctx, case)
    cmd = ctx.command('task.get', {'id': ocmd['id']})
    f = ctx.send(cmd)
    inner = ((f or {}).get('result') or {}).get('task') or {}
    obs = _final_obs(f, case)
    obs.update({'inner_id_matches': inner.get('id') == ocmd['id'], 'inner_state': inner.get('state')})
    return {'observed': obs, 'task_ids': [cmd['id'], ocmd['id']], 'complete': f is not None and of is not None,
            'evidence': {'final': f}}


@procedure('page_switch')
def p_page_switch(ctx, case, slot=None):
    c1 = ctx.command(case['action'], dict(case.get('params', {})))
    f1 = ctx.send(c1)
    cursor = ((f1 or {}).get('result') or {}).get('cursor')
    if not f1 or f1.get('state') != 'succeeded':  # first page itself failed: cannot evaluate, keep its error
        return {'observed': {'page1_state': (f1 or {}).get('state')}, 'task_ids': [c1['id']], 'complete': False,
                'evidence': {'page1_error': (f1 or {}).get('error')}}
    if not cursor:
        return {'observed': {'page1_state': f1.get('state')}, 'task_ids': [c1['id']], 'complete': True,
                'evidence': {}, 'precondition_failed': 'multi_page'}
    p2 = dict(case.get('params', {}), cursor=cursor, **case.get('page2_params', {}))
    c2 = ctx.command(case['action'], p2)
    f2 = ctx.send(c2, 30)
    obs = _final_obs(f2, case)
    obs['page1_state'] = f1.get('state')
    return {'observed': obs, 'task_ids': [c1['id'], c2['id']], 'complete': f2 is not None, 'evidence': {'final': f2}}


@procedure('cursor_expiry')
def p_cursor_expiry(ctx, case, slot=None):
    c1 = ctx.command(case['action'], dict(case.get('params', {})))
    f1 = ctx.send(c1)
    t0 = time.monotonic()
    cursor = ((f1 or {}).get('result') or {}).get('cursor')
    if not f1 or f1.get('state') != 'succeeded':  # first page itself failed: cannot evaluate, keep its error
        return {'observed': {'page1_state': (f1 or {}).get('state')}, 'task_ids': [c1['id']], 'complete': False,
                'evidence': {'page1_error': (f1 or {}).get('error')}}
    if not cursor:
        return {'observed': {'page1_state': f1.get('state')}, 'task_ids': [c1['id']], 'complete': True,
                'evidence': {}, 'precondition_failed': 'multi_page'}
    ctx.log(f"{case['id']}: 等待游标过期 {case.get('wait_s', 310)} s")
    time.sleep(max(0, case.get('wait_s', 310) - (time.monotonic() - t0)))
    c2 = ctx.command(case['action'], dict(case.get('params', {}), cursor=cursor))
    f2 = ctx.send(c2, 30)
    obs = _final_obs(f2, case)
    obs['page1_state'] = f1.get('state')
    return {'observed': obs, 'task_ids': [c1['id'], c2['id']], 'complete': f2 is not None,
            'evidence': {'waited_s': round(time.monotonic() - t0)}}


@procedure('inventory_vs_phones')
def p_inventory_vs_phones(ctx, case, slot=None):
    ip, inv = ctx.paginate('inventory.get', {'page_size': 100})
    pp, rows = ctx.paginate('phones.list', {'page_size': 100})
    a = {i.get('slot') for i in inv}
    b = {(r.get('target') or {}).get('slot') for r in rows}
    ok = lambda pages: all(f and f.get('state') == 'succeeded' for _, f in pages)
    obs = {'inventory_ok': ok(ip), 'phones_ok': ok(pp), 'missing': len(a - b), 'extra': len(b - a)}
    return {'observed': obs, 'task_ids': [i for i, _ in ip + pp],
            'complete': all(f is not None for _, f in ip + pp), 'evidence': {'imeis': len(a), 'slots': len(b)}}


@procedure('certainty_audit')
def p_certainty_audit(ctx, case, slot=None):
    with ctx.n.lock:
        errs = [(tid, r['payload']['error']) for tid, rs in ctx.n.tasks.items() if tid in ctx.n.own_ids
                for r in rs if r['payload'].get('error')]
    bad = [(tid, e) for tid, e in errs if (e or {}).get('certainty') not in CERTAINTY]
    obs = {'error_replies_present': bool(errs), 'all_certainty_valid': not bad}
    return {'observed': obs, 'task_ids': sorted({t for t, _ in errs}), 'complete': True,
            'evidence': {'error_replies': len(errs), 'certainty_values': sorted({str((e or {}).get('certainty')) for _, e in errs}),
                         'bad': bad[:5]}}


@procedure('heartbeat')
def p_heartbeat(ctx, case, slot=None):
    hb = list(ctx.n.heartbeats)
    gaps = [round(b['mono'] - a['mono'], 1) for a, b in zip(hb, hb[1:])]
    pres = [p for p in ctx.n.presence if p['retain']]
    obs = {'intervals_ok': bool(gaps) and all(27 <= g <= 33 for g in gaps),
           'presence_online': bool(pres) and pres[-1]['payload'].get('online') is True}
    return {'observed': obs, 'task_ids': [], 'complete': len(hb) >= 2,
            'evidence': {'heartbeats': len(hb), 'gaps_s': gaps[:20]}}


# ---------------------------------------------------------------- judge
def match(expected, actual):
    if isinstance(expected, list):
        return actual == expected if isinstance(actual, list) else actual in expected
    return actual == expected


def judge(case, outcome):
    """-> {'verdict': pass|fail|untested|insufficient|partial, 'reasons': [...]}"""
    if outcome.get('precondition_failed'):
        return {'verdict': 'untested', 'reasons': [f"前置条件不满足：{outcome['precondition_failed']}"]}
    if outcome.get('skipped'):
        return {'verdict': 'untested', 'reasons': [outcome['skipped']]}
    obs = outcome.get('observed') or {}
    if not outcome.get('complete'):
        return {'verdict': 'insufficient', 'reasons': ['回包超时或只拿到部分回包']}
    reasons, ok = [], True
    for key, exp in case['expect'].items():
        act = obs.get(key)
        hit = match(exp, act)
        ok &= hit
        reasons.append(f"{'✓' if hit else '✗'} {key}: 期望 {json.dumps(exp, ensure_ascii=False)}，实际 {json.dumps(act, ensure_ascii=False)}")
    if not ok:
        return {'verdict': 'fail', 'reasons': reasons}
    if case.get('verdict_cap') == 'partial':
        return {'verdict': 'partial', 'reasons': reasons + ['外部可验证部分全部满足；其余判据需节点/业务端内部状态']}
    return {'verdict': 'pass', 'reasons': reasons}


# ---------------------------------------------------------------- fingerprints
def normalize(case, outcome):
    """Semantic result only: the judged fields (expect keys) plus explicitly declared extra
    observations, minus anything the case marks volatile. Unjudged observations stay in evidence."""
    keep = set(case['expect']) | set(case.get('observe_extra', []))
    drop = set(case.get('volatile_fields', []))
    obs = outcome.get('observed') or {}
    return {k: obs.get(k) for k in sorted(keep - drop) if k in obs}


def case_fingerprint(rec):
    return sha(json.dumps({'id': rec['id'], 'verdict': rec['verdict'], 'normalized': rec['normalized']},
                          sort_keys=True, ensure_ascii=False))[:16]


def run_fingerprint(records):
    det = sorted((r['id'], r['fingerprint']) for r in records if r['stability'] == 'deterministic')
    return sha(json.dumps(det))[:16]


# ---------------------------------------------------------------- run
def expand(ctx, cases):
    for case in cases:
        if case.get('foreach') == 'slots':
            slots = ctx.vars.get('slots') or []
            if not slots:
                yield case, None, f"{case['id']}"
            for s in slots:
                yield case, s, f"{case['id']}@{s['device']}"
        else:
            yield case, None, case['id']


def run(progress=print, include_t43=True, cases=None, out_dir=None):
    cases = cases or load_cases()
    problems = validate_cases(cases)
    if problems:
        raise RuntimeError('用例文件校验失败：' + '；'.join(problems))
    started = datetime.now(CST)
    run_id = started.strftime('%Y%m%d-%H%M%S') + '-' + uuid.uuid4().hex[:6]
    combined, parts = code_sha256()
    n = Node()
    ctx = Ctx(n, {'include_t43': include_t43})
    ctx.log = lambda s: progress(mask_text(f'{ts()} {s}'))
    records = []
    try:
        env = setup(ctx)
        ctx.log(f"环境 {env['environment_snapshot_id']}：{env['environment_summary']}")
        for case, slot, rid in expand(ctx, cases):
            flag = case.get('optional_flag')
            missing = [p for p in case.get('preconditions', []) if not ctx.pre.get(p)]
            if flag and not ctx.options.get(flag):
                outcome = {'skipped': f'本次未启用（{flag}）', 'task_ids': []}
            elif missing:
                outcome = {'precondition_failed': ', '.join(missing), 'task_ids': []}
            else:
                try:
                    outcome = PROCEDURES[case['procedure']](ctx, case, slot)
                except Exception as error:  # a broken procedure is evidence gap, not a pass/fail
                    outcome = {'complete': False, 'task_ids': [], 'evidence': {'exception': repr(error)}}
            j = judge(case, outcome)
            rec = {'id': rid, 't': rid.split('#')[0].split('@')[0], 'action': case['action'], 'path': case['path'],
                   'stability': case['stability'], 'verdict': j['verdict'], 'reasons': j['reasons'],
                   'task_ids': outcome.get('task_ids', []), 'time': ts(),
                   'normalized': normalize(case, outcome), 'evidence': mask(outcome.get('evidence')),
                   'notes': case.get('notes', '')}
            rec['fingerprint'] = case_fingerprint(rec)
            rec['summary'] = mask_text('；'.join(x for x in j['reasons'] if x.startswith('✗')) or j['reasons'][0]
                                       if j['reasons'] else '')
            records.append(rec)
            ctx.log(f"[{rec['verdict']}] {rid}: {rec['summary']}")
    finally:
        n.close()
    out = {'run_id': run_id, 'started': ts(started), 'finished': ts(),
           'meta': {**n.meta, 'code_sha256': combined, 'code_files_sha256': parts},
           **env, 'run_fingerprint': run_fingerprint(records), 'cases': records,
           'commands': mask(ctx.commands),
           'task_messages': mask({k: [r['payload'] for r in v] for k, v in n.tasks.items() if k in n.own_ids}),
           'alarms': mask([r['payload'] for r in n.alarms]), 'other_events': n.other_events}
    ev = Path(out_dir) if out_dir else EVIDENCE / run_id
    ev.mkdir(parents=True, exist_ok=True)
    text = json.dumps(out, ensure_ascii=False, indent=2)
    assert n.pw not in text
    (ev / 'results.json').write_text(text, 'utf-8')
    out['evidence_dir'] = str(ev)
    ctx.log(f"运行指纹 {out['run_fingerprint']}；证据：{ev}")
    return out


# ---------------------------------------------------------------- repeat
HARDWARE_MARKERS = ('eUICC', 'ISD-R', 'CSIM', 'phone failure', 'Profile 失败', '"source": "registry"')


def attribute(runs, items):
    """Per deviant run, in A6 order: code change -> environment probe failed -> environment differs
    from the majority -> field hardware markers in that run's evidence -> undetermined."""
    if len({r['meta'].get('code_sha256') for r in runs}) > 1:
        return '代码变更（不同代码哈希，不可比较）'
    probe_ok = lambda i: (runs[i].get('preconditions') or {}).get('env_probe_ok', True)
    by_run = dict(items)
    if items and all(not probe_ok(i) for i, _ in items):
        return f"仅在环境探测失败的第 {', '.join(str(i + 1) for i, _ in items)} 次出现（目标未能展开）"
    clean = [c.get('fingerprint') for i, c in items if probe_ok(i)] or [c.get('fingerprint') for _, c in items]
    majority = max(sorted(set(clean)), key=clean.count) if clean else None
    majority_runs = [i for i, c in items if c.get('fingerprint') == majority]
    majority_env = {runs[i].get('environment_snapshot_id') for i in majority_runs}
    causes = []
    for i in range(len(runs)):
        c = by_run.get(i)
        if c is not None and c.get('fingerprint') == majority:
            continue
        if not probe_ok(i):
            errs = json.dumps(runs[i].get('env_probe_errors'), ensure_ascii=False)
            why = '现场硬件偶发' if any(mk in errs for mk in HARDWARE_MARKERS) else '见 env_probe_errors'
            causes.append(f'第 {i + 1} 次环境探测失败（{why}）')
        elif runs[i].get('environment_snapshot_id') not in majority_env:
            causes.append(f'第 {i + 1} 次环境变化')
        elif c is None:
            causes.append(f'第 {i + 1} 次未展开该用例')
        elif any(mk in json.dumps(c.get('evidence'), ensure_ascii=False) for mk in HARDWARE_MARKERS):
            causes.append(f'第 {i + 1} 次现场硬件偶发（模块读卡失败）')
        elif len({json.dumps(runs[j].get('selected_targets'), sort_keys=True) for j in (i, *majority_runs[:1])}) > 1:
            causes.append(f'第 {i + 1} 次目标对象不一致')
        else:
            causes.append(f'第 {i + 1} 次待定：需人工定因')
    return '；'.join(causes) or '待定：需人工定因'


def summarize_repeat(runs):
    """Compare N run results of the same code: stable / flipped cases, fingerprints, environment."""
    codes = sorted({r['meta'].get('code_sha256') for r in runs})
    by_case = {}
    for i, r in enumerate(runs):
        for c in r['cases']:
            by_case.setdefault(c['id'], []).append((i, c))
    rows = []
    for cid, items in by_case.items():
        verdicts = [c['verdict'] for _, c in items]
        fps = {c['fingerprint'] for _, c in items}
        changed = sorted({k for _, c in items for k in c['normalized']
                          if len({json.dumps(x['normalized'].get(k), sort_keys=True) for _, x in items}) > 1})
        stable = len(fps) == 1 and len(items) == len(runs)
        rows.append({'id': cid, 'stability': items[0][1]['stability'], 'verdicts': verdicts, 'stable': stable,
                     'changed_fields': changed, 'attribution': '' if stable else attribute(runs, items)})
    det = [r for r in rows if r['stability'] == 'deterministic']
    return {'runs': len(runs), 'code_sha256': codes, 'same_code': len(codes) == 1,
            'run_fingerprints': [r['run_fingerprint'] for r in runs],
            'run_fingerprint_consistent': len({r['run_fingerprint'] for r in runs}) == 1,
            'environment_ids': [r['environment_snapshot_id'] for r in runs],
            'environment_consistent': len({r['environment_snapshot_id'] for r in runs}) == 1,
            'deterministic_total': len(det), 'deterministic_stable': sum(r['stable'] for r in det),
            'flipped': [r['id'] for r in rows if not r['stable']], 'cases': rows,
            'env_probe_failed': [i + 1 for i, r in enumerate(runs) if not (r.get('preconditions') or {}).get('env_probe_ok', True)],
            'run_ids': [r['run_id'] for r in runs]}


LABEL = {'pass': '通过', 'fail': '失败', 'untested': '未测', 'insufficient': '证据不足', 'partial': '未测（部分观察）'}


def repeat_markdown(rep, rel_dirs):
    lines = ['# MQ 第一层复现报告', '',
             f"- 运行次数：{rep['runs']}；代码哈希：{', '.join(c[:16] for c in rep['code_sha256'])}（{'同一版本' if rep['same_code'] else '**版本不一致，不可比较**'}）",
             f"- 运行指纹：{'**一致**' if rep['run_fingerprint_consistent'] else '**不一致**'}（{', '.join(rep['run_fingerprints'])}）",
             f"- 环境快照：{'一致' if rep['environment_consistent'] else '**有变化**'}（{', '.join(rep['environment_ids'])}）",
             f"- 环境探测失败的运行：{', '.join(str(i) for i in rep.get('env_probe_failed', [])) or '无'}",
             f"- deterministic 用例稳定：{rep['deterministic_stable']}/{rep['deterministic_total']}；翻转：{', '.join(rep['flipped']) or '无'}",
             f"- 各次证据：{'；'.join(rel_dirs)}", '',
             '| 用例 | 等级 | 各次判定 | 稳定？ | 变化的字段 | 归因 |', '|---|---|---|---|---|---|']
    for r in rep['cases']:
        counts = {}
        for v in r['verdicts']:
            counts[LABEL.get(v, v)] = counts.get(LABEL.get(v, v), 0) + 1
        lines.append(f"| {r['id']} | {r['stability']} | {'、'.join(f'{k}×{v}' for k, v in counts.items())} | "
                     f"{'稳定' if r['stable'] else '**翻转**'} | {', '.join(r['changed_fields']) or '—'} | {r.get('attribution') or '—'} |")
    return '\n'.join(lines) + '\n'


def write_repeat_report(base, runs, dirs, extra=None):
    rep = summarize_repeat(runs)
    rep.update({'repeat_id': Path(base).name, 'evidence_dir': str(base),
                'summarizer_sha256': code_sha256()[1][Path(__file__).name], **(extra or {})})
    (Path(base) / 'repeat_report.json').write_text(json.dumps(rep, ensure_ascii=False, indent=2), 'utf-8')
    (Path(base) / 'repeat_report.md').write_text(repeat_markdown(rep, dirs), 'utf-8')
    return rep


def resummarize(base):
    """Rebuild repeat_report.* from the saved NN/results.json (no MQTT)."""
    base = Path(base)
    dirs = sorted(p.parent.name for p in base.glob('[0-9][0-9]/results.json'))
    runs = [json.loads((base / d / 'results.json').read_text('utf-8')) for d in dirs]
    old = json.loads((base / 'repeat_report.json').read_text('utf-8')) if (base / 'repeat_report.json').exists() else {}
    return write_repeat_report(base, runs, dirs, {k: old[k] for k in ('interval_s', 'include_t43') if k in old})


def repeat(n_runs=5, interval_s=10, include_t43=False, progress=print):
    n_runs = max(1, min(10, int(n_runs)))
    stamp = datetime.now(CST).strftime('%Y%m%d-%H%M%S')
    base = EVIDENCE / f'repeat-{stamp}'
    runs, dirs = [], []
    for i in range(1, n_runs + 1):
        progress(f'{ts()} ===== 第 {i}/{n_runs} 次 =====')
        d = base / f'{i:02d}'
        runs.append(run(progress=progress, include_t43=include_t43, out_dir=d))
        dirs.append(f'{i:02d}')
        if i < n_runs:
            time.sleep(interval_s)
    rep = write_repeat_report(base, runs, dirs, {'interval_s': interval_s, 'include_t43': include_t43})
    progress(f"{ts()} 复现完成：运行指纹{'一致' if rep['run_fingerprint_consistent'] else '不一致'}，"
             f"deterministic 稳定 {rep['deterministic_stable']}/{rep['deterministic_total']}，翻转 {rep['flipped'] or '无'}；{base}")
    return rep


if __name__ == '__main__':
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--repeat', type=int, default=0)
    ap.add_argument('--interval', type=int, default=10)
    ap.add_argument('--skip-t43', action='store_true')
    ap.add_argument('--include-t43', action='store_true', help='repeat 模式默认跳过 T-43')
    ap.add_argument('--resummarize', metavar='REPEAT_DIR', help='只根据已保存的各次 results.json 重建复现报告')
    a = ap.parse_args()
    if a.resummarize:
        r = resummarize(a.resummarize)
        print(f"{r['repeat_id']}: deterministic 稳定 {r['deterministic_stable']}/{r['deterministic_total']}，翻转 {r['flipped'] or '无'}")
    elif a.repeat:
        repeat(a.repeat, a.interval, include_t43=a.include_t43)
    else:
        run(include_t43=not a.skip_t43)
