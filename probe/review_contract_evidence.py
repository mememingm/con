"""Offline review of the 2026-09-21 authorized read-only batch.

Fail closed if recorded requests, trace, raw replies or expected observations
do not agree. This does not publish any MQTT messages or modify the node.
"""
import hashlib
import json
import re
import sqlite3
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'mqtt-test-console'))
from reporting import parse_source

RAW = ROOT/'.local/mqtt-test-console'
DIRS = [RAW/'contract-20260921-182453-8afc714c', RAW/'contract-20260921-182636-78276238']
OUT = ROOT/'tasks/records/mqtt-console/readonly-contract-20260921-182453'
SOURCE = Path('C:/Users/27792/Desktop/wiki/24-MQ接口测试清单.md')
PROTOCOL = Path('C:/Users/27792/Desktop/cardpool-design-docs-main/docs/server-node-mqtt-v1.md')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def cell(x):
    return str(x).replace('|','&#124;').replace('\n','<br>')


def main():
    catalog = parse_source(SOURCE)
    steps, traces, inputs = {}, {}, []
    for directory in DIRS:
        summary = json.loads((directory/'results.json').read_text('utf-8'))
        assert summary['environment'] == {'broker':'120.55.75.51:1883','node':'ec20test'}
        assert not summary['errors']
        trace = [json.loads(x) for x in (directory/'trace.jsonl').read_text('utf-8').splitlines()]
        traces[directory.name] = trace
        assert any(x['kind']=='connack' and x['reason']=='Success' for x in trace)
        assert any(x['kind']=='suback' and len(x['reasons'])==4 and all(r.startswith('Granted QoS') for r in x['reasons']) for x in trace)
        for step in summary['steps']:
            label = step['label']; assert label not in steps
            request = directory/step['request_file']
            intent = trace[step['intent_line']-1]
            assert intent['kind']=='command_intent' and intent['payload']==step['command']
            assert json.loads(request.read_bytes())==step['command'] and digest(request)==intent['sha256']
            assert any(x['kind']=='mqttx_publish' and x['label']==label and x['exit_code']==0 and 'Message published' in x['output'] for x in trace)
            for reply in step['replies']:
                row = trace[reply['line']-1]
                assert row['kind']==reply['kind'] and row['raw']==reply['raw']
                assert row['observed_at']==reply['received_at'] and json.loads(reply['raw'])==reply['payload']
                assert row['retained'] is False
            step['directory'] = directory
            steps[label] = step
        db = sqlite3.connect(f'file:{(directory/"inbox.sqlite3").as_posix()}?mode=ro',uri=True)
        assert db.execute('SELECT count(*) FROM conflicts').fetchone()[0]==0
        receipt_count=db.execute('SELECT count(*) FROM receipts').fetchone()[0]
        assert receipt_count==sum(x['kind'] in ('owned_task','owned_event') for x in trace)
        for row in trace:
            if row['kind']=='ack_after_commit':
                receipt=trace[row['receipt_line']-1];v=json.loads(receipt['raw']);ack=row['payload']['items'][0]
                assert ack['id']==v['id'] and receipt['line']<row['line']
                assert db.execute('SELECT 1 FROM receipts WHERE raw=?',(receipt['raw'],)).fetchone()
                assert ('seq' in ack)==(ack['kind']=='task')
        db.close()
        inputs += [{'path':str(p),'sha256':digest(p)} for p in sorted(directory.iterdir()) if p.is_file()]

    def final(label):
        candidates=[x for x in steps[label]['replies'] if x['kind']=='owned_task' and x['payload'].get('state') in {'succeeded','failed','rejected','expired','uncertain'}]
        assert candidates, label
        return candidates[-1]

    def rejection(label,code):
        t=final(label)['payload']
        assert t['state'] in {'failed','rejected','expired'} and t['error']['code']==code
        return t

    base=final('baseline-describe')['payload']
    assert base['state']=='succeeded'
    for label in ('T01-exact-replay','T21-expired-exact-replay'):
        assert (steps[label]['directory']/steps[label]['request_file']).read_bytes()==(DIRS[0]/'baseline-describe.json').read_bytes()
        assert final(label)['raw']==final('baseline-describe')['raw']
        assert all(x['payload']==base for x in steps[label]['replies'] if x['kind']=='owned_task')
    for label in ('T04-query-original','T02-query-preserved','T03-query-preserved','T21-query-preserved'):
        query=steps[label]['command'];t=final(label)['payload']
        assert query['id']!=base['id'] and query['params']['id']==base['id'] and t['state']=='succeeded'
        original=t['result']['task']
        assert all(original[k]==base[k] for k in ('id','seq','time','state','result','error'))
        assert original['action']=='node.describe'
    events={}
    for label,field in (('T02-expiry-conflict','expires_at'),('T03-params-conflict','params')):
        original=steps['baseline-describe']['command'];mutated=steps[label]['command']
        assert {k for k in original if original[k]!=mutated[k]}=={field}
        events[label]=[x for x in steps[label]['replies'] if x['kind']=='owned_event' and x['payload']['data']['code']=='IDEMPOTENCY_CONFLICT']
        assert events[label] and all(x['payload']['data']['details']['command']==base['id'] for x in events[label])
        assert final(label)['payload']==base
    for label,code in {
        'T05-not-found':'TASK_NOT_FOUND',
        'T16-missing-expiry-node.describe':'INVALID_ARGUMENT','T16-missing-expiry-task.get':'INVALID_ARGUMENT',
        'T17-expiry-earlier':'INVALID_ARGUMENT','T17-expiry-equal':'INVALID_ARGUMENT',
        'T18-already-expired':'COMMAND_EXPIRED','T27-sms-list':'UNSUPPORTED_ACTION',
        'T55-unknown-action':'UNSUPPORTED_ACTION','T56-wrong-type':'INVALID_ARGUMENT',
        'T56-page-negative':'INVALID_ARGUMENT','T56-page-above-max':'INVALID_ARGUMENT',
        'T56-page-wrong-type':'INVALID_ARGUMENT'}.items():
        rejection(label,code)
    for label in ('T16-missing-expiry-node.describe','T16-missing-expiry-task.get'):
        assert 'expires_at' not in steps[label]['command']
    assert steps['T17-expiry-earlier']['command']['expires_at']<steps['T17-expiry-earlier']['command']['time']
    assert steps['T17-expiry-equal']['command']['expires_at']==steps['T17-expiry-equal']['command']['time']
    past=steps['T18-already-expired'];intent=traces[past['directory'].name][past['intent_line']-1]
    assert past['command']['time']<past['command']['expires_at']<datetime.fromisoformat(intent['observed_at']).strftime('%Y-%m-%d %H:%M:%S')
    assert [x['payload']['state'] for x in past['replies'] if x['kind']=='owned_task']==['expired']
    assert final('T18-already-expired')['payload']['error']['certainty']=='not_started'
    late=steps['T21-expired-exact-replay'];late_intent=traces[late['directory'].name][late['intent_line']-1]
    assert late['command']['expires_at']<datetime.fromisoformat(late_intent['observed_at']).strftime('%Y-%m-%d %H:%M:%S')
    inv=final('baseline-inventory')['payload']['result'];phones=final('baseline-phones')['payload']['result']
    assert inv['complete'] and phones['complete'] and inv['cursor'] is None and phones['cursor'] is None
    slots={x['slot'] for x in inv['items']};phone_slots={x['target']['slot'] for x in phones['items']}
    assert slots==phone_slots and len(slots)==3
    assert inv['source']=='registry' and all(x['profiles_complete'] is False for x in inv['items'])
    assert all(p['state']=='unknown' for x in inv['items'] for p in x['profiles'])
    for label in ('T56-invalid-page-size','T56-page-zero-repeat'):
        assert steps[label]['command']['params']=={'page_size':0}
        assert final(label)['payload']['state']=='succeeded' and final(label)['payload']['error'] is None
    assert '| params.page_size | integer | 可选，默认 50 | 1–100' in PROTOCOL.read_text('utf-8-sig')

    cases={}
    def verdict(number,labels,fields,note='',status='通过'):
        refs=[];ids=[];times=[]
        for label in labels:
            st=steps[label];ids.append(st['command']['id'])
            selected=events[label] if label in events else [final(label)]
            for r in selected:
                times.append(datetime.fromisoformat(r['received_at']).strftime('%Y-%m-%d %H:%M:%S'))
                refs.append(f'[{label} 原始回包]({(st["directory"]/"trace.jsonl").as_posix()}:{r["line"]})')
        cases[f'T-{number:02}']={'conclusion':status,'ids':list(dict.fromkeys(ids)),'times':list(dict.fromkeys(times)),'fields':fields,'note':note,'refs':refs}

    verdict(1,['T01-exact-replay'],'seq=3；原始回包逐字一致','黑盒证据：状态、seq、节点 time 和 result 未变；未使用节点内部执行日志。')
    verdict(2,['T02-expiry-conflict','T02-query-preserved'],'IDEMPOTENCY_CONFLICT；原任务 seq=3 保持','冲突通过关联原任务 ID 的 event 返回。')
    verdict(3,['T03-params-conflict','T03-query-preserved'],'IDEMPOTENCY_CONFLICT；原任务未被覆盖')
    verdict(4,['T04-query-original'],'新查询 ID；result.task 与原终态一致')
    verdict(5,['T05-not-found'],'rejected；TASK_NOT_FOUND；certainty=not_started','预期拒绝，记通过。')
    verdict(16,['T16-missing-expiry-node.describe','T16-missing-expiry-task.get'],'均 rejected / INVALID_ARGUMENT','覆盖 node.describe、task.get 缺期限。')
    verdict(17,['T17-expiry-earlier','T17-expiry-equal'],'均 rejected / INVALID_ARGUMENT','早于、等于 time 两个子场景均已执行。')
    verdict(18,['T18-already-expired'],'仅 expired seq=1；COMMAND_EXPIRED；not_started','过期时间比发送时间早约五分钟，未见 accepted/running。')
    verdict(21,['T21-expired-exact-replay','T21-query-preserved'],'期限后原文重投仍 succeeded seq=3','请求文件哈希一致；节点 time、result 未变。')
    verdict(27,['T27-sms-list'],'rejected / UNSUPPORTED_ACTION','未发送短信；未知 action 不强行放入14行矩阵。')
    verdict(45,['baseline-inventory','baseline-phones'],'complete=true；IMEI 集合各3；missing=[]；extra=[]')
    verdict(48,['baseline-inventory'],'source=registry；profiles_complete=false；Profile state=unknown','按清单记录实现差异，不宣称完整现场 Profile 来自 inventory。')
    verdict(55,['T55-unknown-action'],'rejected / UNSUPPORTED_ACTION','不存在的只读探测 action；不映射到其他 action。')
    verdict(56,['T56-wrong-type','T56-invalid-page-size','T56-page-zero-repeat','T56-page-negative','T56-page-above-max','T56-page-wrong-type'],
            'page_size=0 两次 succeeded/error=null；负数、超限、错误类型均 INVALID_ARGUMENT',
            '类型错误子场景通过；分页范围校验不符合协议第8节1–100。失败回包没有节点错误码，矩阵不伪造 INVALID_ARGUMENT。',status='失败')
    totals=Counter(x['conclusion'] for x in cases.values());assert totals=={'通过':13,'失败':1}
    matrix={a:{k:[] for k in ('成功路径','拒绝路径','边界条件')} for a in catalog['actions']}
    def cover(action,column,labels):
        matrix[action][column]+=list(dict.fromkeys(steps[l]['command']['id'] for l in labels))
    cover('node.describe','成功路径',['baseline-describe'])
    cover('node.describe','拒绝路径',['T02-expiry-conflict','T03-params-conflict','T16-missing-expiry-node.describe','T17-expiry-earlier','T17-expiry-equal','T18-already-expired'])
    cover('node.describe','边界条件',['T01-exact-replay','T21-expired-exact-replay'])
    cover('task.get','成功路径',['T04-query-original','T02-query-preserved','T03-query-preserved','T21-query-preserved'])
    cover('task.get','拒绝路径',['T05-not-found','T16-missing-expiry-task.get','T56-wrong-type'])
    cover('inventory.get','成功路径',['baseline-inventory'])
    cover('phones.list','成功路径',['baseline-phones'])
    cover('phones.list','拒绝路径',['T56-page-negative','T56-page-above-max','T56-page-wrong-type'])
    # Zero-size failures have error=null; preserve them in T-56 and attachment,
    # never put an invented node error into the matrix's required ID+code format.
    lines=['# MQ 接口测试报告 — 第一批只读协议测试','',
           '环境：120.55.75.51:1883 / ec20test / MQTT 5 / TCP 无 TLS。北京时间 2026-09-21。',
           '本批合并主执行与分页边界复核两份现场证据，共25次发布、20个不同任务ID；13通过、1失败、54未测。此前批次不计入。',
           '成功/拒绝覆盖仅代表列出的具体请求；预期拒绝计通过。T-56中page_size=0成功回包缺少错误码，该失败仅入明细和附件，不伪造矩阵错误码。','',
           '| action | 成功路径 | 拒绝路径 | 边界条件 |','|---|---|---|---|']
    for action,columns in matrix.items():
        lines.append('| '+' | '.join([action]+[cell('；'.join(dict.fromkeys(v))) for v in columns.values()])+' |')
    lines+=['','| 编号 | 结论（通过·失败·未测） | 任务 ID | 北京时间 | 关键回包字段 | 备注 |','|---|---|---|---|---|---|']
    for n in range(1,69):
        key=f'T-{n:02}'
        if key in cases:
            c=cases[key];row=[key,c['conclusion'],'；'.join(c['ids']),'；'.join(c['times']),c['fields'],c['note']+' '+'；'.join(c['refs'])]
        else:
            if 7<=n<=15:reason='业务ACK均收到No matching subscribers，未修改节点开关；未完成该专项。'
            elif n in (19,20,49,53,54,62,68):reason='需要排队、换卡、重启或故障条件；本轮未制造现场条件。'
            elif n==57:reason='本轮任务错误certainty均为not_started；known_failed/unknown真实场景未覆盖，不能整项通过。'
            elif n==64:reason='本轮有新鲜心跳；未验证90秒无心跳和retained online陈旧场景。'
            elif n in (60,61,65,66,67):reason='未满足相应时长、补传或保留期现场条件。'
            elif 22<=n<=36 or n in (58,59):reason='本轮限定只读；未执行短信、卡片或隧道变更专项。'
            else:reason='本轮未执行该项完整判据；查询成功不能替代完整场景。'
            row=[key,'未测','','','',reason]
        lines.append('| '+' | '.join(cell(x) for x in row)+' |')
    OUT.mkdir(parents=True,exist_ok=False)
    (OUT/'report.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    ledger=[]
    for label,step in steps.items():
        r=final(label);t=r['payload']
        ledger.append({'label':label,'task_id':step['command']['id'],'action':step['command']['action'],'received_at':r['received_at'],'state':t['state'],'seq':t['seq'],'error':t.get('error'),'request':str(step['directory']/step['request_file']),'trace':str(step['directory']/'trace.jsonl'),'raw_line':r['line']})
    (OUT/'review.json').write_text(json.dumps({'totals':{'通过':13,'失败':1,'未测':54},'cases':cases,'ledger':ledger,'matrix':matrix},ensure_ascii=False,indent=2),encoding='utf-8')
    notes=['# 第一批只读测试证据附件','',
           '新发现：phones.list page_size=0 两次均被接受。协议第8节（第507行）规定范围1–100；对照负数、101、字符串均被INVALID_ARGUMENT拒绝。T-56整体记失败，其他正确拒绝子场景保留。没有修改节点实现。','',
           '两次复现任务：'+steps['T56-invalid-page-size']['command']['id']+'；'+steps['T56-page-zero-repeat']['command']['id']+'。实际回包均 succeeded/error=null，未伪造节点错误码。','',
           '既有边界：业务ACK仍无匹配订阅者；只确认了本批自有任务和两条关联冲突告警，未确认生产消息、未改outbox。node_type仍为vocat_ec20，与设计文档ec20_edge/mdd_cloud存在差异，单独保留，不影响本批具体黑盒判据。',
           '节点响应时间约领先接收端1秒，未SSH核对NTP；T-18使用过去5分钟，T-21等待原期限后至少4秒，避免秒级偏差影响判定。',
           '基线清单仍为3个模块、9个Profile；3条available=true/registered。真实短信收发未测。',
           'T-01的不重复执行结论依据原始回包逐字一致及task.get持久状态不变；没有节点内部日志。T-57只观测到not_started，其他certainty未覆盖。','',
           '## Python关键代码块',
           '- Runner.command()：为新查询生成新UUID和北京时间；重投使用保存的原文件。',
           '- Runner.send()：仅允许白名单只读action，调用MQTTX CLI pub实际发送；保存请求字节、SHA256和回包。',
           '- Store.receive()：只处理本批任务与关联告警；同一事务保存原始回包、去重键和最新状态。',
           '- Runner.on_message()：事务提交后再发业务ACK；event ACK不带seq。',
           '- Runner.run()：串行执行，原任务期限过后逐字节重投；不重启、不改卡、不发短信。',
           '- review_contract_evidence.py：离线核对请求哈希、真实回包、数据库收据及各判据，再生成两张规定表。','',
           '## 原始证据（含卡片及号码标识，保留在私有本地目录）']
    for d in DIRS:
        notes.append(f'- [{d.name} 原始日志]({(d/"trace.jsonl").as_posix()}) · [执行结果]({(d/"results.json").as_posix()})')
    notes+=['','## 所有真实发布记录','', '| 步骤 | 任务 ID | 回包北京时间 | 状态/错误码 |','|---|---|---|---|']
    for x in ledger:
        notes.append('| '+' | '.join(cell(v) for v in [x['label'],x['task_id'],x['received_at'],x['state']+' / '+str((x['error'] or {}).get('code'))])+' |')
    (OUT/'evidence-review.md').write_text('\n'.join(notes)+'\n',encoding='utf-8')
    inputs += [{'path':str(x),'sha256':digest(x)} for x in (SOURCE,PROTOCOL,Path(__file__),Path(__file__).with_name('readonly_contract_batch.py'))]
    manifest={'environment':{'broker':'120.55.75.51:1883','node':'ec20test'},'inputs':inputs,'outputs':[{'path':str(x),'sha256':digest(x)} for x in OUT.iterdir() if x.is_file()]}
    (OUT/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    report=(OUT/'report.md').read_text('utf-8');rows=[x for x in report.splitlines() if re.match(r'^\| T-\d\d \|',x)]
    assert len(rows)==68 and all(len(x.split('|'))==8 for x in rows)
    assert len(steps)==25 and len({s['command']['id'] for s in steps.values()})==21
    # Correct the displayed distinct-ID count from the verified ledger.
    report=report.replace('20个不同任务ID','21个不同任务ID')
    (OUT/'report.md').write_text(report,encoding='utf-8')
    for item in manifest['outputs']:item['sha256']=digest(Path(item['path']))
    (OUT/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'report':str(OUT/'report.md'),'passed':13,'failed':1,'not_tested':54,'publishes':len(steps),'unique_task_ids':len({s['command']['id'] for s in steps.values()})},ensure_ascii=False))


if __name__=='__main__':
    main()
