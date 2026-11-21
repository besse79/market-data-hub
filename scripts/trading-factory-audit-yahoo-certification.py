#!/usr/bin/env python3
"""Fail-closed audit of Yahoo candidate evidence. No DB connection or writes."""
import argparse,csv,json,collections,datetime,re
from pathlib import Path
def norm(x):return re.sub(r'[^A-Z0-9]','',str(x or '').upper())
def main():
 p=argparse.ArgumentParser()
 p.add_argument('--input',type=Path,required=True)
 p.add_argument('--output',type=Path,required=True)
 a=p.parse_args()
 if not a.input.is_file():p.error('missing CSV')
 with a.input.open(newline='',encoding='utf-8') as f:rows=list(csv.DictReader(f))
 required={'instrument_id','name','legacy_symbol','legacy_currency','legacy_mic','mic_verified','candidate_symbol','yahoo_currency','yahoo_exchange','recent_sessions','status'}
 if not rows or not required.issubset(rows[0]):raise SystemExit('BLOCKED: missing expected evidence columns')
 counts=collections.Counter(r['instrument_id'] for r in rows)
 tickers=collections.defaultdict(set)
 for r in rows:
  if r['candidate_symbol']:tickers[norm(r['candidate_symbol'])].add(r['instrument_id'])
 out=[]
 for r in rows:
  reasons=[]
  if counts[r['instrument_id']]!=1:reasons.append('DUPLICATE_INSTRUMENT_ID')
  if r['status']!='CANDIDATE_REVIEW':reasons.append('PROVIDER_UNRESOLVED')
  if not r['candidate_symbol'] or norm(r['legacy_symbol'])!=norm(r['candidate_symbol']):reasons.append('SYMBOL_MISMATCH')
  if len(tickers[norm(r['candidate_symbol'])])>1:reasons.append('TICKER_COLLISION')
  if not r['legacy_currency'] or r['legacy_currency'].upper()!=r['yahoo_currency'].upper():reasons.append('CURRENCY_MISMATCH')
  if not r['yahoo_exchange']:reasons.append('PROVIDER_EXCHANGE_MISSING')
  if str(r['mic_verified']).strip().lower() not in ('true','t','1','yes'):reasons.append('MIC_NOT_VERIFIED')
  if not r['legacy_mic']:reasons.append('LEGACY_MIC_MISSING')
  if not r['name']:reasons.append('INSTRUMENT_NAME_MISSING')
  if int(r['recent_sessions'] or 0)<5:reasons.append('INSUFFICIENT_RECENT_SESSIONS')
  # Yahoo exchangeName is not an ISO 10383 MIC; never equate these.
  reasons.append('ISSUER_IDENTITY_NOT_INDEPENDENTLY_VERIFIED')
  reasons.append('YAHOO_EXCHANGE_NOT_MIC_CERTIFICATION')
  out.append(dict(r,audit_status='BLOCKED_FOR_CERTIFICATION',blockers=';'.join(sorted(set(reasons)))))
 a.output.mkdir(parents=True,exist_ok=True)
 target=a.output/'mapping-certification-audit.csv'
 with target.open('w',newline='',encoding='utf-8') as f:
  w=csv.DictWriter(f,fieldnames=list(out[0]));w.writeheader();w.writerows(out)
 reason_counts=collections.Counter(reason for r in out for reason in r['blockers'].split(';'))
 summary={'timestamp_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),
 'rows':len(out),'unique_instruments':len(counts),'candidate_review':sum(r['status']=='CANDIDATE_REVIEW' for r in rows),
 'distinct_candidate_symbols':len(tickers),'ticker_collision_groups':sum(len(ids)>1 for ids in tickers.values()),
 'blocked_for_certification':len(out),'certified':0,'production_writes':False,
 'pit_eligible':False,'paper_eligible':False,'blockers':dict(reason_counts),
 'evidence':'legacy symbols and Yahoo prices/currency only; no independent issuer/MIC identity verification'}
 (a.output/'summary.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False)+'\n')
 print(json.dumps(summary,indent=2,ensure_ascii=False))
 print('AUDIT='+str(target))
if __name__=='__main__':main()
