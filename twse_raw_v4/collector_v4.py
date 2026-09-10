#!/usr/bin/env python3
from __future__ import annotations
import argparse, datetime as dt, gzip, hashlib, json, os, random, sys, time, zipfile
from pathlib import Path
from urllib.parse import urlparse
import requests

BASE='https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX'
REF='https://www.twse.com.tw/zh/trading/historical/mi-index.html'
ALLOWED_HOSTS={'www.twse.com.tw','twse.com.tw'}
FROZEN_COUNTS={2004:228,2005:248,2006:249,2007:243,2008:249,2009:248,2010:250,2011:247,2012:247,2013:244,2014:248,2015:244,2016:244,2017:246,2018:247,2019:242,2020:245,2021:244,2022:246,2023:239,2024:242,2025:243,2026:143}

def utcnow(): return dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')
def sha(b:bytes): return hashlib.sha256(b).hexdigest()
def wr(p:Path,b:bytes): p.parent.mkdir(parents=True,exist_ok=True); t=p.with_suffix(p.suffix+'.part'); t.write_bytes(b); os.replace(t,p)
def wrgz(p:Path,b:bytes):
    p.parent.mkdir(parents=True,exist_ok=True); t=p.with_suffix(p.suffix+'.part')
    with gzip.open(t,'wb',compresslevel=6) as f:f.write(b)
    os.replace(t,p)
def add_jsonl(p:Path,o:dict):
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('a',encoding='utf-8',newline='\n') as f:f.write(json.dumps(o,ensure_ascii=False,sort_keys=True)+'\n');f.flush();os.fsync(f.fileno())
def official_url(d:dt.date): return BASE+f'?date={d:%Y%m%d}&type=ALLBUT0999&response=json'
def allowed(url:str):
    h=(urlparse(url).hostname or '').lower()
    return h in ALLOWED_HOSTS or h.endswith('.twse.com.tw')
def classify(payload:bytes,d:dt.date):
    try:o=json.loads(payload)
    except Exception as e:return ('SOURCE_ERROR',{'reason':'JSON_PARSE','detail':repr(e)})
    stat=str(o.get('stat',''))
    if stat=='OK':
        got=str(o.get('date',''))
        if got!=f'{d:%Y%m%d}': return ('SOURCE_ERROR',{'reason':'DATE_MISMATCH','got':got})
        target=None
        for t in o.get('tables') or []:
            fs=t.get('fields') or []
            if '證券代號' in fs and '收盤價' in fs: target=t;break
        if target is None:return ('SOURCE_ERROR',{'reason':'SECURITY_TABLE_MISSING'})
        rows=target.get('data') or []; width=len(target.get('fields') or [])
        if not rows:return ('SOURCE_ERROR',{'reason':'SECURITY_TABLE_EMPTY'})
        bad=sum(1 for r in rows if len(r)!=width)
        if bad:return ('SOURCE_ERROR',{'reason':'ROW_WIDTH','bad_rows':bad})
        return ('VALID_RAW',{'rows':len(rows),'width':width})
    low=stat.lower()
    nodata=any(x in stat for x in ['沒有符合條件','查無資料','無資料']) or 'no data' in low or 'no matching' in low
    if nodata:return ('OFFICIAL_NO_DATA',{'stat':stat})
    return ('SOURCE_ERROR',{'reason':'NON_OK_STAT','stat':stat})

def fetch(s:requests.Session,d:dt.date,attempts=6):
    url=official_url(d); last=None
    for a in range(1,attempts+1):
        try:
            r=s.get(url,headers={'Accept':'application/json,text/plain,*/*','Referer':REF,'Cache-Control':'no-cache'},timeout=(20,90),allow_redirects=True)
            chain=[x.url for x in r.history]+[r.url]
            if not all(allowed(u) for u in chain): raise RuntimeError('redirect escaped TWSE: '+repr(chain))
            if r.status_code in (429,500,502,503,504): raise RuntimeError(f'retryable HTTP {r.status_code}')
            if r.status_code!=200: raise RuntimeError(f'HTTP {r.status_code}')
            kind,meta=classify(r.content,d)
            if kind=='SOURCE_ERROR': raise RuntimeError('payload validation: '+repr(meta))
            return kind,r.content,r.url,meta,chain
        except Exception as e:
            last=e
            if a<attempts:
                pause=min(12*(2**(a-1)),120)+random.uniform(0,2.0)
                print(f'RETRY {d} {a}/{attempts}: {e}; sleep={pause:.1f}',flush=True); time.sleep(pause)
                if a in (3,5):
                    try:s.close()
                    except Exception:pass
                    s=requests.Session(); s.headers.update({'User-Agent':'Mozilla/5.0 (compatible; RAW-W01/4.0; +TWSE-official-preservation)'})
    return 'SOURCE_FAILURE',b'',url,{'error':repr(last)},[]
def bounds(year:int,start_arg,end_arg):
    start=dt.date(year,1,1);end=dt.date(year,12,31)
    if year==2004:start=max(start,dt.date(2004,2,11))
    if year==2026:end=min(end,dt.date(2026,8,7))
    if start_arg:start=max(start,dt.date.fromisoformat(start_arg))
    if end_arg:end=min(end,dt.date.fromisoformat(end_arg))
    if start>end:raise SystemExit('empty date range')
    return start,end
def daterange(a,b):
    d=a
    while d<=b:yield d;d+=dt.timedelta(days=1)
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--year',type=int,required=True);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--start');ap.add_argument('--end');ap.add_argument('--sleep-min',type=float,default=1.7);ap.add_argument('--sleep-max',type=float,default=2.6);a=ap.parse_args()
    root=a.out;root.mkdir(parents=True,exist_ok=True);start,end=bounds(a.year,a.start,a.end);events=root/'manifest'/'events.jsonl'; s=requests.Session();s.headers.update({'User-Agent':'Mozilla/5.0 (compatible; RAW-W01/4.0; +TWSE-official-preservation)'})
    counts={'VALID_RAW':0,'OFFICIAL_NO_DATA':0,'SOURCE_FAILURE':0}; failures=[]
    for i,d in enumerate(daterange(start,end),1):
        kind,payload,final,meta,chain=fetch(s,d); ymd=f'{d:%Y%m%d}'
        rec={'work_id':'RAW-W01','dataset_id':'TWSE_DAILY_K','source_family':'TWSE_MI_INDEX_ALLBUT0999','trade_date':d.isoformat(),'request_url':official_url(d),'final_url':final,'redirect_chain':chain,'retrieved_at':utcnow(),'status':kind,**meta}
        if kind in ('VALID_RAW','OFFICIAL_NO_DATA'):
            rel=(Path('raw') if kind=='VALID_RAW' else Path('evidence/no_data'))/str(a.year)/f'{ymd}.json.gz'; wrgz(root/rel,payload); rb=gzip.open(root/rel,'rb').read()
            if rb!=payload: raise RuntimeError(f'readback mismatch {d}')
            rec.update({'relative_path':rel.as_posix(),'bytes_uncompressed':len(payload),'sha256_uncompressed':sha(payload)});counts[kind]+=1
            print(f'[{i}] {kind} {d}'+(f" rows={meta.get('rows')}" if kind=='VALID_RAW' else ''),flush=True)
        else:
            counts['SOURCE_FAILURE']+=1;failures.append(rec);print(f'[{i}] SOURCE_FAILURE {d}: {meta}',file=sys.stderr,flush=True)
        add_jsonl(events,rec);time.sleep(random.uniform(a.sleep_min,a.sleep_max))
    full_year=(start==bounds(a.year,None,None)[0] and end==bounds(a.year,None,None)[1]); frozen=FROZEN_COUNTS.get(a.year)
    summary={'schema':'raw_w01_twse_daily_k_source_scan_v4','created_at':utcnow(),'year':a.year,'coverage_start':start.isoformat(),'coverage_end':end.isoformat(),'full_year_scope':full_year,'calendar_days_scanned':sum(1 for _ in daterange(start,end)),'counts':counts,'source_scan_complete':counts['SOURCE_FAILURE']==0,'frozen_calendar_reference_count':frozen,'valid_vs_frozen_delta':None if frozen is None else counts['VALID_RAW']-frozen,'calendar_reconciliation_status':'MATCH' if frozen is not None and counts['VALID_RAW']==frozen else ('MISMATCH_REVIEW' if frozen is not None else 'NO_REFERENCE'),'failures':failures}
    sp=root/'manifest'/'SUMMARY.json';wr(sp,json.dumps(summary,ensure_ascii=False,indent=2).encode())
    pkg=root/f'TWSE_DAILY_K_{start:%Y%m%d}_{end:%Y%m%d}_OFFICIAL_SOURCE_SCAN_V4.zip'
    with zipfile.ZipFile(pkg.with_suffix('.zip.part'),'w',compression=zipfile.ZIP_STORED,allowZip64=True) as z:
        for p in root.rglob('*'):
            if p.is_file() and p not in (pkg,pkg.with_suffix('.zip.part')): z.write(p,p.relative_to(root).as_posix())
    os.replace(pkg.with_suffix('.zip.part'),pkg)
    pkgmeta={'package':pkg.name,'bytes':pkg.stat().st_size,'sha256':sha(pkg.read_bytes()),'summary':summary};wr(root/'PACKAGE_META.json',json.dumps(pkgmeta,ensure_ascii=False,indent=2).encode())
    print(json.dumps(pkgmeta,ensure_ascii=False),flush=True)
    return 0 if counts['SOURCE_FAILURE']==0 else 2
if __name__=='__main__':raise SystemExit(main())
