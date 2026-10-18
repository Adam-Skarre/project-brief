"""Local single-user portfolio app; binds to loopback only."""
import json, secrets, threading, webbrowser, os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse
from core import generate,apply_review
ROOT=Path(__file__).parent; TOKEN=secrets.token_urlsafe(32); RUNS={}; LOCK=threading.Lock()
class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args): pass
    def send(self,status,data,kind='application/json',headers=None):
        raw=json.dumps(data).encode() if kind=='application/json' else data.encode()
        self.send_response(status);self.send_header('Content-Type',kind+'; charset=utf-8')
        self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Content-Length',str(len(raw)))
        for k,v in (headers or {}).items():self.send_header(k,v)
        self.end_headers();self.wfile.write(raw)
    def do_GET(self):
        if self.path=='/': return self.send(200,(ROOT/'index.html').read_text().replace('__TOKEN__',TOKEN),'text/html')
        if self.path=='/sample': return self.send(200,{'csv':(ROOT/'data/sample.csv').read_text()})
        if self.path.startswith('/export/'):
            rid=self.path.removeprefix('/export/')
            with LOCK: report=RUNS.get(rid)
            if not report:return self.send(404,{'error':'Report not found'})
            if report['review']['status']!='approved':return self.send(409,{'error':'Review and approval required'})
            return self.send(200,report,headers={'Content-Disposition':'attachment; filename="approved-report.json"'})
        self.send(404,{'error':'Not found'})
    def do_POST(self):
        if self.headers.get('X-App-Token')!=TOKEN:return self.send(403,{'error':'Invalid app session'})
        try:
            size=int(self.headers.get('Content-Length','0'))
            if not 0<size<=250000:raise ValueError('Request must be between 1 and 250000 bytes')
            body=json.loads(self.rfile.read(size))
            if not isinstance(body,dict):raise ValueError('Expected JSON object')
            if self.path=='/generate':
                report=generate(body['csv'],body['as_of'],body.get('mode','demo'));rid=secrets.token_hex(12)
                report['run_id']=rid
                with LOCK:
                    if len(RUNS)>=30:RUNS.pop(next(iter(RUNS)))
                    RUNS[rid]=report
                return self.send(200,report)
            if self.path=='/review':
                with LOCK:
                    report=RUNS.get(body['run_id'])
                    if not report:raise ValueError('Report expired; generate again')
                    apply_review(report,body['reviewer'],body['summary'],body.get('notes',''))
                return self.send(200,report)
            self.send(404,{'error':'Not found'})
        except (ValueError,KeyError,TypeError) as exc:self.send(400,{'error':str(exc)})
        except Exception:self.send(500,{'error':'Unexpected failure; no report approved'})
if __name__=='__main__':
    port=int(os.environ.get('PORT','8765'))
    server=ThreadingHTTPServer(('127.0.0.1',port),Handler)
    print(f'Project Brief: http://127.0.0.1:{port} (Ctrl+C to stop)',flush=True)
    server.serve_forever()
