from __future__ import annotations
import http.client, json, re, sys, time, urllib.request, urllib.error
from datetime import date

UA="MarketDataDownloader-CI/0.15 (official open-data full-line qualification; no bypass)"
D=date(2026,9,16)
MAX_BYTES=20*1024*1024
TARGETS={
"TWSE_DAILY_K":[("twse_stock_day_all","https://openapi.twse.com.tw/v1/exchangeReport/STOCK_DAY_ALL","json",["Date"],False)],
"TPEX_DAILY_K":[("tpex_daily_k","https://www.tpex.org.tw/openapi/v1/tpex_mainboard_daily_close_quotes","json",["Date"],False)],
"SECURITY_MASTER":[
 ("twse_company_basic","https://openapi.twse.com.tw/v1/opendata/t187ap03_L","json",["公司代號"],False),
 ("tpex_company_basic","https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap03_O","json",[],False)],
"TAIEX_DAILY":[("twse_taiex_history","https://openapi.twse.com.tw/v1/indicesReport/MI_5MINS_HIST","json",[],True)],
"TPEX_INSTITUTIONAL":[("tpex_inst","https://www.tpex.org.tw/openapi/v1/tpex_3insti_daily_trading","json",["Date"],False)],
"TPEX_FOREIGN_HOLD":[("tpex_qfii","https://www.tpex.org.tw/openapi/v1/tpex_3insti_qfii","json",["Date"],False)],
"TPEX_MARGIN":[("tpex_margin","https://www.tpex.org.tw/openapi/v1/tpex_mainboard_margin_balance","json",["Date"],False)],
"TPEX_LENDING":[("tpex_sbl","https://www.tpex.org.tw/openapi/v1/tpex_margin_sbl","json",["Date"],False)],
"CORPORATE_ACTIONS":[
 ("twse_exright","https://openapi.twse.com.tw/v1/exchangeReport/TWT48U_ALL","json",[],False),
 ("tpex_exright","https://www.tpex.org.tw/openapi/v1/tpex_exright_prepost","json",[],False)],
"MONTHLY_REVENUE":[
 ("twse_revenue","https://openapi.twse.com.tw/v1/opendata/t187ap05_L","json",["資料年月"],False),
 ("tpex_revenue","https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap05_O","json",[],False)],
"FINANCIAL_STATEMENTS_EPS":[
 ("twse_income","https://openapi.twse.com.tw/v1/opendata/t187ap06_L_ci","json",[],False),
 ("tpex_income","https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap06_O_ci","json",[],False)],
"VALUATION_FINANCIAL_QUALITY":[
 ("twse_valuation","https://openapi.twse.com.tw/v1/exchangeReport/BWIBBU_ALL","json",[],False),
 ("tpex_valuation","https://www.tpex.org.tw/openapi/v1/tpex_mainboard_peratio_analysis","json",[],False),
 ("twse_quality","https://openapi.twse.com.tw/v1/opendata/t187ap17_L","json",[],False)],
"MATERIAL_INFO":[
 ("twse_material","https://openapi.twse.com.tw/v1/opendata/t187ap04_L","json",[],False),
 ("tpex_material","https://www.tpex.org.tw/openapi/v1/mopsfin_t187ap04_O","json",[],False)],
"TAIFEX_FUTURES_OI":[("taifex_fut_inst","https://openapi.taifex.com.tw/v1/MarketDataOfMajorInstitutionalTradersDetailsOfFuturesContractsBytheDate","json_or_csv",[],False)],
"TAIFEX_OPTIONS_INSTITUTIONAL":[("taifex_opt_inst","https://openapi.taifex.com.tw/v1/MarketDataOfMajorInstitutionalTradersDetailsOfOptionsContractsBytheDate","json_or_csv",[],False)],
"FX_RATES_VOL_COMMODITIES":[
 ("ecb","https://data-api.ecb.europa.eu/service/data/EXR/D.USD.EUR.SP00.A?startPeriod=2026-09-16&endPeriod=2026-09-16&format=csvdata","csv_or_xml",[],True),
 ("ust","https://home.treasury.gov/resource-center/data-chart-center/interest-rates/pages/xml?data=daily_treasury_yield_curve&field_tdr_date_value_month=202609","xml",["entry"],True),
 ("cboe","https://cdn.cboe.com/api/global/us_indices/daily_prices/VIX_History.csv","csv",["DATE","OPEN","HIGH","LOW","CLOSE"],True)],
"FINANCIAL_NEWS_EVENTS":[("fsc_rss","https://www.fsc.gov.tw/RSS/Messages?language=chinese&serno=201202290009","xml",["<item","<title"],False)]
}
BOUNDARIES=["TWSE_INSTITUTIONAL","TWSE_FOREIGN_HOLD","TWSE_MARGIN","TWSE_LENDING","GLOBAL_INDICES_FUTURES"]

def fetch_once(url, timeout=35):
    req=urllib.request.Request(url,headers={"User-Agent":UA,"Accept":"application/json,text/csv,application/xml,text/xml,*/*;q=0.5","Accept-Encoding":"identity","Connection":"close","Cache-Control":"no-cache","Pragma":"no-cache"})
    try:
        with urllib.request.urlopen(req,timeout=timeout) as r:
            expected=None
            raw_len=r.headers.get("Content-Length","") or ""
            if str(raw_len).isdigit(): expected=int(raw_len)
            chunks=[]; total=0
            try:
                while True:
                    part=r.read(262144)
                    if not part: break
                    chunks.append(part); total+=len(part)
                    if total>MAX_BYTES:
                        return False,"PAYLOAD_TOO_LARGE",0,""
            except http.client.IncompleteRead as e:
                if e.partial: total+=len(e.partial)
                return False,f"INCOMPLETE_READ:{total}/{expected}",total,""
            if expected is not None and total!=expected:
                return False,f"INCOMPLETE_READ:{total}/{expected}",total,""
            raw=b"".join(chunks)
            return True,int(getattr(r,"status",200)),len(raw),raw.decode("utf-8","replace")
    except (urllib.error.URLError, TimeoutError, OSError, http.client.IncompleteRead, ConnectionError) as e:
        return False,f"NETWORK_ERROR:{type(e).__name__}:{e}",0,""
    except Exception as e:
        return False,f"{type(e).__name__}:{e}",0,""

def fetch(ds,url):
    if ds!="TPEX_DAILY_K":
        ok,status,n,text=fetch_once(url,35)
        return ok,status,n,text,1
    backoff=(2,8,20,45)
    last=(False,"UNKNOWN",0,"",0)
    for attempt in range(1,6):
        ok,status,n,text=fetch_once(url,45 if attempt>=4 else 35)
        last=(ok,status,n,text,attempt)
        if ok: return last
        recoverable=str(status).startswith("INCOMPLETE_READ") or str(status).startswith("NETWORK_ERROR")
        if not recoverable or attempt>=5: return last
        time.sleep(backoff[attempt-1])
    return last

def date_ok(text):
    marks=(D.strftime("%Y-%m-%d"),D.strftime("%Y/%m/%d"),D.strftime("%Y%m%d"),D.strftime("%m/%d/%Y"),"1150916","115/09/16","115年09月16日")
    return any(x in text for x in marks)

def validate(kind,text,markers):
    s=text.lstrip()
    if kind=="json":
        try:
            obj=json.loads(text)
            if not isinstance(obj,(list,dict)) or not obj: return False,"EMPTY_JSON"
        except Exception: return False,"JSON_PARSE"
    elif kind=="json_or_csv":
        try:
            obj=json.loads(text)
            if not isinstance(obj,(list,dict)) or not obj: raise ValueError()
        except Exception:
            if not ("," in text[:8192] and "\n" in text): return False,"NOT_JSON_OR_CSV"
    elif kind=="csv":
        if not ("," in text[:8192] and "\n" in text): return False,"NOT_CSV"
    elif kind=="xml":
        low=s.lower()
        if not (low.startswith("<?xml") or "<rss" in low or "<feed" in low or "<entry" in low): return False,"NOT_XML"
    elif kind=="csv_or_xml":
        low=s.lower()
        if not (("," in text[:8192] and "\n" in text) or low.startswith("<?xml") or "<genericdata" in low or "<message:" in low): return False,"NOT_CSV_OR_XML"
    miss=[m for m in markers if m not in text]
    return (not miss, "OK" if not miss else "MISSING_MARKERS:"+",".join(miss))

def main():
    rows=[]; failures=[]
    for ds,comps in TARGETS.items():
        for name,url,kind,markers,needs_date in comps:
            ok,status,n,text,attempts=fetch(ds,url)
            if ok: ok,status=validate(kind,text,markers)
            if ok and needs_date and not date_ok(text):
                ok=False; status="DATE_EVIDENCE_MISSING"
            row={"dataset":ds,"component":name,"ok":ok,"status":status,"bytes":n,"attempts":attempts,"url":url}
            rows.append(row); print(json.dumps(row,ensure_ascii=False),flush=True)
            if not ok: failures.append(f"{ds}/{name}:{status}")
            time.sleep(1)
    out={"policy":"official open-data / OpenAPI only; no paid source; no CAPTCHA/WAF bypass","active_dataset_count":len(TARGETS),"boundary_dataset_count":len(BOUNDARIES),"boundary_datasets":BOUNDARIES,"component_count":len(rows),"failures":failures,"gate":"PASS" if not failures else "FAIL"}
    print(json.dumps(out,ensure_ascii=False,indent=2),flush=True)
    if failures: sys.exit(2)
if __name__=="__main__": main()
