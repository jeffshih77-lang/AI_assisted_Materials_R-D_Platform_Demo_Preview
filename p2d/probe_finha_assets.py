#!/usr/bin/env python3
import hashlib,json,re,ssl
from pathlib import Path
from urllib.parse import urljoin
from urllib.request import Request,urlopen

BASE='https://finha.rockmanagent.com/datasets'
OUT=Path('p2d_finha_probe'); OUT.mkdir(exist_ok=True)
UA='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/150 Safari/537.36'
ctx=ssl.create_default_context()

def get(url):
    req=Request(url,headers={'User-Agent':UA,'Accept':'text/html,application/javascript,application/json,*/*','Accept-Language':'zh-TW,zh;q=0.9'})
    try:
      with urlopen(req,timeout=45,context=ctx) as r:
        b=r.read(); st=getattr(r,'status',200); h=dict(r.headers.items()); final=r.geturl()
    except Exception as e:
      return {'url':url,'status':None,'error':repr(e),'bytes':0,'sha256':hashlib.sha256(b'').hexdigest(),'body':b''}
    return {'url':url,'final':final,'status':st,'headers':h,'error':None,'bytes':len(b),'sha256':hashlib.sha256(b).hexdigest(),'body':b}

root=get(BASE)
(OUT/'datasets.bin').write_bytes(root['body'])
text=root['body'].decode('utf-8','replace')
(OUT/'datasets.html').write_text(text,encoding='utf-8')
print('ROOT',root['status'],root['bytes'],root['sha256'])
# Discover script/link assets
assets=[]
for m in re.findall(r'(?:src|href)=["\']([^"\']+)["\']',text,re.I):
    u=urljoin(BASE,m)
    if any(x in u for x in ('.js','/_next/','/assets/','.css')):
        assets.append(u)
assets=list(dict.fromkeys(assets))
print('ASSETS',len(assets))
keywords=['個股分點券商買賣日報','parquet','broker','dataset','download','api/','/api','storage','supabase','s3','r2','cloudflare','2018-01','TaiwanStockTradingDailyReport']
rows=[]
for i,u in enumerate(assets[:100]):
    r=get(u); b=r['body']; s=b.decode('utf-8','replace')
    fn=OUT/f'asset_{i:03d}.txt'; fn.write_text(s,encoding='utf-8')
    hits={k:len(re.findall(re.escape(k),s,re.I)) for k in keywords if re.search(re.escape(k),s,re.I)}
    urls=re.findall(r'https?://[^"\'`\\\s)]+',s)
    interesting=[x for x in urls if any(k in x.lower() for k in ['api','parquet','dataset','supabase','r2','storage','rockman'])]
    rows.append({'asset':u,'status':r['status'],'bytes':r['bytes'],'sha256':r['sha256'],'hits':hits,'urls':interesting[:100]})
    if hits or interesting:
      print('\nASSET',i,u,'status',r['status'],'bytes',r['bytes'],'hits',hits)
      for x in interesting[:30]: print(' URL',x)
      # context around key strings
      for k in keywords:
        pos=s.lower().find(k.lower())
        if pos>=0:
          print(' CTX',k, s[max(0,pos-500):pos+1200].replace('\n',' ')[:1800])
# Probe common public API/static paths
candidates=[
 'https://finha.rockmanagent.com/api/datasets',
 'https://finha.rockmanagent.com/api/dataset',
 'https://finha.rockmanagent.com/api/v1/datasets',
 'https://finha.rockmanagent.com/api/datasets/broker',
 'https://finha.rockmanagent.com/datasets.json',
 'https://finha.rockmanagent.com/api/download',
 'https://finha.rockmanagent.com/robots.txt',
 'https://finha.rockmanagent.com/sitemap.xml',
]
probes=[]
for u in candidates:
 r=get(u); body=r['body'];
 probes.append({k:v for k,v in r.items() if k!='body'})
 (OUT/('probe_'+re.sub(r'[^A-Za-z0-9]+','_',u)+'.bin')).write_bytes(body)
 print('PROBE',u,r['status'],r['bytes'],r['sha256'],body[:160].decode('utf-8','replace').replace('\n',' '))
(OUT/'summary.json').write_text(json.dumps({'root':{k:v for k,v in root.items() if k!='body'},'assets':rows,'probes':probes},ensure_ascii=False,indent=2),encoding='utf-8')
