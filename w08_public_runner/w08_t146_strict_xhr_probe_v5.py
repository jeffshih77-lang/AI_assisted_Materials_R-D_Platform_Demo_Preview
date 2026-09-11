import datetime as dt
import gzip
import hashlib
import html.parser
import http.cookiejar
import json
import pathlib
import time
import urllib.parse
import urllib.request

ROOT = pathlib.Path('out_w08_t146_strict_v5')
ROOT.mkdir(exist_ok=True)
FRONT = 'https://mopsov.twse.com.tw/mops/web/t146sb10'
MOPS2 = 'https://mopsov.twse.com.tw/mops/web/js/mops2.js'
UA = 'Mozilla/5.0 (compatible; W08T146Qualification/5.0)'


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat().replace('+00:00', 'Z')


def sha(b):
    return hashlib.sha256(b).hexdigest()


def save_bytes(stem, b, gzip_copy=False):
    p = ROOT / stem
    p.write_bytes(b)
    rec = {'file': stem, 'bytes': len(b), 'sha256': sha(b)}
    if gzip_copy:
        gz = ROOT / (stem + '.gz')
        with gzip.GzipFile(gz, 'wb', mtime=0) as f:
            f.write(b)
        gb = gz.read_bytes()
        assert gzip.decompress(gb) == b
        rec.update({'gzip_file': gz.name, 'gzip_sha256': sha(gb), 'gzip_roundtrip_match': True})
    return rec


class OrderedFormParser(html.parser.HTMLParser):
    def __init__(self):
        super().__init__()
        self.in_target = False
        self.form = None
        self.controls = []
        self.cur_select_index = None

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == 'form' and (a.get('name') == 'form1' or a.get('id') == 'form1'):
            self.in_target = True
            self.form = {'action': a.get('action'), 'method': (a.get('method') or 'GET').upper(), 'attrs': a}
            return
        if not self.in_target:
            return
        if tag == 'input':
            self.controls.append({
                'kind': 'input', 'name': a.get('name'), 'type': (a.get('type') or 'text').lower(),
                'value': a.get('value', ''), 'checked': ('checked' in a), 'attrs': a,
            })
        elif tag == 'select':
            self.controls.append({'kind': 'select', 'name': a.get('name'), 'options': [], 'attrs': a})
            self.cur_select_index = len(self.controls) - 1
        elif tag == 'option' and self.cur_select_index is not None:
            self.controls[self.cur_select_index]['options'].append({
                'value': a.get('value', ''), 'selected': ('selected' in a), 'text': ''
            })

    def handle_data(self, data):
        if self.in_target and self.cur_select_index is not None:
            opts = self.controls[self.cur_select_index].get('options') or []
            if opts:
                opts[-1]['text'] += data

    def handle_endtag(self, tag):
        if tag == 'select' and self.in_target:
            self.cur_select_index = None
        elif tag == 'form' and self.in_target:
            self.in_target = False
            self.cur_select_index = None


def js_encode_component(s):
    # ECMAScript encodeURIComponent leaves A-Z a-z 0-9 - _ . ! ~ * ' ( ) unescaped.
    return urllib.parse.quote(str(s), safe="-_.!~*'()")


def selected_value(ctrl):
    opts = ctrl.get('options') or []
    sel = [o for o in opts if o.get('selected')]
    if sel:
        return sel[0].get('value', '')
    return opts[0].get('value', '') if opts else ''


def build_ajax_body(controls, changes):
    parts = ['encodeURIComponent=1']
    emitted = []
    for c in controls:
        name = c.get('name')
        if not name:
            continue
        if c['kind'] == 'input':
            typ = c.get('type', '')
            if typ in ('submit', 'button', 'image', 'reset', 'file'):
                continue
            if typ in ('radio', 'checkbox'):
                target = changes.get(name, None)
                checked = (str(c.get('value', '')) == str(target)) if target is not None else bool(c.get('checked'))
                if not checked:
                    continue
                value = c.get('value', '')
            else:
                value = changes.get(name, c.get('value', ''))
        else:
            value = changes.get(name, selected_value(c))
        parts.append(name + '=' + js_encode_component(value))
        emitted.append([name, str(value)])
    return '&'.join(parts).encode('utf-8'), emitted


jar = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))

def get(url, accept='text/html,*/*'):
    req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept': accept}, method='GET')
    with opener.open(req, timeout=90) as r:
        b = r.read(); s = getattr(r, 'status', None); final = r.geturl(); h = dict(r.headers.items())
    if s != 200 or not b:
        raise RuntimeError(f'GET failed {url} status={s} bytes={len(b)}')
    return b, s, final, h

front_b, front_s, front_final, front_h = get(FRONT)
front_rec = save_bytes('front.response.bin', front_b, True)
mops2_b, mops2_s, mops2_final, mops2_h = get(MOPS2, '*/*')
mops2_rec = save_bytes('mops2.js.response.bin', mops2_b, False)
mops2_t = mops2_b.decode('utf-8', 'replace')
ajax_markers = {
    'encode_prefix': "var str='encodeURIComponent=1'" in mops2_t or 'var str = \'encodeURIComponent=1\'' in mops2_t,
    'form_elements': 'form1.elements' in mops2_t,
    'skip_unchecked_checkbox': 'checkbox' in mops2_t and 'checked' in mops2_t,
    'skip_unchecked_radio': 'radio' in mops2_t and 'checked' in mops2_t,
    'xhr_post': 'open("POST"' in mops2_t or "open('POST'" in mops2_t,
    'form_urlencoded': 'application/x-www-form-urlencoded' in mops2_t,
    'send_serialized': 'send(str)' in mops2_t,
}
if not all(ajax_markers.values()):
    raise SystemExit('current mops2.js ajax1 semantics not fully matched: ' + json.dumps(ajax_markers))

parser = OrderedFormParser(); parser.feed(front_b.decode('utf-8', 'replace'))
if not parser.form or parser.form['method'] != 'POST' or not parser.form.get('action'):
    raise SystemExit('form1 POST contract unresolved')
action = urllib.parse.urljoin(FRONT, parser.form['action'])

cases = [
    {'label':'market_sii_nk30_recent','scope':'2','co_id_1':'','noticeDate':'1','typek':'sii','selecttype':'1','date':'4','noticeKind':'30','sort':'1','yymmdd1':'115/01/01','yymmdd2':'115/09/11'},
    {'label':'market_sii_nk9_recent','scope':'2','co_id_1':'','noticeDate':'1','typek':'sii','selecttype':'1','date':'4','noticeKind':'9','sort':'1','yymmdd1':'115/01/01','yymmdd2':'115/09/11'},
    {'label':'market_sii_nk11_recent','scope':'2','co_id_1':'','noticeDate':'1','typek':'sii','selecttype':'2','date':'4','noticeKind':'11','sort':'1','yymmdd1':'115/01/01','yymmdd2':'115/09/11'},
    {'label':'market_pub_nk29_pre094','scope':'2','co_id_1':'','noticeDate':'1','typek':'pub','selecttype':'1','date':'4','noticeKind':'29','sort':'1','yymmdd1':'093/01/01','yymmdd2':'094/05/04'},
    {'label':'company_2330_nk30_recent','scope':'1','co_id_1':'2330','noticeDate':'1','typek':'sii','selecttype':'1','date':'4','noticeKind':'30','sort':'1','yymmdd1':'115/01/01','yymmdd2':'115/09/11'},
]

results=[]
for c in cases:
    changes = {'firstin':'1', **{k:v for k,v in c.items() if k != 'label'}}
    body, emitted = build_ajax_body(parser.controls, changes)
    (ROOT / (c['label'] + '.request_body.bin')).write_bytes(body)
    cookie_names_before = sorted({x.name for x in jar})
    headers = {
        'User-Agent': UA,
        'Accept': '*/*',
        'Content-Type': 'application/x-www-form-urlencoded',
        'Referer': FRONT,
        'Origin': 'https://mopsov.twse.com.tw',
    }
    req = urllib.request.Request(action, data=body, headers=headers, method='POST')
    ts=now()
    with opener.open(req, timeout=90) as r:
        rb=r.read(); rs=getattr(r,'status',None); rf=r.geturl(); rh=dict(r.headers.items())
    if rs != 200 or not rb:
        raise RuntimeError(f'POST failed {c["label"]} status={rs} bytes={len(rb)}')
    response_rec=save_bytes(c['label']+'.response.bin', rb, True)
    t=rb.decode('utf-8','replace')
    markers={
        'empty_div_shell': ('<div id="div01"></div>' in t or '<div id="div01" >\n\n</div>' in t),
        'security_error': ('FOR SECURITY REASONS' in t or '錯誤代碼' in t),
        'company_input_error': ('請輸入公司代號或簡稱' in t),
        'contains_no_data': any(x in t for x in ['查無資料','無符合','沒有符合']),
        'table_count': t.lower().count('<table'), 'tr_count': t.lower().count('<tr'),
        'contains_2330': '2330' in t,
        'contains_category_terms': any(x in t for x in ['股息','股利','紅利','合併','股份轉換','分割','新股']),
    }
    results.append({
        'label':c['label'],'case':c,'request_url':action,'request_method':'POST',
        'request_body_bytes':len(body),'request_body_sha256':sha(body),'request_fields_in_exact_emission_order':emitted,
        'cookie_names_before_post':cookie_names_before,'cookie_count_before_post':len(cookie_names_before),
        'http_status':rs,'final_url':rf,'retrieved_at':ts,'response':response_rec,'markers':markers,
    })
    print(c['label'], len(body), len(rb), markers, flush=True)
    time.sleep(.3)

assertions={
    'front_http_200': front_s==200,
    'mops2_http_200': mops2_s==200,
    'ajax1_current_semantics_all_matched': all(ajax_markers.values()),
    'form_method_post': parser.form['method']=='POST',
    'all_post_http_200': all(x['http_status']==200 for x in results),
    'all_post_nonempty': all(x['response']['bytes']>0 for x in results),
    'at_least_one_session_cookie_before_post': any(x['cookie_count_before_post']>0 for x in results),
    'at_least_one_data_shaped_or_explicit_no_data_response': any((not x['markers']['empty_div_shell']) and (x['markers']['tr_count']>=2 or x['markers']['contains_no_data']) for x in results),
}
probe={
    'schema':'w08_mops_t146_strict_xhr_probe_v5',
    'role':'SOURCE_QUALIFICATION_EVIDENCE_NOT_FORMAL_RAW',
    'source_family':'MOPS_CA_ANNOUNCEMENT_T146_STRUCTURED_V1',
    'front_url':FRONT,'action':action,'front':front_rec,'front_response_headers':{k:v for k,v in front_h.items() if k.lower()!='set-cookie'},
    'mops2':mops2_rec,'mops2_ajax1_semantic_markers':ajax_markers,
    'cookie_names_after_front':sorted({x.name for x in jar}),
    'form_control_order':[{'kind':x['kind'],'name':x.get('name'),'type':x.get('type')} for x in parser.controls],
    'results':results,'assertions':assertions,
}
(ROOT/'PROBE.json').write_text(json.dumps(probe,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')
print(json.dumps(assertions,ensure_ascii=False,indent=2),flush=True)
# Qualification is fail-closed if no data-shaped/no-data response; artifact still preserved for diagnosis.
if not all([assertions['front_http_200'],assertions['mops2_http_200'],assertions['ajax1_current_semantics_all_matched'],assertions['form_method_post'],assertions['all_post_http_200'],assertions['all_post_nonempty']]):
    raise SystemExit('transport qualification assertions failed')
