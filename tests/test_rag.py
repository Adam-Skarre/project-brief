import json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from rag.pipeline import Pipeline,validate_answer
from rag.retrieval import chunk_document,BM25,rrf,cosine
from eval_rag import metrics
from review_rag import kappa

class RAGTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.p=Pipeline(Path(self.temp.name)/'rag.sqlite')
  self.docs=[{'name':'policy.md','text':'The archive retention period is thirty days. Records must be reviewed before export.'},{'name':'other.md','text':'Apples and pears are available in the kitchen.'}]
  self.idx=self.p.ingest(self.docs)['index_id']
 def tearDown(self):self.temp.cleanup()
 def test_offsets_and_stability(self):
  text='heading\n'+' '.join('word'+str(i) for i in range(90))
  chunks=chunk_document('x',text,30,5)
  for c in chunks:self.assertEqual(text[c['start_char']:c['end_char']],c['text'])
  self.assertEqual(chunks,chunk_document('x',text,30,5));self.assertNotEqual(chunks[0]['chunk_id'],chunk_document('x',text+'!',30,5)[0]['chunk_id'])
 def test_invalid_overlap(self):
  with self.assertRaises(ValueError):chunk_document('x','text',30,30)
 def test_bm25_exact_identifier(self):
  chunks=[{'chunk_id':'a','text':'Requirement PRJ-802 retention'},{'chunk_id':'b','text':'Requirement PRJ-803 retention'}]
  self.assertEqual(BM25(chunks).search('PRJ-802')[0][0],'a')
 def test_fusion(self):self.assertEqual(rrf([[('a',9),('b',1)],[('b',8)]])[0][0],'b')
 def test_dimension_mismatch(self):
  with self.assertRaises(ValueError):cosine([1],[1,2])
 def test_retrieval_all_modes(self):
  for mode in ['dense','hybrid','rerank']:
   found,_=self.p.retrieve(self.idx,'archive retention period',mode)
   self.assertEqual(found[0]['document'],'policy.md')
 def test_offline_not_fake_answer(self):
  answer=self.p.ask(self.idx,'retention')['answer'];self.assertTrue(answer['abstain']);self.assertEqual(answer['claims'],[])
 def test_cache_and_corpus_isolation(self):
  self.assertFalse(self.p.ask(self.idx,'retention')['cache_hit']);self.assertTrue(self.p.ask(self.idx,'retention')['cache_hit'])
  self.assertFalse(self.p.ask(self.idx,'retention',config='dense')['cache_hit'])
  other=self.p.ingest([{'name':'policy.md','text':'Retention is now sixty days.'}])['index_id']
  self.assertNotEqual(other,self.idx);self.assertFalse(self.p.ask(other,'retention')['cache_hit'])
 def test_validate_evidence(self):
  chunks=[{'chunk_id':'a','text':'Retention is thirty days.'}]
  value={'abstain':False,'reason':'','claims':[{'text':'Thirty days.','evidence':[{'chunk_id':'a','quote':'thirty days'}]}]}
  self.assertEqual(validate_answer(value,chunks),value)
  value['claims'][0]['evidence'][0]['quote']='sixty days'
  with self.assertRaises(ValueError):validate_answer(value,chunks)
  value['claims'][0]['evidence'][0]={'chunk_id':'unknown','quote':'thirty days'}
  with self.assertRaises(ValueError):validate_answer(value,chunks)
 def test_budget(self):
  self.p.store.reserve(.7,'generation',1)
  with self.assertRaises(ValueError):self.p.store.reserve(.4,'generation',1)
  with self.assertRaises(ValueError):self.p.store.reserve(float('nan'),'generation',1)
 def test_live_adapter_mock(self):
  with patch.dict('os.environ',{'OPENAI_API_KEY':'test','RAG_EMBEDDING_MAX_USD':'.1','RAG_DAILY_CAP_USD':'1'}),patch('rag.providers.post',return_value={'data':[{'index':0,'embedding':[1,0]}]}) as post:
   self.assertEqual(self.p.provider.embed(['hello'],'openai','test-model'),[[1,0]])
   self.assertEqual(post.call_count,1)
 def test_metrics(self):
  m=metrics(['a','b','c'],{'b','d'});self.assertEqual(m['recall_at_20'],.5);self.assertEqual(m['mrr'],.5);self.assertEqual(m['precision_at_5'],.2)
 def test_kappa(self):self.assertEqual(kappa(['0','1'],['0','1']),1)

if __name__=='__main__':unittest.main()
