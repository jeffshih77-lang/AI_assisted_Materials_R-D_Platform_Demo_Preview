#!/usr/bin/env python3
import hashlib, json, os, re, ssl, time
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

OUT = Path('p2d_probe_output')
OUT.mkdir(parents=True, exist_ok=True)
CTX = ssl.create_default_context()
UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/150 Safari/537.36'

def slug(s):
    return re.sub(r'[^A-Za-z0-9_.-]+','_',s)[:140]

def decode(body):
    for enc in ('big5','cp950','utf-8'):
        try:
            return body.decode(enc), enc
        except Exception:
            pass
    return body.decode('utf-8', errors='replace'), 'utf-8-replace'

def html_stats(text):
    dates = re.findall(r'(?:19|20)\d{2}[/-]\d{1,2}[/-]\d{1,2}', text)
    norm=[]
    for d in dates:
        try:
            parts=re.split(r'[/-]',d)
            norm.append(f'{int(parts[0]):04d}-{int(parts[1]):02d}-{int(parts[2]):02d}')
        except Exception: pass
    broker_links = re.findall(r'zco0\.djhtm\?[^"\']+', text, re.I)
    data_cells = len(re.findall(r'class=["\']?t3n1', text, re.I))
    trs = len(re.findall(r'<tr\b', text, re.I))
    return {
        'date_tokens': len(dates), 'date_min': min(norm) if norm else None,
        'date_max': max(norm) if norm else None, 'unique_dates': len(set(norm)),
        'broker_link_count': len(broker_links), 'data_cell_t3n1_count': data_cells,
        'tr_count': trs,
        'contains_no_data': any(x in text for x in ('查無資料','無資料','沒有資料')),
        'contains_buy_sell_headers': ('買進' in text and '賣出' in text),
    }

def fetch(name,url,repeat=1):
    out=[]
    for i in range(repeat):
        req=Request(url,headers={'User-Agent':UA,'Accept':'text/html,text/plain,*/*;q=0.8','Accept-Language':'zh-TW,zh;q=0.9,en;q=0.7'})
        ts=datetime.now(timezone.utc).isoformat()
        try:
            with urlopen(req, timeout=45, context=CTX) as r:
                body=r.read(); status=getattr(r,'status',200); headers=dict(r.headers.items()); final=r.geturl()
            err=None
        except HTTPError as e:
            body=e.read(); status=e.code; headers=dict(e.headers.items()) if e.headers else {}; final=e.geturl(); err=repr(e)
        except Exception as e:
            body=b''; status=None; headers={}; final=url; err=repr(e)
        sha=hashlib.sha256(body).hexdigest()
        base=OUT/f'{slug(name)}__try{i+1}'
        (base.with_suffix('.bin')).write_bytes(body)
        text,enc=decode(body)
        (base.with_suffix('.txt')).write_text(text,encoding='utf-8')
        meta={'name':name,'requested_url':url,'final_url':final,'fetched_at_utc':ts,'status':status,'headers':headers,'bytes':len(body),'sha256':sha,'decode':enc,'error':err,'stats':html_stats(text)}
        (base.with_suffix('.json')).write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')
        out.append(meta)
        time.sleep(0.7)
    if repeat>1:
        same=len({x['sha256'] for x in out})==1
        for x in out: x['repeat_sha_same']=same
    return out

records=[]
# Front pages / backend / broker-list resources
fixed={
 'fubon_current_2330':'https://fubon-ebrokerdj.fbs.com.tw/z/zc/zco/zco_2330.djhtm',
 'fubon_bcd_2330':'https://fubon-ebrokerdj.fbs.com.tw/Z/ZC/ZCO/CZCO.DJBCD?A=2330',
 'fubon_zbrokerjs':'https://fubon-ebrokerdj.fbs.com.tw/z/js/zbrokerjs.djjs',
 'fubon_mdjjs':'https://fubon-ebrokerdj.fbs.com.tw/z/js/mdj.js',
 'finmind_trader_info':'https://api.finmindtrade.com/api/v4/data?dataset=TaiwanSecuritiesTraderInfo',
}
for name,url in fixed.items(): records += fetch(name,url,2 if name in ('fubon_current_2330','fubon_bcd_2330') else 1)

# Main custom-range page: known to render ranked branches for arbitrary date interval.
for y in (2002,2005,2008,2010,2012,2014,2016,2020,2024,2026):
    records += fetch(f'fubon_main_2330_{y}', f'https://fubon-ebrokerdj.fbs.com.tw/z/zc/zco/zco.djhtm?a=2330&e={y}-1-1&f={y}-12-31')

# Single broker/branch history pages. Parent broker IDs use b==BHID; also include article-demonstrated branch parameters.
pairs=[('2330','9200','9200','kgi_parent'),('2330','9800','9800','yuanta_parent'),('2359','1030','0031003000330043','article_branch')]
for stock,bhid,bcode,label in pairs:
    for y in (2002,2005,2008,2010,2012,2014,2016,2020,2024,2026):
        url=(f'https://fubon-ebrokerdj.fbs.com.tw/z/zc/zco/zco0/zco0.djhtm?'
             f'a={stock}&BHID={bhid}&b={bcode}&C=1&D={y}-1-1&E={y}-12-31&ver=V3')
        records += fetch(f'fubon_single_{label}_{stock}_{y}',url,2 if (stock=='2359' and y==2024) else 1)

# MoneyDJ white-label mirror positive controls.
for host in ('justdata.moneydj.com','concords.moneydj.com'):
    url=f'https://{host}/z/zc/zco/zco0/zco0.djhtm?a=2359&BHID=1030&b=0031003000330043&C=1&D=2024-1-1&E=2024-12-31&ver=V3'
    records += fetch(f'{host}_2359_2024',url)

# Compact summary
summary={'generated_at_utc':datetime.now(timezone.utc).isoformat(),'records':records}
(OUT/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
with (OUT/'summary.tsv').open('w',encoding='utf-8') as f:
    f.write('name\tstatus\tbytes\tsha256\tdate_min\tdate_max\tunique_dates\tbroker_links\tdata_cells\terror\n')
    for r in records:
        s=r['stats']
        f.write('\t'.join(str(x if x is not None else '') for x in [r['name'],r['status'],r['bytes'],r['sha256'],s['date_min'],s['date_max'],s['unique_dates'],s['broker_link_count'],s['data_cell_t3n1_count'],r['error']])+'\n')
print((OUT/'summary.tsv').read_text(encoding='utf-8'))
