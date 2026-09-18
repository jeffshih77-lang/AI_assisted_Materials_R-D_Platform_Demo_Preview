from __future__ import annotations
import json,re,time,urllib.request
from datetime import date
from urllib.parse import urlencode

UA='MarketDataDownloader-CI/0.15-date-capability (official OpenAPI only; no bypass)'
TARGET=date(2026,9,15)
MAX=20*1024*1024
TARGETS={
'TPEX_DAILY_K':'https://www.tpex.org.tw/openapi/v1/tpex_mainboard_daily_close_quotes',
'TPEX_INSTITUTIONAL':'https://www.tpex.org.tw/openapi/v1/tpex_3insti_daily_trading',
'TPEX_FOREIGN_HOLD':'https://www.tpex.org.tw/openapi/v1/tpex_3insti_qfii',
'TPEX_MARGIN':'https://www.tpex.org.tw/openapi/v1/tpex_mainboard_margin_balance',
'TPEX_LENDING':'https://www.tpex.org.tw/openapi/v1/tpex_margin_sbl',
'TAIFEX_FUTURES_OI':'https://openapi.taifex.com.tw/v1/MarketDataOfMajorInstitutionalTradersDetailsOfFuturesContractsBytheDate',
'TAIFEX_OPTIONS_INSTITUTIONAL':'https://openapi.taifex.com.tw/v1/MarketDataOfMajorInstitutionalTradersDetailsOfOptionsContractsBytheDate',
}
PARAMS={
'TPEX':[('none',{}),('date_iso',{'date':'2026-09-15'}),('d_roc',{'d':'1150915'})],
'TAIFEX':[('none',{}),('queryDate_slash',{'queryDate':'2026/09/15'}),('date_compact',{'date':'20260915'})],
}

def fetch(url):
    req=urllib.request.Request(url,headers={'User-Agent':UA,'Accept':'application/json,*/*;q=0.5','Accept-Encoding':'identity','Connection':'close','Cache-Control':'no-cache'})
    with urllib.request.urlopen(req,timeout=45) as r:
        expected=r.headers.get('Content-Length')
        expected=int(expected) if expected and expected.isdigit() else None
        chunks=[]; total=0
        while True:
            b=r.read(262144)
            if not b: break
            chunks.append(b); total+=len(b)
            if total>MAX: raise RuntimeError('too large')
        if expected is not None and total!=expected: raise RuntimeError(f'incomplete {total}/{expected}')
        return b''.join(chunks)

def dates(raw):
    text=raw.decode('utf-8-sig','replace')
    try: obj=json.loads(text)
    except Exception: return [],'non-json'
    rows=obj if isinstance(obj,list) else (obj.get('data') or obj.get('aaData') or [] if isinstance(obj,dict) else [])
    out=[]
    for row in rows[:500]:
        if not isinstance(row,dict): continue
        for k,v in row.items():
            if 'date' not in str(k).lower() and '日期' not in str(k): continue
            s=str(v).strip()
            m=re.fullmatch(r'(20\d{2})(\d{2})(\d{2})',s)
            if m: out.append(f'{m.group(1)}-{m.group(2)}-{m.group(3)}'); continue
            m=re.fullmatch(r'(1\d{2})(\d{2})(\d{2})',s)
            if m: out.append(f'{int(m.group(1))+1911:04d}-{m.group(2)}-{m.group(3)}'); continue
            m=re.search(r'(20\d{2})[-/](\d{2})[-/](\d{2})',s)
            if m: out.append(f'{m.group(1)}-{m.group(2)}-{m.group(3)}'); continue
            m=re.search(r'(1\d{2})[-/](\d{2})[-/](\d{2})',s)
            if m: out.append(f'{int(m.group(1))+1911:04d}-{m.group(2)}-{m.group(3)}')
    return sorted(set(out)),'json'

def main():
    report={'target':TARGET.isoformat(),'policy':'official OpenAPI only; no paid source; no ordinary-site history; no bypass','results':{}}
    for ds,base in TARGETS.items():
        family='TPEX' if ds.startswith('TPEX_') else 'TAIFEX'
        per=[]
        for label,params in PARAMS[family]:
            url=base + (('?' + urlencode(params)) if params else '')
            try:
                raw=fetch(url); ds_dates,fmt=dates(raw)
                row={'case':label,'bytes':len(raw),'dates':ds_dates[:10],'target_present':TARGET.isoformat() in ds_dates,'format':fmt}
            except Exception as e:
                row={'case':label,'error':f'{type(e).__name__}:{e}','target_present':False}
            per.append(row); print(json.dumps({'dataset':ds,**row},ensure_ascii=False),flush=True)
            time.sleep(1)
        report['results'][ds]=per
    report['historical_supported']={ds:any(x.get('target_present') for x in rows[1:]) for ds,rows in report['results'].items()}
    print(json.dumps(report,ensure_ascii=False,indent=2),flush=True)

if __name__=='__main__': main()
