import datetime as dt,gzip,hashlib,http.cookiejar,json,pathlib,re,time,urllib.parse,urllib.request
OUT=pathlib.Path('w08_t59_firstin_click_probe_v3_out'); OUT.mkdir(exist_ok=True)
BASE='https://mopsov.twse.com.tw'; FRONT='/mops/web/t59sb07'; AJAX='/mops/web/ajax_t59sb07'; UA='Mozilla/5.0 (compatible; W08T59ClickSemanticsProbe/3.0)'
def now(): return dt.datetime.now(dt.timezone.utc).isoformat().replace('+00:00','Z')
def sha(b): return hashlib.sha256(b).hexdigest()
def session():
 cj=http.cookiejar.CookieJar(); op=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj)); fu=BASE+FRONT
 with op.open(urllib.request.Request(fu,headers={'User-Agent':UA}),timeout=60) as r: fb=r.read()
 return op,fu,fb
def body(code,year,firstin):
 return urllib.parse.urlencode([('encodeURIComponent','1'),('step','1'),('firstin',firstin),('off','1'),('keyword4',''),('code1',''),('TYPEK2',''),('checkbtn',''),('queryName','co_id'),('inpuType','co_id'),('TYPEK','all'),('co_id',code),('year',year),('month',''),('b_date',''),('e_date','')]).encode('ascii')
def capture(label,code,year,firstin):
 last=None
 for a in range(1,7):
  try:
   op,fu,fb=session(); b=body(code,year,firstin)
   req=urllib.request.Request(BASE+AJAX,data=b,method='POST',headers={'User-Agent':UA,'Accept':'*/*','Content-Type':'application/x-www-form-urlencoded','Referer':fu,'Origin':BASE})
   with op.open(req,timeout=90) as r: rb=r.read(); st=r.status
   break
  except Exception as e:
   last=repr(e)
   if a==6: raise
   time.sleep(a*1.5)
 (OUT/f'{label}.request.body').write_bytes(b); (OUT/f'{label}.response.bin').write_bytes(rb)
 with gzip.GzipFile(OUT/f'{label}.response.bin.gz','wb',mtime=0) as g:g.write(rb)
 t=rb.decode('utf-8','replace')
 return {'label':label,'code':code,'year':year,'firstin':firstin,'http_status':st,'response_bytes':len(rb),'response_sha256':sha(rb),'body_sha256':sha(b),'empty_div_shell':bool(re.search(r'<div\s+id=["\']div01["\'][^>]*>\s*</div>',t,re.I)),'no_data':('查無所需資料' in t or '查無資料' in t),'company_not_exist':('之公司不存在' in t),'security_shell':('FOR SECURITY REASONS' in t or '錯誤代碼' in t),'table_count':t.lower().count('<table'),'tr_count':t.lower().count('<tr')}
op,fu,front=session(); ft=front.decode('utf-8','replace')
assert "document.form1.firstin.value='1'" in ft and 'doAction();ajax1(document.form1' in ft
recs=[capture('0001_093_click_firstin1','0001','093','1'),capture('0001_093_hidden_ture','0001','093','ture'),capture('1101_093_click_firstin1','1101','093','1')]
man={'schema':'w08_t59_firstin_click_semantics_probe_v3','qualification_only':True,'front_sha256':sha(front),'front_bytes':len(front),'ui_evidence':{'hidden_initial':'ture','click_doAction_sets_firstin':'1','query_button_calls':'doAction();ajax1(document.form1,table01)'},'records':recs,'result':'PASS' if recs[2]['table_count']>0 and not recs[2]['security_shell'] else 'CONTROL_FAIL'}
(OUT/'PROBE.json').write_text(json.dumps(man,ensure_ascii=False,indent=2,sort_keys=True)+'\n')
print(json.dumps(man,ensure_ascii=False,indent=2))
if man['result']!='PASS': raise SystemExit(2)
