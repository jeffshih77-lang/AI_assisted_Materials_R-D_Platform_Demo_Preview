#!/usr/bin/env python3
import argparse, concurrent.futures as cf, datetime as dt, hashlib, html, json, pathlib, re, time, urllib.parse, urllib.request, zipfile
UA='Mozilla/5.0 (compatible; P4B-FSC/4.2)'
LIST='https://www.fsc.gov.tw/ch/home.jsp?id=96&parentpath=0%2C2&mcustomize='
BASE='https://www.fsc.gov.tw/ch/'
FROZEN=14638
def nowz(): return dt.datetime.now(dt.timezone.utc).isoformat().replace('+00:00','Z')
def sha(b): return hashlib.sha256(b).hexdigest()
def clean(x): return html.unescape(re.sub(r'<[^>]+>',' ',x)).strip()
def absurl(h):
    if h.startswith('http'): return h
    return 'https://www.fsc.gov.tw'+h if h.startswith('/') else BASE+h
def parse(body):
    s=body.decode('utf-8','replace')
    mt=re.search(r'頁數\s*[0-9,]+\s*/\s*([0-9,]+)',s); mr=re.search(r'共有\s*<span[^>]*class=["\']red["\'][^>]*>\s*([0-9,]+)',s)
    tp=int(mt.group(1).replace(',','')) if mt else None; tr=int(mr.group(1).replace(',','')) if mr else None
    a=s.find('<div class="newslist"'); b=s.find('<div class="page">',a); block=s[a:b if b>0 else len(s)]
    out=[]
    for lm in re.finditer(r'<li\b[^>]*role=["\']row["\'][^>]*>([\s\S]*?)</li>',block,re.I):
        x=lm.group(1)
        def span(c): return re.search(r'<span\b[^>]*class=["\'][^"\']*\b'+c+r'\b[^"\']*["\'][^>]*>(.*?)</span>',x,re.I|re.S)
        no,date,unit=span('no'),span('date'),span('unit')
        if not(no and date and unit): continue
        n=clean(no.group(1))
        if not n.isdigit(): continue
        am=re.search(r'<a\b[^>]*href=["\']([^"\']+)["\'][^>]*>([\s\S]*?)</a>',x,re.I)
        if not am: continue
        href=html.unescape(am.group(1)); title=clean(am.group(2)); dm=re.search(r'(?:[?&]|&amp;)dataserno=(\d+)',href); ds=dm.group(1) if dm else None
        out.append({'current_no':int(n),'published_date':clean(date.group(1)),'unit':clean(unit.group(1)),'dataserno':ds,'title':title,'url':absurl(href),'resource_kind':'HTML_DETAIL' if ds else 'DIRECT_DOCUMENT'})
    return tr,tp,out
def page(p):
    q=urllib.parse.urlencode({'id':'96','contentid':'96','parentpath':'0,2','mcustomize':'news_list.jsp','page':str(p),'pagesize':'15'}).encode()
    for a in range(5):
        try:
            req=urllib.request.Request(LIST,data=q,method='POST',headers={'User-Agent':UA,'Content-Type':'application/x-www-form-urlencoded'})
            with urllib.request.urlopen(req,timeout=60) as r: body=r.read(); st=r.status
            if st==200 and body:
                tr,tp,rows=parse(body); return tr,tp,rows
        except Exception:
            if a==4: raise
            time.sleep(a+1)
def idsha(rows):
    z=''.join(f"{r['record_no']}|{r.get('dataserno') or ''}|{r['published_date']}|{r['record_identity']}\n" for r in rows)
    return sha(z.encode())
def rowsha(rows):
    z=''.join('|'.join([str(r['record_no']),r.get('dataserno') or '',r['published_date'],r['record_identity'],r['resource_kind'],r['unit'],r['title'],r['url']])+'\n' for r in rows)
    return sha(z.encode())
def get(r):
    err=None
    for a in range(8):
        try:
            req=urllib.request.Request(r['url'],headers={'User-Agent':UA,'Accept':'*/*','Connection':'close'})
            with urllib.request.urlopen(req,timeout=120) as x: body=x.read(); hdr=dict(x.headers.items()); final=x.geturl(); st=x.status
            if st==200 and body:
                ct=(hdr.get('Content-Type') or '').lower()
                if r['resource_kind']=='DIRECT_DOCUMENT' and len(body)<64: raise RuntimeError('small document')
                if r['resource_kind']=='HTML_DETAIL' and 'html' not in ct and not body.lstrip().startswith(b'<'): raise RuntimeError('not html')
                return r,body,hdr,final,a+1
        except Exception as e: err=repr(e); time.sleep(min(20,2**a))
    raise RuntimeError(f"record {r['record_no']} failed {err}")
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('chunk'); ns=ap.parse_args()
    specs=json.loads(pathlib.Path('tools/p4b_outstanding_specs.json').read_text()); sp=specs[ns.chunk]; chunk=ns.chunk
    oldlo,oldhi=sp['record_no_min'],sp['record_no_max']; expected=list(range(oldlo,oldhi+1)); ID_SHA=sp['identity_sha256']; ROW_SHA=sp['fullrow_sha256']
    tr,tp,_=page(1)
    if tr < FROZEN: raise SystemExit(f'bad total {tr}')
    delta=tr-FROZEN; lo,hi=oldlo+delta,oldhi+delta; plo=(lo-1)//15+1; phi=(hi-1)//15+1
    pages={}
    with cf.ThreadPoolExecutor(max_workers=4) as ex:
        fs={ex.submit(page,p):p for p in range(plo,phi+1)}
        for f in cf.as_completed(fs): pages[fs[f]]=f.result()
    rows=[]
    for p in range(plo,phi+1):
        tr2,tp2,rr=pages[p]
        if (tr2,tp2)!=(tr,tp): raise SystemExit('snapshot drift')
        for r in rr:
            if lo <= r['current_no'] <= hi:
                old=r['current_no']-delta; x=dict(r); x.pop('current_no'); x['record_no']=old; x['source_page']=(old-1)//15+1; x['record_identity']='dataserno:'+x['dataserno'] if x['dataserno'] else 'record_no:'+str(old); rows.append(x)
    rows.sort(key=lambda x:x['record_no'])
    if [r['record_no'] for r in rows] != expected: raise SystemExit('record set mismatch')
    ids,full=idsha(rows),rowsha(rows)
    if ids!=ID_SHA or full!=ROW_SHA: raise SystemExit(f'gate mismatch id={ids} row={full}')
    root=pathlib.Path('out/payload'); (root/'detail').mkdir(parents=True,exist_ok=True); (root/'meta').mkdir(exist_ok=True)
    got=[]
    with cf.ThreadPoolExecutor(max_workers=2) as ex:
        fs=[ex.submit(get,r) for r in rows]
        for f in cf.as_completed(fs): got.append(f.result())
    manifest=[]
    for r,body,hdr,final,attempts in sorted(got,key=lambda z:z[0]['record_no']):
        ct=(hdr.get('Content-Type') or '').lower(); ext='.html' if r['resource_kind']=='HTML_DETAIL' else ('.pdf' if body.startswith(b'%PDF') or 'pdf' in ct else '.bin')
        rid=r['dataserno'] or f"record{r['record_no']:05d}"; stem=f"{r['source_page']:04d}_{r['record_no']:05d}_{r['published_date']}_{rid}"
        rp=root/'detail'/(stem+'.response'+ext); mp=root/'meta'/(stem+'.capture.json'); rp.write_bytes(body)
        meta={'schema':'p4b_exact_http_capture_v1','lane_code':'P4-B','dataset':'FINANCIAL_NEWS_EVENTS','source_family':'FSC_OFFICIAL_NEWS_ARCHIVE_V1','source_contract_version':'1.2.0','recovery_collector_version':'4.2.0','method':'GET','request_url':r['url'],'final_url':final,'retrieved_at':nowz(),'http_status':200,'response_headers':hdr,'payload_bytes':len(body),'payload_sha256':sha(body),'source_page':r['source_page'],'record_no':r['record_no'],'dataserno':r['dataserno'],'record_identity':r['record_identity'],'resource_kind':r['resource_kind'],'published_date':r['published_date'],'published_date_source':'FSC frozen archive list row reconstructed after hash gate','available_at':'unknown','unit':r['unit'],'title':r['title'],'raw_semantics':'exact FSC linked resource HTTP response bytes','classification':'FORMAL_RAW_CANDIDATE_PENDING_DRIVE_READBACK','attempts_used':attempts}
        mp.write_text(json.dumps(meta,ensure_ascii=False,indent=2,sort_keys=True)+'\n')
        manifest.append({'record_no':r['record_no'],'source_page':r['source_page'],'dataserno':r['dataserno'],'record_identity':r['record_identity'],'resource_kind':r['resource_kind'],'published_date':r['published_date'],'raw_path':str(rp.relative_to(root)),'raw_bytes':len(body),'raw_sha256':sha(body),'metadata_path':str(mp.relative_to(root))})
    m={'schema':'p4b_fsc_recovery_chunk_manifest_v42','chunk':chunk,'expected_record_count':len(expected),'captured_record_count':len(manifest),'failure_count':0,'identity_sha256':ids,'fullrow_sha256':full,'raw_bytes':sum(x['raw_bytes'] for x in manifest),'records':manifest,'status':'CAPTURED_VALIDATED_PENDING_DRIVE_READBACK','generated_at':nowz()}
    (root/f'P4B_FSC_RECOVERY_{chunk}_MANIFEST.json').write_text(json.dumps(m,ensure_ascii=False,indent=2,sort_keys=True)+'\n')
    pkg=pathlib.Path(f'out/P4B_FSC_RECOVERY_{chunk}_V42.zip')
    with zipfile.ZipFile(pkg,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in sorted(root.rglob('*')):
            if p.is_file(): z.write(p,p.relative_to(root))
    receipt={'chunk':chunk,'package':pkg.name,'bytes':pkg.stat().st_size,'sha256':hashlib.sha256(pkg.read_bytes()).hexdigest(),'record_count':len(expected),'identity_sha256':ids,'fullrow_sha256':full,'status':'CAPTURED_VALIDATED_PENDING_DRIVE_READBACK'}
    pathlib.Path(f'out/P4B_FSC_RECOVERY_{chunk}_V42_RECEIPT.json').write_text(json.dumps(receipt,indent=2,sort_keys=True)+'\n')
    print(json.dumps(receipt,sort_keys=True))
if __name__=='__main__': main()
