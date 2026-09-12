#!/usr/bin/env python3
import hashlib,json,re,ssl
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.error import HTTPError,URLError

OUT=Path('p2d_finha_access'); OUT.mkdir(exist_ok=True)
UA='Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/150 Safari/537.36'
ctx=ssl.create_default_context()

def fetch(name,url,headers=None):
    h={'User-Agent':UA,'Accept':'application/json,text/html,*/*'}
    if headers: h.update(headers)
    req=Request(url,headers=h)
    try:
        with urlopen(req,timeout=35,context=ctx) as r:
            b=r.read(); st=getattr(r,'status',200); rh=dict(r.headers.items()); final=r.geturl(); err=None
    except HTTPError as e:
        b=e.read(); st=e.code; rh=dict(e.headers.items()) if e.headers else {}; final=e.geturl(); err=repr(e)
    except Exception as e:
        b=b''; st=None; rh={}; final=url; err=repr(e)
    sha=hashlib.sha256(b).hexdigest()
    txt=b.decode('utf-8','replace')
    (OUT/f'{name}.bin').write_bytes(b)
    (OUT/f'{name}.txt').write_text(txt,encoding='utf-8')
    meta={'name':name,'url':url,'final':final,'status':st,'bytes':len(b),'sha256':sha,'headers':rh,'error':err,'preview':txt[:1000]}
    (OUT/f'{name}.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')
    print('\n###',name,st,len(b),sha,err)
    print(txt[:1200].replace('\n',' ')[:1200])
    return meta

qs='dataset=TaiwanStockTradingDailyReport&stock_id=2330&start=2026-06-01&end=2026-06-01&limit=5'
urls={
 'api_query_anon':f'https://api.finha.rockmanagent.com/v1/query?{qs}',
 'api_query_empty_bearer':f'https://api.finha.rockmanagent.com/v1/query?{qs}',
 'api_catalog':'https://api.finha.rockmanagent.com/v1/datasets',
 'api_dataset':'https://api.finha.rockmanagent.com/v1/datasets/TaiwanStockTradingDailyReport',
 'api_storage':'https://api.finha.rockmanagent.com/v1/storage_objects?dataset=TaiwanStockTradingDailyReport&date=2026-06-02',
 'api_data_day':'https://api.finha.rockmanagent.com/v1/data/TaiwanStockTradingDailyReport/date=2026-06-02',
 'web_detail':'https://finha.rockmanagent.com/datasets/TaiwanStockTradingDailyReport',
 'web_account_me':'https://finha.rockmanagent.com/api/account/me',
}
rows=[]
for n,u in urls.items():
    rows.append(fetch(n,u,{'Authorization':'Bearer '} if n=='api_query_empty_bearer' else None))
# Common custom-domain guesses; only ordinary GETs, no auth bypass.
for host in ['data.finha.rockmanagent.com','r2.finha.rockmanagent.com','storage.finha.rockmanagent.com','quantdata-share.finha.rockmanagent.com']:
    for path in ['','/v1/data/TaiwanStockTradingDailyReport/','/v1/data/TaiwanStockTradingDailyReport/date=2026-06-02/']:
        n='host_'+re.sub(r'[^a-z0-9]+','_',host+path.lower()).strip('_')
        rows.append(fetch(n,'https://'+host+path))
(OUT/'summary.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
