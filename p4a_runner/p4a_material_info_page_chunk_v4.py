import concurrent.futures as cf, datetime as dt, gzip, hashlib, json, os, pathlib, re, time, urllib.parse, urllib.request, random

ROC_YEAR=int(os.environ['ROC_YEAR']); KIND=os.environ['KIND']
START_PAGE=int(os.environ['START_PAGE']); END_PAGE=int(os.environ['END_PAGE'])
PCOUNT=100; WORKERS=int(os.environ.get('DETAIL_WORKERS','12'))
assert 81 <= ROC_YEAR <= 115 and KIND in ('L','O') and 0 <= START_PAGE <= END_PAGE
ROOT=pathlib.Path('out_p4a_chunk')/f'P4A-MATERIAL-ROC{ROC_YEAR}-{KIND}-P{START_PAGE:04d}-{END_PAGE:04d}'
(ROOT/'list').mkdir(parents=True,exist_ok=True); (ROOT/'detail').mkdir(parents=True,exist_ok=True)
UA='Mozilla/5.0 (compatible; P4AMaterialInfoFormalRaw/4.0)'
LIST='https://mopsov.twse.com.tw/mops/web/ajax_t51sb10'; DETAIL='https://mopsov.twse.com.tw/mops/web/ajax_t05st01'
KEY_RE=re.compile(r'document\.fm\.seq_no\.value="([^"]+)";document\.fm\.spoke_time\.value="([^"]+)";document\.fm\.spoke_date\.value="([^"]+)";document\.fm\.i\.value="([^"]+)";document\.fm\.co_id\.value="([^"]+)";document\.fm\.TYPEK\.value="([^"]+)";')
PAGE_RE=re.compile(r"document\.fm\.pagenum\.value='(\d+)'")

def get(url, retries=3):
  last=None
  for attempt in range(retries):
    try:
      req=urllib.request.Request(url,headers={'User-Agent':UA,'Accept':'*/*','Connection':'close'},method='GET')
      ts=dt.datetime.now(dt.timezone.utc).isoformat().replace('+00:00','Z')
      with urllib.request.urlopen(req,timeout=90) as r:
        b=r.read(); status=getattr(r,'status',None); final=r.geturl(); headers=dict(r.headers.items())
      if status==200 and b: return b,status,final,headers,ts,attempt+1
      last=RuntimeError(f'bad response status={status} bytes={len(b)}')
    except Exception as e: last=e
    time.sleep((attempt+1)*1.2+random.random())
  raise last

def list_url(page):
  p=[('encodeURIComponent','1'),('firstin','true'),('id',''),('key',''),('TYPEK',''),('Stp','4'),('go','false'),('COMPANY_ID',''),('r1','1'),('KIND',KIND),('CODE',''),('keyWord',''),('year',str(ROC_YEAR)),('month1','0'),('begin_day','1'),('end_day','31'),('PCount',str(PCOUNT)),('pagenum',str(page))]
  return LIST+'?'+urllib.parse.urlencode(p)

def detail_url(k):
  seq_no,spoke_time,spoke_date,i,co_id,typek=k
  p=[('step','2'),('colorchg','1'),('co_id',co_id),('TYPEK',typek),('off','1'),('firstin','1'),('i',i),('year','2018'),('month','6'),('spoke_date',spoke_date),('spoke_time',spoke_time),('seq_no',seq_no),('b_date','1'),('e_date','1'),('t51sb10','t51sb10')]
  return DETAIL+'?'+urllib.parse.urlencode(p)

def persist_bytes(folder,stem,b):
  raw=folder/(stem+'.response.bin'); raw.write_bytes(b)
  gz=folder/(stem+'.response.bin.gz')
  with gzip.GzipFile(filename='',mode='wb',fileobj=gz.open('wb'),mtime=0) as f: f.write(b)
  return str(raw.relative_to(ROOT)), str(gz.relative_to(ROOT)), hashlib.sha256(b).hexdigest(), hashlib.sha256(gz.read_bytes()).hexdigest()

captures=[]; anomalies=[]; page_summaries=[]; task_meta=[]
for page in range(START_PAGE,END_PAGE+1):
  u=list_url(page); b,s,final,h,ts,att=get(u); tx=b.decode('utf-8','replace')
  if 'FOR SECURITY REASONS' in tx or '因為安全性考量' in tx or (len(b)<3000 and '<div id="div01"></div>' in tx):
    raise SystemExit(f'page {page} source shell')
  keys=KEY_RE.findall(tx); pager=sorted({int(x) for x in PAGE_RE.findall(tx)})
  rawp,gzp,sha,gzsha=persist_bytes(ROOT/'list',f'ROC{ROC_YEAR}_{KIND}_p{page:04d}',b)
  captures.append({'stage':'LIST','request_method':'GET','request_url':u,'retrieved_at':ts,'http_status':s,'final_url':final,'content_type':h.get('Content-Type'),'payload_bytes':len(b),'payload_sha256':sha,'raw_path':rawp,'gzip_path':gzp,'gzip_sha256':gzsha,'roc_year':ROC_YEAR,'kind':KIND,'pagenum':page,'PCount':PCOUNT,'onclick_key_count':len(keys),'pager_values':pager,'attempt_count':att})
  for idx,k in enumerate(keys): task_meta.append((page,idx,k))

def fetch_detail(item):
  page,idx,k=item; du=detail_url(k)
  db,ds,df,dh,dts,att=get(du); dtx=db.decode('utf-8','replace')
  provider='本資料由' in dtx
  seq_no,spoke_time,spoke_date,i,co_id,typek=k
  stem=f'p{page:04d}_k{idx:03d}_{co_id}_{spoke_date}_{spoke_time}_{seq_no}_{i}_{typek}'
  rawp,gzp,sha,gzsha=persist_bytes(ROOT/'detail',stem,db)
  rec={'stage':'DETAIL','request_method':'GET','request_url':du,'retrieved_at':dts,'http_status':ds,'final_url':df,'content_type':dh.get('Content-Type'),'payload_bytes':len(db),'payload_sha256':sha,'raw_path':rawp,'gzip_path':gzp,'gzip_sha256':gzsha,'list_page':page,'key_index':idx,'key':{'seq_no':seq_no,'spoke_time':spoke_time,'spoke_date':spoke_date,'i':i,'co_id':co_id,'TYPEK':typek},'has_company_provider_marker':provider,'attempt_count':att}
  ano=None if provider else {'type':'SOURCE_DETAIL_EMPTY_OR_NONSTANDARD','list_page':page,'key_index':idx,'key':rec['key'],'payload_bytes':len(db),'payload_sha256':sha,'disposition':'PRESERVE_RAW_DO_NOT_ZERO_FILL'}
  return rec,ano

with cf.ThreadPoolExecutor(max_workers=WORKERS) as ex:
  futs=[ex.submit(fetch_detail,x) for x in task_meta]
  for i,f in enumerate(cf.as_completed(futs),1):
    rec,ano=f.result(); captures.append(rec)
    if ano: anomalies.append(ano)
    if i%100==0: print('progress',i,'/',len(futs),flush=True)

for page in range(START_PAGE,END_PAGE+1):
  ds=[x for x in captures if x['stage']=='DETAIL' and x['list_page']==page]
  page_summaries.append({'page':page,'list_key_count':next(x['onclick_key_count'] for x in captures if x['stage']=='LIST' and x['pagenum']==page),'detail_captured':len(ds),'provider_marker_valid':sum(1 for x in ds if x['has_company_provider_marker']),'nonstandard':sum(1 for x in ds if not x['has_company_provider_marker'])})

detail_caps=[x for x in captures if x['stage']=='DETAIL']
assertions={'roc_year':ROC_YEAR,'kind':KIND,'start_page':START_PAGE,'end_page':END_PAGE,'page_count':END_PAGE-START_PAGE+1,'list_capture_count':sum(1 for x in captures if x['stage']=='LIST'),'detail_capture_count':len(detail_caps),'provider_marker_detail_count':sum(1 for x in detail_caps if x['has_company_provider_marker']),'nonstandard_detail_count':len(anomalies),'all_http_200':all(x['http_status']==200 for x in captures),'all_payload_nonempty':all(x['payload_bytes']>0 for x in captures)}
if assertions['list_capture_count']!=assertions['page_count'] or not assertions['all_http_200'] or not assertions['all_payload_nonempty']:
  raise SystemExit('formal raw assertions failed')
package={'schema':'p4a_material_info_page_chunk_v4','lane_code':'P4-A','dataset':'MATERIAL_INFO','work_unit_id':f'P4A-MATERIAL-ROC{ROC_YEAR}-{KIND}-P{START_PAGE:04d}-{END_PAGE:04d}','source_family':'MOPS_T51_T05_HISTORICAL_GET_REPLAY','source_contract_version':'P4-A_V0.1','classification':'FORMAL_RAW_CANDIDATE_PENDING_DRIVE_READBACK','coverage':{'roc_year':ROC_YEAR,'kind':KIND,'PCount':PCOUNT,'start_page':START_PAGE,'end_page':END_PAGE},'page_summaries':page_summaries,'captures':sorted(captures,key=lambda x:(0 if x['stage']=='LIST' else 1,x.get('pagenum',x.get('list_page',-1)),x.get('key_index',-1))),'anomalies':anomalies,'assertions':assertions}
(ROOT/'MANIFEST.json').write_text(json.dumps(package,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')
(ROOT/'ANOMALY.json').write_text(json.dumps({'schema':'p4a_material_info_anomaly_v1','work_unit_id':package['work_unit_id'],'anomalies':anomalies},ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')
print(json.dumps(assertions,ensure_ascii=False),flush=True)
