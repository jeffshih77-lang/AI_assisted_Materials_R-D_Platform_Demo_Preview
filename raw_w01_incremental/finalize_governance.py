#!/usr/bin/env python3
from __future__ import annotations
import hashlib, json, pathlib, sys
from datetime import datetime, timezone

root=pathlib.Path(sys.argv[1] if len(sys.argv)>1 else "out")
manifest_dir=root/"manifest"
packages=sorted((root/"packages").glob("TWSE_DAILY_K_*_OFFICIAL_RAW_V2.zip"))
if len(packages)!=1: raise SystemExit(f"expected exactly 1 package, found {len(packages)}")
pkg=packages[0]
summary=json.loads((manifest_dir/"SUMMARY.json").read_text(encoding="utf-8"))
if not summary.get("complete"): raise SystemExit("collector summary not complete")
meta_files=sorted(manifest_dir.glob("PACKAGE_MANIFEST_*.json"))
if len(meta_files)!=1: raise SystemExit("expected one package manifest")
meta=json.loads(meta_files[0].read_text(encoding="utf-8"))
events=[]
event_path=manifest_dir/"download_events.jsonl"
for line in event_path.read_text(encoding="utf-8").splitlines():
    if line.strip(): events.append(json.loads(line))
done={e["trade_date"]:e for e in events if e.get("status")=="DONE_LOCAL_RAW_VERIFIED"}
member_dates=[m["trade_date"] for m in meta["members"]]
if set(member_dates)!=set(done):
    raise SystemExit(f"event/member mismatch members={member_dates} events={sorted(done)}")
package_bytes=pkg.read_bytes(); package_sha=hashlib.sha256(package_bytes).hexdigest()
fetch_times=[done[d]["retrieved_at"] for d in member_dates]
rows=sum(int(m["rows"]) for m in meta["members"])
package_id=f"RAW-W01-TWSE-DK-INC-{member_dates[0].replace('-','')}-{member_dates[-1].replace('-','')}-{package_sha[:12]}"
created=datetime.now(timezone.utc).isoformat(timespec="seconds")
per_member=[]
for m in meta["members"]:
    e=done[m["trade_date"]]
    per_member.append({
        "trade_date":m["trade_date"],"path":m["path"],"rows":m["rows"],
        "raw_bytes_uncompressed":m["bytes"],"sha256_uncompressed":m["sha256"],
        "source_url":e["request_url"],"final_url":e["final_url"],"retrieved_at":e["retrieved_at"],
        "http_source_status":"HTTP_200_AND_PAYLOAD_VALIDATED","payload_date_validation":"EXACT_MATCH"
    })
control={
  "manifest_schema_version":"raw_incremental_manifest_v1",
  "package_id":package_id,"dataset_id":"TWSE_DAILY_K","source_id":"TWSE",
  "source_family":"TWSE_MI_INDEX","schema_family":"TWSE_MI_INDEX_ALLBUT0999",
  "schema_version":"TWSE_MI_INDEX_JSON_RAW_V2","market":"TWSE",
  "coverage_start":member_dates[0],"coverage_end":member_dates[-1],"historical_cutoff":"2026-09-17",
  "work_units_total":len(member_dates),"work_units_completed":len(member_dates),"work_units_failed":0,
  "raw_member_count":len(meta["members"]),"row_count":rows,
  "package_name":pkg.name,"package_bytes":len(package_bytes),"package_sha256":package_sha,
  "created_at":created,"fetch_started_at":min(fetch_times),"fetch_completed_at":max(fetch_times),
  "cloud_file_id":None,"cloud_verified_at":None,"supersedes":[],"superseded_by":None,
  "validation_result":"PASS_LOCAL_GITHUB__PENDING_CLOUD_READBACK","known_gaps":[],"anomalies":[],
  "raw_member_semantics":"gzip(exact TWSE HTTP JSON response bytes)",
  "sha256_scope":"uncompressed exact HTTP response bytes","members":per_member
}
receipt={
  "receipt_schema_version":"raw_receipt_v1","package_id":package_id,"work_id":"RAW-W01","dataset_id":"TWSE_DAILY_K",
  "acquisition_role":"FORMAL_RAW_INCREMENTAL_CANDIDATE","provider":"Taiwan Stock Exchange (TWSE)",
  "endpoint_template":"https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX?date={YYYYMMDD}&type=ALLBUT0999&response=json",
  "request_contract":{"type":"ALLBUT0999","response":"json","requested_date_must_equal_payload_date":True},
  "transport":{"runner":"GitHub-hosted Ubuntu","collector":"RAW-W01_TWSE_DAILY_K_GITHUB_COLLECTOR_V2.py","byte_preserving":True,"storage_compression":"gzip only"},
  "pit_lineage":{"source_trade_date_field":"TWSE payload date","market_timezone":"Asia/Taipei","retrieved_at_preserved":True,
                 "available_at":None,"available_at_status":"UNKNOWN_RAW_LAYER__DO_NOT_GUESS__DERIVE_CONSERVATIVELY_DOWNSTREAM",
                 "identity_mapping_status":"NOT_APPLIED_RAW_LAYER"},
  "previous_coverage_boundary":"2026-09-17","new_coverage_start":member_dates[0],"new_coverage_end":member_dates[-1],
  "non_overlap_incremental":True,"package_name":pkg.name,"package_bytes":len(package_bytes),"package_sha256":package_sha,
  "members":per_member,"created_at":created
}
coverage={
  "coverage_schema_version":"raw_coverage_delta_v1","package_id":package_id,"dataset_id":"TWSE_DAILY_K","market":"TWSE",
  "previous_authorized_recent_end":"2026-09-17","candidate_extension_start":member_dates[0],"candidate_extension_end":member_dates[-1],
  "candidate_trade_dates":member_dates,"completed_units":len(member_dates),"failed_units":0,
  "status":"GITHUB_LOCAL_VERIFIED_PENDING_DRIVE_CLOUD_VERIFIED","cloud_authority":False,
  "rule":"Do not merge into central authority until package + sidecars are uploaded and Drive readback verifies bytes/SHA."
}
for name,obj in [("RAW-W01_TWSE_DAILY_K_INCREMENTAL_MANIFEST_20260918_20260918.json",control),
                 ("RAW-W01_TWSE_DAILY_K_INCREMENTAL_RECEIPT_20260918_20260918.json",receipt),
                 ("RAW-W01_TWSE_DAILY_K_COVERAGE_DELTA_20260918_20260918.json",coverage)]:
    (manifest_dir/name).write_text(json.dumps(obj,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print(json.dumps({"package":str(pkg),"sha256":package_sha,"bytes":len(package_bytes),"package_id":package_id,"rows":rows,"dates":member_dates},ensure_ascii=False))
