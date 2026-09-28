"""号码互发成功率测试（ask 会话独立版，通过 VoCat 网页接口真实发送短信）。

做法：读出号池里 sms_ready 的线路和真实号码 -> 环形互发（每个号码发一条给下一个）
-> 正文带唯一标记 ASK-… -> 轮询接收方收件箱核对 -> 算发送成功率、到达率 -> 生成网页报告。
不连 Broker；ICCID 只在请求里用，不打印、不写报告。

用法: python sms_rate_ask.py [--limit N] [--wait 秒] [--rounds R] [--gap 秒]
报告: .local/sms-rate-ask/<批次>/report.html，总览 .local/sms-rate-ask/index.html
"""
import argparse
import html
import http.cookiejar
import json
import random
import re
import string
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

BJ = timezone(timedelta(hours=8))
BASE = 'http://192.168.1.5:7575'
CREDS = Path(r'C:\Users\27792\Desktop\vocat.txt')
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / '.local' / 'sms-rate-ask'


def now():
    return datetime.now(BJ)


class VoCat:
    def __init__(self):
        lines = [s.strip() for s in CREDS.read_text('utf-8-sig').splitlines() if s.strip()]
        tokens = [t for t in lines[0].split() if not re.match(r'^(https?://|\d{1,3}(\.\d{1,3}){3})', t)]
        self.user, self.pw = tokens[0], lines[1]
        self.op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        self.csrf = None
        self.login()

    def login(self):
        st, data = self.call('/auth/login', {'username': self.user, 'password': self.pw})
        if st != 200:
            raise SystemExit(f'VoCat 登录失败 HTTP {st}')
        self.csrf = (data or {}).get('csrf_token')

    def call(self, path, body=None):
        headers = {'Content-Type': 'application/json'}
        if body is not None and self.csrf:
            headers['X-CSRF-Token'] = self.csrf
        req = urllib.request.Request(BASE + '/api' + path,
                                     data=None if body is None else json.dumps(body).encode(), headers=headers)
        try:
            with self.op.open(req, timeout=30) as resp:
                payload = json.loads(resp.read() or b'null')
                if isinstance(payload, dict) and 'data' in payload:
                    payload = payload['data']
                return resp.status, payload
        except urllib.error.HTTPError as e:
            text = e.read().decode('utf-8', 'replace').replace(self.pw, '[P]')
            try:
                return e.code, json.loads(text)
            except Exception:
                return e.code, {'error': text[:300]}


def pool_lines(v):
    _, devs = v.call('/devices')
    devices = devs.get('devices', []) if isinstance(devs, dict) else (devs or [])
    out = []
    for d in devices:
        did = str(d.get('id'))
        _, ms = v.call(f'/devices/{did}/multisim')
        for ln in ((ms or {}).get('state') or {}).get('lines') or []:
            st = ln.get('state') or {}
            num = st.get('phone_number')
            if num:
                out.append(dict(device=did, number=num, iccid=ln.get('iccid') or st.get('iccid'),
                                ready=bool(st.get('sms_ready'))))
    out.sort(key=lambda x: (int(x['device']) if x['device'].isdigit() else 0, x['number']))
    return out


def find_inbound(v, recv, sender_number, token):
    q = {'peer': sender_number, 'device_id': recv['device'], 'limit': 30}
    if recv.get('iccid'):
        q['iccid'] = recv['iccid']
    st, msgs = v.call('/sms/thread?' + urllib.parse.urlencode(q))
    if st != 200 or not isinstance(msgs, list):
        return None
    for m in msgs:
        text = m.get('content') or m.get('body') or ''
        if str(m.get('direction')).lower() in ('inbound', 'received', 'in') and token in text:
            if m.get('local_phone') and m['local_phone'] != recv['number']:
                continue
            return m
    return None


def err_text(resp):
    if isinstance(resp, dict):
        e = resp.get('error') or resp.get('message') or resp
        if isinstance(e, dict):
            e = e.get('message') or e.get('code') or json.dumps(e, ensure_ascii=False)
        return str(e)[:160]
    return str(resp)[:160]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--limit', type=int, default=0, help='只发前 N 条（0=全部）')
    ap.add_argument('--wait', type=int, default=180, help='等待到达的最长秒数')
    ap.add_argument('--rounds', type=int, default=1, help='环形互发轮数')
    ap.add_argument('--gap', type=float, default=3.0, help='两条发送之间的间隔秒')
    args = ap.parse_args()

    v = VoCat()
    all_lines = pool_lines(v)
    lines = [l for l in all_lines if l['ready']]
    print(f'号池线路 {len(all_lines)} 条，可收发 {len(lines)} 条')
    if len(lines) < 2:
        raise SystemExit('可收发的号码少于 2 个')
    batch = 'ASK' + now().strftime('%m%d%H%M') + ''.join(random.choices(string.ascii_uppercase, k=2))
    run_dir = OUT / batch
    run_dir.mkdir(parents=True, exist_ok=True)

    plan = []
    for r in range(args.rounds):
        for i, s in enumerate(lines):
            plan.append((s, lines[(i + 1 + r) % len(lines)]))
    plan = [p for p in plan if p[0]['number'] != p[1]['number']]
    if args.limit:
        plan = plan[:args.limit]
    print(f'批次 {batch}：计划发送 {len(plan)} 条')

    msgs = [dict(seq=i, token=f'{batch}-{i:03d}', sender=s['number'], sender_dev=s['device'],
                 receiver=r['number'], receiver_dev=r['device'], status='queued', sent_at=None,
                 sent_text=f'{batch}-{i:03d} 号池互发测试', received_text=None, received_by=None,
                 send_http=None, sent_ok=False, send_error=None, arrived=False, arrived_at=None, latency_s=None)
            for i, (s, r) in enumerate(plan, 1)]
    by_num = {l['number']: l for l in lines}
    started = now().isoformat()
    live(batch, 'running', started, args.wait, msgs)

    def check_arrivals():
        for m in msgs:
            if m['status'] != 'sent':
                continue
            hit = find_inbound(v, by_num[m['receiver']], m['sender'], m['token'])
            if hit:
                m.update(arrived=True, status='arrived', arrived_at=hit.get('timestamp'),
                         received_text=hit.get('content') or hit.get('body'),
                         received_by=hit.get('local_phone') or m['receiver'])
                try:
                    arr = datetime.fromisoformat(str(hit.get('timestamp')).replace('Z', '+00:00'))
                    m['latency_s'] = round((arr - datetime.fromisoformat(m['sent_at'])).total_seconds(), 1)
                except Exception:
                    pass

    throttled = False
    for m in msgs:
        if throttled:
            m['status'] = 'throttled'
            continue
        s, r = by_num[m['sender']], by_num[m['receiver']]
        m['status'] = 'sending'
        live(batch, 'running', started, args.wait, msgs)
        body = {'device_id': s['device'], 'phone': r['number'], 'message': m['sent_text']}
        if s.get('iccid'):
            body['iccid'] = s['iccid']
        st, resp = v.call('/sms/send', body)
        if st in (401, 403):
            v.login()
            st, resp = v.call('/sms/send', body)
        ok = 200 <= st < 300 and not (isinstance(resp, dict) and resp.get('error'))
        m.update(sent_at=now().isoformat(), send_http=st, sent_ok=ok,
                 send_error=None if ok else err_text(resp), status='sent' if ok else 'failed')
        if st == 429:  # VoCat 全局限流（每小时条数上限）：不算发送失败，停止继续发
            m.update(status='throttled', send_error='VoCat 限流：每小时短信条数已达上限，未发送')
            throttled = True
            print('  触发 VoCat 限流，停止发送，剩余标记为"被限流"', flush=True)
            live(batch, 'running', started, args.wait, msgs)
            continue
        print(f"  [{m['seq']:03d}] {m['sender']} -> {m['receiver']}  "
              f"{'发送成功' if ok else '发送失败 HTTP ' + str(st) + ' ' + str(m['send_error'])}", flush=True)
        time.sleep(args.gap)
        check_arrivals()
        live(batch, 'running', started, args.wait, msgs)

    t0 = time.monotonic()
    while any(m['status'] == 'sent' for m in msgs) and time.monotonic() - t0 < args.wait:
        time.sleep(5)
        check_arrivals()
        live(batch, 'waiting', started, args.wait, msgs)
        print(f"  等待到达… 已到 {sum(m['arrived'] for m in msgs)}/{sum(m['sent_ok'] for m in msgs)}"
              f"（{int(time.monotonic() - t0)}s）", flush=True)
    for m in msgs:
        if m['status'] == 'sent':
            m['status'] = 'lost'

    result = dict(batch=batch, started=started, finished=now().isoformat(),
                  wait_s=args.wait, summary=stats(msgs), messages=msgs)
    live(batch, 'done', started, args.wait, msgs)
    (run_dir / 'results.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    (run_dir / 'report.html').write_text(render(result), encoding='utf-8')
    write_index()
    s = result['summary']['overall']
    print(f'\n结果：发送 {s["total"]} 条，发送成功 {s["sent_ok"]}（{s["send_rate"]}%），'
          f'到达 {s["arrived"]}（到达率 {s["arrive_rate"]}%）')
    print(f'报告：{run_dir / "report.html"}')


def live(batch, state, started, wait_s, msgs):
    data = dict(batch=batch, state=state, started=started, updated=now().isoformat(), wait_s=wait_s,
                planned=len(msgs), summary=stats(msgs), messages=msgs)
    tmp = OUT / 'live.json.tmp'
    tmp.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
    tmp.replace(OUT / 'live.json')


def pct(a, b):
    return round(100.0 * a / b, 1) if b else 0.0


def stats(msgs):
    throttled_n = sum(1 for m in msgs if m.get('status') == 'throttled' or m.get('send_http') == 429)
    msgs = [m for m in msgs if m.get('status') not in ('queued', 'sending', 'throttled') and m.get('send_http') != 429]
    per = {}
    for m in msgs:
        a = per.setdefault(m['sender'], dict(number=m['sender'], device=m['sender_dev'],
                                              sent=0, sent_ok=0, expected_in=0, received=0))
        a['sent'] += 1
        a['sent_ok'] += m['sent_ok']
        b = per.setdefault(m['receiver'], dict(number=m['receiver'], device=m['receiver_dev'],
                                                sent=0, sent_ok=0, expected_in=0, received=0))
        b['expected_in'] += 1
        b['received'] += m['arrived']
    rows = sorted(per.values(), key=lambda x: (x['device'], x['number']))
    for p in rows:
        p['send_rate'] = pct(p['sent_ok'], p['sent'])
        p['receive_rate'] = pct(p['received'], p['expected_in'])
    total = len(msgs)
    sent_ok = sum(m['sent_ok'] for m in msgs)
    arrived = sum(m['arrived'] for m in msgs)
    lat = [m['latency_s'] for m in msgs if m['latency_s'] is not None]
    return dict(overall=dict(total=total, sent_ok=sent_ok, arrived=arrived,
                             send_rate=pct(sent_ok, total), arrive_rate=pct(arrived, total),
                             avg_latency_s=round(sum(lat) / len(lat), 1) if lat else None, throttled=throttled_n),
                per_number=rows)


CSS = """
:root{--bg:#f6f7f9;--card:#fff;--ink:#1d2330;--muted:#6b7280;--line:#e5e7eb;--ok:#15803d;--bad:#b91c1c;--mid:#b45309}
@media (prefers-color-scheme:dark){:root{--bg:#14171c;--card:#1c2027;--ink:#e7eaef;--muted:#9aa3b2;--line:#2b313a;--ok:#4ade80;--bad:#f87171;--mid:#fbbf24}}
body{margin:0;padding:24px 16px 48px;background:var(--bg);color:var(--ink);font:15px/1.5 "Segoe UI","Microsoft YaHei",sans-serif;max-width:1000px;margin-inline:auto}
h1{font-size:22px;margin:0 0 4px}.muted{color:var(--muted);font-size:13px}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px;margin:18px 0}
.kpi{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 16px}
.kpi .v{font-size:30px;font-weight:700}.kpi .l{color:var(--muted);font-size:13px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px 16px;margin-top:16px;overflow-x:auto}
table{border-collapse:collapse;width:100%;font-size:14px}th,td{padding:7px 9px;border-bottom:1px solid var(--line);text-align:left;white-space:nowrap}
th{color:var(--muted);font-weight:600}.ok{color:var(--ok);font-weight:600}.bad{color:var(--bad);font-weight:600}.mid{color:var(--mid);font-weight:600}
a{color:inherit}
"""


def cls(rate):
    return 'ok' if rate >= 95 else ('mid' if rate >= 80 else 'bad')


def render(r):
    s = r['summary']['overall']
    e = html.escape
    rows = ''.join(
        f"<tr><td>{e(p['number'])}</td><td>{e(p['device'])}</td>"
        f"<td>{p['sent_ok']}/{p['sent']}</td><td class='{cls(p['send_rate'])}'>{p['send_rate']}%</td>"
        f"<td>{p['received']}/{p['expected_in']}</td><td class='{cls(p['receive_rate'])}'>{p['receive_rate']}%</td></tr>"
        for p in r['summary']['per_number'])
    detail = ''.join(
        f"<tr><td>{m['seq']}</td><td>{e(m['sender'])}</td><td>{e(m['receiver'])}</td>"
        f"<td class='{'ok' if m['sent_ok'] else 'bad'}'>{'成功' if m['sent_ok'] else '失败'}</td>"
        f"<td class='{'ok' if m['arrived'] else 'bad'}'>{'已到达' if m['arrived'] else '未到达'}</td>"
        f"<td>{'' if m['latency_s'] is None else str(m['latency_s']) + ' s'}</td>"
        f"<td class='muted'>{e(str(m['send_error'] or ''))}</td></tr>"
        for m in r['messages'])
    lat = s['avg_latency_s']
    return f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>号码互发成功率 {e(r['batch'])}</title>
<style>{CSS}</style></head><body>
<h1>号码互发成功率</h1><div class="muted">批次 {e(r['batch'])} · {e((r['started'] or '')[:19])} · 最长等待 {r['wait_s']} 秒 · <a href="../index.html">全部批次</a></div>
<div class="kpis">
<div class="kpi"><div class="l">发送条数</div><div class="v">{s['total']}</div></div>
<div class="kpi"><div class="l">发送成功率</div><div class="v {cls(s['send_rate'])}">{s['send_rate']}%</div><div class="l">{s['sent_ok']}/{s['total']}</div></div>
<div class="kpi"><div class="l">到达率</div><div class="v {cls(s['arrive_rate'])}">{s['arrive_rate']}%</div><div class="l">{s['arrived']}/{s['total']}</div></div>
<div class="kpi"><div class="l">平均到达用时</div><div class="v">{'-' if lat is None else str(lat) + ' s'}</div></div>
</div>
<div class="card"><h3 style="margin:0 0 8px">每个号码</h3><table>
<tr><th>号码</th><th>设备</th><th>作为发送方</th><th>发送成功率</th><th>作为接收方</th><th>接收成功率</th></tr>{rows}</table></div>
<div class="card"><h3 style="margin:0 0 8px">每条短信</h3><table>
<tr><th>#</th><th>发送号码</th><th>接收号码</th><th>发送</th><th>到达</th><th>用时</th><th>发送错误</th></tr>{detail}</table></div>
</body></html>"""


def write_index():
    runs = []
    for p in sorted(OUT.glob('*/results.json'), reverse=True):
        try:
            runs.append(json.loads(p.read_text('utf-8')))
        except Exception:
            pass
    e = html.escape
    rows = ''.join(
        f"<tr><td><a href='{e(d['batch'])}/report.html'>{e(d['batch'])}</a></td><td>{e((d['started'] or '')[:19])}</td>"
        f"<td>{d['summary']['overall']['total']}</td>"
        f"<td class='{cls(d['summary']['overall']['send_rate'])}'>{d['summary']['overall']['send_rate']}%</td>"
        f"<td class='{cls(d['summary']['overall']['arrive_rate'])}'>{d['summary']['overall']['arrive_rate']}%</td></tr>"
        for d in runs)
    (OUT / 'index.html').write_text(f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>号码互发成功率</title><style>{CSS}</style></head><body>
<h1>号码互发成功率 · 全部批次</h1><div class="card"><table>
<tr><th>批次</th><th>开始时间</th><th>发送条数</th><th>发送成功率</th><th>到达率</th></tr>{rows}</table></div></body></html>""",
                                    encoding='utf-8')


if __name__ == '__main__':
    main()
