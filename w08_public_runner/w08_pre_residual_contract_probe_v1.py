import datetime as dt, gzip, hashlib, http.cookiejar, io, json, pathlib, re, time, urllib.parse, urllib.request
BASES=['https://mopsov.twse.com.tw','https://mops.twse.com.tw']
FRONT='/mops/web/t59sb07'; AJAX='/mops/web/ajax_t59sb07'; UA='Mozilla/5.0 (compatible; W08PreResidualProbe/1.0)'
OUT=pathlib.Path('out_pre_residual_probe'); OUT.mkdir(exist_ok=True)
def now():return dt.datetime.now(dt.timezone.utc).isoformat().replace('+00:00','Z')
def sha(b):return hashlib.sha256(b).hexdigest()
def cls(rb,code):
 t=rb.decode('utf-8','replace')
 return {'bytes':len(rb),'sha256':sha(rb),'empty_div_shell':bool(re.search(r'<div\s+id=["\']div01["\'][^>]*>\s*</div>',t,re.I)),'no_data':('查無所需資料' in t or '查無資料' in t),'company_not_exist':('之公司不存在' in t),'security_shell':('FOR SECURITY REASONS' in t or '錯誤代碼' in t),'year_error':('年度不可空白' in t),'table_count':t.lower().count('<table'),'tr_count':t.lower().count('<tr')}
def body(code,year,firstin):
 return urllib.parse.urlencode([('encodeURIComponent','1'),('step','1'),('firstin',firstin),('off','1'),('keyword4',''),('code1',''),('TYPEK2',''),('checkbtn',''),('queryName','co_id'),('inpuType','co_id'),('TYPEK','all'),('co_id',code),('year',year),('month',''),('b_date',''),('e_date','')]).encode('ascii')
def one(base,code,year,firstin):
 cj=http.cookiejar.CookieJar(); op=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj)); fu=base+FRONT
 with op.open(urllib.request.Request(fu,headers={'User-Agent':UA,'Accept':'text/html,*/*'}),timeout=60) as r: front=r.read(); fst=r.status; final_front=r.geturl()
 b=body(code,year,firstin); req=urllib.request.Request(base+AJAX,data=b,method='POST',headers={'User-Agent':UA,'Accept':'*/*','Content-Type':'application/x-www-form-urlencoded','Referer':final_front,'Origin':base})
 try:
  with op.open(req,timeout=90) as r: rb=r.read(); st=r.status; final=r.geturl()
 except Exception as e:
  return {'base':base,'code':code,'year':year,'firstin':firstin,'error':repr(e),'front_status':fst,'front_bytes':len(front),'front_sha256':sha(front)}
 c=cls(rb,code); c.update({'base':base,'code':code,'year':year,'firstin':firstin,'http_status':st,'final_url':final,'request_body':b.decode(),'request_sha256':sha(b),'front_status':fst,'front_bytes':len(front),'front_sha256':sha(front)})
 return c
recs=[]
for base in BASES:
 for code,year in [('0001','085'),('0001','093'),('1101','093')]:
  for firstin in ('1','ture'):
   x=one(base,code,year,firstin); recs.append(x); print(json.dumps(x,ensure_ascii=False),flush=True); time.sleep(.2)
man={'schema':'w08_pre_residual_contract_probe_v1','qualification_only':True,'records':recs,'generated_at':now()}
(OUT/'PROBE.json').write_text(json.dumps(man,ensure_ascii=False,indent=2,sort_keys=True)+'\n')
