#!/usr/bin/env python3
from __future__ import annotations
import argparse, datetime as dt, gzip, hashlib, json, os, random, time, urllib.parse, urllib.request, zipfile
from pathlib import Path
BASE='https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX'
REF='https://www.twse.com.tw/zh/trading/historical/mi-index.html'
EXPECTED={2004:228,2005:248,2006:249,2007:243,2008:249,2009:248,2010:250,2011:247,2012:247,2013:244,2014:248,2015:244,2016:244,2017:246,2018:247,2019:242,2020:245,2021:244,2022:246,2023:239,2024:242,2025:243,2026:143}
WEEKENDS={'2014-12-27','2016-01-30','2016-06-04','2016-09-10','2017-02-18','2017-06-03','2017-09-30','2018-03-31','2018-12-22'}
START=dt.date(2004,2,11); END=dt.date(2026,8,7)
def sha(b): return hashlib.sha256(b).hexdigest()
def now(): return dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')
def url(d): return BASE+'?'+urllib.parse.urlencode({'date':d.strftime('%Y%m%d'),'type':'ALLBUT0999','response':'json'})
def validate(b,d):
 o=json.loads(b); ymd=d.strftime('%Y%m%d')
 if o.get('stat')!='OK': return None,o.get('stat')
 if str(o.get('date',''))!=ymd: raise ValueError(f'date mismatch {o.get("date")} != {ymd}')
 for t in o.get('tables') or []:
  f=t.get('fields') or []
  if '證券代號' in f and '收盤價' in f:
   rows=t.get('data') or []; w=len(f)
   if not rows or any(len(r)!=w for r in rows): raise ValueError('security table empty/width mismatch')
   return len(rows),'OK'
 raise ValueError('security table missing')
def fetch(d,attempts=4):
 last=None
 for a in range(attempts):
  try:
   req=urllib.request.Request(url(d),headers={'User-Agent':'MarketData-RAW-W01-GHA/3.0','Accept':'application/json,text/plain,*/*','Referer':REF,'Cache-Control':'no-cache'})
   with urllib.request.urlopen(req,timeout=90) as r: b=r.read(); final=r.geturl(); status=getattr(r,'status',200)
   if status!=200: raise RuntimeError(f'HTTP {status}')
   rows,stat=validate(b,d); return b,final,rows,stat
  except Exception as e:
   last=e
   if a+1<attempts: time.sleep(min(8*(2**a),60)+random.random())
 raise RuntimeError(f'{d}: {last}')
def candidates(y):
 a=max(START,dt.date(y,1,1)); z=min(END,dt.date(y,12,31)); out=[]; d=a
 while d<=z:
  if d.weekday()<5 or d.isoformat() in WEEKENDS: out.append(d)
  d+=dt.timedelta(days=1)
 return out
def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--year',type=int,required=True); ap.add_argument('--out',type=Path,required=True); a=ap.parse_args(); y=a.year
 if y not in EXPECTED: raise SystemExit('unsupported year')
 root=a.out; raw=root/'raw'; nod=[]; valid=[]
 for i,d in enumerate(candidates(y),1):
  b,final,rows,stat=fetch(d)
  rec={'date':d.isoformat(),'request_url':url(d),'final_url':final,'retrieved_at':now(),'bytes':len(b),'sha256':sha(b),'stat':stat}
  if rows is None:
   rec['classification']='OFFICIAL_NO_DATA'; nod.append(rec); print(f'[{i}] NO_DATA {d}',flush=True)
  else:
   p=raw/d.strftime('%Y/%m')/(d.strftime('%Y%m%d')+'.json.gz'); p.parent.mkdir(parents=True,exist_ok=True)
   with gzip.open(p,'wb',compresslevel=6) as f:f.write(b)
   rb=gzip.open(p,'rb').read()
   if rb!=b or sha(rb)!=sha(b): raise RuntimeError('readback mismatch')
   rec.update({'classification':'OFFICIAL_RAW_VALID','rows':rows,'path':p.relative_to(root).as_posix()}); valid.append(rec); print(f'[{i}] OK {d} rows={rows}',flush=True)
  time.sleep(random.uniform(.8,1.4))
 if len(valid)!=EXPECTED[y]:
  (root/'manifest').mkdir(parents=True,exist_ok=True)
  (root/'manifest'/'MISMATCH.json').write_text(json.dumps({'year':y,'expected':EXPECTED[y],'valid':len(valid),'no_data':len(nod)},ensure_ascii=False,indent=2),encoding='utf-8')
  raise SystemExit(f'expected {EXPECTED[y]} valid dates, got {len(valid)}')
 start=valid[0]['date'].replace('-',''); end=valid[-1]['date'].replace('-','')
 meta={'schema':'raw_w01_twse_daily_k_package_v3','dataset_id':'TWSE_DAILY_K','source_family':'TWSE_MI_INDEX_ALLBUT0999','year':y,'coverage_start':valid[0]['date'],'coverage_end':valid[-1]['date'],'work_units':len(valid),'expected_work_units':EXPECTED[y],'raw_member_format':'gzip(exact TWSE HTTP JSON response bytes)','sha256_scope':'uncompressed exact HTTP response bytes','members':valid,'no_data_candidates':nod,'created_at':now()}
 md=root/'manifest'; md.mkdir(parents=True,exist_ok=True); mp=md/f'PACKAGE_MANIFEST_{start}_{end}.json'; mp.write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')
 pkg=root/f'TWSE_DAILY_K_{start}_{end}_OFFICIAL_RAW_V3.zip'; tmp=Path(str(pkg)+'.part')
 with zipfile.ZipFile(tmp,'w',compression=zipfile.ZIP_STORED,allowZip64=True) as z:
  for r in valid:z.write(root/r['path'],r['path'])
  z.write(mp,'manifest/'+mp.name)
 os.replace(tmp,pkg)
 print(json.dumps({'package':str(pkg),'sha256':sha(pkg.read_bytes()),'bytes':pkg.stat().st_size,'valid':len(valid),'no_data':len(nod)},ensure_ascii=False))
if __name__=='__main__':main()
