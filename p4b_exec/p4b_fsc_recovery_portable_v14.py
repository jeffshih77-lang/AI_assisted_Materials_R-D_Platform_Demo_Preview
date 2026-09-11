#!/usr/bin/env python3
import concurrent.futures as cf, datetime as dt, hashlib, json, lzma, os, pathlib, time, urllib.parse, urllib.request, zipfile
UA='Mozilla/5.0 (compatible; P4BFormalRawCollectorPortable/1.4)'
FAMILY='FSC_OFFICIAL_NEWS_ARCHIVE_V1'; CONTRACT='1.2.0'; RECOVERY='1.4.0'
CHUNKS={
'C01':(936,975),'C02':(896,935),'C06':(736,775),'C07':(696,735),'C08':(656,695),'C09':(616,655),'C10':(576,615),'C11':(536,575),'C12':(496,535),'C13':(456,495),'C14':(416,455),'C15':(376,415),'C16':(336,375),'C17':(296,335),'C18':(256,295),'C19':(216,255),'C20':(176,215),'C21':(136,175),'C22':(96,135),'C23':(56,95),'C24':(16,55),'C25':(1,15)}
def nowz(): return dt.datetime.now(dt.timezone.utc).isoformat().replace('+00:00','Z')
def sha(b): return hashlib.sha256(b).hexdigest()
def load_records(path):
    raw=lzma.open(path,'rt',encoding='utf-8')
    with raw:
        return [json.loads(line) for line in raw if line.strip()]
def fetch_one(r,attempts=6,base_sleep=2):
    last=None
    for a in range(attempts):
        try:
            req=urllib.request.Request(r['url'],headers={'User-Agent':UA,'Accept':'*/*','Connection':'close'})
            with urllib.request.urlopen(req,timeout=120) as resp:
                body=resp.read(); st=getattr(resp,'status',None); final=resp.geturl(); hdr=dict(resp.headers.items()); got=nowz()
            if st==200 and body:
                ct=(hdr.get('Content-Type') or '').lower()
                if r['resource_kind']=='DIRECT_DOCUMENT' and len(body)<64: raise RuntimeError('direct document too small')
                if r['resource_kind']=='HTML_DETAIL' and ('html' not in ct and not body.lstrip().startswith(b'<')): raise RuntimeError('expected html detail')
                return {'ok':True,'record':r,'body':body,'status':st,'final_url':final,'headers':hdr,'retrieved_at':got,'attempts_used':a+1}
            last=f'http_status={st} bytes={len(body)}'
        except Exception as e: last=repr(e)
        if a+1<attempts: time.sleep(min(30,base_sleep*(2**a)))
    return {'ok':False,'record':r,'error':last,'attempts_used':attempts,'failed_at':nowz()}
def save_success(root,res):
    r=res['record']; body=res['body']; hdr=res['headers']; ct=(hdr.get('Content-Type') or '').lower()
    ext='.html' if r['resource_kind']=='HTML_DETAIL' else ('.pdf' if body.startswith(b'%PDF') or 'pdf' in ct else '.bin')
    rid=r.get('dataserno') or f"record{int(r['record_no']):05d}"; stem=f"{int(r['source_page']):04d}_{int(r['record_no']):05d}_{r['published_date']}_{rid}"
    rp=root/'detail'/(stem+'.response'+ext); mp=root/'meta'/(stem+'.capture.json'); rp.write_bytes(body)
    meta={'schema':'p4b_exact_http_capture_v1','lane_code':'P4-B','dataset':'FINANCIAL_NEWS_EVENTS','work_unit_id':f"P4B-FSC-PAGE-{int(r['source_page']):04d}",'source_family':FAMILY,'source_contract_version':CONTRACT,'recovery_collector_version':RECOVERY,'method':'GET','request_url':r['url'],'final_url':res['final_url'],'retrieved_at':res['retrieved_at'],'http_status':res['status'],'response_headers':hdr,'payload_bytes':len(body),'payload_sha256':sha(body),'source_page':r['source_page'],'record_no':r['record_no'],'dataserno':r.get('dataserno'),'record_identity':r['record_identity'],'resource_kind':r['resource_kind'],'published_date':r['published_date'],'published_date_source':'FSC frozen archive list row','available_at':'unknown','available_at_reason':'historical archive migration/public-web availability time not proven by page','unit':r['unit'],'title':r['title'],'raw_semantics':'exact FSC linked resource HTTP response bytes','classification':'FORMAL_RAW_CANDIDATE_PENDING_DRIVE_READBACK','recovery_attempts_used':res['attempts_used']}
    mp.write_text(json.dumps(meta,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    return {'record_no':r['record_no'],'source_page':r['source_page'],'dataserno':r.get('dataserno'),'record_identity':r['record_identity'],'resource_kind':r['resource_kind'],'published_date':r['published_date'],'raw_path':str(rp.relative_to(root)),'raw_bytes':len(body),'raw_sha256':sha(body),'metadata_path':str(mp.relative_to(root)),'recovery_attempts_used':res['attempts_used']}
def run_chunk(allrecs,chunk,outbase):
    lo,hi=CHUNKS[chunk]; recs=[r for r in allrecs if lo<=int(r['source_page'])<=hi]
    if not recs: raise SystemExit(f'empty {chunk}')
    root=outbase/chunk; (root/'detail').mkdir(parents=True,exist_ok=True); (root/'meta').mkdir(exist_ok=True)
    first=[]
    with cf.ThreadPoolExecutor(max_workers=int(os.getenv('P4B_WORKERS','2'))) as ex:
        for x in cf.as_completed([ex.submit(fetch_one,r,4,1) for r in recs]): first.append(x.result())
    successes=[x for x in first if x['ok']]; failed=[x for x in first if not x['ok']]
    retry=[fetch_one(x['record'],8,2) for x in failed]
    successes.extend(x for x in retry if x['ok']); final_failed=[x for x in retry if not x['ok']]
    manifest=[save_success(root,x) for x in sorted(successes,key=lambda y:int(y['record']['record_no']))]
    failures=[]
    for x in sorted(final_failed,key=lambda y:int(y['record']['record_no'])):
        r=x['record']; failures.append({'record_no':r['record_no'],'source_page':r['source_page'],'dataserno':r.get('dataserno'),'record_identity':r['record_identity'],'resource_kind':r['resource_kind'],'published_date':r['published_date'],'title':r['title'],'url':r['url'],'host':urllib.parse.urlparse(r['url']).netloc,'error':x['error'],'deep_retry_attempts':x['attempts_used'],'classification':'SOURCE_RESOURCE_UNAVAILABLE_PENDING_REMEDIATION'})
    m={'schema':'p4b_fsc_recovery_chunk_manifest_v2','lane_code':'P4-B','dataset':'FINANCIAL_NEWS_EVENTS','source_family':FAMILY,'source_contract_version':CONTRACT,'recovery_collector_version':RECOVERY,'chunk':chunk,'page_low':lo,'page_high':hi,'expected_record_count':len(recs),'captured_record_count':len(manifest),'failure_count':len(failures),'raw_bytes':sum(x['raw_bytes'] for x in manifest),'records':manifest,'failures':failures,'status':'RECOVERY_CAPTURE_COMPLETE_WITH_FAILURES' if failures else 'RECOVERY_CAPTURE_COMPLETE','generated_at':nowz()}
    (root/f'P4B_FSC_RECOVERY_{chunk}_MANIFEST.json').write_text(json.dumps(m,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    zpath=outbase/f'P4B_FSC_RECOVERY_{chunk}_V14.zip'
    with zipfile.ZipFile(zpath,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in root.rglob('*'):
            if p.is_file(): z.write(p,p.relative_to(root))
    print(json.dumps({'chunk':chunk,'expected':len(recs),'captured':len(manifest),'failures':len(failures),'zip':str(zpath),'zip_bytes':zpath.stat().st_size,'zip_sha256':sha(zpath.read_bytes())},ensure_ascii=False),flush=True)
    return m,zpath
def main():
    payload=pathlib.Path(os.getenv('P4B_PAYLOAD','P4B_FSC_OUTSTANDING_12825_V1.jsonl.xz'))
    allrecs=load_records(payload)
    if len(allrecs)!=12825: raise SystemExit(f'payload count mismatch {len(allrecs)}')
    outbase=pathlib.Path(os.getenv('P4B_OUT','out')); outbase.mkdir(parents=True,exist_ok=True)
    chunks=os.getenv('CHUNK','ALL').split(',')
    if chunks==['ALL']: chunks=list(CHUNKS)
    summaries=[]
    for c in chunks:
        if c not in CHUNKS: raise SystemExit(f'bad chunk {c}')
        m,z=run_chunk(allrecs,c,outbase); summaries.append({'chunk':c,'expected':m['expected_record_count'],'captured':m['captured_record_count'],'failures':m['failure_count'],'zip':z.name,'zip_bytes':z.stat().st_size,'zip_sha256':sha(z.read_bytes())})
    s={'schema':'p4b_fsc_portable_recovery_summary_v1','lane_code':'P4-B','payload_records':len(allrecs),'chunks':summaries,'expected':sum(x['expected'] for x in summaries),'captured':sum(x['captured'] for x in summaries),'failures':sum(x['failures'] for x in summaries),'generated_at':nowz()}
    (outbase/'P4B_FSC_PORTABLE_RECOVERY_SUMMARY.json').write_text(json.dumps(s,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')
if __name__=='__main__': main()
