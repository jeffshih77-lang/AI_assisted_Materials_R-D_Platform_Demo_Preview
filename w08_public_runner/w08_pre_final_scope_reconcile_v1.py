import base64, gzip, hashlib, io, json, os, pathlib, subprocess, urllib.error, urllib.request, zipfile

REPO=os.environ.get('GITHUB_REPOSITORY','jeffshih77-lang/AI_assisted_Materials_R-D_Platform_Demo_Preview')
TOKEN=os.environ['GITHUB_TOKEN']
CORE_COMMIT='4c9f56784ab2df8ad347cbc23f61e8449d22a628'
CORE_PATH='w08_public_runner/w08_final_reconcile_v1.py'
BASE_RUNS=(34689835957,34691209234)
RESIDUAL_RUN=34698561251
EXCLUDED={'0001':'鴻運','0015':'富邦','0029':'富邦店','0050':'元大台灣50'}
OUT=pathlib.Path('out_w08_pre_final_scope'); OUT.mkdir(exist_ok=True)
UA='W08PreScopeFinalizer/1.0'

def load_core():
    try: src=subprocess.check_output(['git','show',f'{CORE_COMMIT}:{CORE_PATH}'],text=True)
    except subprocess.CalledProcessError:
        subprocess.check_call(['git','fetch','--depth=1','origin',CORE_COMMIT]); src=subprocess.check_output(['git','show',f'{CORE_COMMIT}:{CORE_PATH}'],text=True)
    src=src.split("\nif MODE=='t05': run_t05()",1)[0]
    ns={'__name__':'w08_core'}; exec(compile(src,CORE_PATH,'exec'),ns); return ns
ns=load_core()
class NR(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl): return None

def dl(a):
    req=urllib.request.Request(a['archive_download_url'],headers={'Authorization':f'Bearer {TOKEN}','Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28','User-Agent':UA})
    op=urllib.request.build_opener(NR); loc=None
    try:
        with op.open(req,timeout=120) as r:
            if r.status in (301,302,303,307,308): loc=r.headers.get('Location')
            else: return r.read()
    except urllib.error.HTTPError as e:
        if e.code not in (301,302,303,307,308): raise
        loc=e.headers.get('Location')
    if not loc: raise RuntimeError('artifact_redirect_missing')
    with urllib.request.urlopen(urllib.request.Request(loc,headers={'User-Agent':UA}),timeout=240) as r: return r.read()
ns['download_artifact']=dl

def inner_zip(blob,needle):
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        hits=[n for n in z.namelist() if needle in n and n.endswith('.zip')]
        if len(hits)!=1: raise RuntimeError(f'inner_zip_count {len(hits)} {hits}')
        return hits[0],z.read(hits[0])

codes,universe_sha=ns['load_codes']('w08_public_runner/w08_pre20050504_codes_1281.txt.gz.b64',1281)
years=[f'{y:03d}' for y in range(85,95)]
original_target={(c,y) for c in codes for y in years}
assert len(original_target)==12810
store={}; audit=[]
for run_id in BASE_RUNS:
    for a in ns['list_artifacts'](run_id):
        blob=dl(a); r=ns['parse_formal_artifact'](a,blob,'pre',store); r.update({'run_id':run_id,'artifact_id':a['id'],'digest':a.get('digest')}); audit.append(r)
if len(store)!=12576: raise RuntimeError(f'base_success_not_12576 {len(store)}')
arts=ns['list_artifacts'](RESIDUAL_RUN)
ra=[a for a in arts if a.get('name')=='W08_PRE_RESIDUAL_REPAIR_V1_20260912']
if len(ra)!=1: raise RuntimeError(f'residual_artifact_count {len(ra)}')
outer=dl(ra[0]); inner_name,inner=inner_zip(outer,'RAW-W08_MOPS_EXRIGHT_PRE20050505_RESIDUAL_REPAIR_V1_20260912')
fake={'id':ra[0]['id'],'name':ra[0]['name']+'::'+inner_name,'digest':ra[0].get('digest')}
r=ns['parse_formal_artifact'](fake,inner,'pre',store); r.update({'run_id':RESIDUAL_RUN,'artifact_id':ra[0]['id'],'outer_digest':ra[0].get('digest'),'inner_name':inner_name,'inner_sha256':ns['sha'](inner)}); audit.append(r)
if len(store)!=12775: raise RuntimeError(f'union_success_not_12775 {len(store)}')

excluded_codes=set(EXCLUDED)
correct_codes=set(codes)-excluded_codes
if len(correct_codes)!=1277: raise RuntimeError(f'correct_code_count {len(correct_codes)}')
correct_target={(c,y) for c in correct_codes for y in years}
if len(correct_target)!=12770: raise RuntimeError(f'correct_target_count {len(correct_target)}')
in_scope={k:v for k,v in store.items() if k in correct_target}
extras=sorted(set(store)-correct_target)
missing=sorted(correct_target-set(store))
if missing: raise RuntimeError(f'in_scope_missing {len(missing)} {missing[:10]}')
if len(in_scope)!=12770: raise RuntimeError(f'in_scope_success_not_12770 {len(in_scope)}')
if any(k[0] not in excluded_codes for k in extras): raise RuntimeError(f'unexpected_extra {extras[:10]}')

exclusion_ledger={
 'schema':'w08_pre_company_scope_exclusion_v1','reason':'Official t59sb07 scope is 公開發行及94.5.5前之全體公司; four Security Master numeric four-digit securities are funds/ETF rather than companies and therefore are not t59 company targets.',
 'initial_security_master_codes':1281,'excluded_codes':[
  {'code':'0001','name':'鴻運','classification':'證券投資信託基金','evidence':'Historical market/fund reference identifies 0001 as 安泰ING鴻運證券投資信託基金; t59 returned empty shell for all ROC85-94 probes.'},
  {'code':'0015','name':'富邦','classification':'證券投資信託基金/受益憑證','official_twse_evidence':'https://www.twse.com.tw/zh/ETFortune/announcement?company=A00010&date=20030819&fund=0015&seq=1&type=all'},
  {'code':'0029','name':'富邦店','classification':'證券投資信託基金/受益憑證','official_twse_evidence':'https://wwwc.twse.com.tw/zh/ETFortune/announcement?company=A00010&date=20050415&fund=0029&seq=5&type=other'},
  {'code':'0050','name':'元大台灣50','classification':'台股ETF/證券投資信託基金','official_twse_evidence':'https://www.twse.com.tw/zh/ETFortune/etfInfo/0050'}
 ],
 'excluded_company_year_units':40,'observed_out_of_scope_success_units':len(extras),'observed_out_of_scope_success_keys':[list(k) for k in extras],
 'correct_company_codes':1277,'correct_target_units':12770,'in_scope_success_units':len(in_scope),'in_scope_missing_units':0
}
summary={
 'schema':'w08_t59_pre20050505_final_scope_reconciled_v1','work_unit_id':'W08-RAW-MOPS-EXRIGHT-PRE20050505','formal_raw':True,'status':'FORMAL_RAW_COMPLETE',
 'endpoint':'https://mopsov.twse.com.tw/mops/web/ajax_t59sb07','official_scope':'公開發行及94.5.5前之全體公司','initial_security_master_universe_count':1281,
 'initial_universe_sha256':universe_sha,'excluded_noncompany_security_codes':sorted(EXCLUDED),'correct_company_universe_count':1277,'years':years,
 'target_units':12770,'success_units':12770,'missing_units':0,'source_run_ids':list(BASE_RUNS)+[RESIDUAL_RUN],
 'residual_inner_sha256':ns['sha'](inner),'out_of_scope_captured_units':len(extras),'artifact_audit':audit,'generated_at':ns['now']()
}
(OUT/'PRE_COMPANY_SCOPE_EXCLUSION_LEDGER.json').write_text(json.dumps(exclusion_ledger,ensure_ascii=False,indent=2,sort_keys=True)+'\n')
# Full deterministic in-scope RAW package, not a metadata-only reference.
pkg=OUT/'RAW-W08_MOPS_EXRIGHT_PRE20050505_FORMAL_RAW_COMPANY_SCOPE_ROC85_94_FINAL_20260912.zip'
ns['deterministic_zip'](pkg,in_scope,'pre',summary)
info={'file':pkg.name,'bytes':pkg.stat().st_size,'sha256':ns['sha'](pkg.read_bytes()),'summary':{k:v for k,v in summary.items() if k!='artifact_audit'},'exclusion_ledger_sha256':ns['sha']((OUT/'PRE_COMPANY_SCOPE_EXCLUSION_LEDGER.json').read_bytes())}
(OUT/'PACKAGE_INFO.json').write_text(json.dumps(info,ensure_ascii=False,indent=2,sort_keys=True)+'\n')
print('FINAL',json.dumps(info,ensure_ascii=False),flush=True)
