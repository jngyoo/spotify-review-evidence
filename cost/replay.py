"""Offline only: no networking and no model import. Reprice actual saved call usage."""
import argparse,csv,json,collections
from pathlib import Path

def calculate(calls,rates):
    stages={};missing=[]
    for c in calls:
        s=stages.setdefault(c['role'],{'attempts':0,'failed':0,'input_tokens':0,'cached_input_tokens':0,'output_tokens':0,'api_usd':0.,'call_seconds':0.,'input_reviews':0})
        s['attempts']+=1;s['failed']+=c['outcome']!='succeeded';s['call_seconds']+=c['wall_seconds'];s['input_reviews']+=len(c['review_ids'])
        if c.get('input_tokens') is None or c.get('output_tokens') is None:
            missing.append(c['request_id']);continue
        units={'input':c['input_tokens']-c.get('cached_input_tokens',0),'cached_input':c.get('cached_input_tokens',0),'output':c['output_tokens']}
        if min(units.values())<0:raise ValueError('Overlapping token categories')
        for k,n in units.items():
            s[k+'_tokens']+=n;s['api_usd']+=n*rates[(c['model'],k)]
    return stages,missing

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--pilot',type=Path,default=Path(__file__).parent/'pilot');p.add_argument('--rates',type=Path,default=Path(__file__).parent/'rates.csv');p.add_argument('--rows',type=int,default=660622);p.add_argument('--unique',type=int,default=484189);p.add_argument('--nonempty',type=int,default=660609);p.add_argument('--budget',type=float,default=0);p.add_argument('--verification-rate',type=float,default=.01);p.add_argument('--rate-multiplier',type=float,default=1);p.add_argument('--out',type=Path,default=Path(__file__).parent/'report.json');a=p.parse_args()
    if not 0<=a.verification_rate<=1 or not 0<=a.unique<=a.nonempty<=a.rows: p.error('invalid volumes or verification rate')
    rates={(r['model'],r['category']):float(r['usd_per_million'])/1000000*a.rate_multiplier for r in csv.DictReader(a.rates.open())}
    calls=[json.loads(x) for x in (a.pilot/'grading/calls.jsonl').read_text().splitlines()];records=[json.loads(x) for x in (a.pilot/'grading/records.jsonl').read_text().splitlines()]
    runs=[json.loads(p.read_text()) for p in sorted(a.pilot.glob('run-*.json'))]
    experiment=json.loads((a.pilot/'experiment.json').read_text()) if (a.pilot/'experiment.json').exists() else {}
    stages,missing=calculate(calls,rates);cost=sum(s['api_usd'] for s in stages.values());done=sum(r['status']=='completed' for r in records)
    scenarios=[]
    for reuse,work in [(True,a.unique),(False,a.nonempty)]:
        for name,mult in [('base',1),('conservative',1.5)]:
            projected_cost=0;projected_seconds=0;by_stage={}
            for role,s in stages.items():
                if role=='enrich': factor=work/max(s['input_reviews'],1)
                elif role=='verify': factor=a.nonempty*a.verification_rate/max(s['input_reviews'],1)
                else: factor=1
                by_stage[role]={'api_usd':s['api_usd']*factor*mult,'seconds':s['call_seconds']*factor*mult}
                projected_cost+=by_stage[role]['api_usd'];projected_seconds+=by_stage[role]['seconds']
            overhead=max(0,experiment.get('cold_wall_seconds',runs[0]['wall_seconds'] if runs else 0)-sum(s['call_seconds'] for s in stages.values()))
            scenarios.append({'name':name,'exact_text_reuse':reuse,'estimated_api_usd':projected_cost,'estimated_model_and_pilot_overhead_hours':(projected_seconds+overhead)/3600,'budget_exceeded':projected_cost>a.budget,'stages':by_stage})
    report={'measured':{'experiment':experiment,'records':len(records),'completed':done,'quarantined':len(records)-done,'api_usd':cost,'api_usd_per_1000_inputs':cost*1000/max(len(records),1),'api_usd_per_completed':cost/max(done,1),'local_compute_cost_usd':None,'missing_usage_call_ids':missing,'stages':stages,'runs':runs},'projected':{'rows':a.rows,'nonempty':a.nonempty,'unique':a.unique,'verification_rate':a.verification_rate,'fallback_fraction':0,'workers':1,'api_budget_usd':a.budget,'scenarios':scenarios},'limitations':['Local electricity/hardware costs unmeasured, not zero.','Projection uses serial observed model-call throughput; final database/export time is not measured.','First 100 reviews are not a sustained-load benchmark.','No paid API adapter or fallback is enabled.','Warm cached replay requires no new enrichment; inspect run new_calls for all stages.']}
    a.out.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
if __name__=='__main__':main()
