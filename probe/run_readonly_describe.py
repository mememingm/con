"""Run a read-only node.describe using broker config fetched from the web API.

Logs in to SIMHub with vocat.txt, reads /settings/node-mqtt to obtain the live
broker host/port/node/username/password, writes a short-lived credentials file
(unique client-id prefix so it can never kick the VoCat service or another test
session), runs the existing mqttx_readonly.py probe, then deletes the temp file.
The password lives only in the process and the temp file, and is removed after.
"""
import http.cookiejar
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
import uuid
from pathlib import Path

BASE = 'http://192.168.1.5:7575'
VOCAT = Path(r'C:\Users\27792\Desktop\vocat.txt')
PROBE = Path(__file__).resolve().parent / 'mqttx_readonly.py'
PYTHON = Path(__file__).resolve().parents[1] / '.venv' / 'Scripts' / 'python.exe'


def read_credentials(path):
    lines = [s.strip() for s in path.read_text('utf-8-sig').splitlines() if s.strip()]
    fields = {}
    for line in lines:
        parts = re.split(r'[:\uff1a=]', line, maxsplit=1)
        if len(parts) == 2 and not re.match(r'^\s*https?$', parts[0], re.I):
            fields[parts[0].strip().lower()] = parts[1].strip()
    user = fields.get('username') or fields.get('user') or fields.get('\u8d26\u53f7') or fields.get('\u7528\u6237\u540d')
    password = fields.get('password') or fields.get('\u5bc6\u7801')
    if user and password:
        return user, password
    if len(lines) == 2:
        tokens = [t for t in lines[0].split() if not re.match(r'^(https?://|\d{1,3}(\.\d{1,3}){3})', t)]
        if tokens:
            return tokens[0], lines[1]
    raise SystemExit('vocat.txt format not recognized; aborting.')


def main():
    user, password = read_credentials(VOCAT)
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))

    def call(path, body=None):
        data = None if body is None else json.dumps(body).encode()
        request = urllib.request.Request(BASE + '/api' + path, data=data,
                                         headers={'Content-Type': 'application/json'})
        with opener.open(request, timeout=10) as response:
            return json.loads(response.read() or b'null')

    call('/auth/login', {'username': user, 'password': password})
    settings = call('/settings/node-mqtt')['data']['settings']
    host, port = settings['host'], settings['port']
    node, broker_user, broker_pass = settings['node'], settings['username'], settings['password']

    # Unique, clearly-labelled client prefix; the probe adds -rx-/-tx-<uuid> too.
    prefix = 'cc-readonly-' + uuid.uuid4().hex[:6]
    fd, temp_name = tempfile.mkstemp(prefix='brk-', suffix='.txt')
    temp = Path(temp_name)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as handle:
            handle.write(f'broker: {host}:{port}\n')
            handle.write(f'\u8d26\u53f7: {broker_user}/{broker_pass}\n')
            handle.write(f'\u8282\u70b9\u7f16\u53f7: {node}\n')
            handle.write(f'client id: {prefix}\n')
        print(f'broker={host}:{port} node={node} client_prefix={prefix}', flush=True)
        result = subprocess.run(
            [str(PYTHON), str(PROBE), '--credentials-file', str(temp), '--action', 'node.describe'],
            capture_output=True, timeout=180)
        out = result.stdout.decode('utf-8', 'replace')
        err = result.stderr.decode('utf-8', 'replace')
        for stream in (out, err):
            if stream.strip():
                print(stream.replace(broker_pass, '[REDACTED]').replace(broker_user, '[ACCOUNT]'), flush=True)
        return result.returncode
    finally:
        try:
            temp.unlink()
        except OSError:
            pass
        print(f'temp credentials removed: exists={temp.exists()}', flush=True)


if __name__ == '__main__':
    sys.exit(main())
