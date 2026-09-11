import datetime as dt,gzip,hashlib,http.cookiejar,json,os,pathlib,random,re,time,urllib.parse,urllib.request

CHUNK_INDEX=int(os.environ['CHUNK_INDEX']); CHUNK_COUNT=int(os.environ.get('CHUNK_COUNT','8'))
ROOT=pathlib.Path(f'out_t05st09_chunk_{CHUNK_INDEX:02d}_of_{CHUNK_COUNT:02d}'); (ROOT/'raw').mkdir(parents=True,exist_ok=True); (ROOT/'request').mkdir(exist_ok=True)
BASE='https://mopsov.twse.com.tw'; FRONT='/mops/web/t05st09_2'; AJAX='/mops/web/ajax_t05st09_2'; UA='Mozilla/5.0 (compatible; W08FormalRawT05ST09/1.0)'
U=json.loads(pathlib.Path('w08_public_runner/w08_company_code_universe_v1.json').read_text()); codes=U['all_numeric_4digit_codes'][CHUNK_INDEX::CHUNK_COUNT]
manifest=[]; anomalies=[]; retries=[]; session_generation=0

def now(): return dt.datetime.now(dt.timezone.utc).isoformat().replace('+00:00','Z')
def sha(b): return hashlib.sha256(b).hexdigest()
def open_session():
 global session_generation
 session_generation+=1; cj=http.cookiejar.CookieJar(); op=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj)); fu=BASE+FRONT
 req=urllib.request.Request(fu,headers={'User-Agent':UA,'Accept':'text/html,*/*'})
 with op.open(req,timeout=60) as r: fb=r.read(); st=r.status; hdr=dict(r.headers.items())
 if st!=200 or not fb: raise RuntimeError(f'front bad {st} {len(fb)}')
 if session_generation==1:
  (ROOT/'front.response.bin').write_bytes(fb)
  (ROOT/'FRONT.json').write_text(json.dumps({'url':fu,'status':st,'bytes':len(fb),'sha256':sha(fb),'content_type':hdr.get('Content-Type')},indent=2,sort_keys=True)+'\n')
 return op,fu

def body_for(code,qry):
 pairs=[('encodeURIComponent','1'),('step','1'),('firstin','1'),('off','1'),('keyword4',''),('code1',''),('TYPEK2',''),('checkbtn',''),('queryName','co_id'),('inpuType','co_id'),('TYPEK','all'),('isnew','false'),('co_id',code),('date1','085'),('date2','115'),('qryType',str(qry))]
 return urllib.parse.urlencode(pairs).encode('ascii')

def is_shell(txt):
 return ('FOR SECURITY REASONS, THIS PAGE CAN NOT BE ACCESSED' in txt) or (re.search(r'<div id=["\']div01["\']\s*>\s*</div>',txt,re.I|re.S) is not None and len(re.sub(r'<[^>]+>','',txt).strip())<200)

op,referer=open_session(); total=len(codes)*2; done=0
for ci,code in enumerate(codes):
 if ci and ci%100==0: op,referer=open_session()
 for qry in (1,2):
  body=body_for(code,qry); stem=f'{code}_q{qry}'; (ROOT/'request'/f'{stem}.body').write_bytes(body)
  last=None
  for attempt in range(1,7):
   ts=now()
   try:
    req=urllib.request.Request(BASE+AJAX,data=body,method='POST',headers={'User-Agent':UA,'Accept':'*/*','Content-Type':'application/x-www-form-urlencoded','Referer':referer,'Origin':BASE})
    with op.open(req,timeout=90) as r: rb=r.read(); status=r.status; final=r.geturl(); hdr=dict(r.headers.items())
    txt=rb.decode('utf-8','replace')
    if status!=200 or not rb: raise RuntimeError(f'bad status={status} bytes={len(rb)}')
    if is_shell(txt): raise RuntimeError('generic/security shell')
    break
   except Exception as e:
    last=repr(e); retries.append({'code':code,'qryType':qry,'attempt':attempt,'at':ts,'error':last})
    if attempt>=6: raise RuntimeError(f'exhausted {code} q{qry}: {last}')
    time.sleep(min(30,2**(attempt-1)+random.random())); op,referer=open_session()
  raw=ROOT/'raw'/f'{stem}.response.bin'; gz=ROOT/'raw'/f'{stem}.response.bin.gz'; raw.write_bytes(rb)
  with gzip.GzipFile(gz,'wb',mtime=0) as g:g.write(rb)
  if gzip.decompress(gz.read_bytes())!=rb: raise RuntimeError('gzip mismatch')
  no_data=('查無所需資料' in txt); invalid=('公司代號' in txt and ('不存在' in txt or '錯誤' in txt or '請輸入' in txt))
  rec={'code':code,'qryType':qry,'request_method':'POST','request_url':BASE+AJAX,'request_body_path':f'request/{stem}.body','request_body_bytes':len(body),'request_body_sha256':sha(body),'retrieved_at':ts,'http_status':status,'final_url':final,'content_type':hdr.get('Content-Type'),'response_path':f'raw/{stem}.response.bin','response_bytes':len(rb),'response_sha256':sha(rb),'gzip_path':f'raw/{stem}.response.bin.gz','gzip_sha256':sha(gz.read_bytes()),'gzip_roundtrip_match':True,'no_data_marker':no_data,'invalid_code_marker':invalid,'has_table':'<table' in txt.lower(),'session_generation':session_generation,'transport_attempt':attempt}
  manifest.append(rec)
  if no_data or invalid: anomalies.append({'type':'SOURCE_NO_DATA_OR_INVALID_CODE','code':code,'qryType':qry,'response_sha256':rec['response_sha256'],'disposition':'PRESERVE_EXACT_RAW'})
  done+=1
  if done%100==0:
   (ROOT/'RUN_STATE.json').write_text(json.dumps({'schema':'w08_t05st09_chunk_state_v1','chunk_index':CHUNK_INDEX,'chunk_count':CHUNK_COUNT,'codes_in_chunk':len(codes),'completed_requests':done,'expected_requests':total,'updated_at':now()},indent=2,sort_keys=True)+'\n')
   print('progress',done,'/',total,flush=True)
  time.sleep(.05)

assert len(manifest)==total
assert all(x['http_status']==200 and x['response_bytes']>0 and x['gzip_roundtrip_match'] for x in manifest)
assert len({(x['code'],x['qryType']) for x in manifest})==len(manifest)
package={'schema':'raw_w08_mops_t05st09_formal_raw_chunk_v1','work_unit_id':'W08-RAW-MOPS-DIVIDEND-T05ST09','source_family':'MOPS_CA_DIVIDEND_POLICY_T05ST09_V1','classification':'FORMAL_RAW_CHUNK_CANDIDATE_PENDING_DRIVE_READBACK','chunk_index':CHUNK_INDEX,'chunk_count':CHUNK_COUNT,'coverage':{'company_universe':'cloud-verified SECURITY_MASTER derived numeric 4-digit code universe','roc_year_start':'085','roc_year_end':'115','qryType':[1,2]},'source_universe_assertion':{'all_count':U['counts']['all'],'source_pit_sha256':U['source_pit_sha256'],'source_identity_event_sha256':U['source_identity_event_sha256']},'captures':manifest,'anomalies':anomalies,'retry_events':retries,'assertions':{'expected_requests':total,'capture_count':len(manifest),'all_http_200':True,'all_nonempty':True,'all_gzip_roundtrip':True,'unique_code_qry_pairs':True}}
(ROOT/'MANIFEST.json').write_text(json.dumps(package,ensure_ascii=False,indent=2,sort_keys=True)+'\n')
(ROOT/'ANOMALY.json').write_text(json.dumps({'schema':'w08_t05st09_anomaly_v1','anomalies':anomalies},ensure_ascii=False,indent=2,sort_keys=True)+'\n')
(ROOT/'RUN_STATE.json').write_text(json.dumps({'schema':'w08_t05st09_chunk_state_v1','chunk_index':CHUNK_INDEX,'chunk_count':CHUNK_COUNT,'codes_in_chunk':len(codes),'completed_requests':done,'expected_requests':total,'stage':'COMPLETE','updated_at':now()},indent=2,sort_keys=True)+'\n')
print(json.dumps(package['assertions'],indent=2))
