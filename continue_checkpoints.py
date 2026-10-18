"""Run staged local checkpoints and stop on failed validation; never calls paid APIs."""
import argparse,json,sqlite3,subprocess,sys,time,shutil
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--data',type=Path,required=True);p.add_argument('--pilot',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--through',choices=['500','10000'],default='10000');a=p.parse_args();root=Path(__file__).resolve().parent
a.out.mkdir(parents=True,exist_ok=True);src=a.pilot
for size,name in [(500,'checkpoint_500.csv'),(10000,'analysis_10000.csv')]:
 out=a.out/str(size);out.mkdir(exist_ok=True)
 if not (out/'state.sqlite').exists():
  source=sqlite3.connect(src/'state.sqlite');target=sqlite3.connect(out/'state.sqlite');source.backup(target);target.close();source.close()
 started=time.monotonic()
 command=[sys.executable,'-u',str(root/'pipeline.py'),'run','--input',str(a.data/name),'--full',str(a.data/'spotify_reviews_18months.csv'),'--out',str(out),'--classifier','nli','--batch','25','--verify',str(min(50,size//10)),'--phase','resume','--seconds','7200']
 code=subprocess.call(command)
 db=sqlite3.connect(out/'state.sqlite');n=db.execute("SELECT count(*) FROM records WHERE json_extract(payload,'$.status')='completed'").fetchone()[0];db.close()
 report={'scope':size,'completed':n,'wall_seconds':time.monotonic()-started,'exit_code':code,'input':name,'model':'local NLI + local generative verifier/group/memo','api_cost_usd':0}
 (out/'checkpoint-report.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report),flush=True)
 if code or n<size:raise SystemExit('Checkpoint incomplete; stopped before scaling')
 for name in ('checkpoint_before.json','checkpoint_after.json'):
  shutil.copy2(a.pilot/'grading'/name,out/'grading'/name)
 src=out
 if a.through=='500':break
