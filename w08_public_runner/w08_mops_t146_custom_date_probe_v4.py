import json,pathlib,urllib.request,urllib.parse,http.cookiejar,hashlib,re
OUT=pathlib.Path('w08_t146_custom_date_probe_v4_out');OUT.mkdir(exist_ok=True)
BASE='https://mopsov.twse.com.tw';UA='Mozilla/5.0 (compatible; W08T146Probe/4.0)'
COMMON=[('encodeURIComponent','1'),('step','1'),('firstin','1'),('off','1'),('keyword4',''),('code1',''),('TYPEK2',''),('checkbtn',''),('queryName','co_id_1'),('inpuType','co_id')]

def run(name,pairs):
    cj=http.cookiejar.CookieJar();op=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj));front=BASE+'/mops/web/t146sb10'
    with op.open(urllib.request.Request(front,headers={'User-Agent':UA}),timeout=60) as r: front_bytes=r.read()
    body=urllib.parse.urlencode(pairs).encode('ascii')
    req=urllib.request.Request(BASE+'/mops/web/ajax_t146sb10',data=body,method='POST',headers={'User-Agent':UA,'Accept':'*/*','Content-Type':'application/x-www-form-urlencoded','Referer':front,'Origin':BASE})
    with op.open(req,timeout=120) as r: rb=r.read();status=r.status
    (OUT/f'{name}.request.body').write_bytes(body);(OUT/f'{name}.response.bin').write_bytes(rb)
    txt=rb.decode('utf-8','replace');plain=re.sub('<[^>]+>',' ',re.sub(r'<script.*?</script>','',txt,flags=re.S|re.I));plain=' '.join(plain.split())
    return {'name':name,'status':status,'request':body.decode('ascii'),'request_sha256':hashlib.sha256(body).hexdigest(),'response_bytes':len(rb),'response_sha256':hashlib.sha256(rb).hexdigest(),'preview':plain[:1200],'markers':{'empty_div_shell':'<div id="div01"></div>' in txt and '<table' not in txt,'table_count':txt.lower().count('<table'),'tr_count':txt.lower().count('<tr'),'no_data':'查無所需資料' in txt,'company_error':'公司代號不可空白' in txt or '請輸入公司代號' in txt,'security_error':'FOR SECURITY REASONS' in txt,'dividend':'股利' in txt,'merger':'合併' in txt,'announcement':'公告' in txt}}

def p(scope,typek,start,end,notice='1',co=''):
    return COMMON+[('scope',scope),('co_id_1',co),('typek',typek),('selecttype','0'),('noticeDate','1'),('date','4'),('yymmdd1',start),('yymmdd2',end),('noticeKind',notice),('sort','1')]
R=[]
for typ in ('sii','otc','rotc','pub'):
    R.append(run(f'{typ}_roc094_all',p('2',typ,'094/01/01','094/12/31','1')))
for typ in ('sii','otc'):
    R.append(run(f'{typ}_roc115_all',p('2',typ,'115/01/01','115/09/12','1')))
R.append(run('sii_roc085_all',p('2','sii','085/01/01','085/12/31','1')))
R.append(run('company1101_roc094_all',p('1','sii','094/01/01','094/12/31','1','1101')))
for notice in ('30','9','11'):
    R.append(run(f'sii_roc115_notice{notice}',p('2','sii','115/01/01','115/09/12',notice)))
R.append(run('pub_roc094_pre_notice29',p('2','pub','094/01/01','094/05/04','29')))
(OUT/'PROBE.json').write_text(json.dumps(R,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(R,ensure_ascii=False,indent=2))
