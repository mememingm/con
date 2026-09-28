"""Read-only discovery of per-device VoCat GET endpoints for device '1'."""
import http.cookiejar
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

BASE = 'http://192.168.1.5:7575'
VOCAT = Path(r'C:\Users\27792\Desktop\vocat.txt')
SENS = re.compile(r'pass|secret|token|key|csrf|cert|iccid|imsi|imei|msisdn', re.I)


def creds(path):
    lines = [s.strip() for s in path.read_text('utf-8-sig').splitlines() if s.strip()]
    tokens = [t for t in lines[0].split() if not re.match(r'^(https?://|\d{1,3}(\.\d{1,3}){3})', t)]
    return tokens[0], lines[1]


def redact(v):
    if isinstance(v, dict):
        return {k: ('[R]' if SENS.search(k) and v[k] not in (None, '', False, 0) else redact(v[k])) for k in v}
    if isinstance(v, list):
        return [redact(x) for x in v[:1]] + ([f'...(+{len(v)-1})'] if len(v) > 1 else [])
    return v


def main():
    user, pw = creds(VOCAT)
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))

    def get(path, body=None):
        data = None if body is None else json.dumps(body).encode()
        r = urllib.request.Request(BASE + '/api' + path, data=data, headers={'Content-Type': 'application/json'})
        try:
            with op.open(r, timeout=20) as resp:
                return resp.status, json.loads(resp.read() or b'null')
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode('utf-8', 'replace')[:200]

    get('/auth/login', {'username': user, 'password': pw})
    for path in ['/devices/1/overview', '/devices/1/esim', '/devices/1/esim/profiles', '/devices/1/multisim', '/devices/1/cellular-ims']:
        st, body = get(path)
        if isinstance(body, dict) and 'data' in body:
            body = body['data']
        s = json.dumps(redact(body), ensure_ascii=False)
        print(f'--- GET {path}: HTTP {st}\n{s[:1200]}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
