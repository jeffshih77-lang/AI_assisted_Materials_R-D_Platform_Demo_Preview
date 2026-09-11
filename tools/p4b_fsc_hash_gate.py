#!/usr/bin/env python3
import concurrent.futures as cf, hashlib, html, json, re, time, urllib.parse, urllib.request

UA='Mozilla/5.0 (compatible; P4B-FSC-IdentityGate/1.0)'
LIST_URL='https://www.fsc.gov.tw/ch/home.jsp?id=96&parentpath=0%2C2&mcustomize='
FROZEN_TOTAL=14638
FROZEN_FULL_SHA='b27767596c0551ddf0a44b787f8547d54c020fe8ddcc5cbe6855d583175156c8'
EXPECTED={
'C01':'b25fa4c78f6baed561fd220c687473a41d88a872f5f757feb99f46acfa1cae05','C02':'218a6a0aa9793cddf745af0db81b6952268d97570ce8c80bbb139751e5f30acd','C03':'d757d704861bb5ce01a17a08ae7ec16c2a65b4ff3390a705b79c20d088297515','C04':'6bd89f292d39f355bfae74a64eaff78578c33ca367f319ea391b38bc59697c19','C05':'07922bb5c8fde78cf57a290196543a40ae572f9d67c850bfe61e9551e4f988ad','C06':'0c5c2c5666d55f4cc1f87f8f423ddb60b13aa52a5d896b6005071fd56b170c51','C07':'4d2cd7f5c2f315d1d3f4fe2e6b7d0a94c5a3fe6177b6c5dda63dc079186a9d2a','C08':'f1e17f523ab1493ba1821c8c72a339210da4238f7bb93a3133b721a9dfba8f03','C09':'774163524917a945d5981bae75a80aec53cdc23df25df2e6026f886ff437991c','C10':'f5b6b200e2cecdad7d1f8a17b1a8dace88cd5dcf4f210087f2be9cbddcb3f866','C11':'7ce42065c5224a052983ce45ec9ae27d391b1ab5556dfe6ace07286ebb9ac6b0','C12':'71f5d246a8b8b2789829e939162a2a697aac6337d8e974d6b0540bd580661eee','C13':'338cfee215e2bf565331e3487a17366beeb3dbc8cb8cd20316f39468cf4e686f','C14':'4598391760bbe7c3c61a8ee1523efda90dcdf20bd2d12c5608b5aeddd75829e5','C15':'0858018834f4a0a680a6e90394f3af2d4cb1d01f493f2e329403e7cc5cd33627','C16':'a8cb5e2ebca4b191380b95f00da6d15f4d5532f469abab807e2a34e2ee94f50a','C17':'8af020aabd80fba844ef307e135fda2d568e2a4a84764180d57e2742c4c948ce','C18':'b65ea44d355c1511ec355437851e5b3b8a9af60ffb40cef100bc87525b6123fc','C19':'db85783b677001a46aabef477a552fd51cd3ab05e624f66adae6cfaac60a756d','C20':'ff157c546f97049f0d4b98e2a904db3ce77ce8b34e946cfed4570e5126c63fde','C21':'5750c78eef6f1d91e1683c829cb750b0a67a9b93c3eea621d0dad371a9245139','C22':'d52fd8dba56da72f77ed7f5ab7ea4240dc968c1afec0402b7e9495660f42d7c4','C23':'a0c9fa07427f9e86417d03626610d37c54a49cf72c8b3901f511327945d885b9','C24':'0d9bd1d9e4805bdd7cd6ee05c57148e78c76ea68df2f692e2d454c9d23ad4bc5','C25':'385428f7486b385f61a5c1e0aefaa5f459b87cb69c0cc287efa8bbe41920da78'}
RANGES={'C01':(14026,14625),'C02':(13426,14025),'C03':(12826,13425),'C04':(12226,12825),'C05':(11626,12225),'C06':(11026,11625),'C07':(10426,11025),'C08':(9826,10425),'C09':(9226,9825),'C10':(8626,9225),'C11':(8026,8625),'C12':(7426,8025),'C13':(6826,7425),'C14':(6226,6825),'C15':(5626,6225),'C16':(5026,5625),'C17':(4426,5025),'C18':(3826,4425),'C19':(3226,3825),'C20':(2626,3225),'C21':(2026,2625),'C22':(1426,2025),'C23':(826,1425),'C24':(226,825),'C25':(1,225)}

def clean(x): return html.unescape(re.sub(r'<[^>]+>',' ',x)).strip()
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
        if not(no and date): continue
        n=clean(no.group(1))
        if not n.isdigit(): continue
        anchors=[]
        for am in re.finditer(r'<a\b[^>]*href=["\']([^"\']+)["\'][^>]*>([\s\S]*?)</a>',x,re.I):
            href=html.unescape(am.group(1)); title=clean(am.group(2))
            if title: anchors.append((href,title))
        if not anchors: continue
        href,_=anchors[0]; dm=re.search(r'(?:[?&]|&amp;)dataserno=(\d+)',href); ds=dm.group(1) if dm else None
        rows.append({'current_no':int(n),'published_date':clean(date.group(1)),'dataserno':ds})
    return tr,tp,rows

def fetch_page(page,attempts=5):
    q=urllib.parse.urlencode({'id':'96','contentid':'96','parentpath':'0,2','mcustomize':'news_list.jsp','page':str(page),'pagesize':'15'}).encode()
    last=None
    for a in range(attempts):
        try:
            req=urllib.request.Request(LIST_URL,data=q,method='POST',headers={'User-Agent':UA,'Accept':'*/*','Content-Type':'application/x-www-form-urlencoded'})
            with urllib.request.urlopen(req,timeout=60) as r: body=r.read(); st=getattr(r,'status',None)
            if st==200 and body:
                tr,tp,rows=parse_page(body)
                return page,tr,tp,rows
        except Exception as e: last=repr(e)
        time.sleep(a+1)
    raise RuntimeError(f'page {page} failed {last}')

def identity_sha(rows):
    s=''.join(f"{r['record_no']}|{r.get('dataserno') or ''}|{r['published_date']}|{r['record_identity']}\n" for r in sorted(rows,key=lambda x:x['record_no']))
    return hashlib.sha256(s.encode()).hexdigest()

def main():
    p,tr,tp,rows=fetch_page(1)
    if not tr or not tp or tr < FROZEN_TOTAL: raise SystemExit(f'bad current boundary records={tr} pages={tp}')
    results={1:(tr,tp,rows)}
    with cf.ThreadPoolExecutor(max_workers=6) as ex:
        futs={ex.submit(fetch_page,p):p for p in range(2,tp+1)}
        for f in cf.as_completed(futs):
            p2,tr2,tp2,rows2=f.result(); results[p2]=(tr2,tp2,rows2)
    current=[]
    for p in range(1,tp+1):
        tr2,tp2,rows2=results[p]
        if tr2!=tr or tp2!=tp: raise SystemExit(f'snapshot drift at page {p}: {tr2}/{tp2} != {tr}/{tp}')
        current.extend(rows2)
    nos=sorted(r['current_no'] for r in current)
    if nos!=list(range(1,tr+1)): raise SystemExit('current record_no set incomplete')
    delta=tr-FROZEN_TOTAL
    candidate=[]
    for r in current:
        if r['current_no']<=delta: continue
        old_no=r['current_no']-delta
        if not (1<=old_no<=FROZEN_TOTAL): continue
        ds=r.get('dataserno')
        candidate.append({'record_no':old_no,'dataserno':ds,'published_date':r['published_date'],'record_identity':('dataserno:'+ds) if ds else ('record_no:'+str(old_no))})
    if len(candidate)!=FROZEN_TOTAL: raise SystemExit(f'candidate count {len(candidate)}')
    full=identity_sha(candidate)
    chunk_results={}
    ok=(full==FROZEN_FULL_SHA)
    for c,(lo,hi) in RANGES.items():
        part=[r for r in candidate if lo<=r['record_no']<=hi]
        got=identity_sha(part); match=(got==EXPECTED[c]); ok=ok and match
        chunk_results[c]={'count':len(part),'sha256':got,'match':match}
    summary={'status':'PASS' if ok else 'FAIL','current_records':tr,'current_pages':tp,'prepend_delta':delta,'candidate_records':len(candidate),'full_identity_sha256':full,'full_match':full==FROZEN_FULL_SHA,'chunks':chunk_results}
    print(json.dumps(summary,ensure_ascii=False,sort_keys=True))
    if not ok: raise SystemExit(3)

if __name__=='__main__': main()
