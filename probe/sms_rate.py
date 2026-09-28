"""SMS 号码互发到达率/成功率测试（VoCat REST 闭环）。

需求：只测号码互相收发的成功率——发送成功率、到达率、正确率。不分析错误原因。

闭环：POST /api/sms/send 从发送方线路发一条带唯一标记的短信给接收方；
再轮询 GET /api/sms/thread（接收方设备 × 发送方号码）按标记核对是否收到、内容是否一致。
全程走 VoCat REST，不连 Broker、不依赖 longrecive、不需要暂停 PingCode。

安全：默认 dry-run（不真发）。加 --send 才真发；--max N 限制条数（canary 用 --max 1）。
凭据服务端读取，不打印、不落盘。

用法示例：
  python sms_rate.py --participants +A,+B,+C --rounds 2 --bidir            # dry-run 预览计划
  python sms_rate.py --participants +A,+B,+C --rounds 2 --bidir --send --max 1   # 发 1 条 canary
  python sms_rate.py --participants +A,+B,+C --rounds 2 --bidir --send          # 真跑
"""
import argparse
import http.cookiejar
import json
import re
import sys
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

BJ = timezone(timedelta(hours=8))
BASE = 'http://192.168.1.5:7575'
VOCAT = Path(r'C:\Users\27792\Desktop\vocat.txt')
OUT = Path(__file__).resolve().parents[1] / '.local' / 'sms-rate'


def now():
    return datetime.now(BJ)


def read_credentials(path):
    lines = [s.strip() for s in path.read_text('utf-8-sig').splitlines() if s.strip()]
    fields = {}
    for line in lines:
        parts = re.split(r'[:\uff1a=]', line, maxsplit=1)
        if len(parts) == 2 and not re.match(r'^\s*https?$', parts[0], re.I):
            fields[parts[0].strip().lower()] = parts[1].strip()
    user = fields.get('username') or fields.get('user') or fields.get('\u8d26\u53f7')
    password = fields.get('password') or fields.get('\u5bc6\u7801')
    if user and password:
        return user, password
    if len(lines) == 2:
        tokens = [t for t in lines[0].split() if not re.match(r'^(https?://|\d{1,3}(\.\d{1,3}){3})', t)]
        if tokens:
            return tokens[0], lines[1]
    raise SystemExit('vocat.txt 格式无法识别')


class VoCat:
    def __init__(self):
        self.user, self.password = read_credentials(VOCAT)
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        self.csrf = None
        st, _ = self.call('/auth/login', {'username': self.user, 'password': self.password})
        if st != 200:
            raise RuntimeError(f'VoCat 登录失败 HTTP {st}')
        _, sess = self.call('/auth/session')
        self.csrf = sess.get('csrf_token') if isinstance(sess, dict) else None

    def call(self, path, body=None, method=None):
        data = None if body is None else json.dumps(body).encode()
        headers = {'Content-Type': 'application/json'}
        # 写操作（POST/PUT/DELETE）需带 CSRF 头
        if getattr(self, 'csrf', None) and (data is not None or method in ('DELETE', 'PUT')):
            headers['X-CSRF-Token'] = self.csrf
        req = urllib.request.Request(BASE + '/api' + path, data=data,
                                     headers=headers, method=method)
        try:
            with self.opener.open(req, timeout=20) as resp:
                payload = json.loads(resp.read() or b'null')
                if isinstance(payload, dict) and 'data' in payload:
                    payload = payload['data']
                return resp.status, payload
        except urllib.error.HTTPError as e:
            txt = e.read().decode('utf-8', 'replace')
            return e.code, txt[:200]

    def build_map(self):
        """phone -> {device, iccid}；同时 device 列表。"""
        st, devs = self.call('/devices')
        device_list = devs.get('devices', []) if isinstance(devs, dict) else (devs if isinstance(devs, list) else [])
        mp = {}
        for dev in device_list:
            did = dev.get('id')
            _, ms = self.call(f'/devices/{did}/multisim')
            lines = (ms.get('state', {}) or {}).get('lines', []) if isinstance(ms, dict) else []
            for ln in lines:
                phone = ln.get('name')
                iccid = (ln.get('state', {}) or {}).get('iccid') or ln.get('iccid')
                if phone:
                    mp[phone] = {'device': did, 'iccid': iccid}
        return mp

    def send(self, sender, receiver, mp, text):
        s = mp.get(sender, {})
        body = {'device_id': s.get('device'), 'phone': receiver, 'message': text}
        if s.get('iccid'):
            body['iccid'] = s['iccid']  # 多卡设备必须指定发送线路
        return self.call('/sms/send', body)

    def check_arrival(self, sender, receiver, mp, token, timeout=90, interval=5):
        """在接收方会话里找 inbound 且 body==token 的消息。返回 (arrived, correct, secs)。"""
        r = mp.get(receiver, {})
        params = f"?device_id={r.get('device')}&limit=30&peer={urllib.parse.quote(sender)}"
        if r.get('iccid'):
            params += f"&iccid={urllib.parse.quote(r['iccid'])}"  # 同设备多卡靠 iccid 区分接收线路
        start = time.monotonic()
        while time.monotonic() - start < timeout:
            st, thread = self.call('/sms/thread' + params)
            msgs = thread if isinstance(thread, list) else (thread.get('messages', []) if isinstance(thread, dict) else [])
            for m in msgs or []:
                if not isinstance(m, dict) or m.get('direction') != 'inbound':
                    continue
                body = (m.get('body') or m.get('content') or '')
                if token in body:  # 到达
                    return True, body.strip() == token, round(time.monotonic() - start, 1)
            time.sleep(interval)
        return False, False, None


import urllib.parse  # noqa: E402


def build_plan(participants, bidir, rounds):
    pairs = []
    for i, a in enumerate(participants):
        for j, b in enumerate(participants):
            if a == b:
                continue
            if not bidir and j < i:
                continue
            pairs.append((a, b))
    plan = []
    for r in range(1, rounds + 1):
        for (a, b) in pairs:
            plan.append((a, b, r))
    return plan


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--participants', required=True, help='逗号分隔号码')
    ap.add_argument('--rounds', type=int, default=2)
    ap.add_argument('--bidir', action='store_true')
    ap.add_argument('--send', action='store_true', help='真发短信（否则 dry-run 只预览）')
    ap.add_argument('--max', type=int, default=0, help='最多发几条（0=不限；canary 用 1）')
    ap.add_argument('--timeout', type=int, default=90)
    args = ap.parse_args()
    participants = [p.strip() for p in args.participants.split(',') if p.strip()]

    vc = VoCat()
    mp = vc.build_map()
    unknown = [p for p in participants if p not in mp]
    if unknown:
        raise SystemExit(f'这些号码不在号池映射里: {unknown}')
    plan = build_plan(participants, args.bidir, args.rounds)
    total = len(plan) if not args.max else min(args.max, len(plan))
    run_id = now().strftime('%H%M%S') + '-' + uuid.uuid4().hex[:4]

    print(f'参与号码 {len(participants)}: {participants}')
    print(f'方向: {"双向" if args.bidir else "单向"}  轮数: {args.rounds}  计划条数: {len(plan)}  本次执行: {total}')
    print(f'模式: {"真发(--send)" if args.send else "DRY-RUN 预览（不真发）"}  run={run_id}\n')
    for p in participants:
        print(f'  {p} -> 设备 {mp[p]["device"]} iccid …{str(mp[p].get("iccid"))[-4:]}')
    print()

    if not args.send:
        print('DRY-RUN：以上为发送计划与号码映射，未真发。加 --send 才真发。')
        for i, (a, b, r) in enumerate(plan[:total], 1):
            print(f'  #{i:03d} 第{r}轮 {a} -> {b}')
        return 0

    OUT.mkdir(parents=True, exist_ok=True)
    rows = []
    sent_ok = arrived = correct = 0
    for i, (a, b, r) in enumerate(plan[:total], 1):
        token = f'MQR-{run_id}-{i:03d}'
        st, resp = vc.send(a, b, mp, token)
        # sms.send 返回：HTTP 200 视为发送已受理
        ok = st == 200
        sent_ok += 1 if ok else 0
        arr = corr = False
        secs = None
        if ok:
            arr, corr, secs = vc.check_arrival(a, b, mp, token, timeout=args.timeout)
            arrived += 1 if arr else 0
            correct += 1 if corr else 0
        rows.append(dict(seq=i, round=r, sender=a, receiver=b, token=token,
                         send_http=st, sent=ok, arrived=arr, correct=corr, delay_s=secs))
        print(f'  #{i:03d} 第{r}轮 {a}->{b}  发送={"OK" if ok else "失败"+str(st)}  '
              f'到达={"是" if arr else "否"}  正确={"是" if corr else "否"}  时延={secs}')

    def pct(x, n):
        return f'{100.0*x/n:.1f}%' if n else 'N/A'
    print(f'\n=== 汇总（尝试 {total}）')
    print(f'发送成功率: {pct(sent_ok, total)}  ({sent_ok}/{total})')
    print(f'到达率:     {pct(arrived, sent_ok)}  ({arrived}/{sent_ok})   [到达/发送成功]')
    print(f'正确率:     {pct(correct, arrived)}  ({correct}/{arrived})   [内容一致/到达]')
    print(f'端到端成功率: {pct(correct, total)}  ({correct}/{total})   [到达且正确/尝试]')

    report = dict(run_id=run_id, at=now().isoformat(), participants=participants,
                  bidir=args.bidir, rounds=args.rounds, attempted=total,
                  sent_ok=sent_ok, arrived=arrived, correct=correct, rows=rows)
    path = OUT / f'run-{run_id}.json'
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'\n报告: {path}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
