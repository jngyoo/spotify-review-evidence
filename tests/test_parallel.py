import unittest,tempfile,sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from pipeline import *
class ParallelTests(unittest.TestCase):
 def test_exact_duplicates_keep_ids_and_direct_provenance(self):
  with tempfile.TemporaryDirectory() as d:
   out=Path(d);db=connect(out/'state.sqlite');source=out/'data.csv'
   fs=['review_id','review_text','review_rating','review_likes','app_version','review_timestamp']
   table(source,[dict(zip(fs,[i,t,'5','0','','2023-01-01'])) for i,t in [('a','Good'),('b','Good'),('c','Nice')]],fs);ingest(db,source)
   model=object.__new__(LocalModel);model.config='test';model.db=db
   args=SimpleNamespace(out=out,max_new=0,batch=1,workers=2,seconds=10,phase='initial')
   def fake(self,role,data,*args,**kwargs):return {'records':[{'review_id':r['review_id'],'topic':'other','intent':'praise','severity':1,'sentiment':1,'needs_review':False} for r in data]}
   with patch.object(LocalModel,'call',fake):result=enrich_parallel(db,model,args)
   self.assertEqual(result['newly_attempted'],2);self.assertEqual(result['exact_text_cache_hits'],1)
   rows={r['review_id']:json.loads(r['payload']) for r in db.execute('select * from records')}
   self.assertEqual(set(rows),{'a','b','c'});self.assertEqual(rows['b']['cache_source_id'],'a');self.assertNotIn('cache_source_id',rows['a'])
if __name__=='__main__':unittest.main()
