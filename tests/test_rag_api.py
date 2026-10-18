import importlib.util,os,tempfile,unittest
AVAILABLE=all(importlib.util.find_spec(x) for x in ['fastapi','httpx'])
@unittest.skipUnless(AVAILABLE,'FastAPI/httpx dependencies not installed')
class APITests(unittest.TestCase):
 def test_auth_ingest_ask_limits(self):
  from fastapi.testclient import TestClient
  import rag_api
  from unittest.mock import patch
  with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{'RAG_DB':tmp+'/api.sqlite'}),TestClient(rag_api.app) as client:
   rag_api.CALLS.clear()
   self.assertEqual(client.get('/api/sample').status_code,401)
   headers={'Authorization':'Bearer '+(rag_api.ACCESS or rag_api.SESSION)}
   data={'documents':[{'name':'test.md','text':'The retention period is thirty days.'}]}
   r=client.post('/api/ingest',json=data,headers=headers);self.assertEqual(r.status_code,200,r.text)
   answer=client.post('/api/ask',json={'index_id':r.json()['index_id'],'question':'What is retention?'},headers=headers)
   self.assertEqual(answer.status_code,200,answer.text);self.assertTrue(answer.json()['answer']['abstain'])
   self.assertEqual(client.post('/api/ingest',content=b'x'*1500001,headers=headers).status_code,413)
   with patch.dict(os.environ,{'RAG_REQUESTS_PER_MINUTE':'1'}):self.assertEqual(client.get('/api/sample',headers=headers).status_code,429)
