#!/usr/bin/env python3
"""Read-only Yahoo identifier discovery: legacy symbol is a hypothesis, never a certified mapping."""
import argparse,csv,json,re,time
from datetime import datetime,timezone
from pathlib import Path
import psycopg,yfinance as yf
DSN='host=/var/run/postgresql port=5433 dbname=market_data_hub user=benoit'
SYMBOL=re.compile(r'^[A-Za-z0-9.^=_-]{1,80}$')
def main():
 p=argparse.ArgumentParser()
 p.add_argument('--output',required=True,type=Path)
 p.add_argument('--limit',type=int,default=40)
 p.add_argument('--pause',type=float,default=2)
 a=p.parse_args()
 if not 1<=a.limit<=840 or not 0.5<=a.pause<=30: p.error('limit 1..840, pause 0.5..30')
 a.output.mkdir(parents=True,exist_ok=True)
 with psycopg.connect(DSN,options='-c default_transaction_read_only=on') as con:
  with con.cursor() as cur:
   cur.execute("SELECT current_database(),current_user,current_setting('port')")
   if cur.fetchone()!=('market_data_hub','benoit','5433'):raise RuntimeError('wrong DB')
   cur.execute("""SELECT i.id::text,i.name,l.symbol,l.currency,l.mic,l.mic_verified
    FROM public.instruments i LEFT JOIN public.legacy_symbol_map l ON l.instrument_id=i.id
    WHERE NOT EXISTS(SELECT 1 FROM public.instrument_identifiers x
      WHERE x.instrument_id=i.id AND lower(x.provider)='yahoo' AND x.valid_to IS NULL)
    ORDER BY i.id,l.symbol""")
   rows=cur.fetchall()
 unique={}
 for row in rows:
  unique.setdefault(row[0],row)
 selected=list(unique.values())[:a.limit]
 results=[]
 for ident,name,symbol,currency,mic,mic_verified in selected:
  record={'instrument_id':ident,'name':name,'legacy_symbol':symbol,'legacy_currency':currency,
          'legacy_mic':mic,'mic_verified':mic_verified,'candidate_symbol':None,
          'yahoo_currency':None,'yahoo_exchange':None,'recent_sessions':0,
          'status':'UNRESOLVED','reason':''}
  if not symbol or not SYMBOL.fullmatch(symbol):
   record['reason']='missing_or_invalid_legacy_symbol'
  else:
   try:
    ticker=yf.Ticker(symbol)
    hist=ticker.history(period='1mo',auto_adjust=False,actions=False)
    meta=ticker.get_history_metadata() or {}
    observed_currency=str(meta.get('currency') or '').upper()
    observed_exchange=str(meta.get('exchangeName') or meta.get('exchange') or '')
    record.update(candidate_symbol=symbol,yahoo_currency=observed_currency,
                  yahoo_exchange=observed_exchange,recent_sessions=len(hist))
    if hist is None or hist.empty:record['reason']='no_recent_prices'
    elif not observed_currency:record['reason']='currency_unavailable'
    elif not currency:record['reason']='legacy_currency_unavailable'
    elif observed_currency!=str(currency).upper():
     record['reason']='currency_mismatch'
    else:
     record['status']='CANDIDATE_REVIEW'
     record['reason']='currency_and_recent_prices_match;exchange_and_identity_unverified'
   except Exception as exc:record['reason']='provider_error:'+str(exc)[:150]
  results.append(record)
  time.sleep(a.pause)
 with (a.output/'mapping-candidates.csv').open('w',newline='',encoding='utf-8') as f:
  writer=csv.DictWriter(f,fieldnames=list(results[0]) if results else [])
  writer.writeheader();writer.writerows(results)
 summary={'timestamp_utc':datetime.now(timezone.utc).isoformat(),'unmapped_total':len(unique),
          'probed':len(results),'candidate_review':sum(r['status']=='CANDIDATE_REVIEW' for r in results),
          'unresolved':sum(r['status']=='UNRESOLVED' for r in results),
          'auto_mapped':0,'production_writes':False,'pit_verified':False,'paper_eligible':False,
          'next_offset_supported':False,
          'note':'Candidates require instrument identity and MIC verification; no auto-promotion'}
 (a.output/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
 print(json.dumps(summary,indent=2))
if __name__=='__main__':main()
