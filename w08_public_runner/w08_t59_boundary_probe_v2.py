import datetime as dt,gzip,hashlib,http.cookiejar,json,pathlib,random,re,time,urllib.parse,urllib.request
OUT=pathlib.Path('w08_t59_boundary_probe_v2_out'); OUT.mkdir(exist_ok=True)
BASE='https://mopsov.twse.com.tw'; FRONT='/mops/web/t59sb07'; AJAX='/mops/web/ajax_t59sb07'; UA='Mozilla/5.0 (compatible; W08T59BoundaryProbe/2.0)'
CODES=['1101','1216','1301','1402','2002','2303','2317','2330','2454','2603','2881','2882']
YEARS=['094','093','090','085']
def now(): return dt.datetime.now(dt.timezone.utc).isoformat().replace('+00:00','Z')
def sha(b): return hashlib.sha256(b).hexdigest()
def open_session():
    last=None
    for a in range(1,7):
        try:
            cj=http.cookiejar.CookieJar(); op=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj)); fu=BASE+FRONT
            with op.open(urllib.request.Request(fu,headers={'User-Agent':UA,'Accept':'text/html,*/*'}),timeout=60) as r: fb=r.read(); st=r.status
            if st!=200 or not fb: raise RuntimeError(f'front bad {st} {len(fb)}')
            return op,fu,fb,list(cj)
        except Exception as e:
            last=repr(e); time.sleep(min(10,2**(a-1)+random.random()))
    raise RuntimeError('front session exhausted '+str(last))
def body_for(code,year,month='',b='',e=''):
    # Exact current t59sb07 form semantics. Note source HTML literally spells firstin="ture".
    pairs=[('encodeURIComponent','1'),('step','1'),('firstin','ture'),('off','1'),('keyword4',''),('code1',''),('TYPEK2',''),('checkbtn',''),('queryName','co_id'),('inpuType','co_id'),('TYPEK','all'),('co_id',code),('year',year),('month',month),('b_date',b),('e_date',e)]
    return urllib.parse.urlencode(pairs).encode('ascii')
def post(op,fu,label,code,year,month='',b='',e=''):
    body=body_for(code,year,month,b,e); (OUT/f'{label}.request_body.bin').write_bytes(body)
    last=None; retry=[]
    for a in range(1,7):
        ts=now()
        try:
            req=urllib.request.Request(BASE+AJAX,data=body,method='POST',headers={'User-Agent':UA,'Accept':'*/*','Content-Type':'application/x-www-form-urlencoded','Referer':fu,'Origin':BASE})
            with op.open(req,timeout=90) as r: rb=r.read(); st=r.status; final=r.geturl(); hdr=dict(r.headers.items())
            if st!=200 or not rb: raise RuntimeError(f'bad status={st} bytes={len(rb)}')
            break
        except Exception as ex:
            last=repr(ex); retry.append({'attempt':a,'at':ts,'error':last})
            if a>=6: raise
            time.sleep(min(15,2**(a-1)+random.random())); op,fu,_,_=open_session()
    (OUT/f'{label}.response.bin').write_bytes(rb)
    with gzip.GzipFile(OUT/f'{label}.response.bin.gz','wb',mtime=0) as g:g.write(rb)
    txt=rb.decode('utf-8','replace'); plain=' '.join(re.sub('<[^>]+>',' ',re.sub(r'<script.*?</script>','',txt,flags=re.I|re.S)).split())
    return {'label':label,'code':code,'year':year,'month':month,'b_date':b,'e_date':e,'retrieved_at':ts,'status':st,'final_url':final,'body_bytes':len(body),'body_sha256':sha(body),'response_bytes':len(rb),'response_sha256':sha(rb),'gzip_sha256':sha((OUT/f'{label}.response.bin.gz').read_bytes()),'gzip_roundtrip_match':gzip.decompress((OUT/f'{label}.response.bin.gz').read_bytes())==rb,'no_data':('查無所需資料' in txt),'year_error':('年度不可空白' in txt),'company_error':('公司代號不可空白' in txt),'security_shell':('FOR SECURITY REASONS' in txt),'has_table':('<table' in txt.lower()),'plain_preview':plain[:800],'retries':retry}
op,fu,fb,cookies=open_session(); (OUT/'front.response.bin').write_bytes(fb); recs=[]; found=None
# Minimal controlled discovery: prove at least one real historical row under the exact official form contract.
for y in YEARS:
    for c in CODES:
        label=f'discovery_{c}_{y}'
        x=post(op,fu,label,c,y); recs.append(x)
        if x['status']==200 and not x['no_data'] and not x['year_error'] and not x['company_error'] and not x['security_shell'] and x['response_bytes']>3000:
            found={'code':c,'year':y,'label':label}; break
        time.sleep(.08)
    if found: break
# Freeze the source cutoff semantics using exact month/day controls around ROC94-05-05.
if found:
    c=found['code']
    for label,y,m,b,e in [('boundary_094_all','094','','',''),('boundary_094_pre0505','094','05','01','04'),('boundary_094_from0505','094','05','05','31'),('out_of_scope_095_all','095','','','')]:
        recs.append(post(op,fu,label,c,y,m,b,e)); time.sleep(.08)
manifest={'schema':'w08_t59_boundary_probe_v2','qualification_only':True,'work_unit_id':'W08-RAW-MOPS-EXRIGHT-PRE20050505','official_page_semantics':'公開發行及94.5.5前之全體公司','derived_execution_year_scope':{'start':'085','end':'094','basis':['existing W08 ROC85-115 coverage contract','official t59sb07 source cutoff 94.5.5 pre-scope']},'exact_contract':{'endpoint':BASE+AJAX,'method':'POST','firstin_literal':'ture','company_required':True,'year_required':True},'front':{'bytes':len(fb),'sha256':sha(fb),'cookie_names':[c.name for c in cookies]},'found_eventful':found,'records':recs,'assertions':{'all_http_200':all(r['status']==200 for r in recs),'all_nonempty':all(r['response_bytes']>0 for r in recs),'all_gzip_roundtrip':all(r['gzip_roundtrip_match'] for r in recs),'eventful_historical_response_found':bool(found),'no_security_shell':all(not r['security_shell'] for r in recs)}}
(OUT/'PROBE.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')
print(json.dumps(manifest,ensure_ascii=False,indent=2))
if not found: raise SystemExit('BLOCKER: no eventful response under exact firstin=ture contract')
if not all(manifest['assertions'].values()): raise SystemExit('qualification assertion failed')
