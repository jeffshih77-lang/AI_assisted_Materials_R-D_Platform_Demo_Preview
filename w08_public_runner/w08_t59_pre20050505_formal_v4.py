import json, os, pathlib, runpy, time, urllib.request
shard=int(os.environ.get('SHARD','0'))
shards=int(os.environ.get('SHARDS','64'))
if shard>=30:
    root=pathlib.Path(f'out_t59_pre_v4_{shard:02d}_of_{shards:02d}')
    root.mkdir(parents=True,exist_ok=True)
    (root/'DEFERRED_TO_ACCELERATED_TAIL.json').write_text('{"formal_raw":false,"status":"DEFERRED_TO_ACCELERATED_TAIL","reason":"Shard >=30 was still queued when tail accelerator was created; no MOPS request issued by this original job."}\n')
    print('DEFERRED_TO_ACCELERATED_TAIL_NO_REQUESTS',flush=True)
    raise SystemExit(1)
if shard==29:
    url='https://api.github.com/repos/jeffshih77-lang/AI_assisted_Materials_R-D_Platform_Demo_Preview/actions/runs/34691209234'
    deadline=time.time()+5400
    while True:
        try:
            req=urllib.request.Request(url,headers={'User-Agent':'W08-PRE-tail-sync/1.0','Accept':'application/vnd.github+json'})
            with urllib.request.urlopen(req,timeout=30) as r: d=json.loads(r.read())
            print(json.dumps({'tail_sync_status':d.get('status'),'tail_sync_conclusion':d.get('conclusion')}),flush=True)
            if d.get('status')=='completed': break
        except Exception as e:
            print('tail_sync_probe_error '+repr(e),flush=True)
        if time.time()>=deadline: raise SystemExit('TAIL_SYNC_TIMEOUT')
        time.sleep(60)
runpy.run_path('w08_public_runner/w08_t59_pre20050505_formal_v4_tail.py',run_name='__main__')
