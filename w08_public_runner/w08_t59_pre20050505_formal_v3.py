import datetime as dt,json,os,pathlib
SHARD=int(os.environ.get('SHARD','0')); SHARDS=int(os.environ.get('SHARDS','32'))
ROOT=pathlib.Path(f'out_t59_pre_{SHARD:02d}_of_{SHARDS:02d}'); ROOT.mkdir(parents=True,exist_ok=True)
notice={'schema':'w08_t59_pre_v3_deprecation_v1','formal_raw':False,'status':'DEPRECATED_CONTRACT_DO_NOT_PROMOTE','reason':'Official t59 query button executes doAction() before ajax1(form1); doAction sets form1.firstin to 1. v3 used hidden initial literal ture and is qualification-only.','replacement':'w08_t59_pre20050505_formal_v4.py','shard':SHARD,'shards':SHARDS,'generated_at':dt.datetime.now(dt.timezone.utc).isoformat().replace('+00:00','Z')}
(ROOT/'DEPRECATED_CONTRACT.json').write_text(json.dumps(notice,ensure_ascii=False,indent=2,sort_keys=True)+'\n')
print(json.dumps(notice,ensure_ascii=False),flush=True)
raise SystemExit('DEPRECATED_CONTRACT_DO_NOT_EXECUTE_V3')
