import json,tempfile,unittest,sys
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from pipeline import connect,table,ingest,canonical,downstream
class DownstreamTests(unittest.TestCase):
 def test_group_identity_and_unsupported_comparison(self):
  with tempfile.TemporaryDirectory() as folder:
   out=Path(folder);db=connect(out/'state.sqlite');source=out/'source.csv'
   fields=['review_id','review_text','review_rating','review_likes','app_version','review_timestamp']
   table(source,[dict(zip(fields,[i,t,'1','0','','2023-01-01'])) for i,t in [('a','Cannot log in'),('b','Audio annoyance')]],fields);ingest(db,source)
   for row in db.execute('select * from reviews').fetchall():
    record={'review_id':row['review_id'],'source_sha256':row['source_sha256'],'status':'completed','topic':'access' if row['review_id']=='a' else 'playback','intent':'complaint','severity':4 if row['review_id']=='a' else 2,'evidence_quote':row['text'],'label_config':'test'}
    db.execute('insert into records values(?,?,?)',(row['review_id'],'test',canonical(record)))
   db.commit();before=db.execute('select payload from records order by review_id').fetchall();calls=[]
   class Fake:
    model='test'
    def call(self,role,data,ids,**kwargs):
     calls.append((role,data,kwargs.get('schema')))
     if role=='group':result={'issues':[{'issue_id':data['issues'][0]['issue_id'],'name':'Issue','description':'Saved example'}]}
     else:result={'priority_issue':'ISSUE-playback','alternative_issue':'ISSUE-access','reason':'higher_severity'}
     kwargs['check'](result);return result
   downstream(db,Fake(),SimpleNamespace(out=out,verify=0,batch=25))
   self.assertEqual(before,db.execute('select payload from records order by review_id').fetchall())
   group_calls=[c for c in calls if c[0]=='group'];self.assertEqual(len(group_calls),2)
   for _,data,schema in group_calls:
    self.assertEqual(len(data['issues']),1)
    self.assertEqual(schema['properties']['issues']['items']['properties']['issue_id']['enum'],[data['issues'][0]['issue_id']])
   memo=json.loads((out/'memo.json').read_text());self.assertFalse(memo['comparative_reason_supported']);self.assertNotIn('higher severity',memo['recommendation'])
if __name__=='__main__':unittest.main()
