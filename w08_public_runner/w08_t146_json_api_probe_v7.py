import datetime as dt, gzip, hashlib, json, pathlib, time, urllib.request

OUT=pathlib.Path('out_w08_t146_json_v7'); OUT.mkdir(exist_ok=True)
URL='https://mops.twse.com.tw/mops/api/t146sb10'
UA='Mozilla/5.0 (compatible; W08T146JSONProbe/7.0)'

def now(): return dt.datetime.now(dt.timezone.utc).isoformat().replace('+00:00','Z')
def sha(b): return hashlib.sha256(b).hexdigest()

def count_rows(result):
    if isinstance(result,list):
        total=0; headers=[]
        for x in result:
            if isinstance(x,dict):
                d=x.get('data')
                if isinstance(d,list): total += len(d)
                headers.append(str(x.get('header','')))
        return total, headers
    if isinstance(result,dict):
        d=result.get('data')
        return (len(d) if isinstance(d,list) else 0), [str(result.get('header',''))]
    return 0, []

def one(case):
    y=case['year']; market=case['market']
    payload={
      'scopeType':'2',
      'companyId':'',
      'dateType':'1',
      'firstDate':f'{y:03d}0101',
      'lastDate':f'{y+1:03d}0101',
      'marketKind':market,
      'announcementBasis':'0',
      'dateRangeType':'',
      'announcementType':'1',
      'sort':'1',
      'encodeURIComponent':1,
      'step':1,
      'firstin':1,
      'off':1,
    }
    body=json.dumps(payload,separators=(',',':'),ensure_ascii=False).encode('utf-8')
    label=f"y{y:03d}_{market}"
    (OUT/f'{label}.request.json').write_bytes(body)
    last=None
    for attempt in range(1,6):
        try:
            req=urllib.request.Request(URL,data=body,method='POST',headers={'User-Agent':UA,'Accept':'application/json,*/*','Content-Type':'application/json','Origin':'https://mops.twse.com.tw','Referer':'https://mops.twse.com.tw/mops/#/web/t146sb10'})
            ts=now()
            with urllib.request.urlopen(req,timeout=120) as r:
                rb=r.read(); status=r.status; ctype=r.headers.get('content-type','')
            if status!=200 or not rb: raise RuntimeError(f'bad status={status} bytes={len(rb)}')
            break
        except Exception as e:
            last=repr(e)
            if attempt==5: raise
            time.sleep(2*attempt)
    (OUT/f'{label}.response.bin').write_bytes(rb)
    with gzip.GzipFile(OUT/f'{label}.response.bin.gz','wb',mtime=0) as g: g.write(rb)
    parsed=None; parse_error=None
    try: parsed=json.loads(rb.decode('utf-8'))
    except Exception as e: parse_error=repr(e)
    code=parsed.get('code') if isinstance(parsed,dict) else None
    msg=parsed.get('message') if isinstance(parsed,dict) else None
    result=parsed.get('result') if isinstance(parsed,dict) else None
    rows,headers=count_rows(result)
    rec={
      'label':label,'year':y,'market':market,'retrieved_at':ts,'url':URL,'method':'POST',
      'status':status,'content_type':ctype,'request_bytes':len(body),'request_sha256':sha(body),
      'response_bytes':len(rb),'response_sha256':sha(rb),'gzip_sha256':sha((OUT/f'{label}.response.bin.gz').read_bytes()),
      'gzip_roundtrip':gzip.decompress((OUT/f'{label}.response.bin.gz').read_bytes())==rb,
      'json_parse_ok':parsed is not None,'json_parse_error':parse_error,'api_code':code,'api_message':msg,
      'result_type':type(result).__name__,'row_count':rows,'headers':headers[:50],
    }
    print(json.dumps(rec,ensure_ascii=False),flush=True)
    return rec

# Historical coverage probes intentionally span far before and after the 2017 date used by public examples.
years=[85,90,93,94,95,100,105,106,110,114,115]
markets=['sii','otc','rotc','pub']
records=[]
for y in years:
    for m in markets:
        try: records.append(one({'year':y,'market':m}))
        except Exception as e:
            records.append({'label':f'y{y:03d}_{m}','year':y,'market':m,'terminal_error':repr(e)})
        time.sleep(0.35)

historical_nonempty=[r for r in records if r.get('year',999)<=105 and r.get('status')==200 and r.get('api_code')==200 and r.get('row_count',0)>0]
recent_nonempty=[r for r in records if r.get('year',0)>=106 and r.get('status')==200 and r.get('api_code')==200 and r.get('row_count',0)>0]
oldest_nonempty=min([r['year'] for r in records if r.get('status')==200 and r.get('api_code')==200 and r.get('row_count',0)>0],default=None)
manifest={
 'schema':'w08_t146_json_api_probe_v7','work_unit_id':'W08-RAW-MOPS-STRUCTURED-T146','qualification_only':True,
 'candidate_endpoint':URL,'method':'POST','contract_source':'current MOPS JSON API surface; exact request/response bytes retained',
 'years':years,'markets':markets,'records':records,
 'assertions':{
   'all_transport_or_explicit_terminal_recorded':len(records)==len(years)*len(markets),
   'any_historical_pre106_nonempty':bool(historical_nonempty),
   'any_recent_nonempty':bool(recent_nonempty),
   'oldest_nonempty_roc_year':oldest_nonempty,
   'all_success_gzip_roundtrip':all(r.get('gzip_roundtrip',True) for r in records if r.get('status')==200),
 },
 'historical_nonempty_labels':[r['label'] for r in historical_nonempty],
 'recent_nonempty_labels':[r['label'] for r in recent_nonempty],
 'generated_at':now(),
}
(OUT/'PROBE.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')
print(json.dumps(manifest['assertions'],ensure_ascii=False,indent=2),flush=True)
