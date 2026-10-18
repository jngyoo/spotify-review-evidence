"""Record a real cold interrupted/resumed 100-review run, then a warm run."""
import argparse,json,os,signal,subprocess,sys,time,shutil,hashlib
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--input',required=True);p.add_argument('--full',required=True);p.add_argument('--out',type=Path,required=True);p.add_argument('--classifier',choices=['generative','nli'],default='generative');a=p.parse_args()
a.out.mkdir(parents=True,exist_ok=True)
if (a.out/'state.sqlite').exists():raise SystemExit('Cold pilot requires an empty result directory')
root=Path(__file__).resolve().parent;begin=time.monotonic();events=[]
base=[sys.executable,'-u',str(root/'pipeline.py'),'run','--input',str(Path(a.input).resolve()),'--full',str(Path(a.full).resolve()),'--out',str(a.out.resolve()),'--batch','5','--verify','10','--classifier',a.classifier]
sources=[root/'pipeline.py',root/'nli_classifier.py',*sorted((root/'prompts').glob('*.txt'))]
frozen={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}
(a.out/'source_fingerprints.json').write_text(json.dumps(frozen,indent=2)+'\n')
def record(command,interrupt=False):
 if frozen!={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources}:raise SystemExit('Source changed during pilot; use a fresh folder')
 events.append([time.monotonic()-begin,'o','$ '+' '.join(command)+'\r\n'])
 proc=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True);sent=False
 for line in proc.stdout:
  events.append([time.monotonic()-begin,'o',line.replace('\n','\r\n')]);print(line,end='',flush=True)
  if interrupt and not sent and '"newly_attempted": 5' in line:
   proc.send_signal(signal.SIGINT);sent=True;events.append([time.monotonic()-begin,'o','[Recorder sent SIGINT after saved progress]\r\n'])
 code=proc.wait();events.append([time.monotonic()-begin,'o',f'[exit {code}]\r\n']);return code
first=record(base+['--enrich-only'],True)
shutil.copyfile(a.out/'checkpoint_initial_after.json',a.out/'grading/checkpoint_before.json')
second=record(base+['--phase','resume']);cold=time.monotonic()-begin
shutil.copyfile(a.out/'checkpoint_resume_after.json',a.out/'grading/checkpoint_after.json')
warm_start=time.monotonic();third=record(base+['--phase','resume']);warm=time.monotonic()-warm_start
summary={'cold_wall_seconds':cold,'warm_wall_seconds':warm,'exit_codes':[first,second,third],'interruption':'SIGINT after first committed batch; actual captured stdout/stderr','api_cost_usd':0,'local_compute_cost_usd':None}
(a.out/'experiment.json').write_text(json.dumps(summary,indent=2)+'\n')
with (a.out/'interruption.cast').open('w') as f:
 f.write(json.dumps({'version':2,'width':120,'height':30,'timestamp':int(time.time()),'title':'Actual cold pilot interruption, resume, warm replay'})+'\n')
 for event in events:f.write(json.dumps(event)+'\n')
print(json.dumps(summary),flush=True)
if second or third:raise SystemExit('Pipeline failed; inspect saved real evidence')
