"""Read-only tour of SIMHub/VoCat GET endpoints (no MQTT client of our own).

Logs in with vocat.txt, then issues GET-only requests to read-only list
endpoints. VoCat uses its own already-authorized MQTT session to reach the node,
so this never opens a second broker connection and cannot kick any client.
No POST/PUT/DELETE is ever sent. Sensitive fields are redacted; credentials are
read from a file, never printed, never saved.
"""
import argparse
import http.cookiejar
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

SENSITIVE = re.compile(r'pass|secret|token|key|csrf|cert|iccid|imsi|imei|msisdn|phone|number', re.I)
READ_PATHS = ['/system/info', '/dashboard/host', '/dashboard/devices', '/devices']


def read_credentials(path):
    lines = [s.strip() for s in path.read_text('utf-8-sig').splitlines() if s.strip()]
    fields = {}
    for line in lines:
        parts = re.split(r'[:：=]', line, maxsplit=1)
        if len(parts) == 2 and not re.match(r'^\s*https?$', parts[0], re.I):
            fields[parts[0].strip().lower()] = parts[1].strip()
    user = fields.get('username') or fields.get('user') or fields.get('账号') or fields.get('用户名')
    password = fields.get('password') or fields.get('密码')
    if user and password:
        return user, password
    if len(lines) == 2:
        tokens = [t for t in lines[0].split() if not re.match(r'^(https?://|\d{1,3}(\.\d{1,3}){3})', t)]
        if tokens:
            return tokens[0], lines[1]
    raise SystemExit('vocat.txt format not recognized; aborting.')


def redact(value, depth=0):
    if isinstance(value, dict):
        return {k: ('[REDACTED]' if SENSITIVE.search(k) and v not in (None, '', False, 0) else redact(v, depth + 1))
                for k, v in value.items()}
    if isinstance(value, list):
        head = [redact(v, depth + 1) for v in value[:2]]
        if len(value) > 2:
            head.append(f'...(+{len(value) - 2} more, {len(value)} total)')
        return head
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--credentials-file', type=Path, required=True)
    parser.add_argument('--base', default='http://192.168.1.5:7575')
    args = parser.parse_args()
    user, password = read_credentials(args.credentials_file)
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))

    def get(path, body=None):
        # body only for the login POST; everything else is GET.
        data = None if body is None else json.dumps(body).encode()
        request = urllib.request.Request(args.base + '/api' + path, data=data,
                                         headers={'Content-Type': 'application/json'})
        try:
            with opener.open(request, timeout=15) as response:
                return response.status, json.loads(response.read() or b'null')
        except urllib.error.HTTPError as error:
            text = error.read().decode('utf-8', 'replace')
            return error.code, text.replace(password, '[P]').replace(user, '[U]')[:200]

    status, _ = get('/auth/login', {'username': user, 'password': password})
    print(f'login: HTTP {status}')
    if status != 200:
        return 1
    for path in READ_PATHS:
        status, body = get(path)
        if isinstance(body, dict) and 'data' in body:
            body = body['data']
        shaped = json.dumps(redact(body), ensure_ascii=False, indent=2).replace(user, '[U]')
        if len(shaped) > 2500:
            shaped = shaped[:2500] + '\n...[truncated]'
        print(f'--- GET {path}: HTTP {status}\n{shaped}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
