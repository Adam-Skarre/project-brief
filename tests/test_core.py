import copy,json,unittest,sys,io,csv
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from core import *
SAMPLE=(Path(__file__).resolve().parents[1]/'data/sample.csv').read_text()
class Controls(unittest.TestCase):
    def test_sample_facts(self):
        r=generate(SAMPLE,'2026-10-18');f=r['facts']
        self.assertEqual(f['overdue_ids'],['R001','R006']);self.assertEqual(f['blocked_ids'],['R003','R006'])
        self.assertEqual(f['conflicts'][0]['source_ids'],['R005','R006'])
        self.assertEqual(f['missing_fields'],[{'record_id':'R004','fields':['owner','due_date']}])
    def test_duplicate_ids_rejected(self):
        with self.assertRaises(ValueError):parse_csv(SAMPLE.replace('R002','R001'))
    def test_invalid_date(self):
        with self.assertRaises(ValueError):parse_csv(SAMPLE.replace('2026-10-15','2026-02-30'))
    def test_invalid_status(self):
        with self.assertRaises(ValueError):parse_csv(SAMPLE.replace('in_progress','finished'))
    def test_missing_column(self):
        with self.assertRaises(ValueError):parse_csv('record_id,task\n1,test')
    def test_empty_records(self):
        with self.assertRaises(ValueError):parse_csv(','.join(FIELDS))
    def test_unknown_citation(self):
        with self.assertRaises(ValueError):validate_commentary({'summary':'x','observations':[{'text':'x','source_ids':['NOPE']}]},parse_csv(SAMPLE))
    def test_missing_citation(self):
        with self.assertRaises(ValueError):validate_commentary({'summary':'x','observations':[{'text':'x','source_ids':[]}]},parse_csv(SAMPLE))
    def test_extra_output_fields(self):
        with self.assertRaises(ValueError):validate_commentary({'summary':'x','observations':[],'approved':True},parse_csv(SAMPLE))
    def test_review_preserves_original(self):
        r=generate(SAMPLE,'2026-10-18');original=copy.deepcopy(r['commentary'])
        apply_review(r,'Adam','Corrected summary','Reviewed records')
        self.assertEqual(r['commentary'],original);self.assertEqual(r['review']['status'],'approved')
    def test_empty_reviewer(self):
        with self.assertRaises(ValueError):apply_review(generate(SAMPLE,'2026-10-18'),'','Summary','')
    def test_live_requires_credentials(self):
        with patch.dict(os.environ,{},clear=True):
            with self.assertRaises(ValueError):generate(SAMPLE,'2026-10-18','live')
    def test_mock_provider_contract(self):
        class Response:
            def __enter__(self):return io.StringIO(json.dumps({'status':'completed','output':[{'content':[{'type':'output_text','text':json.dumps({'summary':'Review overdue work.','observations':[{'text':'Open task is overdue.','source_ids':['R001']}]})}]}],'usage':{'input_tokens':10,'output_tokens':20}}))
            def __exit__(self,*args):pass
        with patch.dict(os.environ,{'OPENAI_API_KEY':'test-only','OPENAI_MODEL':'test-model'}),patch('urllib.request.urlopen',return_value=Response()) as mock:
            r=generate(SAMPLE,'2026-10-18','live')
            request=mock.call_args.args[0];payload=json.loads(request.data)
            self.assertFalse(payload['store']);self.assertTrue(payload['text']['format']['strict'])
            self.assertEqual(r['metrics']['usage']['input_tokens'],10)
    def test_refusal(self):
        class Response:
            def __enter__(self):return io.StringIO(json.dumps({'status':'completed','output':[{'content':[{'type':'refusal'}]}]}))
            def __exit__(self,*args):pass
        with patch.dict(os.environ,{'OPENAI_API_KEY':'test-only','OPENAI_MODEL':'test-model'}),patch('urllib.request.urlopen',return_value=Response()):
            with self.assertRaises(ValueError):generate(SAMPLE,'2026-10-18','live')
if __name__=='__main__':unittest.main()
