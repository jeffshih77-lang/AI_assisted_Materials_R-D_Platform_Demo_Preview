import json, os, pathlib, runpy
shard=int(os.environ.get('SHARD','0'))
shards=int(os.environ.get('SHARDS','64'))
if shard>=30:
    root=pathlib.Path(f'out_t59_pre_v4_{shard:02d}_of_{shards:02d}'); root.mkdir(parents=True,exist_ok=True)
    (root/'DEFERRED_TO_ACCELERATED_TAIL.json').write_text(json.dumps({'formal_raw':False,'status':'DEFERRED_TO_ACCELERATED_TAIL','reason':'Shard >=30 was still queued when tail accelerator was created; this original matrix job issues zero MOPS requests.'},sort_keys=True)+'\n')
    print('DEFERRED_TO_ACCELERATED_TAIL_NO_REQUESTS',flush=True)
    raise SystemExit(1)
if shard in (28,29):
    root=pathlib.Path(f'out_t59_pre_v4_{shard:02d}_of_{shards:02d}'); root.mkdir(parents=True,exist_ok=True)
    (root/'DEFERRED_TO_EXACT_FINALIZER.json').write_text(json.dumps({'formal_raw':False,'status':'DEFERRED_TO_EXACT_FINALIZER','reason':'Shard was still queued after v2 exact finalizer had already started. Finalizer waits both original-v4 and tail runs, computes target minus validated successes, and captures only true missing units. This matrix job issues zero MOPS requests.'},sort_keys=True)+'\n')
    print('DEFERRED_TO_EXACT_FINALIZER_NO_REQUESTS',flush=True)
    raise SystemExit(1)
runpy.run_path('w08_public_runner/w08_t59_pre20050505_formal_v4_tail.py',run_name='__main__')
