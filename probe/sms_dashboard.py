"""号码互发成功率 · 实时看板（只读，127.0.0.1:8767）。

只读取 .local/sms-rate-ask/ 下测试脚本写出的进度和结果，本身不发短信、不连 VoCat。
运行: python sms_dashboard.py [--port 8767]，浏览器打开 http://127.0.0.1:8767
"""
import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
import sys
sys.path.insert(0, str(HERE))
from sms_rate_ask import stats  # 与测试脚本同一套口径：被限流的不计入成功率
OUT = HERE.parent / '.local' / 'sms-rate-ask'
PAGE = HERE / 'sms_dashboard.html'


def read_json(p):
    try:
        return json.loads(p.read_text('utf-8'))
    except Exception:
        return None


def history():
    runs = []
    for p in sorted(OUT.glob('*/results.json'), key=lambda x: x.stat().st_mtime, reverse=True):
        d = read_json(p)
        if d:
            runs.append(dict(batch=d.get('batch'), started=d.get('started'), overall=stats(d.get('messages') or [])['overall']))
    return runs


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def send(self, code, body, ctype='application/json; charset=utf-8'):
        data = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', ctype)
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        path = self.path.split('?')[0]
        if path in ('/', '/index.html'):
            return self.send(200, PAGE.read_bytes(), 'text/html; charset=utf-8')
        if path == '/api/live':
            lv = read_json(OUT / 'live.json') or {'state': 'idle'}
            if lv.get('state') in (None, 'idle'):  # 没有进行中的测试：显示最近一批
                latest = sorted(OUT.glob('*/results.json'), key=lambda x: x.stat().st_mtime)
                if latest:
                    lv = dict(state='done', batch=latest[-1].parent.name)
            if lv.get('state') == 'done' and lv.get('batch'):
                full = read_json(OUT / lv['batch'] / 'results.json')
                if full:  # 结束后用完整结果（含补录的收到内容）
                    full.update(state='done', planned=len(full.get('messages') or []),
                                summary=stats(full.get('messages') or []))
                    lv = full
            return self.send(200, lv)
        if path == '/api/history':
            return self.send(200, history())
        if path.startswith('/api/run/'):
            batch = path.rsplit('/', 1)[-1]
            if not batch.replace('-', '').isalnum():
                return self.send(400, {'error': 'bad batch'})
            d = read_json(OUT / batch / 'results.json')
            if d:
                d['summary'] = stats(d.get('messages') or [])
            return self.send(200 if d else 404, d or {'error': 'not found'})
        return self.send(404, {'error': 'not found'})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--port', type=int, default=8767)
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    print(f'号码互发成功率看板: http://127.0.0.1:{args.port}', flush=True)
    ThreadingHTTPServer(('127.0.0.1', args.port), Handler).serve_forever()


if __name__ == '__main__':
    main()
