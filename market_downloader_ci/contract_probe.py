from __future__ import annotations
import csv, hashlib, io, json, re, sys, urllib.request, urllib.error
from datetime import date

UA="MarketDataDownloader-CI/0.15 (open-data qualification; no bypass)"
MAX_BYTES=16*1024*1024

TARGETS={
"TPEX_DAILY_K":"https://www.tpex.org.tw/openapi/v1/tpex_mainboard_daily_close_quotes",
"TPEX_INSTITUTIONAL":"https://www.tpex.org.tw/openapi/v1/tpex_3insti_daily_trading",
"TPEX_FOREIGN_HOLD":"https://www.tpex.org.tw/openapi/v1/tpex_3insti_qfii",
"TPEX_MARGIN":"https://www.tpex.org.tw/openapi/v1/tpex_mainboard_margin_balance",
"TPEX_LENDING":"https://www.tpex.org.tw/openapi/v1/tpex_margin_sbl",
"TAIFEX_FUTURES_OI":"https://openapi.taifex.com.tw/v1/MarketDataOfMajorInstitutionalTradersDetailsOfFuturesContractsBytheDate",
"TAIFEX_OPTIONS_INSTITUTIONAL":"https://openapi.taifex.com.tw/v1/MarketDataOfMajorInstitutionalTradersDetailsOfOptionsContractsBytheDate",
}
TP_EX=set(k for k in TARGETS if k.startswith("TPEX_"))
TAI_FEX=set(TARGETS)-TP_EX

def fetch(url):
    req=urllib.request.Request(url,headers={
        "User-Agent":UA,"Accept":"application/json,text/csv,*/*;q=0.5",
        "Accept-Language":"zh-TW,zh;q=0.9,en;q=0.5",
        "Accept-Encoding":"identity","Connection":"close"})
    try:
        with urllib.request.urlopen(req,timeout=35) as r:
            raw=r.read(MAX_BYTES+1)
            if len(raw)>MAX_BYTES:
                return {"status":"PAYLOAD_TOO_LARGE","url":url,"http":getattr(r,"status",200)}
            return {"status":"HTTP_OK","url":url,"http":int(getattr(r,"status",200)),
                    "ctype":r.headers.get("Content-Type","") or "","raw":raw,
                    "bytes":len(raw),"sha256":hashlib.sha256(raw).hexdigest()}
    except urllib.error.HTTPError as e:
        return {"status":"HTTP_ERROR","url":url,"http":e.code,"error":str(e)}
    except Exception as e:
        return {"status":"NETWORK_ERROR","url":url,"error":f"{type(e).__name__}: {e}"}

def decode(raw):
    for enc in ("utf-8-sig","utf-8","cp950","big5"):
        try:return raw.decode(enc)
        except UnicodeDecodeError: pass
    return raw.decode("latin1","replace")

def parsed_rows(text):
    s=text.lstrip()
    if s.startswith("[") or s.startswith("{"):
        obj=json.loads(text)
        if isinstance(obj,list): return obj,"json"
        if isinstance(obj,dict):
            for k in ("data","aaData","rows"):
                if isinstance(obj.get(k),list): return obj[k],"json"
            for t in obj.get("tables") or []:
                if isinstance(t,dict) and isinstance(t.get("data"),list):
                    return t["data"],"json"
            return [obj],"json"
    rows=list(csv.reader(io.StringIO(text)))
    return rows,"csv"

def find_dates(rows):
    vals=[]
    for row in rows[:250]:
        if isinstance(row,dict):
            candidates=[v for k,v in row.items() if "date" in str(k).lower() or "日期" in str(k)]
        else:
            candidates=row[:4] if isinstance(row,list) else []
        for v in candidates:
            s=str(v or "").strip()
            m=re.search(r"(20\d{2})[-/]?(\d{2})[-/]?(\d{2})",s)
            if m:
                vals.append(f"{m.group(1)}-{m.group(2)}-{m.group(3)}"); continue
            m=re.search(r"(?<!\d)(1\d{2})[-/]?(\d{2})[-/]?(\d{2})(?!\d)",s)
            if m:
                vals.append(f"{int(m.group(1))+1911:04d}-{m.group(2)}-{m.group(3)}")
    return sorted(set(vals))

def probe(ds,url):
    r=fetch(url)
    if r["status"]!="HTTP_OK": return {"dataset":ds,**r}
    text=decode(r["raw"])
    try:
        rows,fmt=parsed_rows(text)
    except Exception as e:
        return {"dataset":ds,**{k:v for k,v in r.items() if k!="raw"},
                "status":"PARSE_ERROR","error":f"{type(e).__name__}: {e}"}
    if not rows:
        return {"dataset":ds,**{k:v for k,v in r.items() if k!="raw"},
                "status":"EMPTY","format":fmt,"rows":0}
    dates=find_dates(rows)
    return {"dataset":ds,**{k:v for k,v in r.items() if k!="raw"},
            "status":"DATA","format":fmt,"rows":len(rows),"observed_dates":dates[:8]}

def historical_policy(selected,observed,current_only=True,auto_fill=False,max_backscan=7):
    if selected==observed: return "EXACT_DATA"
    if not current_only: return "HISTORY_QUERY_REQUIRED"
    if auto_fill and observed < selected and 0 <= (selected-observed).days <= max_backscan:
        return "AUTO_FILL_PREVIOUS"
    return "HISTORICAL_AUTOMATION_BOUNDARY"

def main():
    out={"policy":{
        "network":"official OpenAPI / government-open-data linked endpoints only",
        "ordinary_site_history_probe":False,
        "captcha_bypass":False,
        "paid_source":False,
        "historical_current_only_terminal":"HISTORICAL_AUTOMATION_BOUNDARY",
    },"runs":[]}
    failures=[]
    observed_any=None
    for ds,url in TARGETS.items():
        r=probe(ds,url); out["runs"].append(r)
        print(json.dumps(r,ensure_ascii=False),flush=True)
        if r["status"]!="DATA":
            failures.append(f"{ds}:{r['status']}")
        if r.get("observed_dates") and observed_any is None:
            try: observed_any=date.fromisoformat(r["observed_dates"][-1])
            except Exception: pass
    # Model gates: strict wrong-day must never become DATA; auto-fill is explicit and bounded.
    selected=date(2026,9,15)
    if observed_any is not None:
        out["strict_history_policy"]=historical_policy(selected,observed_any,current_only=True,auto_fill=False)
        out["explicit_autofill_policy"]=historical_policy(selected,observed_any,current_only=True,auto_fill=True)
        if observed_any != selected and out["strict_history_policy"]!="HISTORICAL_AUTOMATION_BOUNDARY":
            failures.append("strict_historical_policy_not_boundary")
    out["gate"]="PASS" if not failures else "FAIL"; out["failures"]=failures
    print(json.dumps(out,ensure_ascii=False,indent=2),flush=True)
    if failures: sys.exit(2)

if __name__=="__main__": main()
