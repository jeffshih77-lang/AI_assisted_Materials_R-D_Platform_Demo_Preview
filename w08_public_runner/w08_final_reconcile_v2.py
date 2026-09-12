import json, os, pathlib, subprocess

CORE_COMMIT='4c9f56784ab2df8ad347cbc23f61e8449d22a628'
CORE_PATH='w08_public_runner/w08_final_reconcile_v1.py'

def load_core():
    try:
        src=subprocess.check_output(['git','show',f'{CORE_COMMIT}:{CORE_PATH}'],text=True)
    except subprocess.CalledProcessError:
        subprocess.check_call(['git','fetch','--depth=1','origin',CORE_COMMIT])
        src=subprocess.check_output(['git','show',f'{CORE_COMMIT}:{CORE_PATH}'],text=True)
    marker="\nif MODE=='t05': run_t05()"
    if marker not in src:
        raise RuntimeError('core_dispatch_marker_missing')
    src=src.split(marker,1)[0]
    ns={'__name__':'w08_final_reconcile_core_v1'}
    exec(compile(src,CORE_PATH,'exec'),ns)
    return ns

ns=load_core()
mode=os.environ.get('MODE','t05').strip().lower()

if mode=='t05':
    ns['run_t05']()
elif mode=='pre':
    run_ids=(34689835957,34691209234)
    for run_id in run_ids:
        ns['wait_run'](run_id)
    codes,universe_sha=ns['load_codes']('w08_public_runner/w08_pre20050504_codes_1281.txt.gz.b64',1281)
    years=[f'{y:03d}' for y in range(85,95)]
    target={(c,y) for c in codes for y in years}
    assert len(target)==12810
    store={}; audit=[]
    for run_id in run_ids:
        arts=ns['list_artifacts'](run_id)
        print(json.dumps({'run':run_id,'artifacts':len(arts)}),flush=True)
        for a in arts:
            blob=ns['download_artifact'](a)
            res=ns['parse_formal_artifact'](a,blob,'pre',store)
            res.update({'run_id':run_id,'artifact_id':a['id'],'digest':a.get('digest')})
            audit.append(res)
            print(json.dumps(res),flush=True)
    missing=sorted(target-set(store))
    print(json.dumps({'mode':'pre','have':len(store),'missing':len(missing),'source_runs':run_ids}),flush=True)
    for i,key in enumerate(missing,1):
        body,raw,gz,meta=ns['capture_pre'](key)
        ns['add_item'](store,key,body,raw,gz,meta)
        print(json.dumps({'repair':i,'of':len(missing),'key':key}),flush=True)
    if set(store)!=target:
        raise RuntimeError(f'final_coverage_fail have={len(store)} target={len(target)}')
    summary={'schema':'w08_t59_pre20050505_final_aggregate_v2','work_unit_id':'W08-RAW-MOPS-EXRIGHT-PRE20050505','formal_raw':True,'status':'FORMAL_RAW_COMPLETE','endpoint':ns['BASE']+'/mops/web/ajax_t59sb07','official_scope':'公開發行及94.5.5前之全體公司','universe_count':1281,'universe_sha256':universe_sha,'years':years,'target_units':12810,'success_units':len(store),'missing_repaired_units':len(missing),'source_run_ids':list(run_ids),'contract':{'firstin':'1','TYPEK':'all','company_required':True,'year_required':True,'ui_click_semantics_verified':True,'ui_sequence':'doAction sets firstin=1 before ajax1(form1)'},'artifact_audit':audit,'generated_at':ns['now']()}
    root=pathlib.Path('out_w08_final_pre'); root.mkdir(parents=True,exist_ok=True)
    out=root/'RAW-W08_MOPS_EXRIGHT_PRE20050505_FORMAL_RAW_ROC85_94_FINAL_20260912.zip'
    ns['deterministic_zip'](out,store,'pre',summary)
    info={'file':out.name,'bytes':out.stat().st_size,'sha256':ns['sha'](out.read_bytes()),'summary':{k:v for k,v in summary.items() if k!='artifact_audit'}}
    (root/'PACKAGE_INFO.json').write_text(json.dumps(info,ensure_ascii=False,indent=2,sort_keys=True)+'\n')
    print(json.dumps(info,ensure_ascii=False),flush=True)
else:
    raise SystemExit('MODE must be t05 or pre')
