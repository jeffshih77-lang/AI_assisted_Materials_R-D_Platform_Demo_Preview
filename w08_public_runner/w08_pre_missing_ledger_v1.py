import base64,gzip,json,os,pathlib,subprocess,urllib.request,urllib.error,zipfile,io
CORE_COMMIT='4c9f56784ab2df8ad347cbc23f61e8449d22a628'; CORE_PATH='w08_public_runner/w08_final_reconcile_v1.py'
src=subprocess.check_output(['git','show',f'{CORE_COMMIT}:{CORE_PATH}'],text=True); src=src.split("\nif MODE=='t05': run_t05()",1)[0]; ns={'__name__':'core'}; exec(compile(src,CORE_PATH,'exec'),ns)
class NR(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,req,fp,code,msg,headers,newurl):return None
def dl(a):
 req=urllib.request.Request(a['archive_download_url'],headers={'Authorization':f"Bearer {ns['TOKEN']}",'Accept':'application/vnd.github+json','X-GitHub-Api-Version':'2022-11-28','User-Agent':'W08PreMissingLedger/1.0'}); op=urllib.request.build_opener(NR); loc=None
 try:
  with op.open(req,timeout=120) as r:
   if r.status in (301,302,303,307,308):loc=r.headers.get('Location')
   else:return r.read()
 except urllib.error.HTTPError as e:
  if e.code not in (301,302,303,307,308):raise
  loc=e.headers.get('Location')
 with urllib.request.urlopen(urllib.request.Request(loc,headers={'User-Agent':'W08PreMissingLedger/1.0'}),timeout=240) as r:return r.read()
ns['download_artifact']=dl
codes,_=ns['load_codes']('w08_public_runner/w08_pre20050504_codes_1281.txt.gz.b64',1281); years=[f'{y:03d}' for y in range(85,95)]; target={(c,y) for c in codes for y in years}
store={};audit=[]
for run_id in (34689835957,34691209234):
 for a in ns['list_artifacts'](run_id):
  res=ns['parse_formal_artifact'](a,dl(a),'pre',store); res.update({'run_id':run_id,'artifact_id':a['id']}); audit.append(res)
missing=sorted(target-set(store)); by_code={}; by_year={}
for c,y in missing:by_code.setdefault(c,[]).append(y);by_year[y]=by_year.get(y,0)+1
out=pathlib.Path('out_pre_missing_ledger');out.mkdir(exist_ok=True)
obj={'schema':'w08_pre_missing_ledger_v1','target':12810,'have':len(store),'missing_count':len(missing),'missing':[{'code':c,'year':y} for c,y in missing],'by_code':by_code,'by_year':by_year,'unique_missing_codes':len(by_code),'artifact_audit':audit}
(out/'PRE_MISSING_234.json').write_text(json.dumps(obj,ensure_ascii=False,indent=2,sort_keys=True)+'\n')
print(json.dumps({'have':len(store),'missing':len(missing),'unique_codes':len(by_code),'by_year':by_year,'first_codes':list(by_code.items())[:30]},ensure_ascii=False),flush=True)
