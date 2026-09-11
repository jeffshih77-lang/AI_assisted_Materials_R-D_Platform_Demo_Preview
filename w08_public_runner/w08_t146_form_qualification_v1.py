import datetime as dt
import hashlib
import json
import pathlib
import re
import urllib.request
from html.parser import HTMLParser

ROOT = pathlib.Path('w08_t146_qualification_v1')
ROOT.mkdir(exist_ok=True)
URL = 'https://mopsov.twse.com.tw/mops/web/t146sb10'
UA = 'Mozilla/5.0 (compatible; W08T146Qualification/1.0)'


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat().replace('+00:00','Z')

req = urllib.request.Request(URL, headers={'User-Agent': UA, 'Accept': '*/*'}, method='GET')
with urllib.request.urlopen(req, timeout=75) as resp:
    body = resp.read()
    status = getattr(resp, 'status', None)
    final_url = resp.geturl()
    headers = dict(resp.headers.items())
(ROOT/'page.response.bin').write_bytes(body)
text = body.decode('utf-8','replace')

class P(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.forms=[]; self.stack=[]; self.global_controls=[]; self.seq=0
        self.current_select=None; self.in_option=False; self.option_text=[]
        self.scripts=[]; self.in_script=False; self.script=[]
    def handle_starttag(self, tag, attrs):
        a=dict(attrs); tl=tag.lower()
        if tl=='form':
            idx=len(self.forms)
            self.forms.append({'index':idx+1,'attrs':a,'controls':[]})
            self.stack.append(idx)
        if tl=='script':
            self.in_script=True; self.script=[]
        if tl in ('input','select','textarea','button'):
            self.seq += 1
            rec={'seq':self.seq,'tag':tl,'attrs':a,'form_index':(self.stack[-1]+1 if self.stack else None),'options':[]}
            self.global_controls.append(rec)
            if self.stack: self.forms[self.stack[-1]]['controls'].append(rec)
            if tl=='select': self.current_select=rec
        if tl=='option' and self.current_select is not None:
            self.in_option=True; self.option_text=[]
            self.current_select['options'].append({'attrs':a,'text':''})
    def handle_endtag(self, tag):
        tl=tag.lower()
        if tl=='form' and self.stack: self.stack.pop()
        if tl=='select': self.current_select=None
        if tl=='option' and self.current_select is not None and self.current_select['options']:
            self.current_select['options'][-1]['text']=''.join(self.option_text).strip()
            self.in_option=False; self.option_text=[]
        if tl=='script':
            self.in_script=False; self.scripts.append(''.join(self.script)); self.script=[]
    def handle_data(self, data):
        if self.in_script: self.script.append(data)
        if self.in_option: self.option_text.append(data)

p=P(); p.feed(text)

# Raw-source form tag evidence and relevant JS snippets; do not reconstruct response bytes.
form_tags=[]
for m in re.finditer(r'<form\b[^>]*>', text, re.I|re.S):
    tag=m.group(0)
    form_tags.append({'offset':m.start(),'tag':tag})
relevant_scripts=[]
for s in p.scripts:
    if any(k in s for k in ('form1','ajax_t146sb10','bringval','noticeKind','yymmdd1','yymmdd2')):
        relevant_scripts.append(s)

result={
 'schema':'raw_w08_t146_form_qualification_v1',
 'classification':'QUALIFICATION_ONLY_DO_NOT_PROMOTE_TO_FORMAL_RAW',
 'retrieved_at':now(), 'request_method':'GET','request_url':URL,
 'http_status':status,'final_url':final_url,'response_headers':headers,
 'payload_bytes':len(body),'payload_sha256':hashlib.sha256(body).hexdigest(),
 'form_tags_raw_source':form_tags,
 'forms_parsed':p.forms,
 'global_controls':p.global_controls,
 'relevant_inline_scripts':relevant_scripts,
 'assertions':{
   'http_200':status==200,
   'payload_nonempty':bool(body),
   'ajax_t146_action_present':'ajax_t146sb10' in text,
   'post_token_present':bool(re.search(r'<form\b[^>]*method\s*=\s*[\"\']?post', text, re.I)),
   'form1_token_present':'form1' in text,
   'bringval_token_present':'bringval' in text,
 }
}
(ROOT/'QUALIFICATION.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')
(ROOT/'RELEVANT_JS.txt').write_text('\n\n----- SCRIPT -----\n'.join(relevant_scripts),encoding='utf-8')
(ROOT/'SHA256SUMS.txt').write_text(f"{hashlib.sha256(body).hexdigest()}  page.response.bin\n",encoding='utf-8')
print(json.dumps({'payload_bytes':len(body),'sha256':hashlib.sha256(body).hexdigest(),'forms':len(p.forms),'controls':len(p.global_controls),'form_tags':form_tags,'assertions':result['assertions']},ensure_ascii=False,indent=2))
