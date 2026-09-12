import concurrent.futures, json, os, pathlib, subprocess, sys

SHARD=int(os.environ.get('SHARD','0'))
SHARDS=int(os.environ.get('SHARDS','64'))
CORE_COMMIT='78a14b18ea61a930c9c5bd32f8e8e65155c6d9ec'
CORE_PATH='w08_public_runner/w08_t59_pre20050505_formal_v4_tail.py'
ALREADY_RUNNING={30,31,34,37,39,41,44}
BULK_SHARDS=[32,33,35,36,38,40,42,43,45,46,47,48,49,50,51,52,53,54,55,56,57,58,59,60,61,62,63]
LEADER=63
STANDALONE=(os.environ.get('BULK_STANDALONE','0')=='1')

def ensure_core():
    try:
        subprocess.check_call(['git','cat-file','-e',f'{CORE_COMMIT}^{{commit}}'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    except subprocess.CalledProcessError:
        subprocess.check_call(['git','fetch','--depth=1','origin',CORE_COMMIT])

def run_core_in_process():
    ensure_core()
    src=subprocess.check_output(['git','show',f'{CORE_COMMIT}:{CORE_PATH}'],text=True)
    exec(compile(src,CORE_PATH,'exec'),{'__name__':'__main__'})

def child(shard):
    env=os.environ.copy(); env['SHARD']=str(shard); env['SHARDS']=str(SHARDS); env['TAIL_CHILD']='1'; env.pop('BULK_STANDALONE',None)
    print(json.dumps({'bulk_child_start':shard}),flush=True)
    p=subprocess.run([sys.executable,__file__],env=env)
    print(json.dumps({'bulk_child_end':shard,'returncode':p.returncode}),flush=True)
    return shard,p.returncode

def defer(reason,tag):
    root=pathlib.Path(f'out_t59_pre_v4_{SHARD:02d}_of_{SHARDS:02d}'); root.mkdir(parents=True,exist_ok=True)
    (root/f'{tag}.json').write_text(json.dumps({'formal_raw':False,'status':tag,'leader_shard':LEADER,'reason':reason},sort_keys=True)+'\n')
    print(tag+'_NO_REQUESTS',flush=True)
    raise SystemExit(1)

if os.environ.get('TAIL_CHILD')=='1':
    run_core_in_process()
elif STANDALONE:
    defer('Original tail run shard63 is the unique bulk owner so its artifact remains visible to the already-running final reconciler. This standalone safety run issues zero MOPS requests.','DEFERRED_TO_ORIGINAL_TAIL_LEADER')
elif SHARD in BULK_SHARDS and SHARD!=LEADER:
    defer('This matrix job is owned by shard63 bulk leader and issues zero MOPS requests.','DEFERRED_TO_SHARD63_BULK')
elif SHARD==LEADER:
    ensure_core()
    results=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
        futs=[ex.submit(child,s) for s in BULK_SHARDS]
        for f in concurrent.futures.as_completed(futs): results.append(f.result())
    results.sort()
    print(json.dumps({'bulk_results':results}),flush=True)
    if any(rc!=0 for _,rc in results): raise SystemExit('BULK_HAS_PARTIAL_FAILURES')
else:
    run_core_in_process()
