import json,pathlib,urllib.request,urllib.parse,http.cookiejar,hashlib,time,re
OUT=pathlib.Path('w08_capability_probe_v3_out');OUT.mkdir(exist_ok=True)
BASE='https://mopsov.twse.com.tw';UA='Mozilla/5.0 (compatible; W08CapabilityProbe/3.0)'

def run(name,front,ajax,pairs):
 cj=http.cookiejar.CookieJar();op=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj));fu=BASE+front
 with op.open(urllib.request.Request(fu,headers={'User-Agent':UA}),timeout=60) as r: fb=r.read()
 body=urllib.parse.urlencode(pairs).encode(); req=urllib.request.Request(BASE+ajax,data=body,method='POST',headers={'User-Agent':UA,'Content-Type':'application/x-www-form-urlencoded','Referer':fu,'Origin':BASE})
 with op.open(req,timeout=90) as r: rb=r.read();st=r.status
 (OUT/f'{name}.request.body').write_bytes(body);(OUT/f'{name}.response.bin').write_bytes(rb)
 txt=rb.decode('utf-8','replace'); plain=re.sub('<[^>]+>',' ',re.sub(r'<script.*?</script>','',txt,flags=re.S|re.I));plain=' '.join(plain.split())
 return {'name':name,'status':st,'request':body.decode(),'response_bytes':len(rb),'response_sha256':hashlib.sha256(rb).hexdigest(),'plain_preview':plain[:1000],'markers':{k:(v in txt) for k,v in {'company_error':'公司代號不可空白','input_company':'請輸入公司代號','table':'<table','2330':'2330','dividend':'股利','announcement':'公告'}.items()}}

common146=[('encodeURIComponent','1'),('step','1'),('firstin','1'),('off','1'),('keyword4',''),('code1',''),('TYPEK2',''),('checkbtn',''),('queryName','co_id_1'),('inpuType','co_id')]
R=[]
R.append(run('t146_company_2330_recent_all','/mops/web/t146sb10','/mops/web/ajax_t146sb10',common146+[('scope','1'),('co_id_1','2330'),('typek','sii'),('selecttype','0'),('noticeDate','2'),('date','7'),('yymmdd1',''),('yymmdd2',''),('noticeKind','1'),('sort','2')]))
R.append(run('t146_market_sii_recent_all','/mops/web/t146sb10','/mops/web/ajax_t146sb10',common146+[('co_id_1',''),('scope','2'),('typek','sii'),('selecttype','0'),('noticeDate','2'),('date','4'),('yymmdd1',''),('yymmdd2',''),('noticeKind','1'),('sort','2')]))
R.append(run('t146_company_2330_custom_115_notice30','/mops/web/t146sb10','/mops/web/ajax_t146sb10',common146+[('scope','1'),('co_id_1','2330'),('typek','sii'),('selecttype','0'),('noticeDate','1'),('date','4'),('yymmdd1','115/01/01'),('yymmdd2','115/09/11'),('noticeKind','30'),('sort','1')]))
common59=[('encodeURIComponent','1'),('step','1'),('firstin','1'),('off','1'),('keyword4',''),('code1',''),('TYPEK2',''),('checkbtn',''),('queryName','co_id'),('inpuType','co_id'),('TYPEK','all'),('co_id','2330')]
R.append(run('t59_2330_roc094','/mops/web/t59sb07','/mops/web/ajax_t59sb07',common59+[('year','094'),('month',''),('b_date',''),('e_date','')]))
R.append(run('t59_2330_year_blank','/mops/web/t59sb07','/mops/web/ajax_t59sb07',common59+[('year',''),('month',''),('b_date',''),('e_date','')]))
common05=[('encodeURIComponent','1'),('step','1'),('firstin','1'),('off','1'),('keyword4',''),('code1',''),('TYPEK2',''),('checkbtn',''),('queryName','co_id'),('inpuType','co_id'),('TYPEK','all'),('isnew','false'),('co_id','2330'),('date1','085'),('date2','115')]
R.append(run('t05_v2_2330_full_q1','/mops/web/t05st09_2','/mops/web/ajax_t05st09_2',common05+[('qryType','1')]))
R.append(run('t05_v2_2330_full_q2','/mops/web/t05st09_2','/mops/web/ajax_t05st09_2',common05+[('qryType','2')]))
(OUT/'CAPABILITY.json').write_text(json.dumps(R,ensure_ascii=False,indent=2)+'\n',encoding='utf-8');print(json.dumps(R,ensure_ascii=False,indent=2))
