import datetime as dt
import hashlib, json, pathlib, re
import urllib.parse, urllib.request

ROOT=pathlib.Path('w08_t146_post_qualification_v2'); ROOT.mkdir(exist_ok=True)
URL='https://mopsov.twse.com.tw/mops/web/ajax_t146sb10'
UA='Mozilla/5.0 (compatible; W08T146Qualification/2.0)'
# Ordered successful controls from official form1 DOM after official doAction(), with explicit market-wide/custom-date query choices.
pairs=[
 ('step','1'),('firstin','1'),('off','1'),('keyword4',''),('code1',''),('TYPEK2',''),('checkbtn',''),
 ('queryName','co_id_1'),('inpuType','co_id'),('co_id_1',''),('scope','2'),('typek','sii'),('selecttype','0'),
 ('date','4'),('noticeDate','1'),('yymmdd1','115/01/01'),('yymmdd2','115/09/11'),('noticeKind','30'),('sort','1')]
body=urllib.parse.urlencode(pairs).encode('ascii')
(ROOT/'request.body.bin').write_bytes(body)
req=urllib.request.Request(URL,data=body,method='POST',headers={
 'User-Agent':UA,'Accept':'*/*','Content-Type':'application/x-www-form-urlencoded; charset=UTF-8',
 'Referer':'https://mopsov.twse.com.tw/mops/web/t146sb10'})
ts=dt.datetime.now(dt.timezone.utc).isoformat().replace('+00:00','Z')
with urllib.request.urlopen(req,timeout=90) as resp:
    rb=resp.read(); status=getattr(resp,'status',None); final=resp.geturl(); headers=dict(resp.headers.items())
(ROOT/'response.body.bin').write_bytes(rb)
txt=rb.decode('utf-8','replace')
# Evidence only: preserve bytes; parse only metadata/anomaly markers.
page_nums=sorted(set(int(x) for x in re.findall(r"pagenum[^0-9]{0,30}(\d+)",txt,re.I)))
links=re.findall(r"document\.[A-Za-z0-9_]+\.pagenum\.value=['\"]?(\d+)",txt,re.I)
meta={
 'schema':'raw_w08_t146_post_qualification_v2','classification':'QUALIFICATION_ONLY_DO_NOT_PROMOTE_TO_FORMAL_RAW',
 'retrieved_at':ts,'request_method':'POST','request_url':URL,'request_content_type':'application/x-www-form-urlencoded; charset=UTF-8',
 'request_pairs_ordered':pairs,'request_body_bytes':len(body),'request_body_sha256':hashlib.sha256(body).hexdigest(),
 'http_status':status,'final_url':final,'response_headers':headers,'response_body_bytes':len(rb),'response_body_sha256':hashlib.sha256(rb).hexdigest(),
 'response_evidence':{
   'generic_security_shell': len(rb)<5000 and ('FOR SECURITY REASONS' in txt or '<div id="div01"></div>' in txt),
   'contains_notice_kind_label':'決定分配股息及紅利或其他利益' in txt,
   'contains_company_label':'公司代號' in txt or '公司名稱' in txt,
   'contains_no_data':'查無資料' in txt or '無資料' in txt,
   'pagenum_regex_values':page_nums,'pagenum_assignment_values':sorted(set(int(x) for x in links)),
   'table_tag_count':len(re.findall(r'<table\b',txt,re.I)),
   'tr_tag_count':len(re.findall(r'<tr\b',txt,re.I)),
   'onclick_count':len(re.findall(r'onclick=',txt,re.I)),
 },
 'qualification_basis':{
   'official_form':'form1 action=/mops/web/ajax_t146sb10 method=post',
   'official_pre_submit_js':"doAction() sets step=1 when nonzero and firstin=1, then action=/mops/web/ajax_ + document.fh.funcName.value",
   'serialization':'ordered successful named controls in official form DOM; unchecked radios and unnamed controls excluded; query choices explicitly set to scope=2/typek=sii/custom-date/noticeKind=30/sort=1'
 }
}
(ROOT/'QUALIFICATION.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')
(ROOT/'SHA256SUMS.txt').write_text(f"{hashlib.sha256(body).hexdigest()}  request.body.bin\n{hashlib.sha256(rb).hexdigest()}  response.body.bin\n",encoding='utf-8')
print(json.dumps(meta,ensure_ascii=False,indent=2))
