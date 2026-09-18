from __future__ import annotations
import csv,hashlib,io,json,re,time,urllib.request
UA="MarketDataDownloader-TargetedVerify/0.15"
T86="https://www.twse.com.tw/rwd/zh/fund/T86?date=20260916&selectType=ALL&response=csv"
Q="https://www.twse.com.tw/rwd/zh/fund/MI_QFIIS?date=20260916&response=json&selectType={}"
EXPECTED_DATA_DIGEST="e78c8ed7a1dee1019b90ddc6cc0a4aed5e08dfc27b5e8b0576e128b988c03fc1"
def fetch(url):
    req=urllib.request.Request(url,headers={"User-Agent":UA,"Accept":"*/*","Accept-Encoding":"identity","Connection":"close"})
    with urllib.request.urlopen(req,timeout=45) as r:return r.read()
def decode(raw):
    for enc in ("cp950","utf-8-sig","utf-8"):
        try:return raw.decode(enc)
        except:pass
    return raw.decode("latin1","replace")
def code(x):
    x=x.strip()
    if x.startswith('="') and x.endswith('"'):x=x[2:-1]
    return x
raw=fetch(T86); text=decode(raw); rows=list(csv.reader(io.StringIO(text)))
data=[]
for r in rows:
    if not r: continue
    c=code(r[0])
    if not re.fullmatch(r"[0-9A-Z]{4,10}",c): continue
    rr=[x.strip() for x in r]; rr[0]=c
    if len(rr)>1:rr[1]=" ".join(rr[1].split())
    data.append(rr)
data.sort(key=lambda r:(r[0],json.dumps(r,ensure_ascii=False)))
dg=hashlib.sha256(json.dumps(data,ensure_ascii=False,separators=(",",":")).encode()).hexdigest()
print(json.dumps({"dataset":"TWSE_INSTITUTIONAL","data_rows":len(data),"data_digest":dg,"matches_runtime":dg==EXPECTED_DATA_DIGEST},ensure_ascii=False),flush=True)
for sel in ("ALL","ALLBUT0999","01","02","03","04","05","06","07","08","09","10","11","12","13","14","15","16","17","18","19","20","21","22","23","24","25","26","27","28","29","30"):
    try:
        b=fetch(Q.format(sel)); obj=json.loads(b.decode("utf-8-sig"))
        out={"selectType":sel,"date":obj.get("date"),"stat":obj.get("stat"),"total":obj.get("total"),"data_count":len(obj.get("data") or []),"bytes":len(b)}
    except Exception as e: out={"selectType":sel,"error":f"{type(e).__name__}:{e}"}
    print(json.dumps(out,ensure_ascii=False),flush=True)
    if sel in ("ALL","ALLBUT0999","01","02"): time.sleep(1)
