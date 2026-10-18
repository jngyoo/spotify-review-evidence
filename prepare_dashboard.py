"""Publish saved aggregates plus a bounded evidence subset; never claims all rows are served."""
import argparse,json,sqlite3,hashlib
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
db=sqlite3.connect(a.run/'state.sqlite');analysis=json.loads(db.execute("select payload from artifacts where key='analysis'").fetchone()[0]);memo=json.loads((a.run/'memo.json').read_text());v=json.loads((a.run/'verification.json').read_text());source=json.loads((a.run/'grading/ingestion.json').read_text())
ids=sorted({r['review_id'] for group in analysis['evidence'].values() for r in group})
reviews=[json.loads(db.execute('select payload from records where review_id=?',(i,)).fetchone()[0]) for i in ids];db.close()
analysis.update(recommendation=memo,sourceTotal=source['counts']['records'],apiCost=0,verifierSample=v['sample_size'],verifierDisagreements=sum(bool(r['disagreements']) for r in v['comparisons']),enrichmentModel=v.get('enrichment_model','unknown'),verificationModel=v.get('verification_model','unknown'),evidenceSubset=True,evidenceRows=len(reviews))
identity=hashlib.sha256(json.dumps(analysis,sort_keys=True).encode()).hexdigest()[:16]
seed={'runId':'saved-'+identity,'analysis':analysis,'reviews':reviews}
a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(seed,ensure_ascii=False,separators=(',',':'))+'\n');print(json.dumps({'run_id':seed['runId'],'coverage':analysis['coverage'],'evidence_rows':len(reviews)}))
