import unittest,sys,tempfile,json,csv
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from pipeline import *
class PipelineTests(unittest.TestCase):
    def test_missing_duplicate_foreign_ids(self):
        a={'review_id':'a','topic':'other','intent':'praise','severity':1,'sentiment':1,'needs_review':False}
        validate({'records':[a]},[{'review_id':'a'}])
        for records in ([],[a,a],[dict(a,review_id='x')]):
            with self.assertRaises(ValueError): validate({'records':records},[{'review_id':'a'}])
    def test_numeric_validation(self):
        a={'review_id':'a','topic':'other','intent':'praise','severity':1,'sentiment':1,'needs_review':False}
        for delta in ({'severity':True},{'severity':5.5},{'sentiment':float('nan')},{'sentiment':2},{'needs_review':'false'}):
            with self.assertRaises(ValueError):validate({'records':[{**a,**delta}]},[{'review_id':'a'}])
    def test_ranking_and_ties(self):
        with tempfile.TemporaryDirectory() as d:
            db=connect(Path(d)/'x.sqlite')
            for id,topic,intent,sev in [('a','billing','complaint',3),('b','billing','cancellation',1),('c','access','complaint',4),('d','access','praise',1)]:
                r={'review_id':id,'topic':topic,'intent':intent,'severity':sev,'status':'completed','evidence_quote':'example'}
                db.execute('INSERT INTO records VALUES(?,?,?)',(id,'cfg',canonical(r)))
            db.commit(); a=rank(db,Path(d)); b=rank(db,Path(d))
            self.assertEqual(a,b); self.assertEqual(a['ranking'][0]['issue_id'],'ISSUE-access')
            self.assertEqual(a['ranking'][1]['complaint_count'],2)
            self.assertEqual(a['ranking'][1]['mean_severity'],'2.000000')
    def test_source_integrity(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'x.csv'; db=connect(Path(d)/'x.sqlite')
            fields=['review_id','review_text','review_rating','review_likes','app_version','review_timestamp']
            row=dict(zip(fields,['id','a\nb','5','0','','2023-01-01']))
            table(p,[row],fields); ingest(db,p); ingest(db,p)
            self.assertEqual(db.execute('select count(*) from reviews').fetchone()[0],1)
            row['review_text']='changed';table(p,[row],fields)
            with self.assertRaises(ValueError):ingest(db,p)
if __name__=='__main__':unittest.main()
