#!/usr/bin/env python3
"""Independent metadata enrichment of Yahoo candidates, research only; no certification."""
import argparse,csv,json,re,time,unicodedata,collections
from pathlib import Path
from datetime import datetime,timezone
import yfinance as yf
def normalized(s):
 s=unicodedata.normalize('NFKD',str(s or '')).encode('ascii','ignore').decode().upper()
 return set(re.findall(r'[A-Z0-9]{3,}',s))-{'INC','CORP','LTD','PLC','SA','SAS','THE','GROUP','HOLDINGS','COMPANY'}
def main():
 p=argparse.ArgumentParser()
 p.add_argument('--input',type=Path,required=True)
 p.add_argument('--output',type=Path,required=True)
 p.add_argument('--limit',type=int,default=50)
 p.add_argument('--offset',type=int,default=0)
 p.add_argument('--pause',type=float,default=1.5)
 a=p.parse_args()
 if a.limit<1 or a.offset<0 or a.pause<0.5:p.error('invalid limits')
 with a.input.open(newline='',encoding='utf-8') as f:rows=list(csv.DictReader(f))
 if not rows or not {'instrument_id','name','candidate_symbol','yahoo_currency','yahoo_exchange'}.issubset(rows[0]):raise SystemExit('BLOCKED invalid candidate CSV')
 selected=rows[a.offset:a.offset+a.limit]
 if not selected:raise SystemExit('BLOCKED empty batch')
 a.output.mkdir(parents=True,exist_ok=True)
 out=[]
 for r in selected:
  item={'instrument_id':r['instrument_id'],'legacy_name':r['name'],'symbol':r['candidate_symbol'],
        'legacy_currency':r.get('legacy_currency',''),'observed_currency':r.get('yahoo_currency',''),
        'history_exchange':r.get('yahoo_exchange',''),'provider_name':'','provider_exchange':'',
        'provider_quote_type':'','provider_isin':'','name_token_overlap':'','status':'UNRESOLVED','reason':''}
  try:
   t=yf.Ticker(r['candidate_symbol'])
   info=t.get_info() or {}
   name=info.get('longName') or info.get('shortName') or ''
   item['provider_name']=name
   item['provider_exchange']=str(info.get('exchange') or info.get('fullExchangeName') or '')
   item['provider_quote_type']=str(info.get('quoteType') or '')
   # get_isin is optional/unreliable and does not independently certify identity.
   try:item['provider_isin']=str(t.get_isin() or '')
   except Exception:pass
   tokens1=normalized(r['name']);tokens2=normalized(name)
   overlap= len(tokens1 & tokens2)/len(tokens1) if tokens1 else 0
   item['name_token_overlap']=round(overlap,3)
   issues=[]
   if not name:issues.append('NO_PROVIDER_NAME')
   if not item['provider_exchange']:issues.append('NO_PROVIDER_EXCHANGE')
   if item['provider_quote_type'] not in ('EQUITY','ETF'):issues.append('QUOTE_TYPE_REVIEW')
   if overlap<0.5:issues.append('NAME_MISMATCH_OR_AMBIGUOUS')
   if not item['provider_isin'] or item['provider_isin'].upper() in ('-','N/A'):
    item['provider_isin']=''
   if not issues:item['status']='PROVIDER_CONSISTENT_REVIEW'
   item['reason']=';'.join(issues) or ('PROVIDER_ISIN_AVAILABLE;INDEPENDENT_ISIN_MIC_CONFIRMATION_REQUIRED' if item['provider_isin'] else 'PROVIDER_ISIN_UNAVAILABLE;INDEPENDENT_ISIN_MIC_CONFIRMATION_REQUIRED')
  except Exception as e:item['reason']='PROVIDER_ERROR:'+str(e)[:180]
  out.append(item);time.sleep(a.pause)
 with (a.output/'identity-evidence.csv').open('w',newline='',encoding='utf-8') as f:
  w=csv.DictWriter(f,fieldnames=list(out[0]));w.writeheader();w.writerows(out)
 summary={'timestamp_utc':datetime.now(timezone.utc).isoformat(),'input_count':len(rows),'offset':a.offset,
          'probed':len(out),'provider_consistent_review':sum(x['status']=='PROVIDER_CONSISTENT_REVIEW' for x in out),
          'unresolved':sum(x['status']!='PROVIDER_CONSISTENT_REVIEW' for x in out),
          'provider_isin_available':sum(bool(x['provider_isin']) for x in out),
          'certified':0,'database_writes':False,'pit_eligible':False,'paper_eligible':False,
          'note':'Yahoo quote metadata and Yahoo ISIN are not independent identity/MIC evidence'}
 (a.output/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
 print(json.dumps(summary,indent=2))
 print('EVIDENCE='+str(a.output/'identity-evidence.csv'))
if __name__=='__main__':main()
