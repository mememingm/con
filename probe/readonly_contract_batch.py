"""Bounded live read-only MQTT checks; MQTTX publishes, Paho persists replies.

No credential values are printed or saved. Only owned tasks and conflict events
are stored/ACKed. Malformed commands are restricted to non-mutating actions.
This collects evidence; a separate review assigns checklist verdicts.
"""
import argparse
import copy
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
CLI = Path('C:/Users/27792/AppData/Local/Programs/mqttx-cli/mqttx.exe')
SAFE_ACTIONS = {'node.describe', 'task.get', 'inventory.get', 'phones.list',
                'sms.list', 'readonly.probe.unknown'}
TERMINAL = {'succeeded', 'failed', 'rejected', 'expired', 'uncertain'}


def now():
    return datetime.now(BJ)


def encode(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'))


class Store:
    """One transaction stores receipt, deduplication key and latest state."""
    def __init__(self, path, node):
        self.node = node
        self.lock = threading.RLock()
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.executescript('''
        PRAGMA synchronous=FULL;
        CREATE TABLE commands(id TEXT PRIMARY KEY, raw TEXT NOT NULL);
        CREATE TABLE inbox(node TEXT,kind TEXT,id TEXT,seq INTEGER,raw TEXT,
          PRIMARY KEY(node,kind,id,seq));
        CREATE TABLE latest(id TEXT PRIMARY KEY,seq INTEGER,raw TEXT);
        CREATE TABLE receipts(n INTEGER PRIMARY KEY,received TEXT,kind TEXT,raw TEXT);
        CREATE TABLE conflicts(received TEXT,kind TEXT,raw TEXT);
        ''')

    def own(self, value):
        with self.lock, self.db:
            self.db.execute('INSERT OR IGNORE INTO commands VALUES (?,?)',
                            (value['id'], encode(value)))

    def receive(self, kind, raw, retained=False):
        v = json.loads(raw)
        if retained or not isinstance(v, dict) or not isinstance(v.get('id'), str):
            return False
        if kind == 'task':
            owner, seq = v['id'], v.get('seq')
            if type(seq) is not int or seq < 1:
                return False
        elif kind == 'event':
            data = v.get('data') or {}
            if v.get('event') != 'alarm.raised':
                return False
            owner, seq = (data.get('details') or {}).get('command'), 0
        else:
            return False
        with self.lock, self.db:
            if not self.db.execute('SELECT 1 FROM commands WHERE id=?', (owner,)).fetchone():
                return False
            key = (self.node, kind, v['id'], seq)
            previous = self.db.execute('SELECT raw FROM inbox WHERE node=? AND kind=? AND id=? AND seq=?', key).fetchone()
            if previous and previous[0] != raw:
                self.db.execute('INSERT INTO conflicts VALUES (?,?,?)', (now().isoformat(),kind,raw))
                return False
            self.db.execute('INSERT INTO receipts(received,kind,raw) VALUES (?,?,?)', (now().isoformat(),kind,raw))
            self.db.execute('INSERT OR IGNORE INTO inbox VALUES (?,?,?,?,?)', (*key,raw))
            if kind == 'task':
                self.db.execute('INSERT INTO latest VALUES (?,?,?) ON CONFLICT(id) DO UPDATE SET seq=excluded.seq,raw=excluded.raw WHERE excluded.seq>latest.seq', (v['id'],seq,raw))
        return True


class Runner:
    def __init__(self, credentials):
        fields = {}
        for line in credentials.read_text('utf-8-sig').splitlines():
            a = re.split(r'[:\uff1a]', line, maxsplit=1)
            if len(a) == 2:
                fields[a[0].strip().lower()] = a[1].strip()
        self.host, port = re.match(r'^(\d+(?:\.\d+){3}):(\d+)', fields['broker']).groups()
        self.port = int(port)
        self.user, self.password = map(str.strip, fields['账号'].split('/',1))
        self.node = fields['节点编号']
        if self.node != 'ec20test' or self.host != '120.55.75.51' or self.port != 1883:
            raise ValueError('Environment differs from authorized ec20test broker')
        suffix = uuid.uuid4().hex[:8]
        self.client_prefix = fields['client id']+'-ro-'+suffix
        self.base = 'cardpool/v1/nodes/'+self.node
        self.out = Path(__file__).resolve().parents[2]/'.local/mqtt-test-console'/('contract-'+now().strftime('%Y%m%d-%H%M%S')+'-'+suffix)
        self.out.mkdir(parents=True, exist_ok=False)
        self.store = Store(self.out/'inbox.sqlite3',self.node)
        self.lock = threading.RLock()
        self.records, self.steps, self.acks, self.errors = [], [], [], []
        self.ready = threading.Event()
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=self.client_prefix+'-rx', protocol=mqtt.MQTTv5, reconnect_on_failure=False)
        self.client.username_pw_set(self.user,self.password)
        self.client.on_connect = self.on_connect
        self.client.on_subscribe = self.on_subscribe
        self.client.on_message = self.on_message
        self.client.on_publish = self.on_publish
        self.record('environment', broker=f'{self.host}:{self.port}',node=self.node,tls=False,mqtt_version=5,publisher='MQTTX CLI',receiver='Paho transactional inbox',runner_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())

    def clean(self,s):
        return s.replace(self.password,'[REDACTED]').replace(self.user,'[ACCOUNT]')

    def record(self,kind,**values):
        with self.lock:
            row={'line':len(self.records)+1,'observed_at':now().isoformat(),'kind':kind,**values}
            with (self.out/'trace.jsonl').open('a',encoding='utf-8') as file:
                file.write(encode(row)+'\n')
            self.records.append(row)
            return row

    def on_connect(self,client,userdata,flags,reason,properties):
        self.record('connack',reason=str(reason))
        if reason.is_failure:
            self.errors.append('Connection refused')
        else:
            client.subscribe([(self.base+'/'+x,1 if x!='heartbeat' else 0) for x in ('task','event','presence','heartbeat')])

    def on_subscribe(self,client,userdata,mid,reasons,properties):
        self.record('suback',reasons=[str(x) for x in reasons])
        if len(reasons)==4 and all(not x.is_failure for x in reasons):
            self.ready.set()

    def on_message(self,client,userdata,message):
        try:
            kind=message.topic.rsplit('/',1)[-1]
            raw=message.payload.decode('utf-8')
            if kind in ('presence','heartbeat'):
                self.record(kind,raw=raw,topic=message.topic,retained=message.retain)
                return
            if not self.store.receive(kind,raw,message.retain):
                return
            row=self.record('owned_'+kind,raw=raw,topic=message.topic,retained=message.retain,qos=message.qos)
            value=json.loads(raw)
            item={'kind':kind,'id':value['id']}
            if kind=='task':item['seq']=value['seq']
            ack={'time':now().strftime('%Y-%m-%d %H:%M:%S'),'items':[item]}
            self.record('ack_after_commit',receipt_line=row['line'],payload=ack)
            client.publish(self.base+'/ack',encode(ack),qos=1,retain=False)
        except Exception as exc:
            self.errors.append(type(exc).__name__)
            self.record('receiver_error',error=type(exc).__name__)

    def on_publish(self,client,userdata,mid,reason,properties):
        self.acks.append(str(reason))
        self.record('ack_puback',mid=mid,reason=str(reason))

    def command(self,action='node.describe',params=None,ttl=180):
        t=now()
        return dict(id=str(uuid.uuid4()),action=action,time=t.strftime('%Y-%m-%d %H:%M:%S'),expires_at=(t+timedelta(seconds=ttl)).strftime('%Y-%m-%d %H:%M:%S'),params={} if params is None else params)

    def replies(self,start,task_id):
        with self.lock:
            out=[]
            for row in self.records[start:]:
                if row['kind'] not in ('owned_task','owned_event'):continue
                v=json.loads(row['raw'])
                owner=v['id'] if row['kind']=='owned_task' else v.get('data',{}).get('details',{}).get('command')
                if owner==task_id:out.append({'line':row['line'],'received_at':row['observed_at'],'kind':row['kind'],'payload':v,'raw':row['raw']})
            return out

    def send(self,label,cmd,exact_file=None,expect_event=False):
        if cmd['action'] not in SAFE_ACTIONS or 'target' in cmd:
            raise ValueError('Not an allowed node-level read-only probe')
        self.store.own(cmd)
        request=self.out/(label+'.json')
        raw=exact_file.read_bytes() if exact_file else encode(cmd).encode('utf-8')
        assert json.loads(raw)==cmd
        request.write_bytes(raw)
        with self.lock:start=len(self.records)
        intent=self.record('command_intent',label=label,payload=cmd,request_file=request.name,sha256=hashlib.sha256(raw).hexdigest(),qos=1,retain=False)
        args=[str(CLI),'pub','-h',self.host,'-p',str(self.port),'-V','5.0','-i',self.client_prefix+'-tx','-u',self.user,'-P',self.password,'-rp','0','-t',self.base+'/command','-q','1','-e','180','--file-read',str(request)]
        proc=subprocess.run(args,capture_output=True,timeout=15,creationflags=subprocess.CREATE_NO_WINDOW)
        output=self.clean((proc.stdout+proc.stderr).decode('utf-8','replace'))
        self.record('mqttx_publish',label=label,exit_code=proc.returncode,output=output)
        if proc.returncode:raise RuntimeError('MQTTX failed: '+label)
        deadline=time.monotonic()+16
        while time.monotonic()<deadline:
            replies=self.replies(start,cmd['id'])
            if any((x['kind']=='owned_event' if expect_event else x['kind']=='owned_task' and x['payload'].get('state') in TERMINAL) for x in replies):
                time.sleep(0.7)
                break
            if self.errors:raise RuntimeError('Receiver failed')
            time.sleep(0.1)
        replies=self.replies(start,cmd['id'])
        step={'label':label,'command':cmd,'request_file':request.name,'intent_line':intent['line'],'replies':replies}
        self.steps.append(step)
        self.save()
        print(encode({'step':label,'task_id':cmd['id'],'task_states':[x['payload'].get('state') for x in replies if x['kind']=='owned_task'],'codes':[(x['payload'].get('error') or {}).get('code') if x['kind']=='owned_task' else x['payload'].get('data',{}).get('code') for x in replies]}),flush=True)
        return step

    def save(self):
        summary={'environment':{'broker':f'{self.host}:{self.port}','node':self.node},'steps':self.steps,'ack_pubacks':self.acks,'errors':self.errors,'business_ack_node_processing_verified':False}
        (self.out/'results.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')

    def run(self):
        print('EVIDENCE: '+str(self.out),flush=True)
        self.client.connect(self.host,self.port,keepalive=30)
        self.client.loop_start()
        try:
            if not self.ready.wait(12):raise RuntimeError('Required subscriptions not confirmed')
            base=self.command(ttl=75)
            original=self.send('baseline-describe',base)
            if not any(x['payload'].get('state')=='succeeded' for x in original['replies']):raise RuntimeError('Baseline failed; stop')
            self.send('baseline-phones',self.command('phones.list',{'page_size':50}))
            self.send('baseline-inventory',self.command('inventory.get',{'page_size':50}))
            self.send('T01-exact-replay',base,self.out/'baseline-describe.json')
            self.send('T04-query-original',self.command('task.get',{'id':base['id']}))
            altered=copy.deepcopy(base);altered['expires_at']=(datetime.strptime(base['expires_at'],'%Y-%m-%d %H:%M:%S')+timedelta(seconds=120)).strftime('%Y-%m-%d %H:%M:%S')
            self.send('T02-expiry-conflict',altered,expect_event=True)
            self.send('T02-query-preserved',self.command('task.get',{'id':base['id']}))
            altered=copy.deepcopy(base);altered['params']={'probe':'changed-only-for-conflict'}
            self.send('T03-params-conflict',altered,expect_event=True)
            self.send('T03-query-preserved',self.command('task.get',{'id':base['id']}))
            self.send('T05-not-found',self.command('task.get',{'id':str(uuid.uuid4())}))
            for action in ('node.describe','task.get'):
                cmd=self.command(action,{'id':base['id']} if action=='task.get' else {})
                del cmd['expires_at'];self.send('T16-missing-expiry-'+action,cmd)
            for offset,label in ((-1,'earlier'),(0,'equal')):
                cmd=self.command(ttl=offset);self.send('T17-expiry-'+label,cmd)
            cmd=self.command();cmd['time']=(now()-timedelta(minutes=10)).strftime('%Y-%m-%d %H:%M:%S');cmd['expires_at']=(now()-timedelta(minutes=5)).strftime('%Y-%m-%d %H:%M:%S')
            self.send('T18-already-expired',cmd)
            self.send('T27-sms-list',self.command('sms.list'))
            self.send('T55-unknown-action',self.command('readonly.probe.unknown'))
            self.send('T56-wrong-type',self.command('task.get',{'id':123}))
            self.send('T56-invalid-page-size',self.command('phones.list',{'page_size':0}))
            # Wait past the original expiry, then replay the EXACT saved bytes.
            expiry=datetime.strptime(base['expires_at'],'%Y-%m-%d %H:%M:%S').replace(tzinfo=BJ)+timedelta(seconds=4)
            while now()<expiry:
                remaining=(expiry-now()).total_seconds()
                print('Waiting for original expiry: '+str(round(remaining))+' seconds',flush=True)
                time.sleep(min(10,max(remaining,0)))
            self.send('T21-expired-exact-replay',base,self.out/'baseline-describe.json')
            self.send('T21-query-preserved',self.command('task.get',{'id':base['id']}))
        finally:
            self.client.disconnect();self.client.loop_stop();self.save();self.store.db.close()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--credentials-file',type=Path,required=True)
    args=parser.parse_args()
    Runner(args.credentials_file).run()
