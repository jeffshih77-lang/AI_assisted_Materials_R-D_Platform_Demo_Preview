from __future__ import annotations
import csv, hashlib, io, json, re, urllib.request
from datetime import date
UA='MarketDataDownloader-RT10-Verify/1.0 (official endpoints only; no bypass)'
TARGET='2026-09-16'
EXPECTED_SEMANTIC={'TWSE_INSTITUTIONAL_ORDER':'4102a91d3406f9c3858663f6dab122936066d179422fab335aac02f202cc723e','TWSE_INSTITUTIONAL_SORTED':'cf9c6b88685d8752cb1f9e4deecd19f93becebac530a52358027bb06747a9594'}
EXPECTED={
'TWSE_DAILY_K':'b41fcec43166ee6702d7130237ba11c75347bd75fc922986115f16c004550ae5',
'TWSE_INSTITUTIONAL':'6c1fe3837a9a95da250af902561f52a966f92fe1b3fa687dd85334d8dbb868e9',
'TWSE_MARGIN':'d69c2279a9d59005c6739eeb2e667d846fbf42dde1ed4bc7bf90bd6de3d0b7a7',
'TWSE_LENDING':'3ea708f8721fd28bfd5cc61e8254a1b5e0ffbbddc61be683a155343e7a51bcd9',
'ECB':'99fc30ef95e929323ad013daf71be6200e6bad67c4cd290622674b5d9a78b603',
}
URLS={
'TWSE_DAILY_K':'https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX?date=20260916&type=ALLBUT0999&response=csv',
'TWSE_INSTITUTIONAL':'https://www.twse.com.tw/rwd/zh/fund/T86?date=20260916&selectType=ALL&response=csv',
'TWSE_FOREIGN_HOLD_RUN':'https://www.twse.com.tw/rwd/zh/fund/MI_QFIIS?date=20260916&selectType=ALL&response=json',
'TWSE_FOREIGN_HOLD_CORRECTED':'https://www.twse.com.tw/rwd/zh/fund/MI_QFIIS?date=20260916&selectType=ALLBUT0999&response=json',
'TWSE_MARGIN':'https://www.twse.com.tw/rwd/zh/marginTrading/MI_MARGN?date=20260916&selectType=ALL&response=csv',
'TWSE_LENDING':'https://www.twse.com.tw/exchangeReport/TWT72U?date=20260916&response=html&selectType=SLBNLB',
'TAIEX_DAILY':'https://openapi.twse.com.tw/v1/indicesReport/MI_5MINS_HIST',
'ECB':'https://data-api.ecb.europa.eu/service/data/EXR/D.USD.EUR.SP00.A?startPeriod=2026-09-16&endPeriod=2026-09-16&format=csvdata',
'UST':'https://home.treasury.gov/resource-center/data-chart-center/interest-rates/pages/xml?data=daily_treasury_yield_curve&field_tdr_date_value_month=202609',
'CBOE':'https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv',
}
def fetch(url):
    req=urllib.request.Request(url,headers={'User-Agent':UA,'Accept':'*/*','Accept-Encoding':'identity','Connection':'close','Cache-Control':'no-cache'})
    with urllib.request.urlopen(req,timeout=60) as r:
        raw=r.read()
        return raw, int(getattr(r,'status',200)), r.headers.get('Content-Type','')
def dec(raw):
    for e in ('utf-8-sig','utf-8','cp950','big5'):
        try:return raw.decode(e)
        except UnicodeDecodeError:pass
    return raw.decode('latin1','replace')
def find_csv_line(text,prefix):
    for line in text.splitlines():
        if line.startswith(prefix): return line
    return None
def main():
    out={}
    for name,url in URLS.items():
        try:
            raw,status,ctype=fetch(url); text=dec(raw); sha=hashlib.sha256(raw).hexdigest()
            row={'http':status,'bytes':len(raw),'sha256':sha,'ctype':ctype}
            if name in EXPECTED: row['sha_matches_runtime10']=sha==EXPECTED[name]
            if name=='TWSE_DAILY_K':
                row['date_header_ok']='115年09月16日' in text
                row['friend_2409'] = next((x for x in text.splitlines() if x.startswith('"2409"')),None)
            elif name=='TWSE_INSTITUTIONAL':
                row['date_header_ok']='115年09月16日' in text
                row['friend_2409'] = next((x for x in text.splitlines() if x.startswith('"2409"')),None)
                lines=[x.rstrip() for x in text.replace('\\r\\n','\\n').replace('\\r','\\n').split('\\n')]
                oh=hashlib.sha256('\\n'.join(lines).encode('utf-8')).hexdigest()
                sh=hashlib.sha256('\\n'.join(sorted(lines)).encode('utf-8')).hexdigest()
                row['normalized_order_sha']=oh
                row['normalized_sorted_sha']=sh
                row['normalized_order_matches_runtime10']=oh==EXPECTED_SEMANTIC['TWSE_INSTITUTIONAL_ORDER']
                row['normalized_sorted_matches_runtime10']=sh==EXPECTED_SEMANTIC['TWSE_INSTITUTIONAL_SORTED']
            elif name.startswith('TWSE_FOREIGN_HOLD'):
                obj=json.loads(text); row['stat']=obj.get('stat'); row['date']=obj.get('date'); row['total']=obj.get('total'); row['data_len']=len(obj.get('data') or [])
                row['first_row']=(obj.get('data') or [None])[0]
            elif name=='TWSE_MARGIN':
                row['date_header_ok']='115年09月16日' in text
                row['summary_loan']='586,166,660' in text
            elif name=='TWSE_LENDING':
                row['date_header_ok']='115年09月16日' in text
                row['sample_00400A']='36,847,000' in text
                row['sample_2330']='59,693,000' in text
            elif name=='TAIEX_DAILY':
                obj=json.loads(text)
                rr=[x for x in obj if str(x.get('Date'))=='1150916']; row['target_rows']=rr
            elif name=='ECB':
                row['target_line']=next((x for x in text.splitlines() if '2026-09-16' in x),None)
            elif name=='UST':
                m=re.search(r'<d:NEW_DATE m:type="Edm.DateTime">2026-09-16T00:00:00</d:NEW_DATE>(.*?)</m:properties>',text,re.S)
                if m:
                    vals=dict(re.findall(r'<d:(BC_[A-Z0-9_]+)[^>]*>([^<]+)</d:',m.group(1)))
                    row['target_values']={k:vals.get(k) for k in ['BC_1MONTH','BC_1YEAR','BC_10YEAR','BC_20YEAR','BC_30YEAR']}
                else: row['target_values']=None
            elif name=='CBOE':
                row['target_line']=find_csv_line(text,'09/16/2026,')
            out[name]=row
        except Exception as e:
            out[name]={'error':f'{type(e).__name__}: {e}'}
    print(json.dumps(out,ensure_ascii=False,indent=2))
if __name__=='__main__': main()
