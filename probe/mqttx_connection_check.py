"""Bounded MQTTX CLI login check. No subscriptions, commands or business ACKs.

Credentials are parsed as data, never executed, and are not saved in evidence.
MQTTX accepts the password as a process argument; it is not put in shell history.
"""
import argparse
import json
import re
import subprocess
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--credentials-file', required=True, type=Path)
    args = parser.parse_args()
    fields = {}
    for line in args.credentials_file.read_text('utf-8-sig').splitlines():
        parts = re.split(r'[:\uff1a]', line, maxsplit=1)
        if len(parts) == 2:
            fields[parts[0].strip().lower()] = parts[1].strip()
    endpoint = re.match(r'^(\d{1,3}(?:\.\d{1,3}){3}):(\d+)\b', fields.get('broker', ''))
    account = fields.get('\u8d26\u53f7', '').split('/', 1)
    if endpoint is None or len(account) != 2 or not all(s.strip() for s in account):
        raise SystemExit('Credential file format not recognized; no connection attempted.')
    username, password = (s.strip() for s in account)
    host, port = endpoint.groups()
    prefix = fields.get('client id', '')
    if not prefix:
        raise SystemExit('Missing business client ID; no connection attempted.')
    # A unique suffix avoids disconnecting an existing client with the same ID.
    client_id = prefix + '-conn-' + uuid.uuid4().hex[:8]
    cli = Path('C:/Users/27792/AppData/Local/Programs/mqttx-cli/mqttx.exe')
    started = datetime.now(timezone(timedelta(hours=8)))
    version = subprocess.run([str(cli), '--version'], capture_output=True, timeout=10,
                             creationflags=subprocess.CREATE_NO_WINDOW).stdout.decode('utf-8', 'replace').splitlines()[0]
    command = [str(cli), 'conn', '-h', host, '-p', port, '-l', 'mqtt', '-V', '5.0',
               '-i', client_id, '-u', username, '-P', password,
               '-rp', '0', '--maximum-reconnect-times', '0']
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               creationflags=subprocess.CREATE_NO_WINDOW)
    stopped_at_deadline = False
    try:
        output, _ = process.communicate(timeout=10)
    except subprocess.TimeoutExpired:
        stopped_at_deadline = True
        process.terminate()
        output, _ = process.communicate(timeout=5)
    text = output.decode('utf-8', 'replace').replace(password, '[REDACTED]').replace(username, '[ACCOUNT]')
    text = re.sub(r'\x1b\[[0-9;]*[a-zA-Z]', '', text)
    connected = bool(re.search(r'\bConnected\b', text))
    result = dict(scope='MQTTX connection only; no subscribe/publish/business ACK',
                  started_at=started.isoformat(), finished_at=datetime.now(started.tzinfo).isoformat(),
                  mqttx_version=version, broker=f'{host}:{port}', tls=False, mqtt_version=5,
                  client_id=client_id, broker_login_observed=connected,
                  stopped_at_deadline=stopped_at_deadline, process_exit_code=process.returncode,
                  sanitized_cli_output=text, protocol_cases_completed=0)
    directory = Path(__file__).resolve().parents[1] / 'evidence' / ('mqttx-conn-' + started.strftime('%Y%m%d-%H%M%S'))
    directory.mkdir(exist_ok=False)
    (directory / 'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=True, indent=2))
    print('Evidence: ' + str(directory / 'result.json'))
    return 0 if connected else 1


if __name__ == '__main__':
    raise SystemExit(main())
