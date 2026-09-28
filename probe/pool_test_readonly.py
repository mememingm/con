"""Read-only pool test over the VoCat REST API (no MQTT client of our own).

Runs the fixed pool-test sequence against SIMHub/VoCat, which already owns the
authorized MQTT session to the node, so this never opens a second broker
connection and cannot kick any client. Every request is GET (only the login is
POST); no card writes, no SMS, no config changes.

Fixed sequence -> VoCat read-only endpoint:
  node.describe       -> GET /system/info  + /settings/node-mqtt (status)
  inventory.get       -> GET /devices
  slot.refresh        -> GET /devices/{id}/multisim
  esim.profiles.list  -> GET /devices/{id}/esim/profiles
  phones.list         -> derived from multisim lines
  phones.check        -> per-line readiness from multisim line state

Evidence (with ICCID/IMEI/IMSI/EID redacted) is written under
.local/pool-console/<run-id>/. Phone numbers are kept: they are the pool's
own identity, and the SIMs belong to the operator running this test.
"""
import argparse
import http.cookiejar
import json
import re
import sys
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

BJ = timezone(timedelta(hours=8))
SECRET = re.compile(r'iccid|imsi|imei|eid|certificate|trustedci|csrf|password|secret|token', re.I)


def now():
    return datetime.now(BJ)


def read_credentials(path):
    lines = [s.strip() for s in path.read_text('utf-8-sig').splitlines() if s.strip()]
    fields = {}
    for line in lines:
        parts = re.split(r'[:：=]', line, maxsplit=1)
        if len(parts) == 2 and not re.match(r'^\s*https?$', parts[0], re.I):
            fields[parts[0].strip().lower()] = parts[1].strip()
    user = fields.get('username') or fields.get('user') or fields.get('账号')
    password = fields.get('password') or fields.get('密码')
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


class Client:
    def __init__(self, base, user, password):
        self.base, self.user, self.password = base, user, password
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))

    def request(self, path, body=None):
        data = None if body is None else json.dumps(body).encode()
        req = urllib.request.Request(self.base + '/api' + path, data=data,
                                     headers={'Content-Type': 'application/json'})
        try:
            with self.opener.open(req, timeout=20) as resp:
                payload = json.loads(resp.read() or b'null')
                if isinstance(payload, dict) and 'data' in payload:
                    payload = payload['data']
                return resp.status, payload
        except urllib.error.HTTPError as error:
            text = error.read().decode('utf-8', 'replace')
            return error.code, text.replace(self.password, '[P]').replace(self.user, '[U]')[:200]


def line_ready(state):
    checks = ('sim_ready', 'ims_ready', 'tunnel_ready', 'sms_ready')
    return all(bool(state.get(k)) for k in checks), {k: bool(state.get(k)) for k in checks}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--credentials-file', type=Path, required=True)
    parser.add_argument('--base', default='http://192.168.1.5:7575')
    args = parser.parse_args()
    user, password = read_credentials(args.credentials_file)
    client = Client(args.base, user, password)

    run_id = now().strftime('%Y%m%d-%H%M%S') + '-' + uuid.uuid4().hex[:8]
    out = Path(__file__).resolve().parents[1] / '.local' / 'pool-console' / run_id
    out.mkdir(parents=True, exist_ok=True)
    steps = []

    def step(name, endpoint, status, ok, note, raw=None):
        steps.append(dict(step=name, endpoint=endpoint, http=status, ok=ok, note=note))
        if raw is not None:
            (out / f'{name}.json').write_text(
                json.dumps(redact(raw), ensure_ascii=False, indent=2), encoding='utf-8')
        print(f'[{"PASS" if ok else "FAIL"}] {name:18} {endpoint:34} HTTP {status}  {note}', flush=True)

    status, _ = client.request('/auth/login', {'username': user, 'password': password})
    if status != 200:
        print(f'login failed: HTTP {status}; aborting.')
        return 1
    print(f'login: HTTP {status}   run={run_id}\n')

    # 1. node.describe
    st, info = client.request('/system/info')
    st2, nm = client.request('/settings/node-mqtt')
    conn = (nm or {}).get('status', {}) if isinstance(nm, dict) else {}
    node_ok = st == 200 and st2 == 200 and conn.get('connected') and conn.get('subscribed')
    step('node.describe', '/system/info+/node-mqtt', st,
         bool(node_ok),
         f"version={info.get('version') if isinstance(info, dict) else '?'} "
         f"connected={conn.get('connected')} subscribed={conn.get('subscribed')} "
         f"ack={ (nm or {}).get('settings',{}).get('business_ack_enabled') if isinstance(nm,dict) else '?'}",
         raw={'system_info': info, 'node_mqtt': nm})

    # 2. inventory.get
    st, devs = client.request('/devices')
    device_list = devs.get('devices', []) if isinstance(devs, dict) else (devs if isinstance(devs, list) else [])
    inv_ok = st == 200 and len(device_list) > 0
    step('inventory.get', '/devices', st, inv_ok,
         f'devices={len(device_list)}', raw=devs)

    pool_rows = []
    for dev in device_list:
        did = dev.get('id')
        healthy = dev.get('healthy')

        # 3. slot.refresh (read current multisim/slot state)
        st, ms = client.request(f'/devices/{did}/multisim')
        lines = (ms.get('state', {}) or {}).get('lines', []) if isinstance(ms, dict) else []
        step('slot.refresh', f'/devices/{did}/multisim', st,
             st == 200 and isinstance(ms, dict),
             f'device={did} healthy={healthy} lines={len(lines)}', raw=ms)

        # 4. esim.profiles.list
        st, prof = client.request(f'/devices/{did}/esim/profiles')
        profile_count = sum(len(g.get('profiles', [])) for g in prof) if isinstance(prof, list) else 0
        step('esim.profiles.list', f'/devices/{did}/esim/profiles', st,
             st == 200 and profile_count > 0,
             f'device={did} profiles={profile_count}', raw=prof)

        # 5+6. phones.list / phones.check
        for ln in lines:
            state = ln.get('state', {}) if isinstance(ln, dict) else {}
            ready, detail = line_ready(state)
            pool_rows.append(dict(device=did, number=ln.get('name'),
                                  phase=state.get('phase'), ready=ready, **detail))

    ready_count = sum(1 for r in pool_rows if r['ready'])
    total = len(pool_rows)
    step('phones.check', 'multisim line state', 200, total > 0 and ready_count == total,
         f'ready {ready_count}/{total}')

    print('\n号池就绪明细 (phones.check):')
    for r in pool_rows:
        flag = 'READY' if r['ready'] else 'NOT-READY'
        print(f"  {r['number']:16} dev {r['device']:>2}  {r['phase']:12} "
              f"sim={int(r['sim_ready'])} ims={int(r['ims_ready'])} "
              f"tun={int(r['tunnel_ready'])} sms={int(r['sms_ready'])}  [{flag}]")

    overall = all(s['ok'] for s in steps)
    summary = dict(run_id=run_id, finished_at=now().isoformat(),
                   overall_pass=overall, steps=steps,
                   pool_ready=ready_count, pool_total=total, pool=pool_rows)
    (out / 'report.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'\n总结: 步骤全部通过={overall}, 号池就绪={ready_count}/{total}')
    print(f'证据目录: {out}')
    return 0 if overall else 1


if __name__ == '__main__':
    sys.exit(main())
