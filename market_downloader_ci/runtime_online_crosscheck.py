from __future__ import annotations
import csv, hashlib, io, json, re, sys, urllib.request
from html import unescape

UA="MarketDataDownloader-OnlineCrosscheck/0.15 (official sources only; no bypass)"
TARGET="2026-09-16"
SOURCES={
"TWSE_DAILY_K":"https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX?date=20260916&type=ALLBUT0999&response=csv",
"TWSE_INSTITUTIONAL":"https://www.twse.com.tw/rwd/zh/fund/T86?date=20260916&selectType=ALL&response=csv",
"TWSE_MARGIN":"https://www.twse.com.tw/rwd/zh/marginTrading/MI_MARGN?date=20260916&selectType=ALL&response=csv",
"TWSE_FOREIGN_HOLD":"https://www.twse.com.tw/rwd/zh/fund/MI_QFIIS?date=20260916&selectType=ALL&response=json",
"TWSE_LENDING":"https://www.twse.com.tw/exchangeReport/TWT72U?date=20260916&response=html&selectType=SLBNLB",
"TAIEX_DAILY":"https://openapi.twse.com.tw/v1/indicesReport/MI_5MINS_HIST",
"ECB":"https://data-api.ecb.europa.eu/service/data/EXR/D.USD.EUR.SP00.A?startPeriod=2026-09-16&endPeriod=2026-09-16&format=csvdata",
"UST":"https://home.treasury.gov/resource-center/data-chart-center/interest-rates/pages/xml?data=daily_treasury_yield_curve&field_tdr_date_value_month=202609",
"VIX":"https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv",
}
EXP={
"TWSE_DAILY_K":{"sha":"b41fcec43166ee6702d7130237ba11c75347bd75fc922986115f16c004550ae5","row":["2330","台積電","20,919,285","142,588","49,812,874,845","2,375.00","2,395.00","2,375.00","2,380.00"]},
"TWSE_INSTITUTIONAL":{"sha":"6c1fe3837a9a95da250af902561f52a966f92fe1b3fa687dd85334d8dbb868e9","canonical":"26ffeacd8c7e0d2c0537513e433209e631e13d3d836b50c659b0d3b96897385c","row":["2330","台積電","8,374,396","17,118,776","-8,744,380"]},
"TWSE_MARGIN":{"sha":"d69c2279a9d59005c6739eeb2e667d846fbf42dde1ed4bc7bf90bd6de3d0b7a7","row":["2330","台積電","733","190","59","29,282","29,766"]},
"TWSE_FOREIGN_HOLD":{"sha":"7b07676b1ef8640e513615ab6ef64aad3b9681c9f52e861418eacadbf3b65a37","data_count":0,"total":0},
"TWSE_LENDING":{"sha":"3ea708f8721fd28bfd5cc61e8254a1b5e0ffbbddc61be683a155343e7a51bcd9","row":["2330","台積電","122,610,000","8,787,000","71,704,000","59,693,000","2,380.00","142,069,340,000","集中市場"]},
"TAIEX_DAILY":{"row":{"Date":"1150916","OpeningIndex":"45546.56","HighestIndex":"46077.82","LowestIndex":"45546.56","ClosingIndex":"45848.90"}},
"ECB":{"needle":"2026-09-16,1.1537"},
"UST":{"needle":"2026-09-16T00:00:00","vals":["3.96","4.00","4.07","4.14","4.24","4.22","4.45","4.74","4.82","4.86","4.94","5.01","5.39","5.35"]},
"VIX":{"needle":"09/16/2026,16.910000,18.940000,16.400000,17.710000"},
}
def fetch(url):
    req=urllib.request.Request(url,headers={"User-Agent":UA,"Accept":"*/*","Accept-Encoding":"identity","Connection":"close"})
    with urllib.request.urlopen(req,timeout=45) as r:
        return r.read()
def decode(raw):
    for enc in ("utf-8-sig","utf-8","cp950","big5"):
        try:return raw.decode(enc)
        except UnicodeDecodeError: pass
    return raw.decode("latin1","replace")
def csv_row_2330(text):
    rows=list(csv.reader(io.StringIO(text)))
    for row in rows:
        if row and row[0].replace("=","").strip().strip('"')=="2330":
            return [x.strip() for x in row]
    return None
def html_row_2330(text):
    m=re.search(r"<tr[^>]*>(?:(?!</tr>).)*?<td[^>]*>\s*2330\s*</td>(?:(?!</tr>).)*?</tr>",text,re.S|re.I)
    if not m:return None
    cells=[unescape(re.sub(r"<[^>]+>","",x)).strip() for x in re.findall(r"<td[^>]*>(.*?)</td>",m.group(0),re.S|re.I)]
    return [" ".join(x.split()) for x in cells]
def main():
    results={}; fail=[]
    for name,url in SOURCES.items():
        try: raw=fetch(url)
        except Exception as e:
            results[name]={"ok":False,"error":f"{type(e).__name__}:{e}"}; fail.append(name); continue
        text=decode(raw); sha=hashlib.sha256(raw).hexdigest()
        r={"bytes":len(raw),"sha256":sha,"ok":True}
        if name in ("TWSE_DAILY_K","TWSE_INSTITUTIONAL","TWSE_MARGIN"):
            row=csv_row_2330(text); r["row2330"]=row[:10] if row else None
            exp=EXP[name]; r["exact_sha_match"]=sha==exp["sha"]; r["row_match"]=bool(row and row[:len(exp["row"])]==exp["row"])
            if name=="TWSE_INSTITUTIONAL":
                rows=list(csv.reader(io.StringIO(text)))
                norm=[[x.strip() for x in rr] for rr in rows]
                r["canonical_sha256"]=hashlib.sha256(json.dumps(norm,ensure_ascii=False,separators=(",",":")).encode()).hexdigest()
                r["canonical_match"]=r["canonical_sha256"]==exp["canonical"]
                r["row_count"]=len(rows)
                r["ok"]=r["canonical_match"]
            else:
                r["ok"]=r["exact_sha_match"] or r["row_match"]
        elif name=="TWSE_FOREIGN_HOLD":
            obj=json.loads(text); r["date"]=obj.get("date"); r["stat"]=obj.get("stat"); r["data_count"]=len(obj.get("data") or []); r["total"]=obj.get("total")
            r["exact_sha_match"]=sha==EXP[name]["sha"]
            r["ok"]=obj.get("date")=="20260916" and obj.get("stat")=="OK"
            r["empty_anomaly"]=(r["data_count"]==0)
        elif name=="TWSE_LENDING":
            row=html_row_2330(text); r["row2330"]=row; exp=EXP[name]; r["exact_sha_match"]=sha==exp["sha"]; r["row_match"]=row==exp["row"]
            r["ok"]=r["exact_sha_match"] or r["row_match"]
        elif name=="TAIEX_DAILY":
            try:
                arr=json.loads(text)
                found=next((x for x in arr if isinstance(x,dict) and x.get("Date")=="1150916"),None)
                r["row"]=found
                r["ok"]=found==EXP[name]["row"]
            except Exception as e:
                r["ok"]=False
                r["parse_error"]=f"{type(e).__name__}:{e}"
                r["preview"]=text[:160]
        elif name=="ECB":
            r["ok"]=EXP[name]["needle"] in text
        elif name=="UST":
            i=text.find(EXP[name]["needle"]); seg=text[i:i+1800] if i>=0 else ""; r["target_found"]=i>=0
            r["vals_present"]=all(f">{v}<" in seg for v in EXP[name]["vals"]); r["ok"]=r["target_found"] and r["vals_present"]
        elif name=="VIX":
            r["ok"]=EXP[name]["needle"] in text
        results[name]=r
        print(json.dumps({"dataset":name,**r},ensure_ascii=False),flush=True)
        if not r["ok"]: fail.append(name)
    # Empty foreign hold is treated as independent anomaly even if source reproduces it.
    if results.get("TWSE_FOREIGN_HOLD",{}).get("empty_anomaly"):
        fail.append("TWSE_FOREIGN_HOLD_EMPTY_DATA")
    out={"target":TARGET,"policy":"official URLs only; no paid source; no bypass","results":results,"failures":sorted(set(fail)),"gate":"PASS" if not fail else "FAIL"}
    print(json.dumps(out,ensure_ascii=False,indent=2))
    if fail: sys.exit(2)
if __name__=="__main__": main()
