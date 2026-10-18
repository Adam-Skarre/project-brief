"""Exercise the HTTP handler with real request bytes, without binding a socket."""
import unittest,sys,json,io
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import app
class HTTPFlow(unittest.TestCase):
    def request(self,path,body=None,token=app.TOKEN):
        raw=json.dumps(body).encode() if body is not None else b''
        method='POST' if body is not None else 'GET'
        request=(f'{method} {path} HTTP/1.0\r\nHost: localhost\r\nContent-Type: application/json\r\nX-App-Token: {token}\r\nContent-Length: {len(raw)}\r\n\r\n').encode()+raw
        h=app.Handler.__new__(app.Handler);h.rfile=io.BytesIO(request);h.wfile=io.BytesIO()
        h.client_address=('127.0.0.1',1234);h.server=SimpleNamespace();h.close_connection=True
        h.handle_one_request();headers,payload=h.wfile.getvalue().split(b'\r\n\r\n',1)
        return int(headers.split()[1]),json.loads(payload)
    def test_generate_review_export(self):
        _,sample=self.request('/sample');status,r=self.request('/generate',{'csv':sample['csv'],'as_of':'2026-10-18'})
        self.assertEqual(status,200)
        self.assertEqual(self.request('/export/'+r['run_id'])[0],409)
        self.assertEqual(self.request('/review',{'run_id':r['run_id'],'reviewer':'Adam','summary':'Checked','notes':'Synthetic test'})[0],200)
        status,export=self.request('/export/'+r['run_id']);self.assertEqual(status,200)
        self.assertEqual(export['review']['status'],'approved')
    def test_token_required(self):
        self.assertEqual(self.request('/generate',{},token='invalid')[0],403)
