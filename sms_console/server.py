"""号码互发测试台 · 演示版（http://127.0.0.1:8768）。

- 登录：用 VoCat 账号，后台转给 VoCat 验证，不保存密码。
- 号码：从 VoCat 只读取（GET），不读取也不保存 ICCID。
- 收发：全部在本地模拟，没有限流，想测多少条都可以。
- 本文件没有任何发短信的代码：对 VoCat 只会发登录请求和 GET 读取请求（见 VoCatReader）。

运行: python sms_console\\server.py [--port 8768]
数据: .local\\sms-console\\（模拟记录，与 .local\\sms-rate-ask\\ 的真实结果分开）
"""
import argparse
import csv
import http.cookiejar
import io
import json
import os
import random
import secrets
import string
import sys
import threading
import time
import urllib.error
import urllib.request
from urllib.parse import parse_qs
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

try:
    from .tac_catalog import TacCatalog
except ImportError:  # 允许使用 python sms_console/server.py 直接启动
    from tac_catalog import TacCatalog

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

VERSION = 'v0.4 设备识别与测试台'
BJ = timezone(timedelta(hours=8))
HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
STATIC = HERE / 'static'
DATA = ROOT / '.local' / 'sms-console'
RUNS = DATA / 'runs'
IMEI_DATA = DATA / 'imei-groups.json'
REAL = ROOT / '.local' / 'sms-rate-ask'   # 之前真实发送的结果，只读
SESSION_HOURS = 12
MAX_MESSAGES = 2000
MODES = {'relay': '接力互发', 'pairs': '两两互发', 'pair': '指定一对', 'cross_pool': '号池轮询互发'}
FAIL_REASONS = ['设备未响应', '运营商拒收', '线路忙，提交失败']
DEFAULT_SETTINGS = dict(send_mode='demo', fail_rate=1.0, undelivered_rate=2.0, latency_min=1.0, latency_max=5.0)

LOCK = threading.Lock()
SESSIONS = {}
VOCAT_BASE = 'http://192.168.1.5:7575'

TAC_CSV = Path(os.environ.get(
    'TAC_CSV', str(ROOT.parent / '前端' / 'tac-database-main' / 'tac_full.csv')))
TAC_SOURCE = os.environ.get('TAC_SOURCE', 'MoazEb/tac_full.csv')
TAC_DATA_UPDATED_AT = os.environ.get('TAC_DATA_UPDATED_AT') or None
TAC_DATA_COVERAGE_THROUGH = os.environ.get('TAC_DATA_COVERAGE_THROUGH', '2025-12')
TAC_CATALOG_ERROR = None
try:
    # 进程启动时加载一次；请求路径不读取 CSV/XLSX。
    TAC_CATALOG = TacCatalog.from_csv(
        TAC_CSV, source=TAC_SOURCE, data_updated_at=TAC_DATA_UPDATED_AT,
        coverage_through=TAC_DATA_COVERAGE_THROUGH)
except (OSError, ValueError) as exc:
    TAC_CATALOG = None
    TAC_CATALOG_ERROR = str(exc)


# ---------------------------------------------------------------- VoCat（只读）

class VoCatError(Exception):
    def __init__(self, message, status=502):
        super().__init__(message)
        self.status = status


class VoCatReader:
    """只能登录和 GET。没有发送、修改的方法；_open 也拒绝登录以外的写请求。"""

    def __init__(self):
        self.op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        self.devices = []

    def _open(self, path, body=None):
        if body is not None and path != '/auth/login':
            raise VoCatError('只允许登录和读取')
        req = urllib.request.Request(VOCAT_BASE + '/api' + path, headers={'Content-Type': 'application/json'},
                                     data=None if body is None else json.dumps(body).encode())
        try:
            with self.op.open(req, timeout=15) as resp:
                payload = json.loads(resp.read() or b'null')
                return resp.status, payload.get('data', payload) if isinstance(payload, dict) else payload
        except urllib.error.HTTPError as e:
            return e.code, None
        except (urllib.error.URLError, OSError) as e:
            raise VoCatError(f'连不上 VoCat（{VOCAT_BASE}）') from e

    def login(self, user, password):
        status, _ = self._open('/auth/login', {'username': user, 'password': password})
        if status == 200:
            return True
        if status == 401:
            return False
        if status == 429:
            raise VoCatError('VoCat 暂时限制登录（HTTP 429），请稍后再试，避免连续重试', status=429)
        raise VoCatError(f'VoCat 登录接口异常（HTTP {status}），无法确认账号密码是否正确')

    def get(self, path):
        return self._open(path)

    def numbers(self):
        st, devs = self.get('/devices')
        if st == 401:
            raise PermissionError
        if st != 200:
            raise VoCatError(f'读取设备失败（HTTP {st}）')
        devices = devs.get('devices', []) if isinstance(devs, dict) else (devs or [])
        out = []
        inventory = []
        for d in devices:
            did = str(d.get('id'))
            st, ms = self.get(f'/devices/{did}/multisim')
            if st == 401:
                raise PermissionError
            if st != 200:
                raise VoCatError(f'读取 EC20 {did} 号码失败（HTTP {st}），未替换号码缓存')
            node_name = str(d.get('name') or (f'EC20 {did}' if len(did) < 8 else f'EC20 · {did[-6:]}'))
            pool_id = did or 'pool-default'
            pool_name = node_name
            state = (ms or {}).get('state') or {}
            config = (ms or {}).get('config') or {}
            imeis = list(dict.fromkeys(str((ln.get('state') or {}).get('network_imei') or '').strip()
                                      for ln in state.get('lines') or []))
            imeis = [value for value in imeis if value]
            imei = str(d.get('network_imei') or '').strip()
            imei_source = 'device.network_imei' if imei else 'line.state.network_imei' if imeis else ''
            if imei:
                imeis = [imei] + [value for value in imeis if value != imei]
            else:
                imei = imeis[0] if imeis else ''
            rows = []
            for ln in state.get('lines') or []:
                s = ln.get('state') or {}
                if s.get('phone_number'):
                    # A line/profile is not a physical card slot. Preserve only reported slot IDs.
                    slot_id = ln.get('slot_id', ln.get('slotId', s.get('slot_id')))
                    line_id = ln.get('line_id', ln.get('lineId'))
                    rows.append(dict(number=s['phone_number'], device=did, device_name=node_name,
                                    node_id=did, node_name=node_name, pool_id=pool_id, pool_name=pool_name,
                                    imei=imei,
                                    slot_id=slot_id, line_id=line_id, ready=bool(s.get('sms_ready')),
                                    unavailable_reason='' if s.get('sms_ready') else '线路尚未就绪'))
            # A known local number is inventory, not proof of SMS readiness.
            local_phone = d.get('local_phone')
            if local_phone and not any(n['number'] == local_phone for n in rows):
                rows.append(dict(number=local_phone, device=did, device_name=node_name,
                                 node_id=did, node_name=node_name, pool_id=did, pool_name=node_name,
                                 imei=imei,
                                 slot_id=None, line_id=None, ready=False,
                                 unavailable_reason='已识别本机号码，尚未验证可用于互发的线路'))
            out.extend(rows)
            ready_count = sum(n['ready'] for n in rows)
            reason = '' if ready_count else ('设备未在线' if d.get('physical_present') is False or d.get('control_online') is False
                      else '多号码未启用' if not state.get('enabled') else '尚无就绪号码')
            inventory.append(dict(id=did, name=node_name, online=d.get('control_online'),
                                  imei=imei, imeis=imeis, imei_source=imei_source,
                                  present=d.get('physical_present'), profile_count=len(config.get('profiles') or []),
                                  number_count=len(rows), ready_count=ready_count, reason=reason))
        out.sort(key=lambda x: (x.get('pool_id', ''), int(x['device']) if x['device'].isdigit() else 0,
                                str(x.get('slot_id') or ''), x['number']))
        self.devices = inventory
        return out


# ---------------------------------------------------------------- 存储

def read_json(p, default=None):
    try:
        return json.loads(Path(p).read_text('utf-8'))
    except Exception:
        return default


def write_json(p, data):
    p = Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix('.tmp')
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), 'utf-8')
    tmp.replace(p)


def load_settings():
    s = dict(DEFAULT_SETTINGS)
    s.update(read_json(DATA / 'settings.json', {}) or {})
    s['send_mode'] = 'demo'   # 本期锁定
    return s


def cached_numbers():
    data = read_json(DATA / 'numbers.json', {'numbers': [], 'fetched_at': None}) or {'numbers': [], 'fetched_at': None}
    names = {str(d['id']): d['name'] for d in data.get('devices', [])}
    for n in data.get('numbers') or []:
        # 本测试台以 EC20 设备作为号池；不使用上层分组覆盖设备身份。
        n['pool_id'] = str(n.get('device') or 'pool-default')
        n['pool_name'] = names.get(n['pool_id'], f"EC20 {n.get('device') or '未知'}")
        n['device_name'] = n['pool_name']
        n.setdefault('imei', '')
        n.setdefault('node_id', str(n.get('device') or ''))
        n.setdefault('node_name', str(n.get('device_name') or ''))
        n.setdefault('slot_id', None)
    return data


def imei_luhn(value):
    """验证 15 位 IMEI 的结构和 Luhn 校验位。"""
    value = str(value or '').strip()
    if len(value) != 15 or not value.isascii() or not value.isdigit():
        return False
    total = 0
    for i, digit in enumerate(reversed(value[:-1])):
        n = int(digit) * (2 if i % 2 == 0 else 1)
        total += n // 10 + n % 10
    return (total + int(value[-1])) % 10 == 0


def tac_lookup(tac):
    """从启动时加载的本地 TAC 索引查询，不访问外部服务。"""
    if TAC_CATALOG is None:
        return dict(model_status='unknown', tac='', candidates=[],
                    source='TAC 数据源不可用', data_version=None,
                    data_updated_at=None, coverage_through=None,
                    catalog_available=False)
    return dict(TAC_CATALOG.lookup(tac), catalog_available=True)


def tac_catalog_meta():
    if TAC_CATALOG is None:
        return dict(source='TAC 数据源不可用', data_version=None,
                    data_updated_at=None, coverage_through=None,
                    error=TAC_CATALOG_ERROR)
    return dict(source=TAC_CATALOG.source, data_version=TAC_CATALOG.data_version,
                data_updated_at=TAC_CATALOG.data_updated_at,
                coverage_through=TAC_CATALOG.coverage_through,
                stats=TAC_CATALOG.stats)


def imei_model_lookup(value):
    """校验完整 IMEI，并用前 8 位 TAC 查本地数据源。"""
    value = str(value or '').strip()
    valid = imei_luhn(value)
    tac = value[:8] if len(value) == 15 and value.isascii() and value.isdigit() else ''
    result = tac_lookup(tac) if valid else dict(
        model_status='invalid' if value else 'missing', tac=tac, candidates=[],
        source=tac_catalog_meta().get('source', 'TAC 数据源不可用'),
        data_version=None, data_updated_at=None, coverage_through=None,
    )
    candidates = result.get('candidates') or []
    model = candidates[0] if result.get('model_status') == 'matched' and candidates else None
    return dict(
        imei=value,
        valid=valid,
        status=result.get('model_status'),
        tac=result.get('tac') or tac,
        manufacturer=(model or {}).get('brand', ''),
        model=(model or {}).get('specs', ''),
        device_type=(model or {}).get('device_type', ''),
        candidates=candidates,
        source=result.get('source', ''),
        data_version=result.get('data_version'),
        data_updated_at=result.get('data_updated_at'),
        coverage_through=result.get('coverage_through'),
        catalog_available=bool(TAC_CATALOG),
        queried_at=time.time(),
    )


def live_imei_devices(reader):
    """刷新 VoCat 设备和号码快照，并整理成 IMEI 查询所需字段。"""
    rows = reader.numbers()
    fetched_at = time.time()
    write_json(DATA / 'numbers.json', dict(numbers=rows, devices=reader.devices, fetched_at=fetched_at))
    return [dict(
        device_id=str(d.get('id') or ''), name=d.get('name') or '',
        imei=d.get('imei') or '', imeis=d.get('imeis') or [],
        imei_source=d.get('imei_source') or '', online=d.get('online'),
        pool_id=str(d.get('id') or ''), pool_name=d.get('name') or '',
        profile_count=d.get('profile_count', 0), number_count=d.get('number_count', 0),
        ready_count=d.get('ready_count', 0), reason=d.get('reason') or '',
        numbers=[dict(number=n['number'], ready=n.get('ready', False),
                      line_id=n.get('line_id'), unavailable_reason=n.get('unavailable_reason', ''))
                 for n in rows if str(n.get('device')) == str(d.get('id'))],
    ) for d in reader.devices], fetched_at


def cached_imei_devices():
    """从最近一次 VoCat 号码快照读取设备，供离线或远程暂不可用时展示。"""
    devices = []
    snapshot = cached_numbers()
    for d in snapshot.get('devices') or []:
        imei = str(d.get('imei') or '').strip()
        devices.append(dict(
            device_id=str(d.get('id') or ''), name=d.get('name') or '',
            imei=imei, imeis=d.get('imeis') or ([imei] if imei else []),
            imei_source=d.get('imei_source') or '', online=d.get('online'),
            pool_id=str(d.get('id') or ''), pool_name=d.get('name') or '',
            profile_count=d.get('profile_count', 0), number_count=d.get('number_count', 0),
            ready_count=d.get('ready_count', 0), reason=d.get('reason') or '',
            numbers=[dict(number=n['number'], ready=n.get('ready', False),
                          line_id=n.get('line_id'), unavailable_reason=n.get('unavailable_reason', ''))
                     for n in snapshot.get('numbers', []) if str(n.get('device')) == str(d.get('id'))],
        ))
    return devices



def load_imei_groups():
    data = read_json(IMEI_DATA, None)
    if not isinstance(data, dict):
        data = {'groups': [{'id': 'default', 'name': '短信测试设备', 'purpose': 'EC20 设备识别', 'note': ''}], 'records': []}
    data.setdefault('groups', [])
    data.setdefault('records', [])
    return data


def imei_records():
    """把已保存 IMEI 重新计算状态，避免缓存和设备关联过期。"""
    data = load_imei_groups()
    by_imei = {}
    for d in cached_numbers().get('devices') or []:
        key = str(d.get('imei') or '').strip()
        if key:
            by_imei.setdefault(key, []).append(d)
    seen = set()
    records = []
    for raw in data.get('records') or []:
        value = str(raw.get('imei') or '').strip()
        fmt = 'valid' if imei_luhn(value) else ('duplicate' if value in seen else 'invalid')
        if value in seen:
            fmt = 'duplicate'
        seen.add(value)
        tac = value[:8] if value.isdigit() else ''
        model_result = tac_lookup(tac)
        model_candidates = model_result['candidates']
        model = model_candidates[0] if model_result['model_status'] == 'matched' else None
        device_candidates = by_imei.get(value) or []
        records.append(dict(raw, imei=value, tac=tac,
                            format_status=fmt,
                            model_status=model_result['model_status'],
                            brand=model.get('brand') if model else '',
                            model=model.get('specs') if model else '',
                            candidates=model_candidates,
                            source=model_result['source'],
                            data_version=model_result['data_version'],
                            data_updated_at=model_result['data_updated_at'],
                            coverage_through=model_result['coverage_through'],
                            catalog_available=model_result['catalog_available'],
                            associated='linked' if len(device_candidates) == 1 else ('conflict' if len(device_candidates) > 1 else 'unlinked'),
                            devices=[dict(id=str(d.get('id')), name=d.get('name'), online=d.get('online'),
                                          pool_id=str(d.get('id')), imei=d.get('imei'),
                                          number_count=d.get('number_count', 0), ready_count=d.get('ready_count', 0)) for d in device_candidates]))
        snapshot = raw.get('query_result')
        if snapshot:
            records[-1].update(tac=snapshot.get('tac', ''),
                               model_status=snapshot.get('status', model_result['model_status']),
                               brand=snapshot.get('manufacturer', ''),
                               model=snapshot.get('model', ''),
                               device_type=snapshot.get('device_type', ''),
                               source=snapshot.get('source', ''),
                               candidates=snapshot.get('candidates') or [],
                               queried_at=snapshot.get('queried_at'),
                               data_version=snapshot.get('data_version'))
    return records


def next_group_id(groups):
    used = {str(g.get('id')) for g in groups}
    i = 1
    while f'group-{i}' in used:
        i += 1
    return f'group-{i}'


def all_runs():
    runs = [read_json(p) for p in RUNS.glob('DEMO*.json')]
    return sorted([r for r in runs if r], key=lambda r: r['started'], reverse=True)


# ---------------------------------------------------------------- 模拟

def plan_pairs(nums, mode, rounds, pair, source=None, target=None):
    plan = []
    n = len(nums)
    if mode in ('relay', 'pairs') and n < 2:
        raise ValueError('至少选择 2 个不同号码')
    if mode == 'pair' and (not pair or len(pair) != 2 or pair[0]['number'] == pair[1]['number']):
        raise ValueError('请选择两个不同的号码')
    if mode == 'cross_pool' and (not source or not target):
        raise ValueError('两个号池都至少需要一个号码')
    for r in range(rounds):
        if mode == 'relay':
            for i, s in enumerate(nums):
                t = nums[(i + 1 + r % (n - 1)) % n]
                if t['number'] != s['number']:
                    plan.append((s, t))
        elif mode == 'pairs':
            rot = nums[r % n:] + nums[:r % n]
            groups = [rot[i:i + 2] for i in range(0, n, 2)]
            if len(groups[-1]) == 1:
                groups[-1] = [groups[-1][0], rot[0]]
            for a, b in groups:
                plan += [(a, b), (b, a)]
        elif mode == 'cross_pool':
            left, right = source or [], target or []
            for i in range(max(len(left), len(right))):
                s, t = left[i % len(left)], right[(i + r) % len(right)]
                plan.extend([(s, t), (t, s)])
        else:
            a, b = pair
            plan += [(a, b), (b, a)]
    return plan


def simulate(plan, gap, settings, batch, t0):
    lo, hi = settings['latency_min'], settings['latency_max']
    msgs = []
    for i, (s, t) in enumerate(plan, 1):
        start = t0 + (i - 1) * gap
        latency = round(lo + (hi - lo) * random.betavariate(2, 5), 1)
        roll = random.random() * 100
        if roll < settings['fail_rate']:
            outcome, reason = 'send_failed', random.choice(FAIL_REASONS)
            end = start + random.uniform(0.3, 0.8)
        elif roll < settings['fail_rate'] + settings['undelivered_rate']:
            outcome, reason = 'undelivered', f'等待 {int(hi) + 10} 秒未收到'
            end = start + hi + 3
        else:
            outcome, reason = 'delivered', None
            end = start + latency
        token = f'{batch}-{i:03d}'
        msgs.append(dict(seq=i, token=token, text=f'{token} 号池互发测试',
                         sender=s['number'], sender_dev=s['device'], receiver=t['number'], receiver_dev=t['device'],
                         sender_pool=s.get('pool_id', 'pool-default'), sender_pool_name=s.get('pool_name', '默认号池'),
                         receiver_pool=t.get('pool_id', 'pool-default'), receiver_pool_name=t.get('pool_name', '默认号池'),
                         sender_slot=s.get('slot_id'), receiver_slot=t.get('slot_id'),
                         t_start=round(start, 3),
                         t_submit=round(start + min(0.4, (end - start) * 0.15), 3),
                         t_accept=round(start + (end - start) * 0.4, 3),
                         t_end=round(end, 3), outcome=outcome, reason=reason,
                         latency_s=latency if outcome == 'delivered' else None))
    return msgs


FINAL = ('delivered', 'send_failed', 'undelivered')


def msg_status(m, now, stopped_at):
    if stopped_at and m['t_start'] > stopped_at:
        return 'cancelled'
    if now < m['t_start']:
        return 'waiting'
    if now < m['t_submit']:
        return 'submitting'
    if m['outcome'] == 'send_failed':
        return 'send_failed'
    if now < m['t_accept']:
        return 'submitted'
    if now < m['t_end']:
        return 'accepted'
    return m['outcome']


def pct(a, b):
    return round(a * 100.0 / b, 1) if b else None


def stats(msgs):
    """msgs 需带 status。只统计已出结果的；已停止未发出的单独计数，不计入成功率。"""
    done = [m for m in msgs if m['status'] in FINAL]
    per = {}
    for m in done:
        a = per.setdefault(m['sender'], dict(number=m['sender'], device=m['sender_dev'], sent=0, sent_ok=0, expected_in=0, received=0))
        a['sent'] += 1
        a['sent_ok'] += m['status'] != 'send_failed'
        b = per.setdefault(m['receiver'], dict(number=m['receiver'], device=m['receiver_dev'], sent=0, sent_ok=0, expected_in=0, received=0))
        b['expected_in'] += 1
        b['received'] += m['status'] == 'delivered'
    rows = sorted(per.values(), key=lambda x: (x['device'], x['number']))
    for p in rows:
        p['send_rate'] = pct(p['sent_ok'], p['sent'])
        p['receive_rate'] = pct(p['received'], p['expected_in'])
    total = len(done)
    sent_ok = sum(m['status'] != 'send_failed' for m in done)
    arrived = sum(m['status'] == 'delivered' for m in done)
    lat = [m['latency_s'] for m in done if m.get('latency_s') is not None]
    return dict(overall=dict(total=total, sent_ok=sent_ok, arrived=arrived,
                             send_rate=pct(sent_ok, total), arrive_rate=pct(arrived, total),
                             avg_latency_s=round(sum(lat) / len(lat), 1) if lat else None,
                             cancelled=sum(m['status'] == 'cancelled' for m in msgs),
                             in_flight=sum(m['status'] not in FINAL + ('cancelled',) for m in msgs),
                             planned=len(msgs)),
                per_number=rows)


def view(run, now=None, full=True):
    now = now or time.time()
    msgs = [dict(m, status=msg_status(m, now, run.get('stopped_at'))) for m in run['messages']]
    in_flight = any(m['status'] not in FINAL + ('cancelled',) for m in msgs)
    state = 'running' if in_flight else ('stopped' if run.get('stopped_at') else 'done')
    out = {k: v for k, v in run.items() if k != 'messages'}
    out.update(state=state, mode_name=MODES[run['mode']], now=now, summary=stats(msgs))
    if full:
        out['messages'] = msgs
    return out


def current_run():
    runs = all_runs()
    return runs[0] if runs else None


# ---------------------------------------------------------------- 真实验证（只读）

def real_results():
    msgs, batches = [], []
    for p in sorted(REAL.glob('*/results.json')):
        d = read_json(p) or {}
        for m in d.get('messages') or []:
            if m.get('send_http') == 429 or m.get('status') == 'throttled':
                continue   # 被限流、没有真正发出的，不计入
            status = 'delivered' if m.get('arrived') else ('send_failed' if not m.get('sent_ok') else 'undelivered')
            msgs.append(dict(seq=len(msgs) + 1, token=m.get('token'), text=m.get('sent_text'),
                             received_text=m.get('received_text'), sender=m['sender'], sender_dev=m['sender_dev'],
                             receiver=m['receiver'], receiver_dev=m['receiver_dev'], sent_at=m.get('sent_at'),
                             latency_s=m.get('latency_s'), status=status, reason=m.get('send_error')))
        if d.get('batch'):
            batches.append(dict(batch=d['batch'], started=d.get('started')))
    return dict(batches=batches, messages=msgs, summary=stats(msgs))


# ---------------------------------------------------------------- HTTP

class Handler(BaseHTTPRequestHandler):
    server_version = 'SmsConsole'

    def log_message(self, *a):
        pass

    def send(self, code, body, ctype='application/json; charset=utf-8', headers=None):
        data = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', ctype)
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(data)))
        for k, v in (headers or {}).items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(data)

    def err(self, code, msg):
        return self.send(code, {'error': msg})

    def session(self):
        for part in (self.headers.get('Cookie') or '').split(';'):
            k, _, v = part.strip().partition('=')
            if k == 'smsc_session':
                s = SESSIONS.get(v)
                if s and s['expires'] > time.time():
                    return v, s
        return None, None

    def body(self):
        n = int(self.headers.get('Content-Length') or 0)
        try:
            return json.loads(self.rfile.read(n) or b'{}') if n else {}
        except Exception:
            return {}

    def do_GET(self):
        path, _, query = self.path.partition('?')
        if path in ('/', '/index.html'):
            return self.send(200, (STATIC / 'index.html').read_bytes(), 'text/html; charset=utf-8')
        if path.startswith('/static/'):
            f = (STATIC / path[len('/static/'):]).resolve()
            if STATIC.resolve() not in f.parents or not f.is_file():
                return self.err(404, '没有这个文件')
            ctype = {'.js': 'text/javascript', '.css': 'text/css', '.svg': 'image/svg+xml'}.get(f.suffix, 'application/octet-stream')
            return self.send(200, f.read_bytes(), ctype + '; charset=utf-8')
        if path == '/api/meta':
            return self.send(200, dict(version=VERSION, vocat=VOCAT_BASE))
        sid, s = self.session()
        if not s:
            return self.err(401, '请先登录')
        if path == '/api/me':
            return self.send(200, dict(user=s['user'], offline=bool(s.get('offline'))))
        if path == '/api/numbers':
            if s.get('reader') is None:
                c = cached_numbers()
                c['stale'] = True
                c['warning'] = '当前为离线演示，显示本地缓存；远程 VoCat 未连接。'
                return self.send(200, c)
            if 'refresh=1' in query or 'devices' not in cached_numbers():
                try:
                    nums = s['reader'].numbers()
                    write_json(DATA / 'numbers.json', dict(numbers=nums, devices=s['reader'].devices, fetched_at=time.time()))
                except PermissionError:
                    SESSIONS.pop(sid, None)
                    return self.err(401, 'VoCat 登录已过期，请重新登录')
                except VoCatError as e:
                    c = cached_numbers()
                    if not c['numbers'] and not c.get('devices'):
                        return self.err(502, str(e))
                    return self.send(200, dict(c, stale=True, warning=f'{e}，显示的是上次读取的号码'))
            return self.send(200, cached_numbers())

        if path == '/api/imei/devices':
            cached = cached_numbers()
            if s.get('reader') is None:
                return self.send(200, dict(source='cache', stale=True,
                                           warning='当前为离线演示，显示最近一次 VoCat 快照。',
                                           fetched_at=cached.get('fetched_at'),
                                           devices=cached_imei_devices(),
                                           tac_catalog=tac_catalog_meta()))
            try:
                devices, fetched_at = live_imei_devices(s['reader'])
                return self.send(200, dict(source='VoCat', stale=False,
                                           fetched_at=fetched_at, devices=devices,
                                           tac_catalog=tac_catalog_meta()))
            except PermissionError:
                SESSIONS.pop(sid, None)
                return self.err(401, 'VoCat 登录已过期，请重新登录')
            except VoCatError as e:
                if cached.get('devices'):
                    return self.send(200, dict(source='cache', stale=True,
                                               warning=f'{e}，以下显示最近一次 VoCat 快照。',
                                               fetched_at=cached.get('fetched_at'),
                                               devices=cached_imei_devices(),
                                               tac_catalog=tac_catalog_meta()))
                return self.err(e.status, str(e))

        if path == '/api/imei/lookup':
            value = (parse_qs(query).get('imei') or [''])[0]
            return self.send(200, dict(result=imei_model_lookup(value),
                                       tac_catalog=tac_catalog_meta()))

        if path == '/api/imei':
            data = load_imei_groups()
            return self.send(200, dict(groups=data.get('groups') or [], records=imei_records(),
                                       devices=cached_numbers().get('devices') or [],
                                       updated_at=data.get('updated_at'),
                                       tac_catalog=tac_catalog_meta()))

        if path == '/api/settings':
            return self.send(200, load_settings())
        if path == '/api/overview':
            return self.send(200, self.overview())
        if path == '/api/runs':
            return self.send(200, [view(r, full=False) for r in all_runs()])
        if path == '/api/runs/current':
            r = current_run()
            return self.send(200, view(r) if r else {'state': 'idle'})
        if path == '/api/real':
            return self.send(200, real_results())
        if path.startswith('/api/runs/'):
            rid = path.rsplit('/', 1)[-1]
            csv_out = rid.endswith('.csv')
            rid = rid[:-4] if csv_out else rid
            if not rid.isalnum():
                return self.err(400, '批次号不对')
            run = read_json(RUNS / f'{rid}.json')
            if not run:
                return self.err(404, '没有这个批次')
            v = view(run)
            if csv_out:
                return self.send(200, to_csv(v), 'text/csv; charset=utf-8',
                                 {'Content-Disposition': f'attachment; filename="{rid}.csv"'})
            return self.send(200, v)
        return self.err(404, '没有这个接口')

    def do_POST(self):
        path = self.path.partition('?')[0]
        if self.headers.get('X-Requested-With') != 'sms-console':
            return self.err(403, '请求来源不对')
        if path == '/api/login':
            b = self.body()
            user, pw = str(b.get('username') or '').strip(), str(b.get('password') or '')
            if not user or not pw:
                return self.err(400, '请输入用户名和密码')
            reader = VoCatReader()
            try:
                ok = reader.login(user, pw)
            except VoCatError as e:
                return self.err(e.status, str(e))
            if not ok:
                return self.err(401, 'VoCat 拒绝登录（HTTP 401）：用户名或密码不匹配，请核对 VoCat 账号')
            sid = secrets.token_urlsafe(24)
            SESSIONS[sid] = dict(user=user, reader=reader, expires=time.time() + SESSION_HOURS * 3600)
            return self.send(200, dict(user=user), headers={
                'Set-Cookie': f'smsc_session={sid}; Path=/; HttpOnly; SameSite=Strict; Max-Age={SESSION_HOURS * 3600}'})
        if path == '/api/demo-session':
            sid = secrets.token_urlsafe(24)
            SESSIONS[sid] = dict(user='离线演示', reader=None, offline=True,
                                 expires=time.time() + SESSION_HOURS * 3600)
            return self.send(200, dict(user='离线演示', offline=True), headers={
                'Set-Cookie': f'smsc_session={sid}; Path=/; HttpOnly; SameSite=Strict; Max-Age={SESSION_HOURS * 3600}'})
        sid, s = self.session()
        if not s:
            return self.err(401, '请先登录')
        if path == '/api/logout':
            SESSIONS.pop(sid, None)
            return self.send(200, {'ok': True}, headers={'Set-Cookie': 'smsc_session=; Path=/; Max-Age=0'})
        if path == '/api/settings':
            return self.save_settings(self.body())
        if path == '/api/imei/batch-lookup':
            return self.batch_imei_lookup(self.body())
        if path == '/api/imei/save-results':
            return self.save_imei_results(self.body())
        if path == '/api/runs':
            return self.start_run(self.body(), s['user'])
        if path == '/api/imei':
            return self.save_imei(self.body())
        if path == '/api/runs/current/stop':
            with LOCK:
                r = current_run()
                if not r or view(r, full=False)['state'] != 'running':
                    return self.err(409, '当前没有正在进行的测试')
                r['stopped_at'] = time.time()
                write_json(RUNS / f"{r['batch']}.json", r)
            return self.send(200, view(r, full=False))
        return self.err(404, '没有这个接口')

    def batch_imei_lookup(self, body):
        raw = body.get('imeis') if isinstance(body, dict) else None
        if not isinstance(raw, list):
            return self.err(400, 'IMEI 批量输入格式不对')
        if len(raw) > 500:
            return self.err(400, '单次最多查询 500 个 IMEI')
        values = []
        for item in raw:
            if not isinstance(item, str) or len(item) > 100:
                return self.err(400, '每条 IMEI 必须为不超过 100 字符的文本')
            value = item.strip()
            if value:
                values.append(value)
        if not values:
            return self.err(400, '请至少输入一个 IMEI')
        results = [dict(imei=value, result=imei_model_lookup(value)) for value in values]
        matched = sum(1 for row in results if row['result'].get('status') == 'matched')
        valid = sum(1 for row in results if row['result'].get('valid'))
        return self.send(200, dict(results=results, total=len(results), valid=valid,
                                  matched=matched, invalid=len(results) - valid,
                                  queried_at=time.time()))

    def save_imei_results(self, body):
        raw = body.get('imeis') if isinstance(body, dict) else None
        if not isinstance(raw, list) or not 1 <= len(raw) <= 500:
            return self.err(400, '单次保存 1～500 条 IMEI 记录')
        if any(not isinstance(x, str) or not x.strip() or len(x) > 100 for x in raw):
            return self.err(400, '每条 IMEI 必须为非空且不超过 100 字符的文本')
        values = list(dict.fromkeys(x.strip() for x in raw))
        with LOCK:
            data = load_imei_groups()
            existing = {r.get('imei') for r in data['records']}
            added = 0
            for value in values:
                if value in existing:
                    continue
                data['records'].append(dict(id=secrets.token_hex(6), imei=value,
                                            group_id='default', created_at=time.time(), note='',
                                            query_result=imei_model_lookup(value)))
                existing.add(value)
                added += 1
            data['updated_at'] = time.time()
            write_json(IMEI_DATA, data)
            records = imei_records()
        return self.send(200, dict(records=records, added=added, ignored=len(raw) - added))

    def save_imei(self, body):
        data = load_imei_groups()
        action = str(body.get('action') or '')
        if action == 'create_group':
            name = str(body.get('name') or '').strip()
            if not name or len(name) > 40:
                return self.err(400, '分组名称不能为空且最多 40 个字')
            gid = next_group_id(data['groups'])
            data['groups'].append(dict(id=gid, name=name, purpose=str(body.get('purpose') or '').strip()[:80],
                                       note=str(body.get('note') or '').strip()[:200]))
            data['updated_at'] = time.time()
            write_json(IMEI_DATA, data)
            return self.send(200, dict(groups=data['groups'], records=imei_records()))
        if action == 'import':
            group_id = str(body.get('group_id') or 'default')
            if not any(str(g.get('id')) == group_id for g in data['groups']):
                return self.err(400, '请选择有效的 IMEI 分组')
            raw = body.get('imeis') or []
            if not isinstance(raw, list):
                return self.err(400, 'IMEI 输入格式不对')
            values = []
            for item in raw[:100]:
                value = ''.join(ch for ch in str(item).strip() if ch.isdigit())
                if value and value not in values:
                    values.append(value)
            existing = {str(r.get('imei')) for r in data['records']}
            added = 0
            for value in values:
                if value in existing:
                    continue
                data['records'].append(dict(id=secrets.token_hex(6), imei=value, group_id=group_id,
                                            created_at=time.time(), note=''))
                existing.add(value)
                added += 1
            data['updated_at'] = time.time()
            write_json(IMEI_DATA, data)
            return self.send(200, dict(groups=data['groups'], records=imei_records(), added=added,
                                       ignored=max(0, len(values) - added)))
        if action == 'delete':
            ids = {str(x) for x in (body.get('ids') or [])}
            with LOCK:
                data = load_imei_groups()
                data['records'] = [r for r in data['records'] if str(r.get('id')) not in ids]
                data['updated_at'] = time.time()
                write_json(IMEI_DATA, data)
                records = imei_records()
            return self.send(200, dict(groups=data['groups'], records=records))
        return self.err(400, '不支持的 IMEI 操作')

    def save_settings(self, b):
        if b.get('send_mode', 'demo') != 'demo':
            return self.err(403, '本期锁定为演示模式，真实发送暂未开放')
        try:
            s = dict(send_mode='demo',
                     fail_rate=float(b['fail_rate']), undelivered_rate=float(b['undelivered_rate']),
                     latency_min=float(b['latency_min']), latency_max=float(b['latency_max']))
        except (KeyError, TypeError, ValueError):
            return self.err(400, '参数不完整')
        if not (0 <= s['fail_rate'] <= 50 and 0 <= s['undelivered_rate'] <= 50):
            return self.err(400, '失败比例、未到达比例要在 0～50% 之间')
        if not (0.5 <= s['latency_min'] <= s['latency_max'] <= 60):
            return self.err(400, '到达用时要在 0.5～60 秒之间，且最小值不能大于最大值')
        write_json(DATA / 'settings.json', s)
        return self.send(200, s)

    def start_run(self, b, user):
        mode = b.get('mode')
        if mode not in MODES:
            return self.err(400, '请选择发法')
        pool = {n['number']: n for n in cached_numbers()['numbers'] if n['ready']}
        requested = b.get('numbers') or []
        if not isinstance(requested, list) or any(not isinstance(x, str) or x not in pool for x in requested):
            return self.err(400, '所选号码已不可用，请刷新后重选')
        picked = [pool[x] for x in dict.fromkeys(requested)]
        try:
            rounds = int(b.get('rounds', 1))
            gap = float(b.get('gap', 0.5))
        except (TypeError, ValueError):
            return self.err(400, '参数不对')
        if not (1 <= rounds <= 5 and 0.1 <= gap <= 10):
            return self.err(400, '轮数 1～5，间隔 0.1～10 秒')
        pair = None
        source = target = None
        if mode == 'cross_pool':
            pool_from = str(b.get('pool_from') or '')
            pool_to = str(b.get('pool_to') or '')
            if not pool_from or not pool_to or pool_from == pool_to:
                return self.err(400, '请选择两个不同的号池')
            source = [n for n in picked if n.get('pool_id', 'pool-default') == pool_from]
            target = [n for n in picked if n.get('pool_id', 'pool-default') == pool_to]
            if not source or not target:
                return self.err(400, '两个号池都至少需要 1 个就绪号码')
        if mode == 'pair':
            pair = [pool.get(x) for x in b.get('pair') or []]
            if len(pair) != 2 or None in pair or pair[0]['number'] == pair[1]['number']:
                return self.err(400, '请选择两个不同的就绪号码')
            picked = pair
        elif mode != 'cross_pool' and len(picked) < 2:
            return self.err(400, '至少选择 2 个就绪号码')
        if mode in ('relay', 'pairs') or (mode == 'pair' and b.get('pool_id') is not None):
            selected_pools = {n['pool_id'] for n in picked}
            if len(selected_pools) != 1 or (b.get('pool_id') is not None and str(b['pool_id']) not in selected_pools):
                return self.err(400, '号池内部测试只能选择同一台 EC20 的号码')
        with LOCK:
            r = current_run()
            if r and view(r, full=False)['state'] == 'running':
                return self.err(409, '已有测试在进行，请等它结束或先停止')
            plan = plan_pairs(picked, mode, rounds, pair, source=source, target=target)
            if len(plan) > MAX_MESSAGES:
                return self.err(400, f'一次最多 {MAX_MESSAGES} 条，请减少号码或轮数')
            now = datetime.now(BJ)
            batch = 'DEMO' + now.strftime('%m%d%H%M') + ''.join(random.choices(string.ascii_uppercase, k=2))
            settings = load_settings()
            t0 = time.time() + 0.5
            run = dict(batch=batch, demo=True, started=t0, user=user, mode=mode, rounds=rounds, gap=gap,
                       number_count=len(picked), pool_from=b.get('pool_from'), pool_to=b.get('pool_to'),
                       source_count=len(source or []), target_count=len(target or []), settings=settings, stopped_at=None,
                       messages=simulate(plan, gap, settings, batch, t0))
            write_json(RUNS / f'{batch}.json', run)
        return self.send(200, view(run, full=False))

    def overview(self):
        runs = [view(r) for r in all_runs()]
        msgs = [m for r in runs for m in r['messages']]
        st = stats(msgs)
        last = {}
        for r in runs:
            for m in r['messages']:
                if m['status'] in FINAL:
                    for n in (m['sender'], m['receiver']):
                        last[n] = max(last.get(n, 0), m['t_start'])
        per = {p['number']: p for p in st['per_number']}
        numbers = []
        for n in cached_numbers()['numbers']:
            p = per.get(n['number'], {})
            numbers.append(dict(n, send_rate=p.get('send_rate'), receive_rate=p.get('receive_rate'),
                                sent=p.get('sent', 0), expected_in=p.get('expected_in', 0),
                                last_tested=last.get(n['number'])))
        latest = None
        if runs:
            latest = {k: v for k, v in runs[0].items() if k != 'messages'}
        real = real_results()['summary']['overall']
        cached = cached_numbers()
        return dict(summary=st['overall'], run_count=len(runs), latest=latest, numbers=numbers,
                    devices=cached.get('devices') or [], real=real)


def to_csv(v):
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(['批次', '序号', '发送号码', '发送设备', '接收号码', '接收设备', '发出内容', '收到内容',
                '状态', '用时(秒)', '原因', '数据类型'])
    names = dict(delivered='已到达', send_failed='发送失败', undelivered='未到达', cancelled='已停止未发出')
    for m in v['messages']:
        w.writerow([v['batch'], m['seq'], m['sender'], m['sender_dev'], m['receiver'], m['receiver_dev'], m['text'],
                    m['text'] if m['status'] == 'delivered' else '', names.get(m['status'], '进行中'),
                    m.get('latency_s') or '', m.get('reason') or '', '演示（模拟）'])
    return ('﻿' + buf.getvalue()).encode('utf-8')


def main():
    global VOCAT_BASE
    ap = argparse.ArgumentParser(description='号码互发测试台 · 演示版')
    ap.add_argument('--port', type=int, default=8768)
    ap.add_argument('--vocat', default=VOCAT_BASE)
    args = ap.parse_args()
    VOCAT_BASE = args.vocat.rstrip('/')
    RUNS.mkdir(parents=True, exist_ok=True)
    print(f'号码互发测试台（演示版）: http://127.0.0.1:{args.port}', flush=True)
    ThreadingHTTPServer(('127.0.0.1', args.port), Handler).serve_forever()


if __name__ == '__main__':
    main()
