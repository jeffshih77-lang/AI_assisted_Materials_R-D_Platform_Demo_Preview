#!/usr/bin/env python3
"""RAW-W01 TWSE_DAILY_K GitHub-hosted collector (free-runner friendly).

Downloads exact TWSE MI_INDEX JSON response bytes for frozen market x trading-day
work units, validates the daily security table, stores gzip(exact bytes), computes
SHA-256 over uncompressed bytes, and packages one shard per invocation.

No normalization/reconstruction/zero-fill is performed.
"""
from __future__ import annotations
import argparse, csv, datetime as dt, gzip, hashlib, json, os, random, sys, time
from pathlib import Path
import urllib.error, urllib.parse, urllib.request, zipfile

BASE_URL = "https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX"
REFERER = "https://www.twse.com.tw/zh/trading/historical/mi-index.html"
DATASET_ID = "TWSE_DAILY_K"
SOURCE_FAMILY = "TWSE_MI_INDEX_ALLBUT0999"
SCHEMA_FAMILY = "TWSE_MI_INDEX_JSON_RAW_V2"


def now_utc(): return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
def sha256_bytes(b: bytes): return hashlib.sha256(b).hexdigest()
def atomic_write(p: Path, b: bytes):
    p.parent.mkdir(parents=True, exist_ok=True); t=p.with_name(p.name+f".{os.getpid()}.part"); t.write_bytes(b); os.replace(t,p)
def atomic_gzip(p: Path, b: bytes):
    p.parent.mkdir(parents=True, exist_ok=True); t=p.with_name(p.name+f".{os.getpid()}.part")
    with gzip.open(t,"wb",compresslevel=6) as f: f.write(b)
    os.replace(t,p)
def append_jsonl(p: Path, obj: dict):
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open("a",encoding="utf-8",newline="\n") as f:
        f.write(json.dumps(obj,ensure_ascii=False,sort_keys=True)+"\n"); f.flush(); os.fsync(f.fileno())

def url_for(ymd: str):
    return BASE_URL+"?"+urllib.parse.urlencode({"date":ymd,"type":"ALLBUT0999","response":"json"})

def validate_payload(payload: bytes, ymd: str):
    obj=json.loads(payload)
    if obj.get("stat")!="OK": raise ValueError(f"stat != OK: {obj.get('stat')!r}")
    if str(obj.get("date",""))!=ymd: raise ValueError(f"date mismatch expected={ymd} got={obj.get('date')!r}")
    target=None
    for t in obj.get("tables") or []:
        fields=t.get("fields") or []
        if "證券代號" in fields and "收盤價" in fields:
            target=t; break
    if target is None: raise ValueError("daily security table missing")
    rows=target.get("data") or []
    if not rows: raise ValueError("daily security table empty")
    width=len(target.get("fields") or [])
    bad=sum(1 for r in rows if len(r)!=width)
    if bad: raise ValueError(f"row width mismatch rows={bad}")
    return len(rows)

def fetch_day(ymd: str, attempts: int, retry_wait: float):
    url=url_for(ymd); last=None
    for a in range(1,attempts+1):
        try:
            req=urllib.request.Request(url,headers={
                "User-Agent":"MarketData-RAW-W01-GHA/2.0",
                "Accept":"application/json,text/plain,*/*",
                "Referer":REFERER,"Cache-Control":"no-cache"})
            with urllib.request.urlopen(req,timeout=90) as r:
                status=getattr(r,"status",200); payload=r.read(); final=r.geturl()
            if status!=200: raise RuntimeError(f"HTTP {status}")
            rows=validate_payload(payload,ymd)
            return payload,final,rows
        except (OSError,urllib.error.URLError,urllib.error.HTTPError,json.JSONDecodeError,ValueError,RuntimeError) as e:
            last=e
            if a==attempts: break
            s=min(retry_wait*(2**(a-1)),90)+random.uniform(0,.8)
            print(f"[retry {a}/{attempts}] {ymd}: {e}; sleep={s:.1f}s",flush=True); time.sleep(s)
    raise RuntimeError(f"{ymd}: fetch/validation failed after {attempts} attempts: {last}")

def load_units(p: Path, year: int|None, phase: str|None):
    with p.open("r",encoding="utf-8-sig",newline="") as f: rows=list(csv.DictReader(f))
    req={"work_id","dataset_id","market","trade_date","phase"}
    if not rows or not req.issubset(rows[0]): raise ValueError("work-unit CSV schema mismatch")
    out=[]
    for r in rows:
        if r["dataset_id"]!=DATASET_ID or r["market"]!="TWSE": continue
        if year is not None and int(r["trade_date"][:4])!=year: continue
        if phase is not None and r.get("phase")!=phase: continue
        ymd=r["trade_date"].replace("-","")
        if len(ymd)!=8 or not ymd.isdigit(): raise ValueError(f"bad date {r['trade_date']!r}")
        out.append({**r,"ymd":ymd})
    out.sort(key=lambda r:r["ymd"])
    if not out: raise ValueError("selected shard has zero work units")
    return out

def raw_path(root:Path,ymd:str): return root/"raw"/"twse"/"daily_all"/ymd[:4]/ymd[4:6]/f"{ymd}.json.gz"
def read_valid(p:Path,ymd:str):
    if not p.exists(): return None
    try:
        payload=gzip.open(p,"rb").read(); rows=validate_payload(payload,ymd)
        return {"rows":rows,"sha256":sha256_bytes(payload),"bytes":len(payload)}
    except Exception: return None

def package_shard(root:Path, units:list[dict], scope:Path, manifest:Path):
    start,end=units[0]["ymd"],units[-1]["ymd"]
    name=f"TWSE_DAILY_K_{start}_{end}_OFFICIAL_RAW_V2.zip"
    pkg=root/"packages"/name; pkg.parent.mkdir(parents=True,exist_ok=True)
    members=[]
    for u in units:
        p=raw_path(root,u["ymd"]); info=read_valid(p,u["ymd"])
        if info is None: raise RuntimeError(f"cannot package invalid/missing {u['ymd']}")
        members.append({"trade_date":u["trade_date"],"path":p.relative_to(root).as_posix(),**info})
    scope_subset=root/"manifest"/f"scope_{start}_{end}.csv"
    with scope.open("r",encoding="utf-8-sig",newline="") as f: rdr=csv.DictReader(f); fields=rdr.fieldnames or []
    with scope_subset.open("w",encoding="utf-8-sig",newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields); w.writeheader(); selected={u["trade_date"] for u in units}
        with scope.open("r",encoding="utf-8-sig",newline="") as src:
            for r in csv.DictReader(src):
                if r.get("trade_date") in selected: w.writerow(r)
    meta={"schema":"raw_w01_twse_daily_k_package_v2","created_at":now_utc(),"dataset_id":DATASET_ID,
          "source_family":SOURCE_FAMILY,"schema_family":SCHEMA_FAMILY,"coverage_start":units[0]["trade_date"],
          "coverage_end":units[-1]["trade_date"],"work_units":len(units),"raw_member_format":"gzip(exact TWSE HTTP JSON response bytes)",
          "sha256_scope":"uncompressed exact HTTP response bytes","members":members}
    meta_path=root/"manifest"/f"PACKAGE_MANIFEST_{start}_{end}.json"
    atomic_write(meta_path,json.dumps(meta,ensure_ascii=False,indent=2).encode())
    tmp=pkg.with_name(pkg.name+".part")
    with zipfile.ZipFile(tmp,"w",compression=zipfile.ZIP_STORED,allowZip64=True) as z:
        for m in members: z.write(root/m["path"],m["path"])
        z.write(scope_subset,f"manifest/{scope_subset.name}")
        z.write(meta_path,f"manifest/{meta_path.name}")
        if manifest.exists(): z.write(manifest,"manifest/download_events.jsonl")
    os.replace(tmp,pkg)
    return pkg,meta_path,sha256_bytes(pkg.read_bytes()),pkg.stat().st_size

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--work-units",required=True,type=Path); ap.add_argument("--output-root",required=True,type=Path)
    g=ap.add_mutually_exclusive_group(required=True); g.add_argument("--year",type=int); g.add_argument("--phase",choices=["BRIDGE","HISTORICAL"])
    ap.add_argument("--attempts",type=int,default=4); ap.add_argument("--retry-wait",type=float,default=8); ap.add_argument("--min-delay",type=float,default=.8); ap.add_argument("--max-delay",type=float,default=1.4)
    ap.add_argument("--abort-after-consecutive-failures",type=int,default=3); ap.add_argument("--package",action="store_true")
    a=ap.parse_args(); root=a.output_root.resolve(); root.mkdir(parents=True,exist_ok=True)
    units=load_units(a.work_units,a.year,a.phase); manifest=root/"manifest"/"download_events.jsonl"
    done=skipped=failed=0; streak=0; failures=[]
    for i,u in enumerate(units,1):
        ymd=u["ymd"]; p=raw_path(root,ymd); info=read_valid(p,ymd)
        if info:
            skipped+=1; print(f"[{i}/{len(units)}] SKIP_VALID {ymd}",flush=True); continue
        try:
            payload,final,rows=fetch_day(ymd,a.attempts,a.retry_wait); digest=sha256_bytes(payload); atomic_gzip(p,payload)
            rb=gzip.open(p,"rb").read()
            if rb!=payload or sha256_bytes(rb)!=digest or validate_payload(rb,ymd)!=rows: raise RuntimeError("immutable readback mismatch")
            rec={"work_id":"RAW-W01","dataset_id":DATASET_ID,"trade_date":u["trade_date"],"phase":u.get("phase"),"status":"DONE_LOCAL_RAW_VERIFIED",
                 "request_url":url_for(ymd),"final_url":final,"retrieved_at":now_utc(),"rows":rows,"raw_bytes_uncompressed":len(payload),"sha256_uncompressed":digest,
                 "relative_path":p.relative_to(root).as_posix(),"old_manifest_rows":u.get("old_manifest_rows") or None,"old_manifest_sha256_uncompressed":u.get("old_manifest_sha256_uncompressed") or None}
            append_jsonl(manifest,rec); done+=1; streak=0; print(f"[{i}/{len(units)}] DONE {ymd} rows={rows} sha={digest[:12]}",flush=True)
        except Exception as e:
            failed+=1; streak+=1; rec={"work_id":"RAW-W01","dataset_id":DATASET_ID,"trade_date":u["trade_date"],"status":"FAILED_SOURCE_OR_VALIDATION","failed_at":now_utc(),"error":repr(e),"request_url":url_for(ymd)}
            append_jsonl(manifest,rec); failures.append(rec); print(f"[{i}/{len(units)}] FAIL {ymd}: {e}",file=sys.stderr,flush=True)
            if streak>=a.abort_after_consecutive_failures: break
        time.sleep(random.uniform(a.min_delay,a.max_delay))
    valid=sum(read_valid(raw_path(root,u["ymd"]),u["ymd"]) is not None for u in units); complete=valid==len(units)
    summary={"schema":"raw_w01_twse_daily_k_summary_v2","generated_at":now_utc(),"selected_year":a.year,"selected_phase":a.phase,"scope_units":len(units),"done_this_run":done,"skipped_valid":skipped,"failed":failed,"valid_units_total":valid,"complete":complete,"failures":failures}
    summary_path=root/"manifest"/"SUMMARY.json"; atomic_write(summary_path,json.dumps(summary,ensure_ascii=False,indent=2).encode())
    if not complete: return 2
    if a.package:
        pkg,meta,sha,n=package_shard(root,units,a.work_units,manifest)
        print(json.dumps({"package":str(pkg),"package_manifest":str(meta),"sha256":sha,"bytes":n},ensure_ascii=False),flush=True)
    return 0

if __name__=="__main__": raise SystemExit(main())
