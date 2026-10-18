"""Offline per-field comparison; requires an explicit reference-kind declaration."""
import argparse,csv,json,collections
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--labels',type=Path,required=True);p.add_argument('--predictions',type=Path,required=True);p.add_argument('--reference-kind',choices=['provisional','human-reviewed'],required=True);p.add_argument('--out',type=Path,required=True);a=p.parse_args()
labels=list(csv.DictReader(a.labels.open(encoding='utf-8-sig')));preds={r['review_id']:r for r in map(json.loads,a.predictions.read_text().splitlines())};cases=[];confusion=collections.Counter();totals=collections.Counter();severity_error=0;sentiment_error=0
for row in labels:
 if not row['topic'] or not row['intent'] or not row['severity']:raise SystemExit('Reference labels are incomplete')
 if a.reference_kind=='human-reviewed' and row.get('human_reviewed','').lower()!='true':raise SystemExit('Human-reviewed reference requires recorded confirmation on every row')
 r=preds.get(row['review_id'],{});valid=r.get('status')=='completed';result={'review_id':row['review_id'],'valid_prediction':valid,'reference':row,'prediction':r}
 for k in ('topic','intent','severity'):
  correct=valid and str(r[k])==row[k];result[k+'_match']=correct;totals[k]+=correct
 confusion[(row['topic'],r.get('topic','<missing>'))]+=1
 if valid:
  totals['valid']+=1;severity_error+=abs(int(row['severity'])-r['severity']);sentiment_error+=abs(float(row['sentiment'])-r['sentiment']);result['quote_exact']=bool(r['evidence_quote']) and r['evidence_quote'] in row['review_text'];totals['quote_exact']+=result['quote_exact'];result['needs_review_match']=str(r['needs_review']).lower()==row['needs_review'].lower();totals['needs_review']+=result['needs_review_match']
 cases.append(result)
n=len(labels);v=totals['valid'];report={'reference_kind':a.reference_kind,'human_label_requirement_complete':a.reference_kind=='human-reviewed','n':n,'valid_predictions':v,'missing_or_invalid':n-v,'agreement':{k:totals[k]/n for k in ('topic','intent','severity','needs_review')},'severity_mae_valid_only':severity_error/v if v else None,'sentiment_mae_valid_only':sentiment_error/v if v else None,'quote_exact_fraction':totals['quote_exact']/n,'topic_confusion':[{'expected':k[0],'predicted':k[1],'count':c} for k,c in sorted(confusion.items())],'ambiguous_reference_count':sum(r.get('needs_review','').lower()=='true' for r in labels),'cases':cases,'limitations':['Small diagnostic sample, not population accuracy.','Provisional references do not satisfy the human-label requirement.','Entities and whether quotes substantively support labels need inspection.']}
a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n');print(json.dumps({k:v for k,v in report.items() if k!='cases'},indent=2))
