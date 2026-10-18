"""Local discriminative enrichment; original texts are never sent to a hosted API."""
import time,uuid,json,os
from pathlib import Path
from pipeline import canonical,digest,save,validate,LocalModel
MODEL='MoritzLaurer/deberta-v3-xsmall-zeroshot-v1.1-all-33'
HYPOTHESES={
 'topic':{
 'access':'The review is about logging in, signing up, passwords, or gaining access to an account.',
 'usability':'The review is about ads interrupting music, navigation, the interface, playlists, or playback controls.',
 'playback':'The review is about music failing to play, the app crashing, lag, connection failures, or audio quality.',
 'downloads':'The review is about downloading music or listening to saved music offline.',
 'catalog':'The review is about available songs, music search, song recommendations, or lyrics.',
 'billing':'The review is about prices, charges, subscriptions, premium-only features, or paying to unlock controls.',
 'support':'The review is about contacting customer support or receiving help from support.',
 'other':'The review gives a general opinion about the app without identifying any particular feature.'},
 'intent':{
 'cancellation':'The user says they are leaving, uninstalling, cancelling, or threatening to stop using the app.',
 'complaint':'The user reports a negative experience or complains about the app.',
 'request':'The user asks for a new feature or change without reporting a current problem.',
 'praise':'The user expresses a positive opinion or satisfaction with the app.',
 'unclear':'The text is unrelated, meaningless, or has no clear opinion about using the app.'},
 'severity':{
 '1':'There is no reported problem: the text is praise, neutral, unclear, or only a feature request.',
 '2':'The user reports dislike or annoyance but does not report losing any functionality.',
 '3':'A function is restricted or degraded, but the user can still use the app or a workaround.',
 '4':'The user clearly cannot complete a core task such as logging in or playing music at all.',
 '5':'The user explicitly reports serious financial loss, privacy harm, or loss of personal data.'},
 'sentiment':{'negative':'The user expresses a negative opinion.','neutral':'The user expresses a neutral opinion.','positive':'The user expresses a positive opinion.'}}

class NLIModel:
 def __init__(self,db,out,delegate_model='gemma4:e2b',cap=2048):
  import torch
  from transformers import AutoTokenizer,AutoModelForSequenceClassification
  self.torch=torch;self.db=db;self.out=out;self.cap=cap;self.model=MODEL
  self.delegate=LocalModel(db,out,delegate_model,cap)
  self.device='mps' if torch.backends.mps.is_available() else 'cpu';torch.set_num_threads(4)
  cache=os.environ.get('SPOTIFY_MODEL_CACHE',str(out.parent/'model-cache'))
  self.tokenizer=AutoTokenizer.from_pretrained(MODEL,cache_dir=cache,trust_remote_code=False)
  self.network=AutoModelForSequenceClassification.from_pretrained(MODEL,cache_dir=cache,trust_remote_code=False,use_safetensors=True).to(self.device).eval()
  self.revision=(Path(cache)/('models--'+MODEL.replace('/','--'))/'refs/main').read_text().strip()
  labels=self.network.config.label2id
  self.entail=next(v for k,v in labels.items() if k.lower() in ('entailment','entail'))
  self.entries=[(field,label,h) for field,ls in HYPOTHESES.items() for label,h in ls.items()]
  self.config=digest({'model':MODEL,'revision':self.revision,'hypotheses':HYPOTHESES,'chunk_tokens':384,'stride':32,'threshold':.5,'protocol':'nli-v1'})
  self.identity={'model':MODEL,'revision':self.revision,'device':self.device,'label2id':labels,'hypotheses':HYPOTHESES,'config':self.config}
  save(out/'nli_model.json',self.identity)
 def call(self,role,data,ids,phase='initial',schema=None,check=None):
  if role!='enrich':return self.delegate.call(role,data,ids,phase,schema,check)
  if len(ids)>50 or set(ids)!={r['review_id'] for r in data}:raise ValueError('Invalid bounded input IDs')
  start=time.monotonic();rid=str(uuid.uuid4());torch=self.torch;usage=0
  log={'request_id':rid,'role':role,'review_ids':ids,'model':MODEL,'model_revision':self.revision,'phase':phase,'label_config':self.config,'provider':'local-transformers','api_cost_usd':0,'request':data,'hypotheses':HYPOTHESES,'output_tokens':0,'cached_input_tokens':0,'attempt':1}
  try:
   pairs=[];owners=[];chunks_by_row=[]
   for n,row in enumerate(data):
    tokens=self.tokenizer.encode(row['review_text'],add_special_tokens=False);chunks=[tokens[i:i+384] for i in range(0,max(1,len(tokens)),352)];chunks_by_row.append(len(chunks))
    for chunk in chunks:
     text=self.tokenizer.decode(chunk,skip_special_tokens=True)
     for field,label,hyp in self.entries:pairs.append((text,hyp));owners.append((n,field,label))
   scores=[{f:{k:0. for k in labels} for f,labels in HYPOTHESES.items()} for _ in data]
   for i in range(0,len(pairs),32):
    batch=pairs[i:i+32];inputs=self.tokenizer([x[0] for x in batch],[x[1] for x in batch],padding=True,truncation=False,return_tensors='pt');usage+=int(inputs['attention_mask'].sum());inputs={k:v.to(self.device) for k,v in inputs.items()}
    with torch.inference_mode():probs=self.network(**inputs).logits.float().softmax(-1)[:,self.entail].cpu().tolist()
    for j,value in enumerate(probs):
     n,field,label=owners[i+j];scores[n][field][label]=max(scores[n][field][label],value)
   result=[]
   for n,(row,s) in enumerate(zip(data,scores)):
    intent=next((k for k in ('cancellation','complaint','request','praise') if s['intent'][k]>=.5),'unclear')
    topic=max(s['topic'],key=s['topic'].get)
    severity=max((int(k) for k,v in s['severity'].items() if int(k)>=2 and v>=.5),default=2) if intent in ('complaint','cancellation') else 1
    total=sum(s['sentiment'].values());sentiment=(s['sentiment']['positive']-s['sentiment']['negative'])/total if total else 0
    sorted_topics=sorted(s['topic'].values(),reverse=True);uncertain=sorted_topics[0]<.5 or sorted_topics[0]-sorted_topics[1]<.15 or intent=='unclear' or chunks_by_row[n]>1 or not row['review_text'].isascii()
    result.append({'review_id':row['review_id'],'topic':topic,'intent':intent,'severity':severity,'sentiment':round(sentiment,6),'needs_review':uncertain})
   output={'records':result}
   if check:check(output)
   log.update(outcome='succeeded',input_tokens=usage,probabilities=scores,chunk_counts=chunks_by_row,normalized_response=output)
  except BaseException as e:
   log.update(outcome='failed',input_tokens=usage,error=str(e),usage_missing=False);raise
  finally:
   log['wall_seconds']=time.monotonic()-start
   with self.db:self.db.execute('INSERT INTO calls VALUES(?,?)',(rid,canonical(log)))
  return output
