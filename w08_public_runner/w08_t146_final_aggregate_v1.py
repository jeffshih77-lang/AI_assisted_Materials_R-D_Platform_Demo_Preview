import datetime as dt, gzip, hashlib, io, json, os, pathlib, time, urllib.error, urllib.request, zipfile

REPO=os.environ.get('GITHUB_REPOSITORY','jeffshih77-lang/AI_assisted_Materials_R-D_Platform_Demo_Preview')
TOKEN=os.environ['GITHUB_TOKEN']
SOURCE_RUN=34694385853
SEGMENTS=((85,87),(88,90),(91,93),(94,96),(97,99),(100,102),(103,105),(106,108),(109,111),(112,114),(115,115))
EXPECTED_MONTHS=[144]*10+[48]
UA='W08T146Finalizer/1.0'
OUT=pathlib.Path('out_w08_t146_final'); OUT.mkdir(exist_ok=True)

def now(): return dt.datetime.now(dt.timezone.utc).isoformat().replace('+00:00','Z')
def sha(b): return hashlib.sha256(b).hexdigest()
def api(path):
    req=urllib.request.Request('https://api.github.com'+path,headers={'Authorization':f'Bearer {TOKEN}','Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28','User-Agent':UA})
    with urllib.request.urlopen(req,timeout=120) as r:return json.loads(r.read())
def wait_run():
    while True:
        d=api(f'/repos/{REPO}/actions/runs/{SOURCE_RUN}')
        print(json.dumps({'wait_run':SOURCE_RUN,'status':d.get('status'),'conclusion':d.get('conclusion'),'at':now()}),flush=True)
        if d.get('status')=='completed':
            if d.get('conclusion')!='success': raise RuntimeError(f'source_run_not_success {d.get("conclusion")}')
            return
        time.sleep(30)
def list_artifacts():
    out=[]; page=1
    while True:
        d=api(f'/repos/{REPO}/actions/runs/{SOURCE_RUN}/artifacts?per_page=100&page={page}')
        a=d.get('artifacts',[]); out.extend(a)
        if len(a)<100: return out
        page+=1
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl): return None
def download(a):
    req=urllib.request.Request(a['archive_download_url'],headers={'Authorization':f'Bearer {TOKEN}','Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28','User-Agent':UA})
    op=urllib.request.build_opener(NoRedirect); loc=None
    try:
        with op.open(req,timeout=120) as r:
            if r.status in (301,302,303,307,308):loc=r.headers.get('Location')
            else:return r.read()
    except urllib.error.HTTPError as e:
        if e.code not in (301,302,303,307,308):raise
        loc=e.headers.get('Location')
    if not loc: raise RuntimeError('artifact_location_missing')
    with urllib.request.urlopen(urllib.request.Request(loc,headers={'User-Agent':UA}),timeout=240) as r:return r.read()
def read_zip(blob):
    with zipfile.ZipFile(io.BytesIO(blob)) as z:return {n:z.read(n) for n in z.namelist() if not n.endswith('/')}

def verify_segment(seg,a,blob):
    outer=read_zip(blob)
    infos=[(n,b) for n,b in outer.items() if n.endswith('PACKAGE_INFO.json')]
    inners=[(n,b) for n,b in outer.items() if n.endswith('.zip') and 'RAW-W08_MOPS_T146_FORMAL_RAW_SEG' in n]
    if len(infos)!=1 or len(inners)!=1: raise RuntimeError(f'outer_members seg={seg} infos={len(infos)} inners={len(inners)}')
    info=json.loads(infos[0][1]); inner_name,inner=inners[0]
    if info.get('sha256')!=sha(inner) or info.get('bytes')!=len(inner): raise RuntimeError(f'package_info_mismatch seg={seg}')
    z=read_zip(inner)
    cov=json.loads(z['COVERAGE.json']); man=json.loads(z['MANIFEST.json'])
    ys,ye=SEGMENTS[seg]
    if cov.get('segment')!=seg or cov.get('roc_year_start')!=ys or cov.get('roc_year_end')!=ye: raise RuntimeError(f'coverage_segment_mismatch {seg}')
    if cov.get('monthly_target_count')!=EXPECTED_MONTHS[seg]: raise RuntimeError(f'target_count_mismatch {seg} {cov.get("monthly_target_count")}')
    if cov.get('failure_count')!=0 or cov.get('status')!='FORMAL_RAW_SEGMENT_COMPLETE': raise RuntimeError(f'segment_failed {seg}')
    if man.get('failures'): raise RuntimeError(f'manifest_failures {seg}')
    records=man.get('records',[])
    keys=[]
    for r in records:
        stem=f"{r['market']}_{r['start']}_{r['end']}"
        req=z[r['request_file']]; raw=z[r['response_file']]; gz=z[r['gzip_file']]; meta=z[r['meta_file']]
        if sha(req)!=r['request_sha256'] or sha(raw)!=r['response_sha256'] or sha(gz)!=r['gzip_sha256']: raise RuntimeError(f'record_sha_mismatch {seg} {stem}')
        if gzip.decompress(gz)!=raw or not r.get('gzip_roundtrip'): raise RuntimeError(f'gzip_roundtrip {seg} {stem}')
        m=json.loads(meta)
        if m.get('request_sha256')!=r['request_sha256'] or m.get('response_sha256')!=r['response_sha256']: raise RuntimeError(f'meta_mismatch {seg} {stem}')
        keys.append((r['market'],r['start'],r['end'],r.get('depth')))
    if len(keys)!=len(set(keys)): raise RuntimeError(f'intra_segment_collision {seg}')
    return {
      'segment':seg,'roc_start':ys,'roc_end':ye,'artifact_id':a['id'],'artifact_name':a['name'],'artifact_digest':a.get('digest'),
      'artifact_bytes':len(blob),'formal_zip_name':inner_name,'formal_zip_bytes':len(inner),'formal_zip_sha256':sha(inner),
      'monthly_target_count':cov['monthly_target_count'],'capture_count':cov['capture_count'],'api_200_captures':cov['api_200_captures'],
      'api_406_captures':cov['api_406_captures'],'row_count':cov['row_count_across_200_responses'],'anomaly_count':cov['anomaly_count'],
      'retry_event_count':cov['retry_event_count'],'failure_count':cov['failure_count'],'record_keys':keys
    }

wait_run()
arts=list_artifacts()
byseg={}
for a in arts:
    n=a.get('name','')
    if n.startswith('W08_T146_FORMAL_V8_SEG'):
        try: seg=int(n.split('SEG',1)[1].split('_',1)[0])
        except: continue
        if seg in byseg: raise RuntimeError(f'duplicate_artifact_segment {seg}')
        byseg[seg]=a
if set(byseg)!=set(range(11)): raise RuntimeError(f'artifact_segments_mismatch have={sorted(byseg)}')
segments=[]; global_keys=set()
for seg in range(11):
    a=byseg[seg]; blob=download(a); print(json.dumps({'verify_segment':seg,'artifact':a['id'],'bytes':len(blob)}),flush=True)
    s=verify_segment(seg,a,blob)
    keys=s.pop('record_keys')
    overlap=global_keys.intersection(keys)
    if overlap: raise RuntimeError(f'inter_segment_collision seg={seg} sample={list(overlap)[:3]}')
    global_keys.update(keys); segments.append(s)
summary={
 'schema':'w08_t146_final_reference_aggregate_v1','work_unit_id':'W08-RAW-MOPS-STRUCTURED-T146','formal_raw':True,
 'status':'FORMAL_RAW_COMPLETE','source_run_id':SOURCE_RUN,'segment_count':11,'roc_year_start':85,'roc_year_end':115,
 'monthly_target_count':sum(x['monthly_target_count'] for x in segments),'capture_count':sum(x['capture_count'] for x in segments),
 'api_200_captures':sum(x['api_200_captures'] for x in segments),'api_406_captures':sum(x['api_406_captures'] for x in segments),
 'row_count':sum(x['row_count'] for x in segments),'anomaly_count':sum(x['anomaly_count'] for x in segments),
 'retry_event_count':sum(x['retry_event_count'] for x in segments),'failure_count':sum(x['failure_count'] for x in segments),
 'unique_capture_keys':len(global_keys),'endpoint':'https://mops.twse.com.tw/mops/api/t146sb10','segments':segments,'generated_at':now()
}
if summary['monthly_target_count']!=1488 or summary['failure_count']!=0: raise RuntimeError('aggregate_gate_failed')
ledger=(json.dumps(summary,ensure_ascii=False,indent=2,sort_keys=True)+'\n').encode()
(OUT/'T146_FINAL_REFERENCE_LEDGER.json').write_bytes(ledger)
# deterministic small reference package; source RAW remains in immutable 11 artifacts
pkg=OUT/'RAW-W08_MOPS_T146_FORMAL_RAW_REFERENCE_AGGREGATE_ROC85_115_20260912.zip'
with zipfile.ZipFile(pkg,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
    zi=zipfile.ZipInfo('T146_FINAL_REFERENCE_LEDGER.json',(1980,1,1,0,0,0)); zi.external_attr=0o100644<<16; zi.compress_type=zipfile.ZIP_DEFLATED
    z.writestr(zi,ledger)
info={'file':pkg.name,'bytes':pkg.stat().st_size,'sha256':sha(pkg.read_bytes()),'summary':{k:v for k,v in summary.items() if k!='segments'}}
(OUT/'PACKAGE_INFO.json').write_text(json.dumps(info,ensure_ascii=False,indent=2,sort_keys=True)+'\n')
print('FINAL',json.dumps(info,ensure_ascii=False),flush=True)
