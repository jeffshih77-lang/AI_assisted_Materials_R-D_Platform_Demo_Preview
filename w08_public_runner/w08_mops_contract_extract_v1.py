import hashlib, json, pathlib, re, urllib.parse, urllib.request
from html.parser import HTMLParser

OUT=pathlib.Path('w08_contract_extract_out'); OUT.mkdir(exist_ok=True)
UA='Mozilla/5.0 (compatible; W08ContractExtractor/1.0)'
TARGETS={
 't146':'https://mopsov.twse.com.tw/mops/web/t146sb10',
 't59':'https://mopsov.twse.com.tw/mops/web/t59sb07',
 't05':'https://mopsov.twse.com.tw/mops/web/t05st09_2',
}
TERMS=('ajax_t146sb10','t146sb10','noticeKind','ajax_t59sb07','t59sb07','ajax_t05st09_1','ajax_t05st09_2','t05st09','qryType','date1','date2','yymmdd1','yymmdd2','selecttype','noticeDate')

def fetch(url):
    req=urllib.request.Request(url,headers={'User-Agent':UA,'Accept':'text/html,*/*'})
    with urllib.request.urlopen(req,timeout=60) as r:
        return r.read(), r.geturl(), dict(r.headers.items())

class P(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True); self.forms=[]; self.form_stack=[]; self.scripts=[]; self._script=None; self.select_stack=[]
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=='form':
            f={'attrs':a,'inputs':[],'selects':[],'buttons':[]}; self.forms.append(f); self.form_stack.append(f)
        elif tag=='input' and self.form_stack: self.form_stack[-1]['inputs'].append(a)
        elif tag=='button' and self.form_stack: self.form_stack[-1]['buttons'].append(a)
        elif tag=='select' and self.form_stack:
            s={'attrs':a,'options':[]}; self.form_stack[-1]['selects'].append(s); self.select_stack.append(s)
        elif tag=='option' and self.select_stack: self.select_stack[-1]['options'].append(a)
        elif tag=='script':
            self._script={'attrs':a,'text':''}; self.scripts.append(self._script)
    def handle_endtag(self,tag):
        if tag=='form' and self.form_stack: self.form_stack.pop()
        elif tag=='select' and self.select_stack: self.select_stack.pop()
        elif tag=='script': self._script=None
    def handle_data(self,data):
        if self._script is not None: self._script['text'] += data

results={}
for key,url in TARGETS.items():
    body,final,headers=fetch(url)
    (OUT/f'{key}.html').write_bytes(body)
    text=body.decode('utf-8','replace')
    p=P(); p.feed(text)
    evidence=[]
    for i,line in enumerate(text.splitlines(),1):
        if any(t.lower() in line.lower() for t in TERMS): evidence.append({'line':i,'text':line[:4000]})
    script_refs=[]
    for s in p.scripts:
        src=s['attrs'].get('src')
        if src:
            absu=urllib.parse.urljoin(final,src)
            try:
                sb,sf,sh=fetch(absu)
                st=sb.decode('utf-8','replace')
                hits=[{'line':i,'text':ln[:4000]} for i,ln in enumerate(st.splitlines(),1) if any(t.lower() in ln.lower() for t in TERMS)]
                if hits:
                    name='script_'+hashlib.sha256(absu.encode()).hexdigest()[:12]+'.js'
                    (OUT/name).write_bytes(sb)
                    script_refs.append({'url':absu,'sha256':hashlib.sha256(sb).hexdigest(),'bytes':len(sb),'hits':hits,'saved_as':name})
            except Exception as e:
                script_refs.append({'url':absu,'error':repr(e)})
    results[key]={
      'url':url,'final_url':final,'bytes':len(body),'sha256':hashlib.sha256(body).hexdigest(),
      'headers':headers,'forms':p.forms,'inline_or_html_hits':evidence,'script_refs_with_hits':script_refs,
    }
(OUT/'CONTRACT_EVIDENCE.json').write_text(json.dumps(results,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')
print(json.dumps(results,ensure_ascii=False,indent=2)[:50000])
