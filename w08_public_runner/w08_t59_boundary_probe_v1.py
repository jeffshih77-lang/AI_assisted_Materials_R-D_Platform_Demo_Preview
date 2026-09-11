import hashlib,json,pathlib,urllib.request,urllib.parse,http.cookiejar,re,time
OUT=pathlib.Path('w08_t59_boundary_probe_v1_out'); OUT.mkdir(exist_ok=True)
BASE='https://mopsov.twse.com.tw'; FRONT='/mops/web/t59sb07'; AJAX='/mops/web/ajax_t59sb07'; UA='Mozilla/5.0 (compatible; W08T59BoundaryProbe/1.0)'
CODES=['1101','1301','2002','2303','2317','2330','2409','2603','2881','2882']

def session():
    cj=http.cookiejar.CookieJar(); op=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj)); fu=BASE+FRONT
    with op.open(urllib.request.Request(fu,headers={'User-Agent':UA,'Accept':'text/html,*/*'}),timeout=60) as r: fb=r.read()
    return op,fu,fb

def post(op,fu,code,year,month='',b='',e=''):
    pairs=[('encodeURIComponent','1'),('step','1'),('firstin','1'),('off','1'),('keyword4',''),('code1',''),('TYPEK2',''),('checkbtn',''),('queryName','co_id'),('inpuType','co_id'),('TYPEK','all'),('co_id',code),('year',year),('month',month),('b_date',b),('e_date',e)]
    body=urllib.parse.urlencode(pairs).encode('ascii'); req=urllib.request.Request(BASE+AJAX,data=body,method='POST',headers={'User-Agent':UA,'Accept':'*/*','Content-Type':'application/x-www-form-urlencoded','Referer':fu,'Origin':BASE})
    with op.open(req,timeout=90) as r: rb=r.read(); st=r.status
    txt=rb.decode('utf-8','replace'); plain=' '.join(re.sub('<[^>]+>',' ',re.sub(r'<script.*?</script>','',txt,flags=re.I|re.S)).split())
    return {'code':code,'year':year,'month':month,'b_date':b,'e_date':e,'status':st,'body':body.decode(),'body_sha256':hashlib.sha256(body).hexdigest(),'response_bytes':len(rb),'response_sha256':hashlib.sha256(rb).hexdigest(),'no_data':('查無所需資料' in txt),'year_error':('年度不可空白' in txt),'company_error':('公司代號不可空白' in txt),'has_table':('<table' in txt.lower()),'plain_preview':plain[:600]}

op,fu,fb=session(); recs=[]
# Discover at least one company with data in ROC094, then compare exact monthly/day-filter semantics.
found=None
for c in CODES:
    x=post(op,fu,c,'094'); recs.append(x)
    if x['status']==200 and not x['no_data'] and not x['year_error'] and not x['company_error'] and x['response_bytes']>3000:
        found=c; break
    time.sleep(.1)
if found:
    for m,b,e in [('01','',''),('02','',''),('03','',''),('04','',''),('05','01','04'),('05','05','31')]:
        recs.append(post(op,fu,found,'094',m,b,e)); time.sleep(.1)
manifest={'schema':'w08_t59_boundary_probe_v1','qualification_only':True,'front_sha256':hashlib.sha256(fb).hexdigest(),'front_bytes':len(fb),'found_eventful_code':found,'records':recs}
(OUT/'PROBE.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')
print(json.dumps(manifest,ensure_ascii=False,indent=2))
if not found: raise SystemExit('no eventful code found in probe set; expand discovery set')
if any(r['status']!=200 or r['year_error'] or r['company_error'] for r in recs): raise SystemExit('T59 boundary probe request validation failed')
