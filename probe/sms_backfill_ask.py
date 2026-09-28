"""一次性补录：给已有批次补上"发送内容 / 接收方收到的内容"。只读查询 VoCat，不发短信。"""
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from sms_rate_ask import VoCat, pool_lines, find_inbound, OUT
v = VoCat()
lines = {l['number']: l for l in pool_lines(v)}
for p in sorted(OUT.glob('*/results.json')):
    d = json.loads(p.read_text('utf-8'))
    changed = 0
    for m in d.get('messages') or []:
        m.setdefault('sent_text', f"{m['token']} 号池互发测试")
        if m.get('arrived') and not m.get('received_text') and m['receiver'] in lines:
            hit = find_inbound(v, lines[m['receiver']], m['sender'], m['token'])
            if hit:
                m['received_text'] = hit.get('content') or hit.get('body')
                m['received_by'] = hit.get('local_phone') or m['receiver']
                changed += 1
    p.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding='utf-8')
    print(p.parent.name, '补录', changed, '条')
