import gzip,hashlib,json,pathlib,urllib.request,urllib.parse,http.cookiejar,time,re
OUT=pathlib.Path('w08_post_probe_v2_out'); OUT.mkdir(exist_ok=True)
UA='Mozilla/5.0 (compatible; W08PostContractProbe/2.0)'
BASE='https://mopsov.twse.com.tw'
EMPTY_SHELL_RE=re.compile(r'<div id=["\']div01["\']\s*>\s*(?:<center>\s*<h3><font[^>]*>\s*</font></h3>\s*</center>)?\s*</div>',re.I|re.S)

def enc_pairs(pairs):
    return urllib.parse.urlencode(pairs).encode('ascii')

def session_post(name,front,path,pairs):
    cj=http.cookiejar.CookieJar()
    opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    front_url=BASE+front
    fre=urllib.request.Request(front_url,headers={'User-Agent':UA,'Accept':'text/html,*/*'})
    with opener.open(fre,timeout=60) as r:
        fbody=r.read(); fstatus=getattr(r,'status',None)
    body=enc_pairs(pairs); url=BASE+path
    req=urllib.request.Request(url,data=body,method='POST',headers={'User-Agent':UA,'Accept':'*/*','Content-Type':'application/x-www-form-urlencoded','Referer':front_url,'Origin':BASE})
    last=None
    for attempt in range(1,5):
        try:
            with opener.open(req,timeout=75) as r:
                resp=r.read(); status=getattr(r,'status',None); final=r.geturl(); headers=dict(r.headers.items())
            break
        except Exception as e:
            last=e
            if attempt==4: raise
            time.sleep(attempt*2)
    (OUT/f'{name}.front.response.bin').write_bytes(fbody)
    (OUT/f'{name}.request.body').write_bytes(body)
    (OUT/f'{name}.response.bin').write_bytes(resp)
    with gzip.GzipFile(OUT/f'{name}.response.bin.gz','wb',mtime=0) as g:g.write(resp)
    text=resp.decode('utf-8','replace')
    stripped=re.sub(r'<script.*?</script>','',text,flags=re.I|re.S)
    empty_shell=bool(EMPTY_SHELL_RE.search(stripped)) and len(re.sub(r'<[^>]+>','',stripped).strip())<120
    rec={'name':name,'front_url':front_url,'front_status':fstatus,'front_bytes':len(fbody),'front_sha256':hashlib.sha256(fbody).hexdigest(),'cookie_names':[c.name for c in cj],'url':url,'method':'POST','request_body_ascii':body.decode('ascii'),'request_body_bytes':len(body),'request_body_sha256':hashlib.sha256(body).hexdigest(),'status':status,'final_url':final,'content_type':headers.get('Content-Type'),'response_bytes':len(resp),'response_sha256':hashlib.sha256(resp).hexdigest(),'empty_div01_shell':empty_shell,'markers':{'table':('<table' in text.lower()),'company_code':('公司代號' in text),'announcement':('公告' in text),'dividend':('股利' in text or '股息' in text),'autoform':('autoForm' in text),'red_error':("<font color='red'>" in text)}}
    return rec

T146_COMMON=[('encodeURIComponent','1'),('step','1'),('firstin','1'),('off','1'),('keyword4',''),('code1',''),('TYPEK2',''),('checkbtn',''),('queryName','co_id_1'),('inpuType','co_id'),('co_id_1','')]
probes=[]
probes.append(session_post('t146_pub_notice29_roc094_pre_boundary','/mops/web/t146sb10','/mops/web/ajax_t146sb10',T146_COMMON+[('scope','2'),('typek','pub'),('selecttype','0'),('noticeDate','1'),('date','4'),('yymmdd1','094/01/01'),('yymmdd2','094/05/04'),('noticeKind','29'),('sort','1')]))
probes.append(session_post('t146_sii_notice30_roc115','/mops/web/t146sb10','/mops/web/ajax_t146sb10',T146_COMMON+[('scope','2'),('typek','sii'),('selecttype','0'),('noticeDate','1'),('date','4'),('yymmdd1','115/01/01'),('yymmdd2','115/09/11'),('noticeKind','30'),('sort','1')]))
T59=[('encodeURIComponent','1'),('step','1'),('firstin','1'),('off','1'),('keyword4',''),('code1',''),('TYPEK2',''),('checkbtn',''),('queryName','co_id'),('inpuType','co_id'),('TYPEK','all'),('co_id','')]
probes.append(session_post('t59_all_roc085','/mops/web/t59sb07','/mops/web/ajax_t59sb07',T59+[('year','085'),('month',''),('b_date',''),('e_date','')]))
probes.append(session_post('t59_roc094_may_pre_boundary','/mops/web/t59sb07','/mops/web/ajax_t59sb07',T59+[('year','094'),('month','05'),('b_date','01'),('e_date','04')]))
T05=[('encodeURIComponent','1'),('step','1'),('firstin','1'),('off','1'),('keyword4',''),('code1',''),('TYPEK2',''),('checkbtn',''),('queryName','co_id'),('inpuType','co_id'),('TYPEK','all')]
probes.append(session_post('t05_v2_hist_roc114_115_qry1','/mops/web/t05st09_2','/mops/web/ajax_t05st09_2',T05+[('isnew','false'),('co_id',''),('date1','114'),('date2','115'),('qryType','1')]))
probes.append(session_post('t05_v1_hist_roc100','/mops/web/t05st09_2','/mops/web/ajax_t05st09_1',[('encodeURIComponent','1'),('step','1'),('firstin','1'),('TYPEK','sii'),('year','100'),('co_id',''),('isnew','false')]))
manifest={'schema':'w08_mops_post_contract_probe_v2','qualification_only':True,'session_model':'GET front then POST exact body using same CookieJar + Referer + Origin','probes':probes}
(OUT/'PROBE_MANIFEST.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')
print(json.dumps(probes,ensure_ascii=False,indent=2))
# Fail closed on HTTP failure or the known empty AJAX shell for T146/T59/T05v2. v1 may legitimately be obsolete, but preserve result.
critical=[p for p in probes if p['name']!='t05_v1_hist_roc100']
if any(p['status']!=200 or p['response_bytes']==0 or p['empty_div01_shell'] for p in critical): raise SystemExit('session-aware critical probe gate failed')
