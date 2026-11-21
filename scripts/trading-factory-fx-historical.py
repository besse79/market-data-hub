#!/usr/bin/env python3
"""Research-only historical FX and unmapped symbol evidence; no DB writes."""
import argparse,csv,json,time
from datetime import datetime,timezone
from decimal import Decimal
from pathlib import Path
import psycopg,yfinance as yf
DSN="host=/var/run/postgresql port=5433 dbname=market_data_hub user=benoit"
PAIRS={"CHF":"EURCHF=X","DKK":"EURDKK=X","GBP":"EURGBP=X","NOK":"EURNOK=X","PLN":"EURPLN=X","SEK":"EURSEK=X"}
def main():
 p=argparse.ArgumentParser()
 p.add_argument("--output",type=Path,required=True)
 p.add_argument("--start",required=True)
 p.add_argument("--end",required=True)
 a=p.parse_args()
 a.output.mkdir(parents=True,exist_ok=True)
 with psycopg.connect(DSN,options="-c default_transaction_read_only=on") as con:
  with con.cursor() as cur:
   cur.execute("SELECT current_database(),current_user,current_setting('port')")
   assert cur.fetchone()==('market_data_hub','benoit','5433')
   cur.execute("""SELECT i.id::text,i.name,i.asset_type,i.status,l.symbol,l.currency,l.mic,l.mic_verified
     FROM public.instruments i LEFT JOIN public.legacy_symbol_map l ON l.instrument_id=i.id
     WHERE NOT EXISTS (SELECT 1 FROM public.instrument_identifiers ii
       WHERE ii.instrument_id=i.id AND lower(ii.provider)='yahoo' AND ii.valid_to IS NULL)
     ORDER BY i.name,i.id,l.symbol""")
   missing=cur.fetchall()
 with (a.output/'unmapped-legacy-evidence.csv').open('w',newline='',encoding='utf-8') as f:
  w=csv.writer(f);w.writerow(['instrument_id','name','asset_type','status','legacy_symbol','legacy_currency','legacy_mic','mic_verified'])
  w.writerows(missing)
 summary={'start':a.start,'end_exclusive':a.end,'unmapped_legacy_rows':len(missing),'fx_pairs':{},'errors':{},
          'production_writes':False,'pit_verified':False,'paper_eligible':False}
 for quote,symbol in PAIRS.items():
  try:
   df=yf.download(symbol,start=a.start,end=a.end,auto_adjust=False,actions=False,progress=False,threads=False)
   if df is None or df.empty:raise RuntimeError('empty Yahoo FX history')
   if getattr(df.columns,'nlevels',1)>1:
    if symbol in df.columns.get_level_values(-1):df=df.xs(symbol,axis=1,level=-1)
    elif symbol in df.columns.get_level_values(0):df=df.xs(symbol,axis=1,level=0)
    else:raise RuntimeError('ambiguous columns')
   if 'Close' not in df.columns:raise RuntimeError('missing Close')
   obs=[]
   retrieved=datetime.now(timezone.utc).isoformat()
   for index,row in df.iterrows():
    day=index.date().isoformat()
    if not a.start<=day<a.end:continue
    rate=Decimal(str(row['Close']))
    if not rate.is_finite() or rate<=0:raise RuntimeError('invalid FX close')
    obs.append({'session_date':day,'quote_per_eur':str(rate),'retrieved_at':retrieved,
                'quality_status':'staged_unverified','published_at':None,'first_available_at':None,
                'point_in_time_verified':False,'paper_eligible':False})
   dates=[x['session_date'] for x in obs]
   if len(obs)<250 or len(dates)!=len(set(dates)):raise RuntimeError('short or duplicate FX history')
   doc={'schema_version':1,'provider':'yahoo','pair':symbol,'base':'EUR','quote':quote,
        'quote_units_per_eur':True,'request_start':a.start,'request_end_exclusive':a.end,
        'observations':obs,'pit_verified':False,'paper_eligible':False}
   filename=a.output/(symbol.replace('=','_')+'.json')
   filename.write_text(json.dumps(doc,indent=2)+'\n')
   summary['fx_pairs'][symbol]={'observations':len(obs),'first':dates[0],'last':dates[-1],'file':str(filename)}
  except Exception as exc:summary['errors'][symbol]=str(exc)[:300]
  time.sleep(2)
 (a.output/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
 print(json.dumps(summary,indent=2))
 if summary['errors'] or len(summary['fx_pairs'])!=6:raise SystemExit('NO_GO: incomplete FX research history')
 print('PASS: six FX research histories captured. NO production import; PIT/PAPER remain disabled.')
if __name__=='__main__':main()
