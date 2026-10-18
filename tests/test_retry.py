import unittest,tempfile,sys,json
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from pipeline import LocalModel,connect,validate,SCHEMA
class Response:
 def __init__(self,data):self.data=json.dumps(data).encode()
 def read(self):return self.data
 def __enter__(self):return self
 def __exit__(self,*args):pass
class RetryTests(unittest.TestCase):
 def test_invalid_output_retry_is_logged_and_bounded(self):
  with tempfile.TemporaryDirectory() as d:
   model=object.__new__(LocalModel);model.db=connect(Path(d)/'state.sqlite');model.out=Path(d);model.model='synthetic';model.cap=128;model.compact=False;model.identity={'digest':'fixture'};model.config='fixture';model.endpoint='http://localhost:11434'
   row={'review_id':'synthetic','review_text':'Great app'}
   prediction={'review_id':'synthetic','topic':'other','intent':'praise','severity':1,'sentiment':1,'needs_review':False}
   def response(records):return Response({'done_reason':'stop','message':{'content':json.dumps({'records':records})},'prompt_eval_count':20,'eval_count':10})
   with patch('urllib.request.urlopen',side_effect=[response([]),response([prediction])]) as call,patch('time.sleep'):
    result=model.call('enrich',[row],['synthetic'],schema=SCHEMA,check=lambda x:validate(x,[row]))
   logs=[json.loads(x[0]) for x in model.db.execute('select payload from calls order by rowid')]
   self.assertEqual(call.call_count,2);self.assertEqual([x['outcome'] for x in logs],['failed','succeeded']);self.assertEqual(result['records'][0],prediction)
 def test_two_failures_stop(self):
  with tempfile.TemporaryDirectory() as d:
   model=object.__new__(LocalModel);model.db=connect(Path(d)/'state.sqlite');model.out=Path(d);model.model='synthetic';model.cap=128;model.compact=False;model.identity={'digest':'fixture'};model.config='fixture';model.endpoint='http://localhost:11434'
   with patch('urllib.request.urlopen',side_effect=OSError('synthetic transient failure')) as call,patch('time.sleep'):
    with self.assertRaises(RuntimeError):model.call('enrich',[],[])
   self.assertEqual(call.call_count,2);self.assertEqual(model.db.execute('select count(*) from calls').fetchone()[0],2)
if __name__=='__main__':unittest.main()
