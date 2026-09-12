import base64, gzip, json, os, pathlib, subprocess

CORE_COMMIT='4c9f56784ab2df8ad347cbc23f61e8449d22a628'
CORE_PATH='w08_public_runner/w08_final_reconcile_v1.py'

T05_CHECKPOINT_DRIVE=[
 {'chunk':0,'drive_id':'1z_0rAqwCPanmI_p0FSRumrR5qRr_WCv8','sha256':'ce47107476b76864bdb9577418b9789245bb0455c5c9d16a68ef02185d76d687'},
 {'chunk':1,'drive_id':'1WAFQK2VPEQB8s1ZNGoBdH9yQBDy-89My','sha256':'79b6ad533e88c224ba53bd125b9b55ca9464ac1687499cdf02cd2d31b1c5fbca'},
 {'chunk':2,'drive_id':'102dpdWa7-0mSDSp1UbCuvP2pwYSY7fvz','sha256':'d04ea0c161c6dad63c83c8eac90c4a5d8dccc4787575f4895ccf647859050f04'},
 {'chunk':3,'drive_id':'1J1X5cDqw3DRAmOnlknNyOPK8co1azG_D','sha256':'a3b929690ab40252abc55eae9a8bd02c880b1a0c0c8e53ebaada530512b73b6a'},
 {'chunk':4,'drive_id':'19KrOvQoVgMJfgAlMmY2fZwAoAWauTl1X','sha256':'bd570a96a0770ad24fcfc133add43b1a1b4ba1180c7086ef22eed2bba11d7200'},
 {'chunk':5,'drive_id':'1iVYCSxlDVPZoxQVjX9rmYA6dgTJ6O49K','sha256':'9683b2edccbbf6d043e648d6c1a8dec8b20792b1b5eec67809bb249489c9324d'},
 {'chunk':6,'drive_id':'1ULeOqZ5lOBU0L9638H7ItJ7RItpibd4l','sha256':'0cebbb5c9e74c1577a62106d2e368c7c3a7013238ac796da3b7da1579ca45f05'},
 {'chunk':7,'drive_id':'1pQR2YqJBoOWwL3A6p8woFcWF5gz_X-zc','sha256':'e7e0b81aab9b1971a5f15d159a668502b1b5c3ffc08fadc0d84662c5ccedf62a'},
]

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

def load_checkpoint_keys(path):
    raw=gzip.decompress(base64.b64decode(pathlib.Path(path).read_text().strip()))
    obj=json.loads(raw)
    arr=obj.get('pairs',[]) if isinstance(obj,dict) else obj
    out=set()
    for x in arr:
        if isinstance(x,dict):
            out.add((str(x['code']),int(x['qryType'])))
        else:
            c,q=x; out.add((str(c),int(q)))
    if len(out)!=621:
        raise RuntimeError(f'checkpoint_key_count_not_621 {len(out)}')
    return out, ns['sha'](raw)

ns=load_core()
mode=os.environ.get('MODE','t05').strip().lower()

if mode=='t05':
    repair_runs=(34688535810,34688916414)
    for run_id in repair_runs:
        ns['wait_run'](run_id)
    codes,universe_sha=ns['load_codes']('w08_public_runner/w08_security_master_4digit_universe_2436.txt.gz.b64',2436)
    checkpoint,checkpoint_key_sha=load_checkpoint_keys('w08_public_runner/w08_t05_completed_621.json.gz.b64')
    target={(c,q) for c in codes for q in (1,2)}
    if len(target)!=4872 or not checkpoint <= target:
        raise RuntimeError('t05_target_or_checkpoint_invalid')
    remaining_target=target-checkpoint
    if len(remaining_target)!=4251:
        raise RuntimeError(f'remaining_target_not_4251 {len(remaining_target)}')
    store={}; audit=[]
    for run_id in repair_runs:
        arts=ns['list_artifacts'](run_id)
        print(json.dumps({'run':run_id,'artifacts':len(arts)}),flush=True)
        for a in arts:
            blob=ns['download_artifact'](a)
            res=ns['parse_formal_artifact'](a,blob,'t05',store)
            res.update({'run_id':run_id,'artifact_id':a['id'],'digest':a.get('digest')})
            audit.append(res); print(json.dumps(res),flush=True)
    # Dispatcher artifacts must never overlap frozen checkpoint successes.
    overlap=set(store)&checkpoint
    if overlap:
        raise RuntimeError(f'repair_checkpoint_overlap {len(overlap)} sample={sorted(overlap)[:5]}')
    unexpected=set(store)-remaining_target
    if unexpected:
        raise RuntimeError(f'repair_outside_remaining_target {len(unexpected)} sample={sorted(unexpected)[:5]}')
    missing=sorted(remaining_target-set(store))
    print(json.dumps({'mode':'t05','checkpoint_units':len(checkpoint),'repair_success_units':len(store),'missing':len(missing),'remaining_target':len(remaining_target)}),flush=True)
    for i,key in enumerate(missing,1):
        body,raw,gz,meta=ns['capture_t05'](key)
        ns['add_item'](store,key,body,raw,gz,meta)
        print(json.dumps({'repair':i,'of':len(missing),'key':key}),flush=True)
    if set(store)!=remaining_target:
        raise RuntimeError(f'final_remaining_coverage_fail have={len(store)} target={len(remaining_target)}')
    if checkpoint & set(store) or len(checkpoint|set(store))!=4872:
        raise RuntimeError('final_union_coverage_fail')
    summary={
      'schema':'w08_t05st09_final_reference_aggregate_v2',
      'work_unit_id':'W08-RAW-MOPS-DIVIDEND-T05ST09','formal_raw':True,'status':'FORMAL_RAW_COMPLETE',
      'endpoint':ns['BASE']+'/mops/web/ajax_t05st09_2','universe_count':2436,'universe_sha256':universe_sha,
      'target_units':4872,'checkpoint_units':621,'remaining_units':4251,'remaining_success_units':len(store),
      'union_success_units':4872,'missing_repaired_units':len(missing),'checkpoint_key_ledger_sha256':checkpoint_key_sha,
      'checkpoint_reference_mode':'IMMUTABLE_DRIVE_SHARDS_NO_REGRAB','checkpoint_drive_shards':T05_CHECKPOINT_DRIVE,
      'source_run_ids':list(repair_runs),'contract':{'date1':'085','date2':'115','qryType':[1,2],'firstin':'1','TYPEK':'all'},
      'artifact_audit':audit,'generated_at':ns['now']()}
    root=pathlib.Path('out_w08_final_t05'); root.mkdir(parents=True,exist_ok=True)
    out=root/'RAW-W08_MOPS_DIVIDEND_T05ST09_FORMAL_RAW_REMAINING_4251_FINAL_20260912.zip'
    ns['deterministic_zip'](out,store,'t05',summary)
    ref={k:v for k,v in summary.items() if k!='artifact_audit'}
    (root/'FINAL_REFERENCE_LEDGER.json').write_text(json.dumps(ref,ensure_ascii=False,indent=2,sort_keys=True)+'\n')
    info={'file':out.name,'bytes':out.stat().st_size,'sha256':ns['sha'](out.read_bytes()),'summary':ref}
    (root/'PACKAGE_INFO.json').write_text(json.dumps(info,ensure_ascii=False,indent=2,sort_keys=True)+'\n')
    print(json.dumps(info,ensure_ascii=False),flush=True)

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
    missing=sorted(target-set(store)); print(json.dumps({'mode':'pre','have':len(store),'missing':len(missing),'source_runs':run_ids}),flush=True)
    for i,key in enumerate(missing,1):
        body,raw,gz,meta=ns['capture_pre'](key); ns['add_item'](store,key,body,raw,gz,meta); print(json.dumps({'repair':i,'of':len(missing),'key':key}),flush=True)
    if set(store)!=target: raise RuntimeError(f'final_coverage_fail have={len(store)} target={len(target)}')
    summary={'schema':'w08_t59_pre20050505_final_aggregate_v2','work_unit_id':'W08-RAW-MOPS-EXRIGHT-PRE20050505','formal_raw':True,'status':'FORMAL_RAW_COMPLETE','endpoint':ns['BASE']+'/mops/web/ajax_t59sb07','official_scope':'公開發行及94.5.5前之全體公司','universe_count':1281,'universe_sha256':universe_sha,'years':years,'target_units':12810,'success_units':len(store),'missing_repaired_units':len(missing),'source_run_ids':list(run_ids),'contract':{'firstin':'1','TYPEK':'all','company_required':True,'year_required':True,'ui_click_semantics_verified':True,'ui_sequence':'doAction sets firstin=1 before ajax1(form1)'},'artifact_audit':audit,'generated_at':ns['now']()}
    root=pathlib.Path('out_w08_final_pre'); root.mkdir(parents=True,exist_ok=True)
    out=root/'RAW-W08_MOPS_EXRIGHT_PRE20050505_FORMAL_RAW_ROC85_94_FINAL_20260912.zip'
    ns['deterministic_zip'](out,store,'pre',summary)
    info={'file':out.name,'bytes':out.stat().st_size,'sha256':ns['sha'](out.read_bytes()),'summary':{k:v for k,v in summary.items() if k!='artifact_audit'}}
    (root/'PACKAGE_INFO.json').write_text(json.dumps(info,ensure_ascii=False,indent=2,sort_keys=True)+'\n'); print(json.dumps(info,ensure_ascii=False),flush=True)
else:
    raise SystemExit('MODE must be t05 or pre')
