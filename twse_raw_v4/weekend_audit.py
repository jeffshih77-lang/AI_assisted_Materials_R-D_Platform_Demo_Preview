#!/usr/bin/env python3
from __future__ import annotations
import argparse, datetime as dt, gzip, hashlib, json, os, random, time, zipfile
from pathlib import Path
from urllib.parse import urlparse
import requests

BASE='https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX'
REF='https://www.twse.com.tw/zh/trading/historical/mi-index.html'
ALLOWED={'www.twse.com.tw','twse.com.tw'}

def sha(b): return hashlib.sha256(b).hexdigest()
def now(): return dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')
def url(d): return BASE+f'?date={d:%Y%m%d}&type=ALLBUT0999&response=json'
def host_ok(u):
    h=(urlparse(u).hostname or '').lower(); return h in ALLOWED or h.endswith('.twse.com.tw')
def classify(b,d):
    try:o=json.loads(b)
    except Exception as e:return 'SOURCE_ERROR',{'reason':'JSON_PARSE','detail':repr(e)}
    stat=str(o.get('stat',''))
    if stat=='OK':
        if str(o.get('date',''))!=f'{d:%Y%m%d}': return 'SOURCE_ERROR',{'reason':'DATE_MISMATCH','got':o.get('date')}
        for t in o.get('tables') or []:
            f=t.get('fields') or []
            if '證券代號' in f and '收盤價' in f:
                rows=t.get('data') or []
                if not rows:return 'SOURCE_ERROR',{'reason':'EMPTY_TABLE'}
                if any(len(r)!=len(f) for r in rows):return 'SOURCE_ERROR',{'reason':'ROW_WIDTH'}
                return 'VALID_RAW',{'rows':len(rows)}
        return 'SOURCE_ERROR',{'reason':'SECURITY_TABLE_MISSING'}
    low=stat.lower()
    if any(x in stat for x in ['沒有符合條件','查無資料','無資料']) or 'no data' in low or 'no matching' in low:
        return 'OFFICIAL_NO_DATA',{'stat':stat}
    return 'SOURCE_ERROR',{'reason':'NON_OK_STAT','stat':stat}

def fetch(s,d,attempts=5):
    last=None
    for i in range(attempts):
        try:
            r=s.get(url(d),headers={'Accept':'application/json,text/plain,*/*','Referer':REF,'Cache-Control':'no-cache'},timeout=(20,90),allow_redirects=True)
            chain=[x.url for x in r.history]+[r.url]
            if not all(host_ok(u) for u in chain): raise RuntimeError('redirect escaped TWSE')
            if r.status_code in (429,500,502,503,504): raise RuntimeError(f'retryable HTTP {r.status_code}')
            if r.status_code!=200: raise RuntimeError(f'HTTP {r.status_code}')
            kind,meta=classify(r.content,d)
            if kind=='SOURCE_ERROR': raise RuntimeError(repr(meta))
            return kind,r.content,r.url,chain,meta
        except Exception as e:
            last=e
            if i+1<attempts: time.sleep(min(10*(2**i),90)+random.uniform(0,2))
    return 'SOURCE_FAILURE',b'',url(d),[],{'error':repr(last)}

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--year',type=int,required=True); ap.add_argument('--out',type=Path,required=True); a=ap.parse_args()
    if not 2007<=a.year<=2013: raise SystemExit('year must be 2007..2013')
    root=a.out; root.mkdir(parents=True,exist_ok=True); mdir=root/'manifest'; mdir.mkdir(parents=True,exist_ok=True)
    s=requests.Session(); s.headers.update({'User-Agent':'Mozilla/5.0 (compatible; RAW-W01-weekend-audit/1.0)'})
    d=dt.date(a.year,1,1); end=dt.date(a.year,12,31); events=[]; counts={'VALID_RAW':0,'OFFICIAL_NO_DATA':0,'SOURCE_FAILURE':0}
    while d<=end:
        if d.weekday()>=5:
            kind,b,final,chain,meta=fetch(s,d)
            rec={'date':d.isoformat(),'weekday':d.strftime('%A'),'status':kind,'request_url':url(d),'final_url':final,'redirect_chain':chain,'retrieved_at':now(),**meta}
            if kind in ('VALID_RAW','OFFICIAL_NO_DATA'):
                rel=(Path('raw/weekend') if kind=='VALID_RAW' else Path('evidence/no_data/weekend'))/str(a.year)/f'{d:%Y%m%d}.json.gz'
                p=root/rel; p.parent.mkdir(parents=True,exist_ok=True)
                with gzip.open(p,'wb',compresslevel=6) as f:f.write(b)
                rb=gzip.open(p,'rb').read()
                if rb!=b: raise RuntimeError(f'readback mismatch {d}')
                rec.update({'relative_path':rel.as_posix(),'bytes_uncompressed':len(b),'sha256_uncompressed':sha(b)})
            counts[kind]+=1; events.append(rec); print(kind,d,meta,flush=True); time.sleep(random.uniform(1.8,2.8))
        d+=dt.timedelta(days=1)
    ep=mdir/'weekend_events.json'; ep.write_text(json.dumps(events,ensure_ascii=False,indent=2),encoding='utf-8')
    summary={'schema':'raw_w01_twse_weekend_audit_v1','year':a.year,'created_at':now(),'weekend_days_scanned':len(events),'counts':counts,'valid_weekend_dates':[x['date'] for x in events if x['status']=='VALID_RAW'],'complete':counts['SOURCE_FAILURE']==0}
    sp=mdir/'SUMMARY.json'; sp.write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    pkg=root/f'TWSE_DAILY_K_{a.year}_WEEKEND_AUDIT_V1.zip'; tmp=Path(str(pkg)+'.part')
    with zipfile.ZipFile(tmp,'w',compression=zipfile.ZIP_STORED,allowZip64=True) as z:
        for p in root.rglob('*'):
            if p.is_file() and p not in (pkg,tmp): z.write(p,p.relative_to(root).as_posix())
    os.replace(tmp,pkg)
    (root/'PACKAGE_META.json').write_text(json.dumps({'package':pkg.name,'bytes':pkg.stat().st_size,'sha256':sha(pkg.read_bytes()),'summary':summary},ensure_ascii=False,indent=2),encoding='utf-8')
    raise SystemExit(0 if summary['complete'] else 2)
if __name__=='__main__': main()
