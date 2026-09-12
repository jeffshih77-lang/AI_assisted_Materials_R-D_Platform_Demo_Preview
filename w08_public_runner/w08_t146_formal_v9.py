import base64, datetime as dt, gzip, hashlib, io, json, os, pathlib, random, re, time, urllib.error, urllib.request, zipfile

SHARD=int(os.environ.get('SHARD','0'))
SHARDS=int(os.environ.get('SHARDS','64'))
if SHARD<0 or SHARD>=SHARDS: raise SystemExit('invalid shard')
ROOT=pathlib.Path(f'out_w08_t146_v9_{SHARD:02d}_of_{SHARDS:02d}')
STAGE=ROOT/'stage'; STAGE.mkdir(parents=True,exist_ok=True)
URL='https://mops.twse.com.tw/mops/api/t146sb10'
UA='Mozilla/5.0 (compatible; W08T146Formal/9.0)'
MARKETS=('sii','otc','rotc','pub')

def now(): return dt.datetime.now(dt.timezone.utc).isoformat().replace('+00:00','Z')
def sha(b): return hashlib.sha256(b).hexdigest()
def stable_gzip(b):
    q=io.BytesIO()
    with gzip.GzipFile(fileobj=q,mode='wb',filename='',mtime=0) as g:g.write(b)
    return q.getvalue()
def load_codes(path,expected):
    raw=gzip.decompress(base64.b64decode(pathlib.Path(path).read_text().strip()))
    codes=[x.strip() for x in raw.decode('utf-8').splitlines() if x.strip()]
    assert len(codes)==expected and len(set(codes))==expected and all(len(c)==4 and c.isdigit() for c in codes)
    return sorted(codes),sha(raw)

pre,pre_sha=load_codes('w08_public_runner/w08_pre20050504_codes_1281.txt.gz.b64',1281)
full,full_sha=load_codes('w08_public_runner/w08_security_master_4digit_universe_2436.txt.gz.b64',2436)
assert set(pre)<=set(full)

target=[]
# Before ROC94, use only companies with formal pre-2005 identity evidence.
for y in range(85,94):
    for code in pre: target.append(('company',y,code,'sii'))
# ROC94-105: full frozen Security Master universe, company scope required because market-wide history is incomplete.
for y in range(94,106):
    for code in full: target.append(('company',y,code,'sii'))
# ROC106-115: market-wide annual scope is qualified and far more efficient.
for y in range(106,116):
    for market in MARKETS: target.append(('market',y,'',market))
assert len(target)==40801, len(target)
keys=[f'{m}|{y:03d}|{c}|{k}' for m,y,c,k in target]
assert len(keys)==len(set(keys))
target_hash=sha(('\n'.join(keys)+'\n').encode())
assigned=[u for i,u in enumerate(target) if i%SHARDS==SHARD]
assigned_keys=[f'{m}|{y:03d}|{c}|{k}' for m,y,c,k in assigned]

def body_for(u):
    mode,y,code,market=u
    d={
      'scopeType':'1' if mode=='company' else '2',
      'companyId':code if mode=='company' else '',
      'dateType':'1','firstDate':f'{y:03d}0101','lastDate':f'{y:03d}1231',
      'marketKind':market,'announcementBasis':'0','dateRangeType':'',
      'announcementType':'1','sort':'1','encodeURIComponent':1,'step':1,'firstin':1,'off':1
    }
    return json.dumps(d,separators=(',',':'),ensure_ascii=False).encode('utf-8')

def analyze(raw,y):
    p=json.loads(raw.decode('utf-8'))
    code=p.get('code'); msg=p.get('message')
    if code not in (200,406): raise RuntimeError(f'api_code={code} message={msg!r}')
    result=p.get('result')
    rows=0; dates=[]; headers=[]
    if code==406:
        if result not in (None,[],{}): raise RuntimeError('406_with_nonempty_result')
        return {'api_code':code,'api_message':msg,'result_groups':0,'row_count':0,'date_count':0,'min_date':None,'max_date':None,'out_of_year_count':0,'headers':[]}
    if not isinstance(result,list): raise RuntimeError(f'200_result_not_list:{type(result).__name__}')
    for group in result:
        if not isinstance(group,dict): raise RuntimeError('result_group_not_dict')
        headers.append(str(group.get('header','')))
        titles=group.get('titles') or []; data=group.get('data') or []
        if not isinstance(data,list): raise RuntimeError('group_data_not_list')
        mains=[str(x.get('main','')) if isinstance(x,dict) else str(x) for x in titles]
        try: di=mains.index('公告日期')
        except ValueError: di=None
        rows+=len(data)
        if len(data)>0 and di is None: raise RuntimeError('rows_without_announcement_date_title')
        if di is not None:
            for r in data:
                if not isinstance(r,list) or di>=len(r): raise RuntimeError('row_date_column_missing')
                s=str(r[di]).strip()
                if not re.fullmatch(r'\d{1,3}/\d{1,2}/\d{1,2}',s): raise RuntimeError(f'invalid_announcement_date:{s!r}')
                dates.append(s)
    if rows!=len(dates): raise RuntimeError(f'row_date_count_mismatch rows={rows} dates={len(dates)}')
    out=[d for d in dates if int(d.split('/')[0])!=y]
    if out: raise RuntimeError(f'out_of_year_dates count={len(out)} examples={out[:5]}')
    return {'api_code':code,'api_message':msg,'result_groups':len(result),'row_count':rows,'date_count':len(dates),'min_date':min(dates,default=None),'max_date':max(dates,default=None),'out_of_year_count':0,'headers':headers}

def fetch_one(u):
    mode,y,code,market=u; body=body_for(u); key=f'{mode}|{y:03d}|{code}|{market}'
    last=None; retry=[]
    for attempt in range(1,6):
        try:
            req=urllib.request.Request(URL,data=body,method='POST',headers={'User-Agent':UA,'Accept':'application/json,*/*','Content-Type':'application/json','Origin':'https://mops.twse.com.tw','Referer':'https://mops.twse.com.tw/mops/#/web/t146sb10'})
            ts=now()
            with urllib.request.urlopen(req,timeout=90) as r:
                raw=r.read(); status=r.status; final_url=r.geturl(); headers_raw=str(r.headers)
            if status!=200 or not raw: raise RuntimeError(f'http={status} bytes={len(raw)}')
            a=analyze(raw,y); gz=stable_gzip(raw)
            if gzip.decompress(gz)!=raw: raise RuntimeError('gzip_roundtrip_fail')
            rec={'key':key,'mode':mode,'year':y,'companyId':code,'marketKind':market,'scopeType':'1' if mode=='company' else '2','retrieved_at':ts,'request_url':URL,'final_url':final_url,'method':'POST','http_status':status,'response_headers':headers_raw,'request_bytes':len(body),'request_sha256':sha(body),'response_bytes':len(raw),'response_sha256':sha(raw),'gzip_bytes':len(gz),'gzip_sha256':sha(gz),'gzip_roundtrip':True,'retry_count':len(retry),'retry_events':retry}
            rec.update(a)
            return body,raw,gz,rec
        except Exception as e:
            last=repr(e); retry.append({'attempt':attempt,'at':now(),'error':last})
            # Contract/API errors are deterministic; transport/JSON failures may recover.
            if 'api_code=' in last or 'out_of_year_dates' in last or 'rows_without_' in last or 'invalid_announcement_date' in last or 'row_date_' in last or '406_with_' in last or '200_result_' in last or 'result_group_' in last or 'group_data_' in last:
                break
            if attempt<5: time.sleep(min(15,1.8**attempt+random.random()))
    raise RuntimeError(f'{key} terminal {last}')

def stem(u):
    mode,y,code,market=u
    return f'company/{y:03d}/{code}' if mode=='company' else f'market/{y:03d}/{market}'

records=[]; failures=[]; file_sha={}
for n,u in enumerate(assigned,1):
    s=stem(u); key=f'{u[0]}|{u[1]:03d}|{u[2]}|{u[3]}'
    try:
        body,raw,gz,rec=fetch_one(u)
        for rel,b in [(f'request/{s}.json',body),(f'raw/{s}.response.bin',raw),(f'raw/{s}.response.bin.gz',gz)]:
            p=STAGE/rel; p.parent.mkdir(parents=True,exist_ok=True); p.write_bytes(b); file_sha[rel]=sha(b)
        records.append(rec)
        print(json.dumps({'done':n,'of':len(assigned),'key':key,'api_code':rec['api_code'],'rows':rec['row_count'],'bytes':rec['response_bytes']},ensure_ascii=False),flush=True)
    except Exception as e:
        f={'key':key,'mode':u[0],'year':u[1],'companyId':u[2],'marketKind':u[3],'error':repr(e),'failed_at':now()}; failures.append(f); print(json.dumps({'FAILED':f},ensure_ascii=False),flush=True)
    time.sleep(0.25+random.random()*0.10)

manifest={'schema':'w08_t146_formal_raw_shard_v9','work_unit_id':'W08-RAW-MOPS-STRUCTURED-T146','formal_raw':True,'source_authority':'MOPS/TWSE','endpoint':URL,'method':'POST','contract':{'company_scope':{'scopeType':'1','dateType':'1','firstDate':'YYY0101','lastDate':'YYY1231','marketKind':'sii (non-semantic under scopeType=1; separately qualified)','announcementBasis':'0','dateRangeType':'','announcementType':'1','sort':'1','encodeURIComponent':1,'step':1,'firstin':1,'off':1},'market_scope':{'scopeType':'2','companyId':'','dateType':'1','firstDate':'YYY0101','lastDate':'YYY1231','marketKind':['sii','otc','rotc','pub'],'announcementBasis':'0','dateRangeType':'','announcementType':'1','sort':'1','encodeURIComponent':1,'step':1,'firstin':1,'off':1},'lastDate_semantics':'inclusive; therefore annual segments end at same-year 1231','roc_year_encoding':'three digits with leading zero for years <100'},'coverage_contract':{'roc85_93':'1281 pre-2005 identity-evidence companies x 9 years, company scope','roc94_105':'2436 frozen Security Master companies x 12 years, company scope','roc106_115':'4 markets x 10 years, market scope','target_units':40801,'target_work_unit_set_sha256':target_hash,'pre_universe_count':1281,'pre_universe_sha256':pre_sha,'full_universe_count':2436,'full_universe_sha256':full_sha},'shard':SHARD,'shards':SHARDS,'assigned_units':len(assigned),'assigned_keys_sha256':sha(('\n'.join(assigned_keys)+'\n').encode()),'success_units':len(records),'failed_units':len(failures),'records':records,'failures':failures,'generated_at':now()}
(STAGE/'MANIFEST.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')
(STAGE/'FAILURES.json').write_text(json.dumps(failures,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')
(STAGE/'SHA256.txt').write_text(''.join(f'{v}  {k}\n' for k,v in sorted(file_sha.items())),encoding='utf-8')

out=ROOT/f'RAW-W08_MOPS_T146_FORMAL_RAW_V9_SHARD_{SHARD:02d}_OF_{SHARDS:02d}_20260912.zip'
with zipfile.ZipFile(out,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6,allowZip64=True) as z:
    for p in sorted(STAGE.rglob('*')):
        if not p.is_file(): continue
        rel=p.relative_to(STAGE).as_posix(); data=p.read_bytes(); zi=zipfile.ZipInfo(rel,(1980,1,1,0,0,0)); zi.compress_type=zipfile.ZIP_DEFLATED; zi.external_attr=0o100644<<16; z.writestr(zi,data,compress_type=zipfile.ZIP_DEFLATED,compresslevel=6)
info={'file':out.name,'bytes':out.stat().st_size,'sha256':sha(out.read_bytes()),'shard':SHARD,'shards':SHARDS,'assigned_units':len(assigned),'success_units':len(records),'failed_units':len(failures),'target_units':40801,'target_work_unit_set_sha256':target_hash,'generated_at':now()}
(ROOT/'PACKAGE_INFO.json').write_text(json.dumps(info,ensure_ascii=False,indent=2,sort_keys=True)+'\n')
print(json.dumps(info,ensure_ascii=False),flush=True)
if failures: raise SystemExit(f'PARTIAL_FORMAL_SHARD failures={len(failures)}')
