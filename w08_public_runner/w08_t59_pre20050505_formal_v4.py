import os, pathlib, runpy
shard=int(os.environ.get('SHARD','0'))
if shard>=30:
    root=pathlib.Path(f'out_t59_pre_v4_{shard:02d}_of_{int(os.environ.get("SHARDS","64")):02d}')
    root.mkdir(parents=True,exist_ok=True)
    (root/'DEFERRED_TO_ACCELERATED_TAIL.json').write_text('{"formal_raw":false,"status":"DEFERRED_TO_ACCELERATED_TAIL","reason":"Shard >=30 was still queued when tail accelerator was created; no MOPS request issued by this original job."}\n')
    print('DEFERRED_TO_ACCELERATED_TAIL_NO_REQUESTS')
    raise SystemExit(1)
runpy.run_path('w08_public_runner/w08_t59_pre20050505_formal_v4_tail.py',run_name='__main__')
