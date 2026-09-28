"""Minimal read-only MQTT probe with the dedicated tester credential.

One connection using exactly the client_id from the desktop Broker file.
Subscribes task/event/presence/heartbeat, publishes one node.describe
(new UUID, with expires_at), waits for the terminal task state, disconnects.
Never sends /ack, never publishes anything else. Password is never printed
or written to evidence.
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
TERMINAL = ('succeeded', 'failed', 'expired', 'uncertain', 'rejected')


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


def now_s(dt=None):
    return (dt or datetime.now(CST)).strftime('%Y-%m-%d %H:%M:%S')


def main():
    host, port, user, pw, cid, node = load_cred()
    prefix = f'cardpool/v1/nodes/{node}'
    run = datetime.now(CST).strftime('%Y%m%d-%H%M%S') + '-' + uuid.uuid4().hex[:6]
    ev = ROOT / '.local' / 'mqtt-probe' / run
    ev.mkdir(parents=True, exist_ok=True)
    log, msgs = [], []
    done, connected = threading.Event(), threading.Event()
    state = {}

    def note(s):
        line = f'{now_s()} {s}'
        print(line, flush=True)
        log.append(line)

    task_id = str(uuid.uuid4())
    t0 = datetime.now(CST)
    cmd = {'id': task_id, 'action': 'node.describe', 'time': now_s(t0),
           'expires_at': now_s(t0 + timedelta(seconds=120)), 'params': {}}

    def on_connect(c, u, flags, rc, props):
        state['connack'] = str(rc)
        note(f'CONNACK reason={rc} session_present={flags.session_present}')
        (done if rc.is_failure else connected).set()

    def on_subscribe(c, u, mid, rcs, props):
        note('SUBACK ' + ', '.join(str(r) for r in rcs))

    def on_message(c, u, m):
        try:
            body = json.loads(m.payload.decode('utf-8'))
        except Exception:
            body = {'_raw': m.payload.decode('utf-8', 'replace')}
        kind = m.topic.rsplit('/', 1)[-1]
        msgs.append({'rx_time': now_s(), 'topic': m.topic, 'retain': m.retain, 'qos': m.qos, 'payload': body})
        if kind == 'task':
            note(f"RX task id={body.get('id')} seq={body.get('seq')} state={body.get('state')} error={body.get('error')}")
            if body.get('id') == task_id and body.get('state') in TERMINAL:
                state['final'] = body
                done.set()
        elif kind == 'event':
            note(f"RX event id={body.get('id')} type={body.get('type') or body.get('event')}")
        else:
            note(f"RX {kind} retain={m.retain} " + json.dumps(body, ensure_ascii=False)[:200])

    def on_disconnect(c, u, flags, rc, props):
        note(f'DISCONNECT reason={rc}')

    c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=cid, protocol=mqtt.MQTTv5)
    c.username_pw_set(user, pw)
    c.on_connect, c.on_subscribe, c.on_message, c.on_disconnect = on_connect, on_subscribe, on_message, on_disconnect
    cp = Properties(PacketTypes.CONNECT)
    cp.SessionExpiryInterval = 0
    note(f'connect {host}:{port} client_id={cid} node={node} (clean_start, session_expiry=0)')
    c.connect(host, port, keepalive=30, clean_start=True, properties=cp)
    c.loop_start()
    try:
        if not connected.wait(15):
            note(f"no successful CONNACK; connack={state.get('connack')}")
            return 2
        c.subscribe([(f'{prefix}/{k}', 1) for k in ('task', 'event', 'presence', 'heartbeat')])
        time.sleep(2)
        c.publish(f'{prefix}/command', json.dumps(cmd), qos=1)
        note(f"TX command node.describe id={task_id} time={cmd['time']} expires_at={cmd['expires_at']}")
        done.wait(60)
        time.sleep(1)
    finally:
        c.disconnect()
        c.loop_stop()
        (ev / 'command.json').write_text(json.dumps(cmd, ensure_ascii=False, indent=2), 'utf-8')
        (ev / 'messages.json').write_text(json.dumps(msgs, ensure_ascii=False, indent=2), 'utf-8')
        (ev / 'log.txt').write_text('\n'.join(log), 'utf-8')

    final = state.get('final')
    if final:
        r = final.get('result') or {}
        caps = r.get('capabilities')
        note(f"FINAL state={final.get('state')} seq={final.get('seq')} software_version={r.get('software_version')} "
             f"node_type={r.get('node_type')} capabilities={len(caps) if isinstance(caps, list) else caps}")
    else:
        note(f"no terminal task reply; connack={state.get('connack')}")
    blob = (ev / 'messages.json').read_text('utf-8') + (ev / 'log.txt').read_text('utf-8')
    note(f'evidence: {ev}  password_in_evidence={pw in blob}')
    return 0 if final and final.get('state') == 'succeeded' else 1


if __name__ == '__main__':
    sys.exit(main())
