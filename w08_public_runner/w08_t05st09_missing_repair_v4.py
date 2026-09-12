import json, os, pathlib
shard=int(os.environ.get('SHARD','0')); shards=int(os.environ.get('SHARDS','16'))
if shard==9:
    root=pathlib.Path(f'out_t05_repair_{shard:02d}_of_{shards:02d}'); root.mkdir(parents=True,exist_ok=True)
    (root/'DEFERRED_TO_EXACT_FINALIZER.json').write_text(json.dumps({'formal_raw':False,'status':'DEFERRED_TO_EXACT_FINALIZER','reason':'Shard 9 was still queued after validated shards 0-7 completed and shard 8 entered capture. Existing W08 finalizer already owns exact target-minus-success reconciliation and will capture only the true remaining keys. This matrix job issues zero MOPS requests.'},sort_keys=True)+'\n')
    print('DEFERRED_TO_EXACT_FINALIZER_NO_REQUESTS',flush=True)
    raise SystemExit(1)
raise SystemExit('REPAIR_V4_SOURCE_FROZEN_AFTER_SHARD9_DEFER; do not rerun completed shards with this dispatcher')
