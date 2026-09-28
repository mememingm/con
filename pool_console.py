"""Local pool-test console: VoCat REST baseline + MQ layer-1 protocol tests.

Runs on the laptop, binds to 127.0.0.1 only. Two read-only test paths:

* REST baseline ("VoCat API" evidence): logs in to the VoCat web API and reads the
  node's own state. It does not touch the broker.
* MQ layer 1 ("direct MQTT" evidence): mq_layer1.py connects to the broker as the
  business side with the dedicated tester client_id and runs the read-only protocol
  cases of 24-MQ接口测试清单. Only one MQ run at a time, because a second connection
  with the same client_id would kick the first. It never publishes /ack.

The coverage view (mq_coverage.py) lists all 68 checklist items; layer 2/3 and
long-run items are shown and explained but never executed from this console.

Read-only by construction: the only requests it makes to VoCat are the login
POST and GET queries. It never sends SMS, writes cards, or changes any config.
Credentials are read server-side from a file and are never exposed to the page.

Fixed sequence -> VoCat read-only endpoint:
  node.describe       -> GET /system/info + /settings/node-mqtt (status)
  inventory.get       -> GET /devices
  slot.refresh        -> GET /devices/{id}/multisim
  esim.profiles.list  -> GET /devices/{id}/esim/profiles
  phones.list/check   -> derived from multisim line state

Run:  .venv\\Scripts\\python.exe pool_console.py
Then open http://127.0.0.1:8765
"""
import argparse
import http.cookiejar
import json
import os
import re
import threading
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import mq_coverage
import mq_layer1

BJ = timezone(timedelta(hours=8))
ROOT = Path(__file__).resolve().parent
WEB = ROOT / 'web'
EVIDENCE = ROOT / '.local' / 'pool-console'
SECRET = re.compile(r'iccid|imsi|imei|eid|certificate|trustedci|csrf|password|secret|token', re.I)
BASE = os.environ.get('VOCAT_BASE', 'http://192.168.1.5:7575')
CREDS = Path(os.environ.get('VOCAT_CREDENTIALS', r'C:\Users\27792\Desktop\vocat.txt'))


def now():
    return datetime.now(BJ)


def read_credentials(path):
    lines = [s.strip() for s in path.read_text('utf-8-sig').splitlines() if s.strip()]
    fields = {}
    for line in lines:
        parts = re.split(r'[:\uff1a=]', line, maxsplit=1)
        if len(parts) == 2 and not re.match(r'^\s*https?$', parts[0], re.I):
            fields[parts[0].strip().lower()] = parts[1].strip()
    user = fields.get('username') or fields.get('user') or fields.get('\u8d26\u53f7')
    password = fields.get('password') or fields.get('\u5bc6\u7801')
    if user and password:
        return user, password
    if len(lines) == 2:
        tokens = [t for t in lines[0].split() if not re.match(r'^(https?://|\d{1,3}(\.\d{1,3}){3})', t)]
        if tokens:
            return tokens[0], lines[1]
    raise SystemExit('vocat.txt format not recognized; aborting.')


def redact(value):
    if isinstance(value, dict):
        return {k: ('[REDACTED]' if SECRET.search(k) and value[k] not in (None, '', False, 0) else redact(value[k]))
                for k in value}
    if isinstance(value, list):
        return [redact(v) for v in value]
    return value


class VoCat:
    """A short-lived authenticated session that only issues login + GET."""

    def __init__(self):
        self.user, self.password = read_credentials(CREDS)
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        status, _ = self._call('/auth/login', {'username': self.user, 'password': self.password})
        if status != 200:
            raise RuntimeError(f'VoCat login failed: HTTP {status}')

    def _call(self, path, body=None):
        data = None if body is None else json.dumps(body).encode()
        req = urllib.request.Request(BASE + '/api' + path, data=data,
                                     headers={'Content-Type': 'application/json'})
        try:
            with self.opener.open(req, timeout=20) as resp:
                payload = json.loads(resp.read() or b'null')
                if isinstance(payload, dict) and 'data' in payload:
                    payload = payload['data']
                return resp.status, payload
        except urllib.error.HTTPError as error:
            return error.code, None

    def get(self, path):
        return self._call(path)


def line_ready(state):
    checks = ('sim_ready', 'ims_ready', 'tunnel_ready', 'sms_ready')
    return all(bool(state.get(k)) for k in checks), {k: bool(state.get(k)) for k in checks}


def list_pool():
    """Return the selectable pool: devices and their lines (numbers only)."""
    vocat = VoCat()
    status, devs = vocat.get('/devices')
    device_list = devs.get('devices', []) if isinstance(devs, dict) else (devs if isinstance(devs, list) else [])
    pool = []
    for dev in device_list:
        did = dev.get('id')
        _, ms = vocat.get(f'/devices/{did}/multisim')
        lines = (ms.get('state', {}) or {}).get('lines', []) if isinstance(ms, dict) else []
        pool.append(dict(
            id=did,
            model=dev.get('modem', {}).get('model') or dev.get('device_type'),
            healthy=bool(dev.get('healthy')),
            lifecycle=dev.get('lifecycle_phase'),
            lines=[dict(number=ln.get('name'), phase=(ln.get('state', {}) or {}).get('phase'))
                   for ln in lines],
        ))
    return dict(base=BASE, devices=pool)


def run_sequence(device_ids):
    """Run the fixed read-only sequence for the selected devices."""
    vocat = VoCat()
    run_id = now().strftime('%Y%m%d-%H%M%S') + '-' + uuid.uuid4().hex[:8]
    out = EVIDENCE / run_id
    out.mkdir(parents=True, exist_ok=True)
    steps = []

    def record(name, endpoint, status, ok, note, raw=None):
        entry = dict(step=name, endpoint=endpoint, http=status, ok=bool(ok), note=note,
                     at=now().isoformat())
        steps.append(entry)
        if raw is not None:
            (out / f'{len(steps):02d}-{name}.json').write_text(
                json.dumps(redact(raw), ensure_ascii=False, indent=2), encoding='utf-8')
        return entry

    # 1. node.describe
    st, info = vocat.get('/system/info')
    st2, nm = vocat.get('/settings/node-mqtt')
    conn = (nm or {}).get('status', {}) if isinstance(nm, dict) else {}
    settings = (nm or {}).get('settings', {}) if isinstance(nm, dict) else {}
    record('node.describe', '/system/info + /settings/node-mqtt', st,
           st == 200 and st2 == 200 and conn.get('connected') and conn.get('subscribed'),
           f"version={info.get('version') if isinstance(info, dict) else '?'}, "
           f"connected={conn.get('connected')}, subscribed={conn.get('subscribed')}, "
           f"ack={settings.get('business_ack_enabled')}",
           raw={'system_info': info, 'node_mqtt': nm})

    # 2. inventory.get
    st, devs = vocat.get('/devices')
    all_devices = devs.get('devices', []) if isinstance(devs, dict) else (devs if isinstance(devs, list) else [])
    selected = [d for d in all_devices if str(d.get('id')) in {str(x) for x in device_ids}] or all_devices
    record('inventory.get', '/devices', st, st == 200 and len(all_devices) > 0,
           f'devices_total={len(all_devices)}, selected={len(selected)}', raw=devs)

    pool_rows = []
    for dev in selected:
        did = dev.get('id')
        # 3. slot.refresh
        st, ms = vocat.get(f'/devices/{did}/multisim')
        lines = (ms.get('state', {}) or {}).get('lines', []) if isinstance(ms, dict) else []
        record('slot.refresh', f'/devices/{did}/multisim', st,
               st == 200 and isinstance(ms, dict),
               f'device={did}, healthy={dev.get("healthy")}, lines={len(lines)}', raw=ms)
        # 4. esim.profiles.list
        st, prof = vocat.get(f'/devices/{did}/esim/profiles')
        profile_count = sum(len(g.get('profiles', [])) for g in prof) if isinstance(prof, list) else 0
        record('esim.profiles.list', f'/devices/{did}/esim/profiles', st,
               st == 200 and profile_count > 0,
               f'device={did}, profiles={profile_count}', raw=prof)
        # 5+6. phones.list / phones.check
        for ln in lines:
            state = ln.get('state', {}) if isinstance(ln, dict) else {}
            ready, detail = line_ready(state)
            pool_rows.append(dict(device=did, number=ln.get('name'),
                                  phase=state.get('phase'), ready=ready, **detail))

    ready_count = sum(1 for r in pool_rows if r['ready'])
    total = len(pool_rows)
    record('phones.check', 'multisim line state', 200,
           total > 0 and ready_count == total,
           f'ready {ready_count}/{total}')

    overall = all(s['ok'] for s in steps)
    report = dict(run_id=run_id, base=BASE, finished_at=now().isoformat(),
                  overall_pass=overall, steps=steps,
                  pool_ready=ready_count, pool_total=total, pool=pool_rows,
                  evidence_dir=str(out))
    (out / 'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    return report


class MqJob:
    """At most one MQ layer-1 run at a time; progress is polled by the page."""

    def __init__(self):
        self.lock = threading.Lock()
        self.running = False
        self.log, self.error, self.result, self.repeat = [], None, None, None

    def start(self, include_t43=True, repeat=0, interval_s=10):
        with self.lock:
            if self.running:
                return False
            self.running, self.log, self.error = True, [], None
        threading.Thread(target=self._work, args=(include_t43, repeat, interval_s), daemon=True).start()
        return True

    def _work(self, include_t43, repeat, interval_s):
        try:
            if repeat:
                self.repeat = mq_layer1.repeat(repeat, interval_s, include_t43=include_t43, progress=self.log.append)
            else:
                self.result = mq_layer1.run(progress=self.log.append, include_t43=include_t43)
        except Exception as error:
            self.error = str(error)
            self.log.append(f'运行中止：{error}')
        finally:
            with self.lock:
                self.running = False

    def status(self):
        rep = self.repeat
        return {'running': self.running, 'log': self.log[-300:], 'error': self.error,
                'run_id': (self.result or {}).get('run_id'),
                'repeat': {k: rep[k] for k in ('repeat_id', 'runs', 'same_code', 'run_fingerprint_consistent',
                                               'environment_consistent', 'deterministic_stable', 'deterministic_total',
                                               'flipped', 'cases', 'evidence_dir', 'run_fingerprints')} if rep else None}

    def latest(self):
        return mq_coverage.stable_run()


MQ = MqJob()

CONTENT_TYPES = {'.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8',
                 '.css': 'text/css; charset=utf-8'}


class Handler(BaseHTTPRequestHandler):
    server_version = 'PoolConsole/1.0'

    def log_message(self, *args):
        pass  # keep the console quiet

    def _send(self, status, body, content_type='application/json; charset=utf-8'):
        data = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', content_type)
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _static(self, name):
        path = (WEB / name).resolve()
        if WEB not in path.parents or not path.is_file():
            return self._send(404, {'error': 'not found'})
        self._send(200, path.read_bytes(), CONTENT_TYPES.get(path.suffix, 'application/octet-stream'))

    def do_GET(self):
        if self.path in ('/', '/index.html'):
            return self._static('index.html')
        if self.path == '/api/pool':
            try:
                return self._send(200, list_pool())
            except Exception as error:
                return self._send(502, {'error': str(error)})
        if self.path == '/api/mq/status':
            return self._send(200, MQ.status())
        if self.path == '/api/mq/coverage':
            return self._send(200, mq_coverage.coverage(MQ.latest()))
        if self.path == '/api/mq/report.md':
            cov = mq_coverage.coverage(MQ.latest())
            text = mq_coverage.to_markdown(cov)
            if cov.get('evidence_dir'):
                (Path(cov['evidence_dir']) / 'report.md').write_text(text, encoding='utf-8')
            name = f"mq-layer1-{cov.get('run_id') or 'empty'}.md"
            data = text.encode('utf-8')
            self.send_response(200)
            self.send_header('Content-Type', 'text/markdown; charset=utf-8')
            self.send_header('Content-Disposition', f'attachment; filename="{name}"')
            self.send_header('Content-Length', str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        if self.path.startswith('/') and '..' not in self.path:
            return self._static(self.path.lstrip('/'))
        return self._send(404, {'error': 'not found'})

    def do_POST(self):
        length = int(self.headers.get('Content-Length', 0) or 0)
        if self.path == '/api/mq/run':
            body = json.loads(self.rfile.read(length) or b'{}')
            if not MQ.start(bool(body.get('include_t43', True))):
                return self._send(409, {'error': '已有一个 MQ 测试在运行（同一 client_id 不能并发连接）'})
            return self._send(202, MQ.status())
        if self.path == '/api/mq/repeat':
            body = json.loads(self.rfile.read(length) or b'{}')
            n = max(1, min(10, int(body.get('n', 5))))
            interval_s = max(0, min(120, int(body.get('interval_s', 10))))
            if not MQ.start(bool(body.get('include_t43', False)), repeat=n, interval_s=interval_s):
                return self._send(409, {'error': '已有一个 MQ 测试在运行（同一 client_id 不能并发连接）'})
            return self._send(202, MQ.status())
        if self.path != '/api/run':
            return self._send(404, {'error': 'not found'})
        try:
            body = json.loads(self.rfile.read(length) or b'{}')
            device_ids = body.get('device_ids', [])
            return self._send(200, run_sequence(device_ids))
        except Exception as error:
            return self._send(502, {'error': str(error)})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=8765)
    args = parser.parse_args()
    # Check credentials but allow server to start without them (demo mode)
    try:
        read_credentials(CREDS)
        print('✓ Credentials loaded')
    except (FileNotFoundError, SystemExit) as e:
        print(f'⚠ No credentials found (demo mode): {e}')
        print('  API calls will fail, but web interface is available for testing')
    server = ThreadingHTTPServer((args.host, args.port), Handler)
    print(f'Pool console (read-only) on http://{args.host}:{args.port}')
    print(f'VoCat base: {BASE}   evidence: {EVIDENCE}')
    print(f'MQ credentials: {mq_layer1.BROKER_CREDENTIALS}   MQ evidence: {mq_coverage.MQ_EVIDENCE}')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\\nstopped')


if __name__ == '__main__':
    main()
