import base64,datetime as dt,gzip,hashlib,http.cookiejar,json,os,pathlib,random,re,time,urllib.parse,urllib.request
SHARD=int(os.environ.get('SHARD','0')); SHARDS=int(os.environ.get('SHARDS','16'))
ROOT=pathlib.Path(f'out_t05_repair_{SHARD:02d}_of_{SHARDS:02d}'); (ROOT/'raw').mkdir(parents=True,exist_ok=True); (ROOT/'request').mkdir(exist_ok=True)
BASE='https://mopsov.twse.com.tw'; FRONT='/mops/web/t05st09_2'; AJAX='/mops/web/ajax_t05st09_2'; UA='Mozilla/5.0 (compatible; W08T05ST09FormalRepair/4.0)'
def now(): return dt.datetime.now(dt.timezone.utc).isoformat().replace('+00:00','Z')
def sha(b): return hashlib.sha256(b).hexdigest()
def load_completed():
 s=pathlib.Path('w08_public_runner/w08_t05_completed_621.json.gz.b64').read_text().strip(); return { (str(c),int(q)) for c,q in json.loads(gzip.decompress(base64.b64decode(s)).decode()) }
def load_codes():
 d=json.loads(pathlib.Path('w08_public_runner/w08_company_code_universe_v1.json').read_text()); codes=d['all_numeric_4digit_codes']; assert len(codes)==2436 and len(set(codes))==2436; return codes,d
def open_session():
 last=None
 for a in range(1,9):
  try:
   cj=http.cookiejar.CookieJar(); op=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj)); fu=BASE+FRONT
   with op.open(urllib.request.Request(fu,headers={'User-Agent':UA,'Accept':'text/html,*/*'}),timeout=60) as r: fb=r.read(); st=r.status
   if st!=200 or not fb: raise RuntimeError(f'front status={st} bytes={len(fb)}')
   return op,fu,fb,[c.name for c in cj]
  except Exception as e:
   last=repr(e); time.sleep(min(20,1.5**a+random.random()*2))
 raise RuntimeError('open_session_exhausted '+str(last))
def body_for(code,q):
 return urllib.parse.urlencode([('encodeURIComponent','1'),('step','1'),('firstin','1'),('off','1'),('keyword4',''),('code1',''),('TYPEK2',''),('checkbtn',''),('queryName','co_id'),('inpuType','co_id'),('TYPEK','all'),('isnew','false'),('co_id',code),('date1','085'),('date2','115'),('qryType',str(q))]).encode('ascii')
def classify(rb,code):
 t=rb.decode('utf-8','replace')
 return {'security_shell':('FOR SECURITY REASONS' in t or '錯誤代碼' in t),'empty_div_shell':bool(re.search(r'<div\s+id=["\']div01["\'][^>]*>\s*</div>',t,re.I)),'company_not_exist':(f'{code} 之公司不存在' in t or '之公司不存在' in t),'no_data':('查無所需資料' in t or '查無資料' in t),'table_count':t.lower().count('<table'),'tr_count':t.lower().count('<tr')}
def capture(code,q):
 body=body_for(code,q); stem=f'{code}_q{q}'; (ROOT/'request'/f'{stem}.body').write_bytes(body); retries=[]; last=None
 for a in range(1,9):
  try:
   op,fu,fb,cookies=open_session()
   req=urllib.request.Request(BASE+AJAX,data=body,method='POST',headers={'User-Agent':UA,'Accept':'*/*','Content-Type':'application/x-www-form-urlencoded','Referer':fu,'Origin':BASE})
   ts=now()
   with op.open(req,timeout=90) as r: rb=r.read(); st=r.status; final=r.geturl(); hdr={k:v for k,v in r.headers.items() if k.lower()!='set-cookie'}
   if st!=200 or not rb: raise RuntimeError(f'post status={st} bytes={len(rb)}')
   cls=classify(rb,code)
   if cls['security_shell'] or cls['empty_div_shell']: raise RuntimeError('invalid_response_shell '+json.dumps(cls,ensure_ascii=False))
   break
  except Exception as e:
   last=repr(e); retries.append({'attempt':a,'at':now(),'error':last})
   if a>=8: return None,{'code':code,'qryType':q,'request_body_sha256':sha(body),'retries':retries,'terminal_error':last}
   time.sleep(min(25,1.7**a+random.random()*3))
 (ROOT/'raw'/f'{stem}.response.bin').write_bytes(rb)
 with gzip.GzipFile(ROOT/'raw'/f'{stem}.response.bin.gz','wb',mtime=0) as g:g.write(rb)
 gz=(ROOT/'raw'/f'{stem}.response.bin.gz').read_bytes(); assert gzip.decompress(gz)==rb
 rec={'code':code,'qryType':q,'retrieved_at':ts,'request_url':BASE+AJAX,'method':'POST','request_body_bytes':len(body),'request_body_sha256':sha(body),'http_status':st,'final_url':final,'response_bytes':len(rb),'response_sha256':sha(rb),'gzip_sha256':sha(gz),'gzip_roundtrip':True,'classification':cls,'retry_count':len(retries),'retries':retries,'headers':hdr}
 return rec,None
codes,universe=load_codes(); completed=load_completed(); full=[(c,q) for c in codes for q in (1,2)]; missing=[x for x in full if x not in completed]
assert len(full)==4872 and len(completed)==621 and len(missing)==4251
assigned=[x for i,x in enumerate(missing) if i%SHARDS==SHARD]
records=[]; failures=[]
for i,(c,q) in enumerate(assigned,1):
 rec,fail=capture(c,q)
 if rec: records.append(rec)
 else: failures.append(fail)
 if i%20==0: print(f'shard={SHARD} progress={i}/{len(assigned)} ok={len(records)} fail={len(failures)}',flush=True)
 time.sleep(.06+random.random()*.09)
manifest={'schema':'w08_t05st09_missing_repair_v4','work_unit_id':'W08-RAW-MOPS-DIVIDEND-T05ST09','formal_raw':True,'endpoint':BASE+AJAX,'front':BASE+FRONT,'contract':{'date1':'085','date2':'115','qryType':[1,2],'firstin':'1','TYPEK':'all'},'universe_count':len(codes),'target_units':4872,'checkpoint_units':621,'missing_units':4251,'shard':SHARD,'shards':SHARDS,'assigned_units':len(assigned),'success_units':len(records),'failed_units':len(failures),'records':records,'failures':failures,'source_universe_sha':universe.get('source_pit_sha256'),'source_identity_event_sha':universe.get('source_identity_event_sha256')}
(ROOT/'MANIFEST.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2,sort_keys=True)+'\n')
(ROOT/'COVERAGE.json').write_text(json.dumps({k:manifest[k] for k in ['work_unit_id','universe_count','target_units','checkpoint_units','missing_units','shard','shards','assigned_units','success_units','failed_units']},ensure_ascii=False,indent=2,sort_keys=True)+'\n')
(ROOT/'ANOMALY.json').write_text(json.dumps({'classification_counts':{k:sum(1 for r in records if r['classification'].get(k)) for k in ['company_not_exist','no_data','security_shell','empty_div_shell']},'failures':failures},ensure_ascii=False,indent=2,sort_keys=True)+'\n')
with (ROOT/'SHA256.txt').open('w') as f:
 for p in sorted(ROOT.rglob('*')):
  if p.is_file() and p.name!='SHA256.txt': f.write(f'{sha(p.read_bytes())}  {p.relative_to(ROOT)}\n')
print(json.dumps({'shard':SHARD,'assigned':len(assigned),'success':len(records),'failed':len(failures)},ensure_ascii=False),flush=True)
if failures: raise SystemExit(f'FAILED_UNITS={len(failures)}')
