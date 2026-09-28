"""Read-only SIMHub /node-mqtt status check.

Logs in to the SIMHub web API, then reads /auth/session and
/settings/node-mqtt. Never calls the connection test or saves settings.
Credentials are read from a file, never printed, and never saved.
"""
import argparse
import http.cookiejar
import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

SENSITIVE = re.compile(r'pass|secret|token|key|csrf|cert', re.I)


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
    # Two-line form: last non-address token of line 1, whole line 2.
    if len(lines) == 2:
        tokens = [t for t in lines[0].split() if not re.match(r'^(https?://|\d{1,3}(\.\d{1,3}){3})', t)]
        if tokens:
            return tokens[-1], lines[1]
    raise SystemExit('Credential file format not recognized; no request sent.')


def redact(value):
    if isinstance(value, dict):
        return {k: '[REDACTED]' if SENSITIVE.search(k) and v not in (None, '', False) else redact(v)
                for k, v in value.items()}
    if isinstance(value, list):
        return [redact(v) for v in value]
    return value


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--credentials-file', type=Path, required=True)
    parser.add_argument('--base', default='http://192.168.1.5:7575')
    args = parser.parse_args()
    user, password = read_credentials(args.credentials_file)
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))

    def call(path, body=None):
        data = None if body is None else json.dumps(body).encode()
        request = urllib.request.Request(args.base + '/api' + path, data=data,
                                         headers={'Content-Type': 'application/json'})
        try:
            with opener.open(request, timeout=10) as response:
                return response.status, json.loads(response.read() or b'null')
        except urllib.error.HTTPError as error:
            text = error.read().decode('utf-8', 'replace')
            return error.code, text.replace(password, '[P]').replace(user, '[U]')[:300]

    status, body = call('/auth/login', {'username': user, 'password': password})
    print(f'login: HTTP {status}')
    if status != 200:
        print(body)
        return 1
    for path in ('/auth/session', '/settings/node-mqtt'):
        status, body = call(path)
        text = json.dumps(redact(body), ensure_ascii=False, indent=2).replace(user, '[U]')
        print(f'--- GET {path}: HTTP {status}\n{text}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
