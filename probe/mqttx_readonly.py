"""MQTTX publishes; paho subscribes and transactionally stores owned replies.

Only node.describe, inventory.get and phones.list are permitted. No card writes.
Credentials never enter saved commands or evidence. Raw replies stay private.
"""
import argparse
import hashlib
import json
import re
import sqlite3
import subprocess
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import paho.mqtt.client as mqtt

BJ = timezone(timedelta(hours=8))
CLI = 'C:/Users/27792/AppData/Local/Programs/mqttx-cli/mqttx.exe'
ALLOWED = {'node.describe', 'inventory.get', 'phones.list'}


def now():
    return datetime.now(BJ)


class Inbox:
    def __init__(self, path):
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.lock = threading.Lock()
        self.db.executescript('''
        PRAGMA synchronous=FULL;
        CREATE TABLE IF NOT EXISTS commands(id TEXT PRIMARY KEY, raw TEXT);
        CREATE TABLE IF NOT EXISTS inbox(id TEXT, seq INTEGER, raw TEXT, received TEXT, PRIMARY KEY(id,seq));
        CREATE TABLE IF NOT EXISTS latest(id TEXT PRIMARY KEY, seq INTEGER, raw TEXT);
        CREATE TABLE IF NOT EXISTS conflicts(id TEXT, seq INTEGER, raw TEXT, received TEXT);
        CREATE TABLE IF NOT EXISTS receipts(id TEXT, seq INTEGER, raw TEXT, received TEXT);
        CREATE TABLE IF NOT EXISTS ack_intents(id TEXT, seq INTEGER, created TEXT);
        ''')

    def own(self, command):
        raw = json.dumps(command, ensure_ascii=False, separators=(',', ':'))
        with self.lock, self.db:
            self.db.execute('INSERT INTO commands VALUES (?,?)', (command['id'], raw))
        return raw

    def receive(self, raw, retained=False):
        value = json.loads(raw)
        task, seq = value.get('id'), value.get('seq')
        if retained or type(seq) is not int or seq < 1:
            return False
        with self.lock, self.db:
            if not self.db.execute('SELECT 1 FROM commands WHERE id=?', (task,)).fetchone():
                return False
            received = now().isoformat()
            previous = self.db.execute('SELECT raw FROM inbox WHERE id=? AND seq=?', (task, seq)).fetchone()
            if previous and previous[0] != raw:
                self.db.execute('INSERT INTO conflicts VALUES (?,?,?,?)', (task, seq, raw, received))
                return False
            self.db.execute('INSERT INTO receipts VALUES (?,?,?,?)', (task, seq, raw, received))
            self.db.execute('INSERT OR IGNORE INTO inbox VALUES (?,?,?,?)', (task, seq, raw, received))
            self.db.execute('INSERT INTO latest VALUES (?,?,?) ON CONFLICT(id) DO UPDATE SET seq=excluded.seq,raw=excluded.raw WHERE excluded.seq>latest.seq', (task, seq, raw))
            self.db.execute('INSERT INTO ack_intents VALUES (?,?,?)', (task, seq, received))
        return True  # The transaction, including business state, has committed.

    def terminal(self, task):
        with self.lock:
            row = self.db.execute('SELECT raw FROM latest WHERE id=?', (task,)).fetchone()
        value = json.loads(row[0]) if row else None
        return value if value and value.get('state') in {'succeeded','failed','rejected','expired','uncertain'} else None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--credentials-file', type=Path, required=True)
    parser.add_argument('--action', choices=sorted(ALLOWED), required=True)
    parser.add_argument('--page-size', type=int, default=50)
    args = parser.parse_args()
    if not 1 <= args.page_size <= 100:
        parser.error('page size must be between 1 and 100')
    fields = {}
    for line in args.credentials_file.read_text('utf-8-sig').splitlines():
        parts = re.split(r'[:\uff1a]', line, maxsplit=1)
        if len(parts) == 2:
            fields[parts[0].strip().lower()] = parts[1].strip()
    host, port = re.match(r'^(\d{1,3}(?:\.\d{1,3}){3}):(\d+)\b', fields['broker']).groups()
    username, password = [part.strip() for part in fields['\u8d26\u53f7'].split('/',1)]
    node = fields['\u8282\u70b9\u7f16\u53f7']
    if not re.fullmatch(r'[\w-]+', node):
        raise SystemExit('Invalid node identifier')
    suffix = uuid.uuid4().hex[:8]
    prefix = fields['client id']
    base = f'cardpool/v1/nodes/{node}'
    out = Path(__file__).resolve().parents[2] / '.local/mqtt-test-console' / (now().strftime('%Y%m%d-%H%M%S')+'-'+suffix)
    out.mkdir(parents=True, exist_ok=False)
    inbox = Inbox(out/'inbox.sqlite3')
    subscribed, errors, pending, acks = threading.Event(), [], {}, []
    log_lock = threading.Lock()

    def record(kind, **data):
        with log_lock, (out/'trace.jsonl').open('a',encoding='utf-8') as f:
            f.write(json.dumps(dict(observed_at=now().isoformat(),kind=kind,**data),ensure_ascii=False)+'\n')

    def on_connect(client, userdata, flags, reason, properties):
        record('connack',reason=str(reason))
        if reason.is_failure:
            errors.append('Connection refused')
        else:
            client.subscribe([(base+'/task',1),(base+'/event',1)])

    def on_subscribe(client, userdata, mid, reasons, properties):
        record('suback',reasons=[str(r) for r in reasons])
        if len(reasons)==2 and all(not r.is_failure for r in reasons):
            subscribed.set()
        else:
            errors.append('Required subscription refused')

    def on_message(client, userdata, message):
        if message.topic != base+'/task':
            return  # Do not store or ACK unrelated production events.
        try:
            raw=message.payload.decode('utf-8')
            value=json.loads(raw)
            if not inbox.receive(raw,message.retain):
                return
            record('owned_task',raw=raw,topic=message.topic,qos=message.qos,retained=message.retain)
            ack={'time':now().strftime('%Y-%m-%d %H:%M:%S'),'items':[{'kind':'task','id':value['id'],'seq':value['seq']}]}
            record('ack_after_commit',payload=ack)
            info=client.publish(base+'/ack',json.dumps(ack),qos=1,retain=False)
            pending[info.mid]=value['id']+':'+str(value['seq'])
        except Exception as error:
            errors.append(type(error).__name__)

    def on_publish(client, userdata, mid, reason, properties):
        item=dict(task_seq=pending.pop(mid,'unknown'),reason=str(reason))
        acks.append(item)
        record('ack_puback',**item)

    receiver=mqtt.Client(mqtt.CallbackAPIVersion.VERSION2,client_id=prefix+'-rx-'+suffix,protocol=mqtt.MQTTv5,reconnect_on_failure=False)
    receiver.username_pw_set(username,password)
    receiver.on_connect,receiver.on_subscribe=on_connect,on_subscribe
    receiver.on_message,receiver.on_publish=on_message,on_publish
    record('environment',broker=f'{host}:{port}',node=node,mqtt_version=5,tls=False,action=args.action,receiver='paho',publisher='MQTTX CLI 1.13.1')
    results=[]
    try:
        receiver.connect(host,int(port),keepalive=30)
        receiver.loop_start()
        if not subscribed.wait(12):
            raise RuntimeError('Required subscriptions not ready; no command published')
        cursor=None
        generated=None
        seen_cursors=set()
        for page in range(1,11):
            created=now()
            params={} if args.action=='node.describe' else {'page_size':args.page_size}
            if cursor is not None:
                params['cursor']=cursor
            command=dict(id=str(uuid.uuid4()),action=args.action,time=created.strftime('%Y-%m-%d %H:%M:%S'),expires_at=(created+timedelta(minutes=3)).strftime('%Y-%m-%d %H:%M:%S'),params=params)
            raw=inbox.own(command)
            request_file=out/f'command-{page}.json'
            request_file.write_text(raw,encoding='utf-8')
            record('command_intent',payload=command,raw_sha256=hashlib.sha256(raw.encode()).hexdigest(),topic=base+'/command',qos=1,retain=False)
            cmd=[CLI,'pub','-h',host,'-p',port,'-V','5.0','-i',prefix+'-tx-'+suffix,'-u',username,'-P',password,'-rp','0','-t',base+'/command','-q','1','-e','180','--file-read',str(request_file)]
            try:
                pub=subprocess.run(cmd,capture_output=True,timeout=15,creationflags=subprocess.CREATE_NO_WINDOW)
            except subprocess.TimeoutExpired:
                raise RuntimeError('Publish timeout; original task ID retained, no republish') from None
            output=(pub.stdout+pub.stderr).decode('utf-8','replace').replace(password,'[REDACTED]').replace(username,'[ACCOUNT]')
            record('mqttx_publish_result',exit_code=pub.returncode,output=output)
            if pub.returncode:
                raise RuntimeError('MQTTX publish failed; original task ID retained')
            deadline=time.monotonic()+90
            terminal=None
            while time.monotonic()<deadline and not errors:
                terminal=inbox.terminal(command['id'])
                if terminal:
                    break
                time.sleep(0.1)
            if terminal is None:
                raise RuntimeError('No terminal reply within observation window; no republish')
            results.append(terminal)
            print(json.dumps(dict(action=args.action,page=page,task_id=command['id'],state=terminal['state'],error=terminal.get('error'),result_keys=list((terminal.get('result') or {}).keys())),ensure_ascii=True),flush=True)
            if terminal['state']!='succeeded' or args.action=='node.describe':
                break
            data=terminal['result']
            if page>1 and data.get('generated_at')!=generated:
                raise RuntimeError('Snapshot changed across pages')
            generated=data.get('generated_at')
            if data.get('complete') is True and data.get('cursor') is None:
                break
            cursor=data.get('cursor')
            if not cursor or cursor in seen_cursors:
                raise RuntimeError('Incomplete/invalid paging cursor')
            seen_cursors.add(cursor)
        else:
            errors.append('Page limit reached; snapshot incomplete')
        deadline=time.monotonic()+3
        while pending and time.monotonic()<deadline:
            time.sleep(0.1)
    except Exception as error:
        errors.append(str(error).replace(password,'[REDACTED]').replace(username,'[ACCOUNT]'))
    finally:
        receiver.disconnect()
        receiver.loop_stop()
    summary=dict(action=args.action,results=results,errors=errors,ack_pubacks=acks,unconfirmed_ack_publishes=list(pending.values()),business_ack_node_processing_verified=False)
    (out/'result.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    record('finished',errors=errors,tasks=len(results))
    inbox.db.close()
    print(json.dumps(dict(evidence=str(out),errors=errors,ack_pubacks=acks),ensure_ascii=True),flush=True)
    return 0 if results and not errors and all(r['state']=='succeeded' for r in results) else 1


if __name__=='__main__':
    raise SystemExit(main())
