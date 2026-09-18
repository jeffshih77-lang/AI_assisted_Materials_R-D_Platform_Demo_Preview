from __future__ import annotations
import hashlib, json, re, sys, time, urllib.request, urllib.error
from datetime import date

UA="MarketDataDownloader-CI/0.15 (official-source qualification; no bypass)"
MAX_BYTES=16*1024*1024
BLOCK_STRONG=("access denied","request blocked","verify you are human","are you human",
              "attention required! | cloudflare","<title>just a moment","cf-chl-",
              "challenge-platform","hcaptcha.com/1/api.js","g-recaptcha-response")

TARGETS={
"TPEX_DAILY_K":{"kind":"json_exact","urls":[
  "https://www.tpex.org.tw/web/stock/aftertrading/otc_quotes_no1430/stk_wn1430_result.php?l=zh-tw&d={roc}&se=AL",
  "https://www.tpex.org.tw/web/stock/aftertrading/daily_close_quotes/stk_quote_result.php?l=zh-tw&o=json&d={roc}&s=0,asc,0"]},
"TPEX_INSTITUTIONAL":{"kind":"json_exact","min_cols":20,"urls":[
  "https://www.tpex.org.tw/www/zh-tw/insti/dailyTrade?type=Daily&sect=EW&date={roc}&id=&response=json"]},
"TPEX_FOREIGN_HOLD":{"kind":"delimited_exact","markers":["代號"],"urls":[
  "https://www.tpex.org.tw/web/stock/3insti/qfii/qfii_result.php?l=zh-tw&d={roc}&o=data"]},
"TPEX_MARGIN":{"kind":"json_exact","min_cols":8,"urls":[
  "https://www.tpex.org.tw/web/stock/margin_trading/margin_balance/margin_bal_result.php?l=zh-tw&o=json&d={roc}"]},
"TPEX_LENDING":{"kind":"json_exact","min_cols":6,"urls":[
  "https://www.tpex.org.tw/web/stock/margin_trading/loan_sbl/margin_sbl_result.php?l=zh-tw&d={roc}&o=json"]},
"TAIFEX_FUTURES_OI":{"kind":"html_exact","markers":["未平倉"],"urls":[
  "https://www.taifex.com.tw/cht/3/futContractsDate?queryDate={iso}"]},
"TAIFEX_OPTIONS_INSTITUTIONAL":{"kind":"html_exact","markers":["選擇權","未平倉"],"urls":[
  "https://www.taifex.com.tw/cht/3/optContractsDate?queryDate={iso}"]},
}

def fmt(d): return {"iso":d.strftime("%Y/%m/%d"),"roc":f"{d.year-1911:03d}/{d.month:02d}/{d.day:02d}"}
def date_markers(d):
    roc=d.year-1911
    return (d.strftime("%Y/%m/%d"),d.strftime("%Y-%m-%d"),d.strftime("%Y%m%d"),
            f"{roc:03d}/{d.month:02d}/{d.day:02d}",f"{roc}年{d.month:02d}月{d.day:02d}日")
def has_date(text,d):
    flat=text.replace(" ","")
    return any(x.replace(" ","") in flat for x in date_markers(d))
def blocked(text):
    low=(text or "").lower()
    if any(x in low for x in BLOCK_STRONG): return True
    if len(low)<200000 and ("captcha" in low or "cloudflare" in low):
        if any(x in low for x in ("challenge","blocked","security check","human verification")): return True
    return False
def parse_date(v):
    s=re.sub(r"\D","",str(v or ""))
    if len(s)==7: return date(int(s[:3])+1911,int(s[3:5]),int(s[5:7]))
    if len(s)==8 and int(s[:4])>=1912: return date(int(s[:4]),int(s[4:6]),int(s[6:8]))
    return None
def json_dates(obj):
    out=[]
    def add(v):
        d=parse_date(v)
        if d and d not in out: out.append(d)
    if isinstance(obj,dict):
        for k in ("date","Date","reportDate","dataDate","queryDate"): add(obj.get(k))
        for t in obj.get("tables") or []:
            if isinstance(t,dict):
                for k in ("date","Date","reportDate","dataDate"): add(t.get(k))
    elif isinstance(obj,list):
        for row in obj[:100]:
            if isinstance(row,dict):
                for k in ("date","Date","reportDate","dataDate"): add(row.get(k))
    return out
def json_rows(obj):
    if isinstance(obj,dict):
        for t in obj.get("tables") or []:
            if isinstance(t,dict) and isinstance(t.get("data"),list): return t["data"]
        for k in ("aaData","data"):
            if isinstance(obj.get(k),list): return obj[k]
    if isinstance(obj,list): return obj
    return []
def fetch(url):
    req=urllib.request.Request(url,headers={"User-Agent":UA,"Accept":"application/json,text/csv,text/html,*/*;q=0.5",
      "Accept-Language":"zh-TW,zh;q=0.9,en;q=0.5","Accept-Encoding":"identity","Connection":"close"})
    try:
        with urllib.request.urlopen(req,timeout=35) as r:
            raw=r.read(MAX_BYTES+1)
            if len(raw)>MAX_BYTES: return {"status":"PAYLOAD_TOO_LARGE","url":url,"http":getattr(r,"status",200)}
            return {"status":"HTTP_OK","url":url,"http":int(getattr(r,"status",200)),
                    "ctype":r.headers.get("Content-Type","") or "","raw":raw,"bytes":len(raw),
                    "sha256":hashlib.sha256(raw).hexdigest()}
    except urllib.error.HTTPError as e:
        return {"status":"ACCESS_LIMITED" if e.code in (401,403,429) else "HTTP_ERROR","url":url,"http":e.code,"error":str(e)}
    except Exception as e:
        return {"status":"NETWORK_ERROR","url":url,"error":f"{type(e).__name__}: {e}"}
def decode(raw):
    for enc in ("utf-8-sig","utf-8","cp950","big5"):
        try:return raw.decode(enc)
        except UnicodeDecodeError: pass
    return raw.decode("latin1","replace")
def slim(res): return {k:v for k,v in res.items() if k!="raw"}
def validate(spec,d,res):
    if res["status"]!="HTTP_OK": return res
    text=decode(res["raw"])
    if blocked(text): return {**slim(res),"status":"SOURCE_BLOCKED","preview_hash":hashlib.sha256(text[:4096].encode("utf-8","replace")).hexdigest()}
    try:
        if spec["kind"]=="json_exact":
            obj=json.loads(text); dates=json_dates(obj); rows=json_rows(obj)
            if dates and any(x!=d for x in dates): return {**slim(res),"status":"WRONG_DATE","dates":[x.isoformat() for x in dates]}
            if not dates and not has_date(text,d): return {**slim(res),"status":"DATE_UNPROVEN"}
            if not rows: return {**slim(res),"status":"NO_DATA","rows":0}
            m=spec.get("min_cols",1)
            if m>1 and any(isinstance(r,list) and len(r)<m for r in rows[:20]): return {**slim(res),"status":"SCHEMA_MISMATCH","rows":len(rows)}
            return {**slim(res),"status":"DATA","rows":len(rows)}
        if spec["kind"]=="delimited_exact":
            if not has_date(text,d): return {**slim(res),"status":"DATE_UNPROVEN"}
            if not any(x in text[:8192] for x in spec.get("markers",[])): return {**slim(res),"status":"SCHEMA_MISMATCH"}
            return {**slim(res),"status":"DATA"}
        if spec["kind"]=="html_exact":
            if not has_date(text,d): return {**slim(res),"status":"DATE_UNPROVEN"}
            if "<table" not in text.lower(): return {**slim(res),"status":"SCHEMA_MISMATCH"}
            if not all(x in text for x in spec.get("markers",[])): return {**slim(res),"status":"SCHEMA_MISMATCH"}
            return {**slim(res),"status":"DATA"}
    except json.JSONDecodeError:
        return {**slim(res),"status":"CONTENT_TYPE_MISMATCH","preview_hash":hashlib.sha256(text[:4096].encode()).hexdigest()}
    return {**slim(res),"status":"UNRECOGNIZED"}
def probe_one(ds,d):
    attempts=[]
    for tmpl in TARGETS[ds]["urls"]:
        r=validate(TARGETS[ds],d,fetch(tmpl.format(**fmt(d)))); attempts.append(slim(r))
        if r["status"] in ("DATA","NO_DATA"): return {"dataset":ds,"date":d.isoformat(),"status":r["status"],"attempts":attempts}
        time.sleep(1)
    return {"dataset":ds,"date":d.isoformat(),"status":"FAILED","attempts":attempts}
def main():
    out={"policy":"official-only; ordinary GET only; no captcha bypass; no paid source","runs":[]}; failures=[]
    for d in (date(2026,9,15),date(2026,9,16)):
        for ds in TARGETS:
            r=probe_one(ds,d); out["runs"].append(r); print(json.dumps(r,ensure_ascii=False),flush=True)
            if r["status"]!="DATA": failures.append(f"{ds}@{d}:{r['status']}")
            time.sleep(1)
    b=probe_one("TPEX_DAILY_K",date(2026,9,13)); out["boundary"]=b
    if b["status"] not in ("NO_DATA","FAILED"): failures.append("boundary_unexpected:"+b["status"])
    out["gate"]="PASS" if not failures else "FAIL"; out["failures"]=failures
    print(json.dumps(out,ensure_ascii=False,indent=2),flush=True)
    if failures: sys.exit(2)
if __name__=="__main__": main()
