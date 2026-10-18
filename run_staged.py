"""Resumeable local-only execution with consistency and disagreement gates."""
import argparse,json,subprocess,sys,time,sqlite3,shutil,hashlib
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--data',type=Path,required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--pilot-reference',type=Path,required=True);p.add_argument('--through',choices=['10000','full'],default='10000');a=p.parse_args()
root=Path(__file__).resolve().parent;a.out.mkdir(parents=True,exist_ok=True)
sources=[root/'pipeline.py',root/'nli_classifier.py',*sorted((root/'prompts').glob('*.txt'))]
fingerprints={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
freeze=a.out/'source_fingerprints.json'
if freeze.exists() and json.loads(freeze.read_text())!=fingerprints:raise SystemExit('Frozen source differs; use a fresh output folder')
freeze.write_text(json.dumps(fingerprints,indent=2)+'\n')
def state(stage,status,**kw):
 d={'stage':stage,'status':status,'updated_epoch':time.time(),**kw};(a.out/'progress.json').write_text(json.dumps(d,indent=2)+'\n');print(json.dumps(d),flush=True)
def run(*args):
 if fingerprints!={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}:raise RuntimeError('Source changed during staged execution')
 subprocess.run([sys.executable,*map(str,args)],check=True)
def backup(src,dst):
 if dst.exists():return
 source=sqlite3.connect(src);target=sqlite3.connect(dst);source.backup(target);target.close();source.close()
def gate(folder,expected):
 db=sqlite3.connect(folder/'state.sqlite');counts={r[0]:r[1] for r in db.execute("select json_extract(payload,'$.status'),count(*) from records group by 1")};db.close()
 if counts.get('completed',0)!=expected:raise RuntimeError(f'Incomplete checkpoint: {counts}')
 v=json.loads((folder/'verification.json').read_text());dis=sum(bool(r['disagreements']) for r in v['comparisons']);fraction=dis/v['sample_size'] if v['sample_size'] else 1
 report={'expected_completed':expected,'counts':counts,'verifier_disagreements':dis,'verification_sample':v['sample_size'],'disagreement_fraction':fraction,'threshold':.5,'note':'Operational gate only; model agreement is not ground truth.'};(folder/'quality-gate.json').write_text(json.dumps(report,indent=2)+'\n')
 if fraction>.5:raise RuntimeError(f'Independent disagreement {fraction:.1%} exceeds 50% gate; inspect before scaling')
try:
 pilot=a.out/'pilot100';state('pilot100','running')
 if not (pilot/'experiment.json').exists():run(root/'record_pilot.py','--classifier','nli','--input',a.data/'cost_100.csv','--full',a.data/'spotify_reviews_18months.csv','--out',pilot)
 experiment=json.loads((pilot/'experiment.json').read_text())
 if experiment['exit_codes'][1:]!=[0,0]:raise RuntimeError('Pilot did not complete cleanly')
 run(root/'vendor/check_submission.py','check','--reference',a.pilot_reference,'--submission',pilot/'grading','--out',pilot/'audit.json')
 if json.loads((pilot/'audit.json').read_text())['status']!='pass':raise RuntimeError('Pilot audit failed')
 run(root/'cost/replay.py','--pilot',pilot,'--out',pilot/'cost-report.json')
 previous=pilot
 for count,filename in [(500,'checkpoint_500.csv'),(10000,'analysis_10000.csv')]:
  folder=a.out/str(count);folder.mkdir(exist_ok=True);backup(previous/'state.sqlite',folder/'state.sqlite');state(str(count),'running');start=time.monotonic()
  run(root/'pipeline.py','run','--classifier','nli','--input',a.data/filename,'--full',a.data/'spotify_reviews_18months.csv','--out',folder,'--batch','25','--verify','50','--phase','resume','--seconds','14400')
  for name in ('checkpoint_before.json','checkpoint_after.json'):shutil.copy2(pilot/'grading'/name,folder/'grading'/name)
  gate(folder,count);state(str(count),'completed',wall_seconds=time.monotonic()-start);previous=folder
 if a.through=='full':
  if shutil.disk_usage(a.out).free<12*1024**3:raise RuntimeError('Less than 12 GiB available for full run')
  folder=a.out/'full';folder.mkdir(exist_ok=True);backup(previous/'state.sqlite',folder/'state.sqlite');state('full','running');start=time.monotonic()
  run(root/'pipeline.py','run','--classifier','nli','--input',a.data/'spotify_reviews_18months.csv','--full',a.data/'spotify_reviews_18months.csv','--out',folder,'--batch','25','--verify','200','--phase','resume','--seconds','172800')
  for name in ('checkpoint_before.json','checkpoint_after.json'):shutil.copy2(pilot/'grading'/name,folder/'grading'/name)
  gate(folder,660609);state('full','classified',wall_seconds=time.monotonic()-start)
  run(root/'vendor/check_submission.py','reference','--full',a.data/'spotify_reviews_18months.csv','--analysis',a.data/'spotify_reviews_18months.csv','--out',a.out/'full-reference.json')
  run(root/'vendor/check_submission.py','check','--reference',a.out/'full-reference.json','--submission',folder/'grading','--out',folder/'audit.json')
  if json.loads((folder/'audit.json').read_text())['status']!='pass':raise RuntimeError('Full audit failed')
 state(a.through,'completed',remaining='Final dashboard update, publication package and human-reviewed golden evaluation')
except BaseException as e:
 state('stopped','failed',error=str(e) or type(e).__name__);raise
