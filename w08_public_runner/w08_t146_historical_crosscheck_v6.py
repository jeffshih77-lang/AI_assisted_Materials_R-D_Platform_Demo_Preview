import datetime as dt,gzip,hashlib,http.cookiejar,json,pathlib,random,re,time,urllib.parse,urllib.request
OUT=pathlib.Path('out_w08_t146_v6'); OUT.mkdir(exist_ok=True)
BASE='https://mopsov.twse.com.tw'; FRONT='/mops/web/t146sb10'; AJAX='/mops/web/ajax_t146sb10'; UA='Mozilla/5.0 (compatible; W08T146HistCrosscheck/6.0)'
def now(): return dt.datetime.now(dt.timezone.utc).isoformat().replace('+00:00','Z')
def sha(b): return hashlib.sha256(b).hexdigest()
def open_session():
  last=None
  for a in range(1,8):
    try:
      cj=http.cookiejar.CookieJar(); op=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj)); fu=BASE+FRONT
      with op.open(urllib.request.Request(fu,headers={'User-Agent':UA,'Accept':'text/html,*/*'}),timeout=60) as r: fb=r.read(); st=r.status
      if st!=200 or not fb: raise RuntimeError(f'front bad {st} {len(fb)}')
      return op,fu,fb,[c.name for c in cj]
    except Exception as e:
      last=repr(e); time.sleep(min(10,2**(a-1)+random.random()))
  raise RuntimeError('front exhausted '+str(last))
def body_for(case):
  pairs=[('encodeURIComponent','1'),('step','1'),('firstin',case.get('firstin','1')),('off','1'),('keyword4',''),('code1',''),('TYPEK2',''),('checkbtn',''),('queryName','co_id_1'),('inpuType','co_id'),('scope',case['scope']),('co_id_1',case.get('co_id','')),('typek',case['typek']),('selecttype',case['selecttype']),('noticeDate',case['noticeDate']),('date',case.get('date','4')),('yymmdd1',case.get('from','')),('yymmdd2',case.get('to','')),('noticeKind',case['noticeKind']),('sort',case.get('sort','1'))]
  return urllib.parse.urlencode(pairs).encode('ascii')
def classify(rb):
  t=rb.decode('utf-8','replace'); plain=' '.join(re.sub('<[^>]+>',' ',re.sub(r'<script.*?</script>','',t,flags=re.I|re.S)).split())
  return {'empty_div_shell':('<div id="div01"></div>' in t or bool(re.search(r'<div\s+id=["\']div01["\'][^>]*>\s*</div>',t,re.I))), 'security_shell':('FOR SECURITY REASONS' in t or '錯誤代碼' in t), 'no_data':any(x in t for x in ['查無資料','查無所需資料','無符合','沒有符合']), 'table_count':t.lower().count('<table'), 'tr_count':t.lower().count('<tr'), 'has_1101':('1101' in t), 'known_930316':('93/03/16' in t), 'known_930723':('93/07/23' in t), 'plain_preview':plain[:1200]}
def post(case):
  label=case['label']; body=body_for(case); (OUT/(label+'.request_body.bin')).write_bytes(body); retries=[]; last=None
  for a in range(1,8):
    try:
      op,fu,fb,cookies=open_session() if a==1 or a>1 else (None,None,None,None)
      req=urllib.request.Request(BASE+AJAX,data=body,method='POST',headers={'User-Agent':UA,'Accept':'*/*','Content-Type':'application/x-www-form-urlencoded','Referer':fu,'Origin':BASE})
      ts=now()
      with op.open(req,timeout=90) as r: rb=r.read(); st=r.status; final=r.geturl()
      if st!=200 or not rb: raise RuntimeError(f'post bad {st} {len(rb)}')
      break
    except Exception as e:
      last=repr(e); retries.append({'attempt':a,'at':now(),'error':last});
      if a==7: raise
      time.sleep(min(12,2**(a-1)+random.random()))
  (OUT/(label+'.response.bin')).write_bytes(rb)
  with gzip.GzipFile(OUT/(label+'.response.bin.gz'),'wb',mtime=0) as g:g.write(rb)
  c=classify(rb); return {'label':label,'case':case,'retrieved_at':ts,'status':st,'final_url':final,'request_body_bytes':len(body),'request_body_sha256':sha(body),'response_bytes':len(rb),'response_sha256':sha(rb),'gzip_sha256':sha((OUT/(label+'.response.bin.gz')).read_bytes()),'gzip_roundtrip':gzip.decompress((OUT/(label+'.response.bin.gz')).read_bytes())==rb,'classification':c,'retries':retries}
# Grounded cases: t59 exact-contract evidence proves 1101 has announcements on 93/03/16 and 93/07/23; use those dates to test T146 historical surface.
cases=[
 {'label':'known_1101_09303_nk11_f1','scope':'1','co_id':'1101','typek':'sii','selecttype':'2','noticeDate':'1','from':'093/03/01','to':'093/03/31','noticeKind':'11','sort':'1','firstin':'1'},
 {'label':'known_1101_09307_nk11_f1','scope':'1','co_id':'1101','typek':'sii','selecttype':'2','noticeDate':'1','from':'093/07/01','to':'093/07/31','noticeKind':'11','sort':'1','firstin':'1'},
 {'label':'known_1101_093_all_f1','scope':'1','co_id':'1101','typek':'sii','selecttype':'0','noticeDate':'1','from':'093/01/01','to':'093/12/31','noticeKind':'1','sort':'1','firstin':'1'},
 {'label':'known_1101_09303_nk11_ture','scope':'1','co_id':'1101','typek':'sii','selecttype':'2','noticeDate':'1','from':'093/03/01','to':'093/03/31','noticeKind':'11','sort':'1','firstin':'ture'},
 {'label':'pre_1101_093_nk29_pub','scope':'1','co_id':'1101','typek':'pub','selecttype':'1','noticeDate':'1','from':'093/01/01','to':'094/05/04','noticeKind':'29','sort':'1','firstin':'1'},
 {'label':'post_2330_095_nk30','scope':'1','co_id':'2330','typek':'sii','selecttype':'1','noticeDate':'1','from':'095/01/01','to':'095/12/31','noticeKind':'30','sort':'1','firstin':'1'},
 {'label':'recent_2330_control','scope':'1','co_id':'2330','typek':'sii','selecttype':'0','noticeDate':'2','date':'7','from':'','to':'','noticeKind':'1','sort':'2','firstin':'1'}]
records=[]
for c in cases:
  x=post(c); records.append(x); print(c['label'],x['response_bytes'],x['classification'],flush=True); time.sleep(.25)
data_shaped=[r for r in records if not r['classification']['empty_div_shell'] and not r['classification']['security_shell'] and (r['classification']['tr_count']>=2 or r['classification']['no_data'])]
historical_data=[r for r in records[:-1] if not r['classification']['empty_div_shell'] and not r['classification']['security_shell'] and r['classification']['tr_count']>=2 and not r['classification']['no_data']]
manifest={'schema':'w08_t146_historical_crosscheck_v6','work_unit_id':'W08-RAW-MOPS-STRUCTURED-T146','qualification_only':True,'endpoint':BASE+AJAX,'method':'POST','basis':'controlled probes grounded by exact t59 event dates; no bulk download until historical contract is proven','records':records,'assertions':{'all_http_200':all(r['status']==200 for r in records),'all_nonempty':all(r['response_bytes']>0 for r in records),'all_gzip_roundtrip':all(r['gzip_roundtrip'] for r in records),'recent_control_data_shaped':records[-1] in data_shaped,'historical_data_shaped_found':bool(historical_data)},'historical_data_labels':[r['label'] for r in historical_data]}
(OUT/'PROBE.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')
print(json.dumps(manifest['assertions'],ensure_ascii=False,indent=2),flush=True)
