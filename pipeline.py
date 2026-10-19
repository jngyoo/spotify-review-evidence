"""Auditable local Spotify pipeline. Python standard library; paid calls unsupported."""
import argparse, csv, hashlib, json, math, os, random, sqlite3, sys, time, urllib.request, uuid, threading
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from pathlib import Path
from decimal import Decimal, ROUND_HALF_UP
sys.path.insert(0, str(Path(__file__).parent / 'vendor'))
from check_submission import row_sha, csv_rows, sha, profile, TOPICS, INTENTS
ROOT = Path(__file__).resolve().parent

def canonical(x): return json.dumps(x, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)
def digest(x): return hashlib.sha256(canonical(x).encode()).hexdigest()
def save(path, value):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix(path.suffix+'.tmp'); tmp.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n'); os.replace(tmp,path)
def table(path,rows,fields):
    with Path(path).open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields); w.writeheader(); w.writerows(rows)
def prompt(role): return (ROOT/'prompts'/f'{role}.txt').read_text()
def connect(path):
    Path(path).parent.mkdir(parents=True,exist_ok=True)
    db=sqlite3.connect(path); db.row_factory=sqlite3.Row
    db.executescript('''PRAGMA journal_mode=WAL;
    CREATE TABLE IF NOT EXISTS reviews(review_id TEXT PRIMARY KEY,source_json TEXT NOT NULL,source_sha256 TEXT NOT NULL,text TEXT NOT NULL,text_hash TEXT NOT NULL);
    CREATE INDEX IF NOT EXISTS text_idx ON reviews(text_hash);
    CREATE TABLE IF NOT EXISTS records(review_id TEXT PRIMARY KEY,config TEXT NOT NULL,payload TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS cache(cache_key TEXT PRIMARY KEY,source_id TEXT NOT NULL,payload TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS calls(request_id TEXT PRIMARY KEY,payload TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS artifacts(key TEXT PRIMARY KEY,payload TEXT NOT NULL);
    '''); return db

def ingest(db,path):
    n=0; seen=set(); existing_ids={r[0] for r in db.execute("SELECT review_id FROM reviews")}
    with db:
        for r in csv_rows(path):
            if r['review_id'] in seen: raise ValueError('Duplicate source ID: '+r['review_id'])
            seen.add(r['review_id'])
            h=row_sha(r); old=db.execute('SELECT source_sha256 FROM reviews WHERE review_id=?',(r['review_id'],)).fetchone()
            if old and old[0]!=h: raise ValueError('Source ID changed: '+r['review_id'])
            db.execute('INSERT OR IGNORE INTO reviews VALUES(?,?,?,?,?)',(r['review_id'],canonical(r),h,r['review_text'],digest(r['review_text'])))
            n+=1
        if existing_ids-seen: raise ValueError("Input is not a superset of this run; use a fresh output directory")
    return n

FIELDS={'review_id':{'type':'string'},'topic':{'type':'string','enum':list(TOPICS)},'intent':{'type':'string','enum':list(INTENTS)},'severity':{'type':'integer','minimum':1,'maximum':5},'sentiment':{'type':'number','minimum':-1,'maximum':1},'needs_review':{'type':'boolean'}}
SCHEMA={'type':'object','properties':{'records':{'type':'array','items':{'type':'object','properties':FIELDS,'required':list(FIELDS),'additionalProperties':False}}},'required':['records'],'additionalProperties':False}

def validate(raw,rows):
    preds=raw['records']; expected={r['review_id'] for r in rows}
    if len(preds)!=len(rows) or {r['review_id'] for r in preds}!=expected: raise ValueError('Missing/duplicate/foreign review IDs')
    for r in preds:
        if set(r)!=set(FIELDS): raise ValueError('Unexpected fields')
        if r['topic'] not in TOPICS or r['intent'] not in INTENTS: raise ValueError('Invalid label')
        if type(r['severity']) is not int or not 1<=r['severity']<=5: raise ValueError('Invalid severity')
        if type(r['sentiment']) not in (int,float) or not math.isfinite(r['sentiment']) or not -1<=r['sentiment']<=1: raise ValueError('Invalid sentiment')
        if type(r['needs_review']) is not bool: raise ValueError('Invalid review flag')
    return preds

class LocalModel:
    def __init__(self,db,out,model,cap,compact=False):
        self.db=db; self.out=out; self.model=model; self.cap=cap; self.compact=compact; self.endpoint=os.environ.get('SPOTIFY_OLLAMA_URL','http://localhost:11434')
        if self.endpoint not in ('http://localhost:11434','http://127.0.0.1:11435'): raise ValueError('Only local, zero-API-cost endpoints are allowed')
        with urllib.request.urlopen(self.endpoint+'/api/tags',timeout=10) as r: models=json.load(r)['models']
        found=next((m for m in models if m['name']==model),None)
        if not found: raise ValueError('Local model is not installed')
        self.identity=found
        save(out/'model.json',found)
        self.config=digest({'identity':found['digest'],'prompt':prompt('enrich'),'schema':SCHEMA,'think':False,'temperature':0,'num_ctx':8192,'num_predict':cap})
        if compact: self.config=digest({'base':self.config,'wire_protocol':'id-keyed-array-v2'})
    def call(self,role,data,ids,phase='initial',schema=None,check=None):
        system=prompt(role)+(prompt('enrich') if role=='verify' else '')
        compact=self.compact and role in ('enrich','verify')
        if compact:
            system+='\nWIRE FORMAT OVERRIDE: Return a JSON object whose keys are EVERY exact supplied review_id. Each value is an array in this exact order: [topic string, intent string, severity integer, sentiment number, needs_review boolean]. No records wrapper, no explanations. Include every ID exactly once.'
            schema={'type':'object','properties':{i:{'type':'array','prefixItems':[FIELDS[k] for k in ('topic','intent','severity','sentiment','needs_review')],'items':False,'minItems':5,'maxItems':5} for i in ids},'required':ids,'additionalProperties':False}
        request={'model':self.model,'messages':[{'role':'system','content':system},{'role':'user','content':canonical(data)}], 'stream':False,'think':False,'format':schema or 'json','options':{'temperature':0,'num_ctx':8192,'num_predict':self.cap}}
        # Cache downstream by all role instructions, actual inputs, model digest and options.
        key='role:'+digest({'request':request,'model_digest':self.identity['digest']})
        if role!='enrich':
            old=self.db.execute('SELECT payload FROM artifacts WHERE key=?',(key,)).fetchone()
            if old: return json.loads(old[0])
        for attempt in range(2):
            rid=str(uuid.uuid4()); start=time.monotonic(); response=None
            log={'request_id':rid,'role':role,'review_ids':ids,'model':self.model,'model_digest':self.identity['digest'],'phase':phase,'label_config':self.config,'attempt':attempt+1,'provider':'ollama-local','endpoint':self.endpoint,'api_cost_usd':0,'input_tokens':None,'output_tokens':None,'prompt_version':digest(system),'request':request}
            try:
                req=urllib.request.Request(self.endpoint+'/api/chat',data=canonical(request).encode(),headers={'Content-Type':'application/json'})
                with urllib.request.urlopen(req,timeout=300) as r: response=json.load(r)
                log.update(input_tokens=response.get('prompt_eval_count'),output_tokens=response.get('eval_count'),cached_input_tokens=response.get('prompt_eval_cached_count',0),response=response)
                if response.get('done_reason')!='stop': raise ValueError('Truncated or incomplete output')
                result=json.loads(response['message']['content'])
                if compact:
                    if set(result)!=set(ids) or any(not isinstance(v,list) or len(v)!=5 for v in result.values()): raise ValueError('Invalid compact ID mapping')
                    result={'records':[dict(zip(['review_id','topic','intent','severity','sentiment','needs_review'],[k]+v)) for k,v in result.items()]}
                    log['normalized_response']=result
                if check: check(result)
                log['outcome']='succeeded'
            except BaseException as e:
                log.update(outcome='failed',error=str(e) or type(e).__name__,usage_missing=response is None,interrupted=isinstance(e,(KeyboardInterrupt,SystemExit)))
            log['wall_seconds']=time.monotonic()-start
            with self.db: self.db.execute('INSERT INTO calls VALUES(?,?)',(rid,canonical(log)))
            if log.get('interrupted'):
                raise KeyboardInterrupt
            if log['outcome']=='succeeded':
                if role!='enrich':
                    with self.db: self.db.execute('INSERT OR REPLACE INTO artifacts VALUES(?,?)',(key,canonical(result)))
                return result
            if attempt==0: time.sleep(1)
        raise RuntimeError(log['error'])

def completed(db): return [r[0] for r in db.execute("SELECT review_id FROM records WHERE json_extract(payload,'$.status')='completed' ORDER BY review_id")]
def enrich(db,model,args):
    # One sequential writer: validated batch commits are atomic. No concurrent reservations needed at $0 API spend.
    source=list(db.execute('SELECT * FROM reviews ORDER BY rowid'))
    queue=[]; processed=0; hits=0; start=time.monotonic(); completed_count=len(completed(db))
    def flush():
        nonlocal processed, completed_count
        if not queue: return
        group=list(queue); queue.clear()
        data=[{'review_id':r['review_id'],'review_text':r['text']} for r in group]
        try:
            result=model.call('enrich',data,[r['review_id'] for r in group],args.phase,SCHEMA,lambda x:validate(x,group))
            preds={r['review_id']:r for r in result['records']}
            with db:
                for row in group:
                    r={**preds[row['review_id']],'source_sha256':row['source_sha256'],'status':'completed','entities':[],'evidence_quote':row['text'],'label_config':model.config}
                    db.execute('INSERT OR REPLACE INTO records VALUES(?,?,?)',(row['review_id'],model.config,canonical(r)))
                    db.execute('INSERT OR IGNORE INTO cache VALUES(?,?,?)',(digest([row['text'],model.config]),row['review_id'],canonical(r)))
            completed_count+=len(group)
        except RuntimeError as e:
            with db:
                for row in group:
                    r={'review_id':row['review_id'],'source_sha256':row['source_sha256'],'status':'quarantined','reason':'model_failed: '+str(e),'attempts':2,'label_config':model.config}
                    db.execute('INSERT OR REPLACE INTO records VALUES(?,?,?)',(row['review_id'],model.config,canonical(r)))
        processed+=len(group)
        print(json.dumps({'newly_attempted':processed,'completed':completed_count,'seconds':round(time.monotonic()-start,1)}),flush=True)
    for row in source:
        if args.max_new and processed+len(queue)>=args.max_new: break
        if args.seconds and time.monotonic()-start>=args.seconds: break
        old=db.execute('SELECT config,payload FROM records WHERE review_id=?',(row['review_id'],)).fetchone()
        if old and old[0]==model.config: continue
        if not row['text'].strip():
            r={'review_id':row['review_id'],'source_sha256':row['source_sha256'],'status':'quarantined','reason':'empty_review_text'}
            with db: db.execute('INSERT OR REPLACE INTO records VALUES(?,?,?)',(row['review_id'],model.config,canonical(r)))
            continue
        key=digest([row['text'],model.config]); cached=db.execute('SELECT source_id,payload FROM cache WHERE cache_key=?',(key,)).fetchone()
        if cached:
            r=json.loads(cached[1]); r.update(review_id=row['review_id'],source_sha256=row['source_sha256'],cache_source_id=cached[0])
            with db: db.execute('INSERT OR REPLACE INTO records VALUES(?,?,?)',(row['review_id'],model.config,canonical(r)))
            hits+=1; completed_count+=1; continue
        if any(q['text']==row['text'] for q in queue):
            flush()
            cached=db.execute('SELECT source_id,payload FROM cache WHERE cache_key=?',(key,)).fetchone()
            if cached:
                r=json.loads(cached[1]); r.update(review_id=row['review_id'],source_sha256=row['source_sha256'],cache_source_id=cached[0])
                with db: db.execute('INSERT OR REPLACE INTO records VALUES(?,?,?)',(row['review_id'],model.config,canonical(r)))
                hits+=1; completed_count+=1; continue
        # Bound review requests also by source size, not just record count.
        if queue and sum(len(q['text']) for q in queue)+len(row['text'])>10000: flush()
        queue.append(row)
        if len(queue)>=args.batch: flush()
    flush()
    return {'newly_attempted':processed,'exact_text_cache_hits':hits}

def enrich_parallel(db,model,args):
    """Bounded concurrent model work; main thread alone commits records/cache."""
    start=time.monotonic(); processed=0;hits=0;groups={}
    for row in db.execute('SELECT * FROM reviews ORDER BY rowid'):
        old=db.execute('SELECT config FROM records WHERE review_id=?',(row['review_id'],)).fetchone()
        if old and old[0]==model.config: continue
        if not row['text'].strip():
            r={'review_id':row['review_id'],'source_sha256':row['source_sha256'],'status':'quarantined','reason':'empty_review_text'}
            with db:db.execute('INSERT OR REPLACE INTO records VALUES(?,?,?)',(row['review_id'],model.config,canonical(r)))
            continue
        groups.setdefault(row['text'],[]).append(dict(row))
    pending=[]
    for text,rows in groups.items():
        hit=db.execute('SELECT source_id,payload FROM cache WHERE cache_key=?',(digest([text,model.config]),)).fetchone()
        if hit:
            with db:
                for row in rows:
                    r=json.loads(hit[1]);r.update(review_id=row['review_id'],source_sha256=row['source_sha256'],cache_source_id=hit[0]);db.execute('INSERT OR REPLACE INTO records VALUES(?,?,?)',(row['review_id'],model.config,canonical(r)));hits+=1
        else:pending.append(rows)
    if args.max_new:pending=pending[:args.max_new]
    batches=[];batch=[];chars=0
    for rows in pending:
        if batch and (len(batch)>=args.batch or chars+len(rows[0]['text'])>10000):batches.append(batch);batch=[];chars=0
        batch.append(rows);chars+=len(rows[0]['text'])
    if batch:batches.append(batch)
    thread=threading.local()
    def work(batch):
        if not hasattr(thread,'model'):
            # Avoid concurrent model.json writes. All worker configs are the exact parent config.
            m=object.__new__(LocalModel);m.__dict__.update(model.__dict__);m.db=connect(args.out/'state.sqlite');thread.model=m
        rows=[rs[0] for rs in batch];data=[{'review_id':r['review_id'],'review_text':r['text']} for r in rows]
        try:return batch,thread.model.call('enrich',data,[r['review_id'] for r in rows],args.phase,SCHEMA,lambda x:validate(x,rows)),None
        except RuntimeError as e:return batch,None,str(e)
    pool=ThreadPoolExecutor(max_workers=args.workers);active=set();iterator=iter(batches);failed=0
    try:
        def dispatch():
            if time.monotonic()-start>=args.seconds:return False
            try:b=next(iterator)
            except StopIteration:return False
            active.add(pool.submit(work,b));return True
        for _ in range(args.workers):dispatch()
        while active:
            finished,active=wait(active,return_when=FIRST_COMPLETED)
            for future in finished:
                batch,result,error=future.result();preds={r['review_id']:r for r in result['records']} if result else {}
                with db:
                    for aliases in batch:
                        origin=aliases[0]
                        for row in aliases:
                            if error:r={'review_id':row['review_id'],'source_sha256':row['source_sha256'],'status':'quarantined','reason':'model_failed: '+error,'attempts':2,'label_config':model.config};failed+=1
                            else:
                                r={**preds[origin['review_id']],'review_id':row['review_id'],'source_sha256':row['source_sha256'],'status':'completed','entities':[],'evidence_quote':row['text'],'label_config':model.config}
                                if row['review_id']!=origin['review_id']:r['cache_source_id']=origin['review_id'];hits+=1
                                else:db.execute('INSERT OR IGNORE INTO cache VALUES(?,?,?)',(digest([row['text'],model.config]),origin['review_id'],canonical(r)))
                            db.execute('INSERT OR REPLACE INTO records VALUES(?,?,?)',(row['review_id'],model.config,canonical(r)))
                processed+=len(batch)
                n=db.execute("SELECT count(*) FROM records WHERE json_extract(payload,'$.status')='completed'").fetchone()[0]
                print(json.dumps({'newly_attempted':processed,'completed':n,'failed':failed,'workers':args.workers,'seconds':round(time.monotonic()-start,1)}),flush=True)
                if failed<max(5,processed*.02):dispatch()
    finally:pool.shutdown(wait=True,cancel_futures=True)
    return {'newly_attempted':processed,'exact_text_cache_hits':hits,'workers':args.workers,'failed':failed}

def rank(db,out):
    rows=[json.loads(r[0]) for r in db.execute('SELECT payload FROM records')]
    members=[]; groups={}
    for r in rows:
        if r['status']=='completed' and r['intent'] in ('complaint','cancellation'):
            issue='ISSUE-'+r['topic']; members.append({'issue_id':issue,'review_id':r['review_id']}); groups.setdefault(issue,[]).append(r)
    ranking=[]
    for issue,rs in groups.items():
        total=sum(r['severity'] for r in rs); n=len(rs)
        ranking.append({'issue_id':issue,'complaint_count':n,'severity_sum':total,'mean_severity':str((Decimal(total)/n).quantize(Decimal('.000001'),rounding=ROUND_HALF_UP)),'priority_score':total})
    ranking.sort(key=lambda r:(-r['priority_score'],r['issue_id']))
    for i,r in enumerate(ranking,1): r['rank']=i
    out.mkdir(parents=True,exist_ok=True)
    table(out/'membership.csv',sorted(members,key=lambda r:(r['issue_id'],r['review_id'])),['issue_id','review_id'])
    table(out/'ranking.csv',ranking,['rank','issue_id','complaint_count','severity_sum','mean_severity','priority_score'])
    claims=[{'claim_id':f"{r['issue_id']}-{m}",'issue_id':r['issue_id'],'metric':m,'value':r[m]} for r in ranking for m in ('complaint_count','severity_sum','mean_severity','priority_score')]
    table(out/'claims.csv',claims,['claim_id','issue_id','metric','value'])
    result={'ranking':ranking,'claims':claims,'evidence':{i:[{'review_id':r['review_id'],'quote':r['evidence_quote'],'severity':r['severity']} for r in sorted(rs,key=lambda r:(-r['severity'],r['review_id']))[:3]] for i,rs in groups.items()},'coverage':{'source':db.execute('SELECT count(*) FROM reviews').fetchone()[0],'completed':sum(r['status']=='completed' for r in rows),'quarantined':sum(r['status']=='quarantined' for r in rows)}}
    with db: db.execute('INSERT OR REPLACE INTO artifacts VALUES(?,?)',('analysis',canonical(result)))
    return result

def downstream(db,model,args):
    rs=[json.loads(r[0]) for r in db.execute("SELECT payload FROM records WHERE json_extract(payload,'$.status')='completed'")]
    chosen=random.Random(20261018).sample(sorted(rs,key=lambda r:r['review_id']),min(args.verify,len(rs)))
    original=[{'review_id':r['review_id'],'review_text':db.execute('SELECT text FROM reviews WHERE review_id=?',(r['review_id'],)).fetchone()[0]} for r in chosen]
    comparisons=[]
    verify_batch=min(args.batch,5)
    for i in range(0,len(original),verify_batch):
        batch=original[i:i+verify_batch]; verified=model.call('verify',batch,[r['review_id'] for r in batch],schema=SCHEMA,check=lambda x:validate(x,batch))
        for v in verified['records']:
            first=next(r for r in chosen if r['review_id']==v['review_id'])
            comparisons.append({'review_id':v['review_id'],'first':first,'independent':v,'disagreements':[k for k in ('topic','intent','severity') if v[k]!=first[k]]})
    save(args.out/'verification.json',{'seed':20261018,'sample_size':len(chosen),'method':'random sample; verifier sees original text and rubric only; separate prompt','enrichment_model':model.model,'verification_model':getattr(model,'delegate',model).model,'comparisons':comparisons})
    analysis=rank(db,args.out/'grading')
    if not analysis['ranking']: return
    group_input={'issues':[{'issue_id':r['issue_id'],'examples':analysis['evidence'][r['issue_id']]} for r in analysis['ranking']]}
    def check_group(result):
        entries=result['issues']
        if len(entries)!=len(analysis['ranking']) or {r['issue_id'] for r in entries}!={r['issue_id'] for r in analysis['ranking']}: raise ValueError('Group IDs changed')
        if not all(isinstance(r.get('name'),str) and isinstance(r.get('description'),str) for r in entries): raise ValueError('Missing issue names')
    groups={'issues':[]}
    for issue in group_input['issues']:
        item_schema={'type':'object','properties':{'issue_id':{'type':'string','enum':[issue['issue_id']]},'name':{'type':'string'},'description':{'type':'string'}},'required':['issue_id','name','description'],'additionalProperties':False}
        group_schema={'type':'object','properties':{'issues':{'type':'array','items':item_schema,'minItems':1,'maxItems':1}},'required':['issues'],'additionalProperties':False}
        def check_one(result):
            if len(result.get('issues',[]))!=1 or result['issues'][0].get('issue_id')!=issue['issue_id']:raise ValueError('Group ID changed')
            if not all(isinstance(result['issues'][0].get(k),str) and result['issues'][0][k].strip() for k in ('name','description')):raise ValueError('Missing group description')
        answer=model.call('group',{'issues':[issue]},[],schema=group_schema,check=check_one)
        groups['issues'].extend(answer['issues'])
    check_group(groups);save(args.out/'issues.json',groups)
    issue_ids=[r['issue_id'] for r in analysis['ranking']]
    memo_schema={'type':'object','properties':{'priority_issue':{'type':'string','enum':issue_ids},'alternative_issue':{'type':'string','enum':issue_ids},'reason':{'type':'string','enum':['combined_frequency_and_severity','higher_severity','higher_frequency']}},'required':['priority_issue','alternative_issue','reason'],'additionalProperties':False}
    def check_memo(result):
        if set(result)!=set(memo_schema['required']): raise ValueError('Missing recommendation selection')
        for k in ('priority_issue','alternative_issue'):
            if result[k] not in issue_ids: raise ValueError('Unknown issue')
        if len(issue_ids)>1 and result['priority_issue']==result['alternative_issue']: raise ValueError('Alternative must differ')
        if result['reason'] not in memo_schema['properties']['reason']['enum']: raise ValueError('Unsupported reason')
    selection=model.call('memo',{'ranking':analysis['ranking'],'evidence':analysis['evidence'],'coverage':analysis['coverage']},[],schema=memo_schema,check=check_memo)
    priority=selection['priority_issue']; alternative=selection['alternative_issue']
    action={'playback':'Fix playback interruptions and failures','usability':'Reduce disruptive ads and simplify playback controls','billing':'Clarify paid feature access and resolve subscription problems','access':'Fix login and account access failures','downloads':'Restore reliable offline listening','catalog':'Improve content, search and discovery','support':'Improve support resolution','other':'Investigate the general dissatisfaction before choosing a specific fix'}
    p_rank=next(r for r in analysis['ranking'] if r['issue_id']==priority);a_rank=next(r for r in analysis['ranking'] if r['issue_id']==alternative)
    metric={'combined_frequency_and_severity':'priority_score','higher_severity':'mean_severity','higher_frequency':'complaint_count'}[selection['reason']]
    reason_supported=Decimal(str(p_rank[metric]))>Decimal(str(a_rank[metric]))
    reasoning=(' based on '+selection['reason'].replace('_',' ')) if reason_supported else ' as a candidate for further investigation'
    memo={'recommendation':action[priority.removeprefix('ISSUE-')]+'. Prioritize '+priority+reasoning+'.','alternatives':'Compare this with '+alternative+' before allocating the next quarter of product effort.','limitations':f"Scope: {analysis['coverage']['completed']:,} completed records from {analysis['coverage']['source']:,} loaded source records. Historical, self-selected reviews with coarse topic-level groups do not measure revenue, confirmed churn or causal retention effects. Human-reviewed label evaluation is not complete.",'citations':[{'issue_id':i,'claim_id':i+'-priority_score','review_id':analysis['evidence'][i][0]['review_id']} for i in dict.fromkeys([priority,alternative])],'model_selection':selection,'comparative_reason_supported':reason_supported,'rendering':'Model selects priorities from saved metrics; code renders wording, numbers and exact evidence references.'}
    save(args.out/'memo.json',memo)
    with db: db.execute('INSERT OR REPLACE INTO artifacts VALUES(?,?)',('recommendation',canonical(memo)))
    lines=['# Spotify product priority — measured run','',f"Scope: {analysis['coverage']}",'',memo['recommendation'],'',memo['alternatives'],'',memo['limitations'],'','## Saved evidence']
    for c in memo['citations']:
        claim=next(x for x in analysis['claims'] if x['claim_id']==c['claim_id'])
        lines.append(f"- {c['claim_id']}: {claim['value']}; issue {c['issue_id']}; review {c['review_id']}")
    (args.out/'memo.md').write_text('\n'.join(lines)+'\n')

def export(db,args):
    folder=args.out/'grading'; folder.mkdir(exist_ok=True)
    with (folder/'records.jsonl').open('w') as f:
        for row in db.execute('SELECT r.review_id,r.source_sha256,p.payload FROM reviews r LEFT JOIN records p ON p.review_id=r.review_id ORDER BY r.review_id'):
            payload=row['payload'] or canonical({'review_id':row['review_id'],'source_sha256':row['source_sha256'],'status':'quarantined','reason':'not_processed_within_current_run_limit','attempts':0})
            f.write(payload+'\n')
    with (folder/'calls.jsonl').open('w') as f:
        for r in db.execute('SELECT payload FROM calls ORDER BY rowid'):f.write(r[0]+'\n')
    save(folder/'run.json',{'version':'a5-audit-v1','analysis_count':db.execute('SELECT count(*) FROM reviews').fetchone()[0],'analysis_sha256':sha(args.input),'classification_input_fields':['review_text'],'allow_multi_issue':False})
    save(folder/'ingestion.json',profile(args.full or args.input))

def main():
    p=argparse.ArgumentParser(); sub=p.add_subparsers(dest='cmd',required=True)
    q=sub.add_parser('ingest'); q.add_argument('--input',type=Path,required=True); q.add_argument('--db',type=Path,required=True)
    q=sub.add_parser('rank'); q.add_argument('--db',type=Path,required=True); q.add_argument('--out',type=Path,required=True)
    q=sub.add_parser('run'); q.add_argument('--input',type=Path,required=True); q.add_argument('--full',type=Path); q.add_argument('--out',type=Path,required=True); q.add_argument('--model',default='gemma4:e2b'); q.add_argument('--batch',type=int,default=5); q.add_argument('--verify',type=int,default=10); q.add_argument('--max-new',type=int,default=0); q.add_argument('--seconds',type=int,default=1800); q.add_argument('--output-cap',type=int,default=2048); q.add_argument('--phase',choices=['initial','resume'],default='initial'); q.add_argument('--enrich-only',action='store_true'); q.add_argument('--compact',action='store_true'); q.add_argument('--workers',type=int,choices=[1,2,4],default=1); q.add_argument('--classifier',choices=['generative','nli'],default='generative')
    args=p.parse_args()
    if args.cmd=='ingest': print({'ingested':ingest(connect(args.db),args.input)}); return
    if args.cmd=='rank': print(rank(connect(args.db),args.out)['coverage']); return
    if not 1<=args.batch<=50: p.error('batch must be 1..50')
    if args.max_new<0 or args.verify<0 or args.seconds<=0 or args.output_cap<=0: p.error('invalid resource limit')
    run_started=time.monotonic()
    args.out.mkdir(parents=True,exist_ok=True); db=connect(args.out/'state.sqlite'); ingest(db,args.input)
    if args.classifier=='nli':
        if args.workers!=1: p.error('NLI uses one GPU worker with internal bounded batching')
        from nli_classifier import NLIModel
        model=NLIModel(db,args.out,args.model,args.output_cap)
    else: model=LocalModel(db,args.out,args.model,args.output_cap,args.compact)
    stale=db.execute('SELECT count(*) FROM records WHERE config!=?',(model.config,)).fetchone()[0]
    if stale: p.error('configuration changed: use a fresh output directory for clean provenance')
    before_calls=db.execute('SELECT count(*) FROM calls').fetchone()[0]; start=run_started; summary={}
    save(args.out/f'checkpoint_{args.phase}_before.json',{'completed_ids':completed(db)})
    try:
        summary=enrich_parallel(db,model,args) if args.workers>1 else enrich(db,model,args)
        if not args.enrich_only: downstream(db,model,args)
    finally:
        export(db,args)
        save(args.out/f'checkpoint_{args.phase}_after.json',{'completed_ids':completed(db)})
        summary.update(wall_seconds=time.monotonic()-start,completed=len(completed(db)),source=db.execute('SELECT count(*) FROM reviews').fetchone()[0],new_calls=db.execute('SELECT count(*) FROM calls').fetchone()[0]-before_calls,workers=args.workers,batch_size=args.batch,output_cap=args.output_cap,verification_sample=args.verify,api_cost_usd=0,local_compute_cost_usd=None,label_config=model.config,phase=args.phase)
        save(args.out/('run-'+str(time.time_ns())+'.json'),summary)
        print(json.dumps(summary),flush=True)
if __name__=='__main__': main()
