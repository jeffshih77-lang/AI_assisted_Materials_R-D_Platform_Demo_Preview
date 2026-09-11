#!/usr/bin/env python3
import argparse, concurrent.futures as cf, datetime as dt, hashlib, html, json, os, pathlib, re, shutil, time, urllib.parse, urllib.request, uuid, zipfile

UA='Mozilla/5.0 (compatible; P4BFormalRawCollector/PublicTransportV4)'
LIST_URL='https://www.fsc.gov.tw/ch/home.jsp?id=96&parentpath=0%2C2&mcustomize='
BASE='https://www.fsc.gov.tw/ch/'
FROZEN_TOTAL=14638
FAMILY='FSC_OFFICIAL_NEWS_ARCHIVE_V1'
CONTRACT='1.2.0'
RECOVERY='4.0.0-public-transport'
CHUNKS={
'C01':(14026,14625,'b25fa4c78f6baed561fd220c687473a41d88a872f5f757feb99f46acfa1cae05','ec010634e86d52ff2c2e5b249b1ab4380c353512980487c613f1b6d68d23eaa3'),
'C02':(13426,14025,'218a6a0aa9793cddf745af0db81b6952268d97570ce8c80bbb139751e5f30acd','4d8609fc521e74e6c71a0a0a0e4e0529ce7ccf1564226c63489020c2d8805ebc'),
'C06':(11026,11625,'0c5c2c5666d55f4cc1f87f8f423ddb60b13aa52a5d896b6005071fd56b170c51','3e7cd02ce491dbad4e83f0670ed4f82ff8e04f6037df7e27f8689c690aec530e'),
'C07':(10426,11025,'4d2cd7f5c2f315d1d3f4fe2e6b7d0a94c5a3fe6177b6c5dda63dc079186a9d2a','8c26315fef5feb9b06b669f56d3e41818c5ffe0e367f6e5089e6aefe7551f2e4'),
'C08':(9826,10425,'f1e17f523ab1493ba1821c8c72a339210da4238f7bb93a3133b721a9dfba8f03','a875cd41d0b33d673cac0bee7fbd00d3e3268eb84a902e5f3e2c834c5a29f6e3'),
'C09':(9226,9825,'774163524917a945d5981bae75a80aec53cdc23df25df2e6026f886ff437991c','8e0620386a367b166c5f30774fec0f43f3b5ccc0299fd18c30f2c172c67ffad4'),
'C10':(8626,9225,'f5b6b200e2cecdad7d1f8a17b1a8dace88cd5dcf4f210087f2be9cbddcb3f866','2eb4797148b714649c489ae58308fb7f36a37934301a6911d45bdeb1e3e34d8b'),
'C11':(8026,8625,'7ce42065c5224a052983ce45ec9ae27d391b1ab5556dfe6ace07286ebb9ac6b0','9f6d458ca657c82ee6b57b3732741f1984f905f41fca039955aa42c27176dc39'),
'C12':(7426,8025,'71f5d246a8b8b2789829e939162a2a697aac6337d8e974d6b0540bd580661eee','f23c0fef91bfb55dd512913c12fc382a2db672420cf80df277eff424b86e3b8b'),
'C13':(6826,7425,'338cfee215e2bf565331e3487a17366beeb3dbc8cb8cd20316f39468cf4e686f','3376bf8204fdff5544ff727895c4505157512bf50bcfb68f005c016030e65a4e'),
'C14':(6226,6825,'4598391760bbe7c3c61a8ee1523efda90dcdf20bd2d12c5608b5aeddd75829e5','a6e6c7fb83ca5d1746f8a6b6ddf62738fcda5a6d71cd19479655fd4f2803f9a9'),
'C15':(5626,6225,'0858018834f4a0a680a6e90394f3af2d4cb1d01f493f2e329403e7cc5cd33627','922c45bfded6807c2f80557f99b4a02f77d9698cb282c0ee394af2c80be077d6'),
'C16':(5026,5625,'a8cb5e2ebca4b191380b95f00da6d15f4d5532f469abab807e2a34e2ee94f50a','0baacf3947b43f32fef7cfe1f58267bbc44664ce106e4433fe29828a448aafa9'),
'C17':(4426,5025,'8af020aabd80fba844ef307e135fda2d568e2a4a84764180d57e2742c4c948ce','2fc2511f431dd259da86ca05e3919acebdef3d53be200b41fc822aeb80240690'),
'C18':(3826,4425,'b65ea44d355c1511ec355437851e5b3b8a9af60ffb40cef100bc87525b6123fc','07af06345e4f430a2d37d7aa7c186fe4c72162982d98537ffdb990bc4ce0ec1d'),
'C19':(3226,3825,'db85783b677001a46aabef477a552fd51cd3ab05e624f66adae6cfaac60a756d','01d36f333f7596f60eb68c6ed21246e3ad8c75e00091c57797e0bb9da968d828'),
'C20':(2626,3225,'ff157c546f97049f0d4b98e2a904db3ce77ce8b34e946cfed4570e5126c63fde','e285d3b7a49c5b080ba28b96b033a4f6b825c9b22409790df97b294a1495851d'),
'C21':(2026,2625,'5750c78eef6f1d91e1683c829cb750b0a67a9b93c3eea621d0dad371a9245139','5fdd51f2edb91d52f8aa55ba95e80a56f83ab3d5430d3c61d3f5b63cce364159'),
'C22':(1426,2025,'d52fd8dba56da72f77ed7f5ab7ea4240dc968c1afec0402b7e9495660f42d7c4','2cfa94411d1ff4607b97e390e79c3183d5a85514f62f75f8b89847cda101909a'),
'C23':(826,1425,'a0c9fa07427f9e86417d03626610d37c54a49cf72c8b3901f511327945d885b9','296f00d934e2a5cd1820d24d28d2c836777c9a9454c8ac0f33390c1715f44015'),
'C24':(226,825,'0d9bd1d9e4805bdd7cd6ee05c57148e78c76ea68df2f692e2d454c9d23ad4bc5','66512f427fb937698ef0c1506f89fb340df390b71a564694b421e921d39ee487'),
'C25':(1,225,'385428f7486b385f61a5c1e0aefaa5f459b87cb69c0cc287efa8bbe41920da78','bcaca26cc93d7ace99bf70dc2d94adb03737f589e24b4c2ce452dc4c0778f8d2')}

def nowz(): return dt.datetime.now(dt.timezone.utc).isoformat().replace('+00:00','Z')
def sha_bytes(b): return hashlib.sha256(b).hexdigest()
def sha_file(p):
    h=hashlib.sha256()
    with open(p,'rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''): h.update(block)
    return h.hexdigest()
def clean(x): return html.unescape(re.sub(r'<[^>]+>',' ',x)).strip()
def absurl(h):
    if h.startswith('http://') or h.startswith('https://'): return h
    if h.startswith('/'): return 'https://www.fsc.gov.tw'+h
    return BASE+h

def parse_page(body):
    s=body.decode('utf-8',errors='replace')
    mt=re.search(r'頁數\s*([0-9,]+)\s*/\s*([0-9,]+)',s); mr=re.search(r'共有\s*<span[^>]*class=["\']red["\'][^>]*>\s*([0-9,]+)',s)
    tp=int(mt.group(2).replace(',','')) if mt else None; tr=int(mr.group(1).replace(',','')) if mr else None
    a=s.find('<div class="newslist"'); b=s.find('<div class="page">',a) if a>=0 else -1; block=s[a:b if b>0 else len(s)] if a>=0 else ''
    rows=[]
    for lm in re.finditer(r'<li\b[^>]*role=["\']row["\'][^>]*>([\s\S]*?)</li>',block,re.I):
        x=lm.group(1)
        no=re.search(r'<span\b[^>]*class=["\'][^"\']*\bno\b[^"\']*["\'][^>]*>(.*?)</span>',x,re.I|re.S)
        date=re.search(r'<span\b[^>]*class=["\'][^"\']*\bdate\b[^"\']*["\'][^>]*>(.*?)</span>',x,re.I|re.S)
        unit=re.search(r'<span\b[^>]*class=["\'][^"\']*\bunit\b[^"\']*["\'][^>]*>(.*?)</span>',x,re.I|re.S)
        if not(no and date and unit): continue
        n=clean(no.group(1))
        if not n.isdigit(): continue
        anchors=[]
        for am in re.finditer(r'<a\b[^>]*href=["\']([^"\']+)["\'][^>]*>([\s\S]*?)</a>',x,re.I):
            href=html.unescape(am.group(1)); title=clean(am.group(2))
            if title: anchors.append((href,title))
        if not anchors: continue
        href,title=anchors[0]; dm=re.search(r'(?:[?&]|&amp;)dataserno=(\d+)',href); ds=dm.group(1) if dm else None
        rows.append({'current_no':int(n),'published_date':clean(date.group(1)),'unit':clean(unit.group(1)),'dataserno':ds,'title':title,'url':absurl(href),'resource_kind':'HTML_DETAIL' if ds else 'DIRECT_DOCUMENT'})
    return tr,tp,rows

def fetch_page(page,attempts=5):
    q=urllib.parse.urlencode({'id':'96','contentid':'96','parentpath':'0,2','mcustomize':'news_list.jsp','page':str(page),'pagesize':'15'}).encode(); last=None
    for a in range(attempts):
        try:
            req=urllib.request.Request(LIST_URL,data=q,method='POST',headers={'User-Agent':UA,'Accept':'*/*','Content-Type':'application/x-www-form-urlencoded','Connection':'close'})
            with urllib.request.urlopen(req,timeout=60) as r: body=r.read(); st=getattr(r,'status',None)
            if st==200 and body:
                tr,tp,rows=parse_page(body); return {'page':page,'total_records':tr,'total_pages':tp,'rows':rows}
            last=f'http_status={st}'
        except Exception as e: last=repr(e)
        if a+1<attempts: time.sleep(min(12,a+1))
    raise RuntimeError(f'list page {page} failed {last}')

def identity_sha(rows):
    s=''.join(f"{int(r['record_no'])}|{r.get('dataserno') or ''}|{r['published_date']}|{r['record_identity']}\n" for r in sorted(rows,key=lambda x:int(x['record_no'])))
    return hashlib.sha256(s.encode('utf-8')).hexdigest()
def fullrow_sha(rows):
    def line(r): return '|'.join([str(int(r['record_no'])),r.get('dataserno') or '',r['published_date'],r['record_identity'],r['resource_kind'],r.get('unit') or '',r.get('title') or '',r.get('url') or ''])+'\n'
    return hashlib.sha256(''.join(line(r) for r in sorted(rows,key=lambda x:int(x['record_no']))).encode('utf-8')).hexdigest()

def reconstruct_chunk(chunk):
    lo,hi,exp_identity,exp_fullrow=CHUNKS[chunk]
    first=fetch_page(1); tr=first['total_records']; tp=first['total_pages']
    if not tr or not tp or tr<FROZEN_TOTAL: raise RuntimeError(f'current archive smaller than frozen: {tr}/{tp}')
    delta=tr-FROZEN_TOTAL
    cur_lo,cur_hi=lo+delta,hi+delta
    p_lo=(cur_lo-1)//15+1; p_hi=(cur_hi-1)//15+1
    pages={1:first} if 1>=p_lo and 1<=p_hi else {}
    targets=[p for p in range(p_lo,p_hi+1) if p not in pages]
    with cf.ThreadPoolExecutor(max_workers=4) as ex:
        futs=[ex.submit(fetch_page,p) for p in targets]
        for f in cf.as_completed(futs):
            r=f.result(); pages[r['page']]=r
    current=[]
    for p in range(p_lo,p_hi+1):
        r=pages[p]
        if r['total_records']!=tr or r['total_pages']!=tp: raise RuntimeError(f'snapshot drift page {p}')
        current.extend(r['rows'])
    candidate=[]
    for r in current:
        if not (cur_lo<=r['current_no']<=cur_hi): continue
        old_no=r['current_no']-delta
        x={k:v for k,v in r.items() if k!='current_no'}
        x.update({'record_no':old_no,'source_page':(old_no-1)//15+1,'record_identity':('dataserno:'+r['hataserno']) if r.get('dataserno') else ('record_no:'+str(old_no))})
        candidate.append(x)
    candidate.sort(key=lambda x:x['record_no'])
    expected_ids=list(range(lo,hi+1)); got_ids=[x['record_no'] for x in candidate]
    if got_ids!=expected_ids: raise RuntimeError(f'{chunk} record number reconstruction mismatch')
    got_identity=identity_sha(candidate); got_fullrow=fullrow_sha(candidate)
    if got_identity!=exp_identity: raise RuntimeError(f'{chunk} identity SHA mismatch {got_identity}')
    if got_fullrow!=exp_fullrow: raise RuntimeError(f'{chunk} full-row SHA mismatch {got_fullrow}')
    return candidate,{'current_total_records':tr,'current_total_pages':tp,'prepend_delta':delta,'current_page_low':p_lo,'current_page_high':p_hi,'expected_identity_sha256':exp_identity,'captured_identity_sha256':got_identity,'expected_fullrow_sha256':exp_fullrow,'captured_fullrow_sha256':got_fullrow}

def fetch_one(r,attempts,base_sleep=1):
    last=None
    for a in range(attempts):
        try:
            req=urllib.request.Request(r['url'],headers={'User-Agent':UA,'Accept':'*/*','Connection':'close'})
            with urllib.request.urlopen(req,timeout=120) as resp:
                body=resp.read(); st=getattr(resp,'status',None); final=resp.geturl(); hdr=dict(resp.headers.items()); got=nowz()
            if st==200 and body:
                ct=(hdr.get('Content-Type') or '').lower()
                if r['resource_kind']=='DIRECT_DOCUMENT' and len(body)<64: raise RuntimeError('direct document too small')
                if r['resource_kind']=='HTML_DETAIL' and ('html' not in ct and not body.lstrip().startswith(b'<')): raise RuntimeError('expected html detail')
                return {'ok':True,'r':r,'body':body,'status':st,'final_url':final,'headers':hdr,'retrieved_at':got,'attempts':a+1}
            last=f'http_status={st} bytes={len(body)}'
        except Exception as exc: last=repr(exc)
        if a+1<attempts: time.sleep(min(30,base_sleep*(2**a)))
    return {'ok':False,'r':r,'error':last,'attempts':attempts,'failed_at':nowz()}

def save_success(root,res):
    r=res['r']; body=res['body']; hdr=res['headers']; ct=(hdr.get('Content-Type') or '').lower()
    ext='.html' if r['resource_kind']=='HTML_DETAIL' else ('.pdf' if body.startswith(b'%PDF') or 'pdf' in ct else '.bin')
    rid=r.get('dataserno') or f"record{int(r['record_no']):05d}"
    stem=f"{int(r['source_page']):04d}_{int(r['record_no']):05d}_{r['published_date']}_{rid}"
    rp=root/'detail'/(stem+'.response'+ext); mp=root/'meta'/(stem+'.capture.json'); rp.write_bytes(body)
    meta={'schema':'p4b_exact_http_capture_v1','lane_code':'P4-B','dataset':'FINANCIAL_NEWS_EVENTS','work_unit_id':f"P4B-FSC-PAGE-{int(r['source_page']):04d}",'source_family':FAMILY,'source_contract_version':CONTRACT,'recovery_collector_version':RECOVERY,'method':'GET','request_url':r['url'],'final_url':res['final_url'],'retrieved_at':res['retrieved_at'],'http_status':res['status'],'response_headers':hdr,'payload_bytes':len(body),'payload_sha256':sha_bytes(body),'source_page':r['source_page'],'record_no':r['record_no'],'dataserno':r.get('dataserno'),'record_identity':r['record_identity'],'resource_kind':r['resource_kind'],'published_date':r['published_date'],'published_date_source':'FSC frozen archive list row reconstructed only after frozen identity/full-row hash gate','available_at':'unknown','available_at_reason':'historical archive migration/public-web availability time not proven by page','unit':r['unit'],'title':r['title'],'raw_semantics':'exact FSC linked resource HTTP response bytes','classification':'FORMAL_RAW_CANDIDATE_PENDING_DRIVE_READBACK','recovery_attempts_used':res['attempts'],'transport':'isolated public hosted runner; catalog content never committed'}
    mp.write_text(json.dumps(meta,ensure_ascii=False,indent=2,sort_keys=True)+'\n')
    return {'record_no':r['record_no'],'source_page':r['source_page'],'dataserno':r.get('dataserno'),'record_identity':r['record_identity'],'resource_kind':r['resource_kind'],'published_date':r['published_date'],'raw_path':str(rp.relative_to(root)),'raw_bytes':len(body),'raw_sha256':sha_bytes(body),'metadata_path':str(mp.relative_to(root)),'recovery_attempts_used':res['attempts']}

def run(chunk,outbase):
    recs,gate=reconstruct_chunk(chunk)
    outbase=pathlib.Path(outbase); outbase.mkdir(parents=True,exist_ok=True)
    staging=outbase/'.staging'/f'{chunk}-{uuid.uuid4().hex}'; root=staging/'payload'; (root/'detail').mkdir(parents=True); (root/'meta').mkdir()
    first=[]
    with cf.ThreadPoolExecutor(max_workers=2) as pool:
        futs=[pool.submit(fetch_one,r,4,1) for r in recs]
        for f in cf.as_completed(futs): first.append(f.result())
    successes=[x for x in first if x['ok']]; failed=[x for x in first if not x['ok']]
    retry=[fetch_one(x['r'],8,2) for x in failed]; successes += [x for x in retry if x['ok']]; final_failed=[x for x in retry if not x['ok']]
    rows=[save_success(root,x) for x in sorted(successes,key=lambda y:int(y['r']['record_no']))]
    failures=[{'record_no':x['r']['record_no'],'source_page':x['r']['source_page'],'dataserno':x['r'].get('dataserno'),'record_identity':x['r']['record_identity'],'resource_kind':x['r']['resource_kind'],'published_date':x['r']['published_date'],'title':x['r']['title'],'url':x['r']['url'],'error':x['error'],'deep_retry_attempts':x['attempts']} for x in final_failed]
    exp_identity=CHUNKS[chunk][2]; captured_identity=identity_sha([{'record_no':x['record_no'],'dataserno':x.get('dataserno'),'published_date':x['published_date'],'record_identity':x['record_identity']} for x in rows]) if rows else None
    complete=(not failures and len(rows)==len(recs) and captured_identity==exp_identity)
    manifest={'schema':'p4b_fsc_recovery_chunk_manifest_v4','lane_code':'P4-B','dataset':'FINANCIAL_NEWS_EVENTS','source_family':FAMILY,'source_contract_version':CONTRACT,'recovery_collector_version':RECOVERY,'chunk':chunk,'frozen_catalog_reconstruction_gate':gate,'expected_record_count':len(recs),'captured_record_count':len(rows),'failure_count':len(failures),'record_no_min':CHUNKS[chunk][0],'record_no_max':CHUNKS[chunk][1],'expected_identity_sha256':exp_identity,'captured_identity_sha256':captured_identity,'identity_match':captured_identity==exp_identity,'raw_bytes':sum(x['raw_bytes'] for x in rows),'records':rows,'failures':failures,'status':'CAPTURED_VALIDATED_PENDING_DRIVE_READBACK' if complete else 'STAGING_INCOMPLETE_NOT_FORMAL_RAW','generated_at':nowz()}
    (root/f'P4B_FSC_RECOVERY_{chunk}_MANIFEST.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2,sort_keys=True)+'\n')
    if not complete:
        faildir=outbase/'failures'; faildir.mkdir(exist_ok=True)
        (faildir/f'P4B_FSC_RECOVERY_{chunk}_FAILURE.json').write_text(json.dumps({'chunk':chunk,'gate':gate,'manifest':manifest},ensure_ascii=Falslindent=2,sort_keys=True)+'\n')
        shutil.rmtree(staging, ignore_errors=True)
        print(json.dumps({'chunk':chunk,'status':'INCOMPLETE','captured':len(rows),'failures':len(failures)},ensure_ascii=False)); return 2
    packages=outbase/'packages'; packages.mkdir(exist_ok=True)
    tmp=packages/f'.{chunk}.{uuid.uuid4().hex}.tmp.zip'
    with zipfile.ZipFile(tmp,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in sorted(root.rglob('*')):
            if p.is_file(): z.write(p,p.relative_to(root))
    zp=packages/f'P4B_FSC_RECOVERY_{chunk}_V4.zip'; os.replace(tmp,zp)
    receipt={'schema':'p4b_local_package_receipt_v1','chunk':chunk,'package':zp.name,'bytes':zp.stat().st_size,'sha256':sha_file(zp),'record_count':len(rows),'identity_sha256':captured_identity,'fullrow_catalog_sha256':gate['captured_fullrow_sha256'],'status':'CAPTURED_VALIDATED_PENDING_DRIVE_READBACK','generated_at':nowz()}
    (packages/f'P4B_FSC_RECOVERY_{chunk}_V4_RECEIPT.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2,sort_keys=True)+'\n')
    shutil.rmtree(staging,ignore_errors=True); print(json.dumps(receipt,ensure_ascii=False)); return 0

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('chunk',choices=sorted(CHUNKS)); ap.add_argument('--out-dir',default='out'); ns=ap.parse_args(); raise SystemExit(run(ns.chunk,ns.out_dir))
if __name__=='__main__': main()
