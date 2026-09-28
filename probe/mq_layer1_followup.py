"""Follow-up for the layer-1 suite: T-39 rerun and slot.refresh / esim.profiles.list
with binding_version. Read-only, no /ack. Masked evidence."""
import json, sys, time
from datetime import datetime
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from mq_layer1_suite import Node, mask, ts, CST, ROOT

n = Node()
out, run = [], datetime.now(CST).strftime('%Y%m%d-%H%M%S')

def call(label, action, params=None, target=None, timeout=90):
    cmd = n.send(action, params, target)
    f = n.final(cmd['id'], timeout)
    r = (f or {}).get('result') or {}
    print(f"{ts()} {label}: id={cmd['id']} state={(f or {}).get('state')} error={json.dumps((f or {}).get('error'), ensure_ascii=False)}", flush=True)
    out.append({'label': label, 'command': mask(cmd), 'final': mask(f)})
    return f

f = call('phones.list default', 'phones.list', {'page_size': 100})
items = (f.get('result') or {}).get('items') or []
slots = []
for i in items:
    t = i['target']
    if (t['device'], t['slot']) not in slots:
        slots.append((t['device'], t['slot']))
for k in (1, 2):
    f = call(f'T-39 rerun #{k}', 'phones.list', {'page_size': 100, 'include_empty_slots': False})
    if f and f.get('state') == 'succeeded':
        print('   items', len(f['result'].get('items') or []), 'empty', sum(1 for i in f['result']['items'] if not i['target'].get('iccid')))
    time.sleep(5)
for dev, slot in slots:
    tgt = {'device': dev, 'slot': slot, 'binding_version': 1}
    f = call(f'slot.refresh dev={dev}', 'slot.refresh', {}, tgt)
    if f and f.get('state') == 'succeeded':
        s = f['result'].get('slot') or {}
        print('   slot.state', s.get('state'), 'profiles', len(s.get('profiles') or []), 'profiles_complete', s.get('profiles_complete'))
    f = call(f'esim.profiles.list dev={dev}', 'esim.profiles.list', {}, tgt)
    if f and f.get('state') == 'succeeded':
        print('   profiles', len(f['result'].get('profiles') or []), 'complete', f['result'].get('complete'))
n.close()
ev = ROOT / '.local' / 'mq-layer1' / f'followup-{run}'
ev.mkdir(parents=True, exist_ok=True)
text = json.dumps(out, ensure_ascii=False, indent=2)
assert n.pw not in text
(ev / 'results.json').write_text(text, 'utf-8')
print('evidence:', ev)
