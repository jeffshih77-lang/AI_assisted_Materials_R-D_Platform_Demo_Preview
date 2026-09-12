import base64, datetime as dt, gzip, hashlib, http.cookiejar, io, json, os, pathlib, random, re, time, urllib.parse, urllib.request, zipfile

REPO=os.environ.get('GITHUB_REPOSITORY','jeffshih77-lang/AI_assisted_Materials_R-D_Platform_Demo_Preview')
TOKEN=os.environ['GITHUB_TOKEN']
MODE=os.environ.get('MODE','t05').strip().lower()
ROOT=pathlib.Path(f'out_w08_final_{MODE}'); ROOT.mkdir(parents=True,exist_ok=True)
BASE='https://mopsov.twse.com.tw'
UA='Mozilla/5.0 (compatible; W08FormalFinalizer/1.0)'

def now(): return dt.datetime.now(dt.timezone.utc).isoformat().replace('+00:00','Z')
def sha(b): return hashlib.sha256(b).hexdigest()
def api(path):
    req=urllib.request.Request('https://api.github.com'+path,headers={'Authorization':f'Bearer {TOKEN}','Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28','User-Agent':UA})
    with urllib.request.urlopen(req,timeout=120) as r: return json.loads(r.read())
def get_run(run_id): return api(f'/repos/{REPO}/actions/runs/{run_id}')
def wait_run(run_id,limit=7200):
    t0=time.time()
    while True:
        d=get_run(run_id); print(json.dumps({'wait_run':run_id,'status':d.get('status'),'conclusion':d.get('conclusion'),'at':now()}),flush=True)
        if d.get('status')=='completed': return d
        if time.time()-t0>limit: raise RuntimeError(f'upstream_timeout {run_id}')
        time.sleep(30)
def list_artifacts(run_id):
    out=[]; page=1
    while True:
        d=api(f'/repos/{REPO}/actions/runs/{run_id}/artifacts?per_page=100&page={page}')
        a=d.get('artifacts',[]); out.extend(a)
        if len(a)<100: break
        page+=1
    return out
def download_artifact(artifact):
    url=artifact['archive_download_url']
    req=urllib.request.Request(url,headers={'Authorization':f'Bearer {TOKEN}','Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28','User-Agent':UA})
    with urllib.request.urlopen(req,timeout=180) as r: return r.read()
def zip_entries(blob):
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        return {n:z.read(n) for n in z.namelist() if not n.endswith('/')}
def find_suffix(entries,suffix):
    m=[(n,b) for n,b in entries.items() if n.endswith(suffix)]
    if len(m)!=1: return None
    return m[0]
def load_codes(path,count):
    s=pathlib.Path(path).read_text().strip(); raw=gzip.decompress(base64.b64decode(s)); codes=raw.decode().splitlines()
    assert len(codes)==count and len(set(codes))==count and all(len(c)==4 and c.isdigit() for c in codes)
    return codes,sha(raw)
def gz_ok(gz,raw):
    try: return gzip.decompress(gz)==raw
    except Exception: return False

def classify(rb,code):
    t=rb.decode('utf-8','replace')
    return {'security_shell':('FOR SECURITY REASONS' in t or '錯誤代碼' in t),'empty_div_shell':bool(re.search(r'<div\s+id=["\']div01["\'][^>]*>\s*</div>',t,re.I)),'company_not_exist':(f'{code} 之公司不存在' in t or '之公司不存在' in t),'no_data':('查無所需資料' in t or '查無資料' in t),'year_error':('年度不可空白' in t),'table_count':t.lower().count('<table'),'tr_count':t.lower().count('<tr')}

def add_item(store,key,body,raw,gz,meta):
    if sha(body)!=meta.get('request_body_sha256',sha(body)): raise RuntimeError(f'body_sha_mismatch {key}')
    if sha(raw)!=meta.get('response_sha256',sha(raw)): raise RuntimeError(f'raw_sha_mismatch {key}')
    if not gz_ok(gz,raw): raise RuntimeError(f'gzip_roundtrip_fail {key}')
    item={'body':body,'raw':raw,'gz':gz,'meta':dict(meta)}
    if key in store:
        old=store[key]
        if old['body']!=body or old['raw']!=raw:
            raise RuntimeError(f'collision_nonidentical_duplicate {key}')
        return False
    store[key]=item; return True

def parse_formal_artifact(artifact,blob,kind,store):
    entries=zip_entries(blob)
    mans=[(n,b) for n,b in entries.items() if n.endswith('MANIFEST.json')]
    if not mans: return {'artifact':artifact['name'],'accepted':0,'reason':'no_manifest'}
    accepted=0
    for mn,mb in mans:
        try: man=json.loads(mb)
        except Exception: continue
        if not man.get('formal_raw'): continue
        for rec in man.get('records',[]):
            if kind=='t05': key=(str(rec['code']),int(rec['qryType'])); stem=f"{key[0]}_q{key[1]}"
            else: key=(str(rec['code']),str(rec['year'])); stem=f"{key[0]}_{key[1]}"
            bodies=[b for n,b in entries.items() if n.endswith('/request/'+stem+'.body') or n.endswith('request/'+stem+'.body')]
            raws=[b for n,b in entries.items() if n.endswith('/raw/'+stem+'.response.bin') or n.endswith('raw/'+stem+'.response.bin')]
            gzs=[b for n,b in entries.items() if n.endswith('/raw/'+stem+'.response.bin.gz') or n.endswith('raw/'+stem+'.response.bin.gz')]
            if len(bodies)!=1 or len(raws)!=1 or len(gzs)!=1: raise RuntimeError(f'artifact_member_missing {artifact["name"]} {key}')
            meta=dict(rec); meta['source_artifact_id']=artifact['id']; meta['source_artifact_name']=artifact['name']; meta['source_artifact_digest']=artifact.get('digest')
            if add_item(store,key,bodies[0],raws[0],gzs[0],meta): accepted+=1
    return {'artifact':artifact['name'],'accepted':accepted,'bytes':len(blob)}

def parse_t05_checkpoint(artifact,blob,allowed,store):
    entries=zip_entries(blob); accepted=0
    for n,raw in list(entries.items()):
        if not n.endswith('.response.bin'): continue
        m=re.search(r'/(\d{4})_q([12])\.response\.bin$',n)
        if not m: m=re.search(r'^(?:raw/)?(\d{4})_q([12])\.response\.bin$',n)
        if not m: continue
        key=(m.group(1),int(m.group(2)))
        if key not in allowed: continue
        stem=f'{key[0]}_q{key[1]}'
        bodies=[b for nn,b in entries.items() if nn.endswith('/request/'+stem+'.body') or nn.endswith('request/'+stem+'.body')]
        gzs=[b for nn,b in entries.items() if nn.endswith('/raw/'+stem+'.response.bin.gz') or nn.endswith('raw/'+stem+'.response.bin.gz')]
        if len(bodies)!=1 or len(gzs)!=1: raise RuntimeError(f'checkpoint_member_missing {artifact["name"]} {key}')
        meta={'code':key[0],'qryType':key[1],'request_body_sha256':sha(bodies[0]),'response_sha256':sha(raw),'gzip_sha256':sha(gzs[0]),'gzip_roundtrip':True,'source_artifact_id':artifact['id'],'source_artifact_name':artifact['name'],'source_artifact_digest':artifact.get('digest'),'source_kind':'validated_checkpoint_v3'}
        if add_item(store,key,bodies[0],raw,gzs[0],meta): accepted+=1
    return {'artifact':artifact['name'],'accepted':accepted,'bytes':len(blob)}

def open_session(front,verify_click=False):
    last=None
    for a in range(1,13):
        try:
            cj=http.cookiejar.CookieJar(); op=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj)); fu=BASE+front
            req=urllib.request.Request(fu,headers={'User-Agent':UA,'Accept':'text/html,*/*'})
            with op.open(req,timeout=60) as r: fb=r.read(); st=r.status
            if st!=200 or not fb: raise RuntimeError(f'front status={st} bytes={len(fb)}')
            if verify_click:
                ft=fb.decode('utf-8','replace')
                if "document.form1.firstin.value='1'" not in ft or 'doAction();ajax1(document.form1' not in ft: raise RuntimeError('front_click_semantics_not_verified')
            return op,fu,sha(fb),len(fb)
        except Exception as e:
            last=repr(e); time.sleep(min(30,1.6**a+random.random()*2))
    raise RuntimeError('open_session_exhausted '+str(last))

def capture_t05(key):
    code,q=key; front='/mops/web/t05st09_2'; ajax='/mops/web/ajax_t05st09_2'
    body=urllib.parse.urlencode([('encodeURIComponent','1'),('step','1'),('firstin','1'),('off','1'),('keyword4',''),('code1',''),('TYPEK2',''),('checkbtn',''),('queryName','co_id'),('inpuType','co_id'),('TYPEK','all'),('isnew','false'),('co_id',code),('date1','085'),('date2','115'),('qryType',str(q))]).encode('ascii')
    retries=[]; last=None
    for a in range(1,13):
        try:
            op,fu,fsha,fbytes=open_session(front)
            req=urllib.request.Request(BASE+ajax,data=body,method='POST',headers={'User-Agent':UA,'Accept':'*/*','Content-Type':'application/x-www-form-urlencoded','Referer':fu,'Origin':BASE})
            ts=now()
            with op.open(req,timeout=90) as r: rb=r.read(); st=r.status; final=r.geturl()
            if st!=200 or not rb: raise RuntimeError(f'post status={st} bytes={len(rb)}')
            cls=classify(rb,code)
            if cls['security_shell'] or cls['empty_div_shell']: raise RuntimeError('invalid_response_shell '+json.dumps(cls,ensure_ascii=False))
            gzbuf=io.BytesIO();
            with gzip.GzipFile(fileobj=gzbuf,mode='wb',mtime=0) as g:g.write(rb)
            gz=gzbuf.getvalue()
            return body,rb,gz,{'code':code,'qryType':q,'retrieved_at':ts,'request_url':BASE+ajax,'method':'POST','request_body_sha256':sha(body),'response_bytes':len(rb),'response_sha256':sha(rb),'gzip_sha256':sha(gz),'gzip_roundtrip':True,'classification':cls,'retry_count':len(retries),'retries':retries,'source_kind':'final_missing_only_repair','session_front_sha256':fsha,'session_front_bytes':fbytes}
        except Exception as e:
            last=repr(e); retries.append({'attempt':a,'at':now(),'error':last}); time.sleep(min(35,1.7**a+random.random()*3))
    raise RuntimeError(f't05_terminal {key} {last}')

def capture_pre(key):
    code,year=key; front='/mops/web/t59sb07'; ajax='/mops/web/ajax_t59sb07'
    body=urllib.parse.urlencode([('encodeURIComponent','1'),('step','1'),('firstin','1'),('off','1'),('keyword4',''),('code1',''),('TYPEK2',''),('checkbtn',''),('queryName','co_id'),('inpuType','co_id'),('TYPEK','all'),('co_id',code),('year',year),('month',''),('b_date',''),('e_date','')]).encode('ascii')
    retries=[]; last=None
    for a in range(1,13):
        try:
            op,fu,fsha,fbytes=open_session(front,verify_click=True)
            req=urllib.request.Request(BASE+ajax,data=body,method='POST',headers={'User-Agent':UA,'Accept':'*/*','Content-Type':'application/x-www-form-urlencoded','Referer':fu,'Origin':BASE})
            ts=now()
            with op.open(req,timeout=90) as r: rb=r.read(); st=r.status; final=r.geturl()
            if st!=200 or not rb: raise RuntimeError(f'post status={st} bytes={len(rb)}')
            cls=classify(rb,code)
            if cls['security_shell'] or cls['empty_div_shell'] or cls['year_error']: raise RuntimeError('invalid_response_shell '+json.dumps(cls,ensure_ascii=False))
            gzbuf=io.BytesIO();
            with gzip.GzipFile(fileobj=gzbuf,mode='wb',mtime=0) as g:g.write(rb)
            gz=gzbuf.getvalue()
            return body,rb,gz,{'code':code,'year':year,'retrieved_at':ts,'request_url':BASE+ajax,'method':'POST','request_body_sha256':sha(body),'response_bytes':len(rb),'response_sha256':sha(rb),'gzip_sha256':sha(gz),'gzip_roundtrip':True,'classification':cls,'retry_count':len(retries),'retries':retries,'source_kind':'final_missing_only_repair','session_front_sha256':fsha,'session_front_bytes':fbytes,'ui_sequence':'doAction sets firstin=1 before ajax1(form1)'}
        except Exception as e:
            last=repr(e); retries.append({'attempt':a,'at':now(),'error':last}); time.sleep(min(35,1.7**a+random.random()*3))
    raise RuntimeError(f'pre_terminal {key} {last}')

def deterministic_zip(path,store,kind,summary):
    records=[]; sha_lines=[]
    with zipfile.ZipFile(path,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6,allowZip64=True) as z:
        def put(name,data,compress=zipfile.ZIP_DEFLATED):
            zi=zipfile.ZipInfo(name,(1980,1,1,0,0,0)); zi.compress_type=compress; zi.external_attr=0o100644<<16
            z.writestr(zi,data,compress_type=compress,compresslevel=6 if compress==zipfile.ZIP_DEFLATED else None); sha_lines.append(f'{sha(data)}  {name}')
        for key in sorted(store):
            it=store[key]
            if kind=='t05': stem=f'{key[0]}_q{key[1]}'; rec_key={'code':key[0],'qryType':key[1]}
            else: stem=f'{key[0]}_{key[1]}'; rec_key={'code':key[0],'year':key[1]}
            put(f'request/{stem}.body',it['body']); put(f'raw/{stem}.response.bin',it['raw']); put(f'raw/{stem}.response.bin.gz',it['gz'],zipfile.ZIP_STORED)
            m=dict(it['meta']); m.update(rec_key); records.append(m)
        manifest=dict(summary); manifest['records']=records
        put('MANIFEST.json',(json.dumps(manifest,ensure_ascii=False,indent=2,sort_keys=True)+'\n').encode())
        cov={k:v for k,v in summary.items() if k not in ('artifact_audit',)}; put('COVERAGE.json',(json.dumps(cov,ensure_ascii=False,indent=2,sort_keys=True)+'\n').encode())
        put('ARTIFACT_AUDIT.json',(json.dumps(summary.get('artifact_audit',[]),ensure_ascii=False,indent=2,sort_keys=True)+'\n').encode())
        put('SHA256.txt',('\n'.join(sorted(sha_lines))+'\n').encode())

def run_t05():
    original=34673076096; repair1=34688535810; repair2=34688916414
    wait_run(repair2)
    codes,universe_sha=load_codes('w08_public_runner/w08_security_master_4digit_universe_2436.txt.gz.b64',2436)
    done_raw=gzip.decompress(base64.b64decode(pathlib.Path('w08_public_runner/w08_t05_completed_621.json.gz.b64').read_text().strip()))
    checkpoint={(str(c),int(q)) for c,q in json.loads(done_raw)}; assert len(checkpoint)==621
    target={(c,q) for c in codes for q in (1,2)}; assert len(target)==4872
    store={}; audit=[]
    for run_id in (original,repair1,repair2):
        arts=list_artifacts(run_id); print(json.dumps({'run':run_id,'artifacts':len(arts)}),flush=True)
        for a in arts:
            blob=download_artifact(a)
            if run_id==original: res=parse_t05_checkpoint(a,blob,checkpoint,store)
            else: res=parse_formal_artifact(a,blob,'t05',store)
            res.update({'run_id':run_id,'artifact_id':a['id'],'digest':a.get('digest')}); audit.append(res); print(json.dumps(res),flush=True)
    have=set(store); missing=sorted(target-have)
    print(json.dumps({'mode':'t05','have':len(have),'missing':len(missing),'checkpoint_recovered':len(have & checkpoint)}),flush=True)
    if len(have & checkpoint)!=621: raise RuntimeError(f'checkpoint_recovery_not_621 {len(have & checkpoint)}')
    for i,key in enumerate(missing,1):
        body,raw,gz,meta=capture_t05(key); add_item(store,key,body,raw,gz,meta); print(json.dumps({'repair':i,'of':len(missing),'key':key}),flush=True)
    if set(store)!=target: raise RuntimeError(f'final_coverage_fail have={len(store)} target={len(target)}')
    summary={'schema':'w08_t05st09_final_aggregate_v1','work_unit_id':'W08-RAW-MOPS-DIVIDEND-T05ST09','formal_raw':True,'status':'FORMAL_RAW_COMPLETE','endpoint':BASE+'/mops/web/ajax_t05st09_2','universe_count':2436,'universe_sha256':universe_sha,'target_units':4872,'success_units':len(store),'missing_repaired_units':len(missing),'checkpoint_units':621,'contract':{'date1':'085','date2':'115','qryType':[1,2],'firstin':'1','TYPEK':'all'},'artifact_audit':audit,'generated_at':now()}
    out=ROOT/'RAW-W08_MOPS_DIVIDEND_T05ST09_FORMAL_RAW_ROC85_115_FINAL_20260912.zip'; deterministic_zip(out,store,'t05',summary)
    info={'file':out.name,'bytes':out.stat().st_size,'sha256':sha(out.read_bytes()),'summary':{k:v for k,v in summary.items() if k!='artifact_audit'}}; (ROOT/'PACKAGE_INFO.json').write_text(json.dumps(info,ensure_ascii=False,indent=2,sort_keys=True)+'\n'); print(json.dumps(info,ensure_ascii=False),flush=True)

def run_pre():
    run_id=34689835957; wait_run(run_id)
    codes,universe_sha=load_codes('w08_public_runner/w08_pre20050504_codes_1281.txt.gz.b64',1281)
    years=[f'{y:03d}' for y in range(85,95)]; target={(c,y) for c in codes for y in years}; assert len(target)==12810
    store={}; audit=[]; arts=list_artifacts(run_id); print(json.dumps({'run':run_id,'artifacts':len(arts)}),flush=True)
    for a in arts:
        blob=download_artifact(a); res=parse_formal_artifact(a,blob,'pre',store); res.update({'run_id':run_id,'artifact_id':a['id'],'digest':a.get('digest')}); audit.append(res); print(json.dumps(res),flush=True)
    missing=sorted(target-set(store)); print(json.dumps({'mode':'pre','have':len(store),'missing':len(missing)}),flush=True)
    for i,key in enumerate(missing,1):
        body,raw,gz,meta=capture_pre(key); add_item(store,key,body,raw,gz,meta); print(json.dumps({'repair':i,'of':len(missing),'key':key}),flush=True)
    if set(store)!=target: raise RuntimeError(f'final_coverage_fail have={len(store)} target={len(target)}')
    summary={'schema':'w08_t59_pre20050505_final_aggregate_v1','work_unit_id':'W08-RAW-MOPS-EXRIGHT-PRE20050505','formal_raw':True,'status':'FORMAL_RAW_COMPLETE','endpoint':BASE+'/mops/web/ajax_t59sb07','official_scope':'公開發行及94.5.5前之全體公司','universe_count':1281,'universe_sha256':universe_sha,'years':years,'target_units':12810,'success_units':len(store),'missing_repaired_units':len(missing),'contract':{'firstin':'1','TYPEK':'all','company_required':True,'year_required':True,'ui_click_semantics_verified':True,'ui_sequence':'doAction sets firstin=1 before ajax1(form1)'},'artifact_audit':audit,'generated_at':now()}
    out=ROOT/'RAW-W08_MOPS_EXRIGHT_PRE20050505_FORMAL_RAW_ROC85_94_FINAL_20260912.zip'; deterministic_zip(out,store,'pre',summary)
    info={'file':out.name,'bytes':out.stat().st_size,'sha256':sha(out.read_bytes()),'summary':{k:v for k,v in summary.items() if k!='artifact_audit'}}; (ROOT/'PACKAGE_INFO.json').write_text(json.dumps(info,ensure_ascii=False,indent=2,sort_keys=True)+'\n'); print(json.dumps(info,ensure_ascii=False),flush=True)

if MODE=='t05': run_t05()
elif MODE=='pre': run_pre()
else: raise SystemExit('MODE must be t05 or pre')
