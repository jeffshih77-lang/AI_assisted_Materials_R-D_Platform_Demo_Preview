import gzip,hashlib,json,pathlib,urllib.request,urllib.error,time

OUT=pathlib.Path('w08_post_probe_out'); OUT.mkdir(exist_ok=True)
UA='Mozilla/5.0 (compatible; W08PostContractProbe/1.0)'
BASE='https://mopsov.twse.com.tw'
GENERIC=(b'<div id="div01"></div>',b'FOR SECURITY REASONS, THIS PAGE CAN NOT BE ACCESSED')

def enc_pairs(pairs):
    from urllib.parse import quote
    return ('&'.join(f'{quote(str(k),safe="") }={quote(str(v),safe="")}' for k,v in pairs)).encode('ascii')

def post(name,path,pairs):
    body=enc_pairs(pairs)
    url=BASE+path
    req=urllib.request.Request(url,data=body,method='POST',headers={'User-Agent':UA,'Accept':'*/*','Content-Type':'application/x-www-form-urlencoded'})
    last=None
    for attempt in range(1,5):
        try:
            with urllib.request.urlopen(req,timeout=75) as r:
                resp=r.read(); status=getattr(r,'status',None); final=r.geturl(); headers=dict(r.headers.items())
            break
        except Exception as e:
            last=e
            if attempt==4: raise
            time.sleep(attempt*2)
    (OUT/f'{name}.request.body').write_bytes(body)
    (OUT/f'{name}.response.bin').write_bytes(resp)
    with gzip.GzipFile(OUT/f'{name}.response.bin.gz','wb',mtime=0) as g:g.write(resp)
    text=resp.decode('utf-8','replace')
    rec={'name':name,'url':url,'method':'POST','request_body_ascii':body.decode('ascii'),'request_body_bytes':len(body),'request_body_sha256':hashlib.sha256(body).hexdigest(),'status':status,'final_url':final,'content_type':headers.get('Content-Type'),'response_bytes':len(resp),'response_sha256':hashlib.sha256(resp).hexdigest(),'generic_shell':len(resp)<5000 and any(x in resp for x in GENERIC),'markers':{'table':('<table' in text.lower()),'no_data':('查無資料' in text or '無資料' in text),'provider':('本資料由' in text),'company_code':('公司代號' in text),'announcement':('公告' in text),'dividend':('股利' in text or '股息' in text)}}
    return rec

probes=[]
# T146 exact DOM/ajax1 order; market-wide scope=2, custom date noticeDate=1.
probes.append(post('t146_pub_notice29_roc094_pre_boundary','/mops/web/ajax_t146sb10',[
 ('encodeURIComponent','1'),('step','1'),('firstin','1'),('off','1'),('keyword4',''),('code1',''),('TYPEK2',''),('checkbtn',''),('queryName','co_id_1'),('inpuType','co_id'),('co_id_1',''),('scope','2'),('typek','pub'),('selecttype','0'),('noticeDate','1'),('date','4'),('yymmdd1','094/01/01'),('yymmdd2','094/05/04'),('noticeKind','29'),('sort','1')]))
probes.append(post('t146_sii_notice30_roc115','/mops/web/ajax_t146sb10',[
 ('encodeURIComponent','1'),('step','1'),('firstin','1'),('off','1'),('keyword4',''),('code1',''),('TYPEK2',''),('checkbtn',''),('queryName','co_id_1'),('inpuType','co_id'),('co_id_1',''),('scope','2'),('typek','sii'),('selecttype','0'),('noticeDate','1'),('date','4'),('yymmdd1','115/01/01'),('yymmdd2','115/09/11'),('noticeKind','30'),('sort','1')]))
# t59 exact current form order.
probes.append(post('t59_all_roc085','/mops/web/ajax_t59sb07',[
 ('encodeURIComponent','1'),('step','1'),('firstin','1'),('off','1'),('keyword4',''),('code1',''),('TYPEK2',''),('checkbtn',''),('queryName','co_id'),('inpuType','co_id'),('TYPEK','all'),('co_id',''),('year','085'),('month',''),('b_date',''),('e_date','')]))
probes.append(post('t59_roc094_may_pre_boundary','/mops/web/ajax_t59sb07',[
 ('encodeURIComponent','1'),('step','1'),('firstin','1'),('off','1'),('keyword4',''),('code1',''),('TYPEK2',''),('checkbtn',''),('queryName','co_id'),('inpuType','co_id'),('TYPEK','all'),('co_id',''),('year','094'),('month','05'),('b_date','01'),('e_date','04')]))
# T05 current _2 exact form/ajax1 order. Historical isnew=false.
probes.append(post('t05_v2_hist_roc114_115_qry1','/mops/web/ajax_t05st09_2',[
 ('encodeURIComponent','1'),('step','1'),('firstin','1'),('off','1'),('keyword4',''),('code1',''),('TYPEK2',''),('checkbtn',''),('queryName','co_id'),('inpuType','co_id'),('TYPEK','all'),('isnew','false'),('co_id',''),('date1','114'),('date2','115'),('qryType','1')]))
# Historical observed _1 contract from Rev13; qualification-only probe.
probes.append(post('t05_v1_hist_roc100','/mops/web/ajax_t05st09_1',[
 ('encodeURIComponent','1'),('step','1'),('firstin','1'),('TYPEK','sii'),('year','100'),('co_id',''),('isnew','false')]))

(OUT/'PROBE_MANIFEST.json').write_text(json.dumps({'schema':'w08_mops_post_contract_probe_v1','qualification_only':True,'probes':probes},ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')
print(json.dumps(probes,ensure_ascii=False,indent=2))
if any(p['status']!=200 or p['response_bytes']==0 or p['generic_shell'] for p in probes): raise SystemExit('probe gate failed')
