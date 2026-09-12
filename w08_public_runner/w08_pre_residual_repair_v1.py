import base64,concurrent.futures,datetime as dt,gzip,hashlib,http.cookiejar,io,json,os,pathlib,random,subprocess,time,urllib.error,urllib.parse,urllib.request
CORE_COMMIT='4c9f56784ab2df8ad347cbc23f61e8449d22a628'; CORE_PATH='w08_public_runner/w08_final_reconcile_v1.py'
src=subprocess.check_output(['git','show',f'{CORE_COMMIT}:{CORE_PATH}'],text=True); src=src.split("\nif MODE=='t05': run_t05()",1)[0]; ns={'__name__':'core'}; exec(compile(src,CORE_PATH,'exec'),ns)
BASE='https://mopsov.twse.com.tw'; FRONT='/mops/web/t59sb07'; AJAX='/mops/web/ajax_t59sb07'; UA='Mozilla/5.0 (compatible; W08PreResidualRepair/1.0)'; OUT=pathlib.Path('out_pre_residual_repair');OUT.mkdir(exist_ok=True)
def now():return dt.datetime.now(dt.timezone.utc).isoformat().replace('+00:00','Z')
def sha(b):return hashlib.sha256(b).hexdigest()
class NR(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,req,fp,code,msg,headers,newurl):return None
def dl(a):
 req=urllib.request.Request(a['archive_download_url'],headers={'Authorization':f"Bearer {ns['TOKEN']}",'Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28','User-Agent':UA});op=urllib.request.build_opener(NR);loc=None
 try:
  with op.open(req,timeout=120) as r:
   if r.status in (301,302,303,307,308):loc=r.headers.get('Location')
   else:return r.read()
 except urllib.error.HTTPError as e:
  if e.code not in (301,302,303,307,308):raise
  loc=e.headers.get('Location')
 if not loc:raise RuntimeError('artifact_redirect_missing')
 with urllib.request.urlopen(urllib.request.Request(loc,headers={'User-Agent':UA}),timeout=240) as r:return r.read()
ns['download_artifact']=dl

def make_body(code,year,firstin):
 return urllib.parse.urlencode([('encodeURIComponent','1'),('step','1'),('firstin',firstin),('off','1'),('keyword4',''),('code1',''),('TYPEK2',''),('checkbtn',''),('queryName','co_id'),('inpuType','co_id'),('TYPEK','all'),('co_id',code),('year',year),('month',''),('b_date',''),('e_date','')]).encode('ascii')
def classify(rb,code):return ns['classify'](rb,code)
def session():
 cj=http.cookiejar.CookieJar();op=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj));fu=BASE+FRONT
 with op.open(urllib.request.Request(fu,headers={'User-Agent':UA,'Accept':'text/html,*/*'}),timeout=60) as r:fb=r.read();st=r.status;final=r.geturl()
 if st!=200 or not fb:raise RuntimeError(f'front status={st} bytes={len(fb)}')
 return op,final,sha(fb),len(fb)
def capture(key):
 code,year=key; attempts=[]
 # Both are source-grounded: UI click state firstin=1 and hidden initial state firstin=ture.
 for firstin in ('1','ture'):
  for k in range(1,5):
   try:
    op,fu,fsha,fbytes=session();body=make_body(code,year,firstin);req=urllib.request.Request(BASE+AJAX,data=body,method='POST',headers={'User-Agent':UA,'Accept':'*/*','Content-Type':'application/x-www-form-urlencoded','Referer':fu,'Origin':BASE});ts=now()
    with op.open(req,timeout=90) as r:rb=r.read();st=r.status;final=r.geturl()
    c=classify(rb,code);rec={'firstin':firstin,'attempt':k,'http_status':st,'bytes':len(rb),'sha256':sha(rb),'classification':c,'at':ts}
    attempts.append(rec)
    if st==200 and rb and not c['security_shell'] and not c['empty_div_shell'] and not c['year_error']:
     z=io.BytesIO();
     with gzip.GzipFile(fileobj=z,mode='wb',mtime=0) as g:g.write(rb)
     gz=z.getvalue();meta={'code':code,'year':year,'retrieved_at':ts,'request_url':BASE+AJAX,'method':'POST','request_body_sha256':sha(body),'response_bytes':len(rb),'response_sha256':sha(rb),'gzip_sha256':sha(gz),'gzip_roundtrip':gzip.decompress(gz)==rb,'classification':c,'firstin':firstin,'contract_variant':'ui_click_state' if firstin=='1' else 'official_hidden_initial_state','residual_repair':True,'attempt_history':attempts,'session_front_sha256':fsha,'session_front_bytes':fbytes}
     return {'ok':True,'key':key,'body':body,'raw':rb,'gz':gz,'meta':meta}
   except Exception as e:attempts.append({'firstin':firstin,'attempt':k,'error':repr(e),'at':now()})
   time.sleep(min(5,0.5*k+random.random()))
 return {'ok':False,'key':key,'attempts':attempts}

codes,universe_sha=ns['load_codes']('w08_public_runner/w08_pre20050504_codes_1281.txt.gz.b64',1281);years=[f'{y:03d}' for y in range(85,95)];target={(c,y) for c in codes for y in years}
base_store={}
for run_id in (34689835957,34691209234):
 for a in ns['list_artifacts'](run_id):ns['parse_formal_artifact'](a,dl(a),'pre',base_store)
missing=sorted(target-set(base_store));assert len(base_store)==12576 and len(missing)==234
print(json.dumps({'base_success':len(base_store),'missing':len(missing)}),flush=True)
repair={};fail=[]
with concurrent.futures.ThreadPoolExecutor(max_workers=4) as ex:
 fut={ex.submit(capture,k):k for k in missing}
 done=0
 for f in concurrent.futures.as_completed(fut):
  r=f.result();done+=1
  if r['ok']:
   ns['add_item'](repair,r['key'],r['body'],r['raw'],r['gz'],r['meta'])
  else:fail.append({'code':r['key'][0],'year':r['key'][1],'attempts':r['attempts']})
  if done%10==0 or not r['ok']:print(json.dumps({'progress':done,'of':len(missing),'repair_success':len(repair),'failure':len(fail),'last':r['key'],'ok':r['ok']}),flush=True)
summary={'schema':'w08_pre_residual_repair_v1','formal_raw':True,'work_unit_id':'W08-RAW-MOPS-EXRIGHT-PRE20050505','base_success_units':len(base_store),'residual_target_units':len(missing),'residual_success_units':len(repair),'residual_failure_units':len(fail),'union_success_units':len(base_store)+len(repair),'universe_count':1281,'universe_sha256':universe_sha,'endpoint':BASE+AJAX,'contract_variants':['firstin=1 ui click','firstin=ture official hidden initial'],'generated_at':now()}
if repair:
 out=OUT/'RAW-W08_MOPS_EXRIGHT_PRE20050505_RESIDUAL_REPAIR_V1_20260912.zip';ns['deterministic_zip'](out,repair,'pre',dict(summary,artifact_audit=[]));summary['package_file']=out.name;summary['package_bytes']=out.stat().st_size;summary['package_sha256']=sha(out.read_bytes())
(OUT/'RESIDUAL_FAILURES.json').write_text(json.dumps(fail,ensure_ascii=False,indent=2,sort_keys=True)+'\n');(OUT/'SUMMARY.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2,sort_keys=True)+'\n')
print('FINAL',json.dumps(summary,ensure_ascii=False),flush=True)
