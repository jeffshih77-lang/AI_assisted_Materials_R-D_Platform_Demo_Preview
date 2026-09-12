import datetime as dt, gzip, hashlib, io, json, os, pathlib, random, time, urllib.error, urllib.request, zipfile

BASE='https://mops.twse.com.tw'
ENDPOINT=BASE+'/mops/api/t146sb10'
UA='Mozilla/5.0 (compatible; W08T146Formal/8.1)'
MARKETS=('sii','otc','rotc','pub')
SEGMENTS=((85,87),(88,90),(91,93),(94,96),(97,99),(100,102),(103,105),(106,108),(109,111),(112,114),(115,115))
SEG=int(os.environ.get('SEGMENT','0'))
YSTART,YEND=SEGMENTS[SEG]
ROOT=pathlib.Path(f'out_t146_formal_seg{SEG:02d}_{YSTART:03d}_{YEND:03d}')
ROOT.mkdir(parents=True,exist_ok=True)
CAP=ROOT/'capture'; CAP.mkdir(exist_ok=True)
records=[]; anomalies=[]; retry_events=[]; failures=[]

def now(): return dt.datetime.now(dt.timezone.utc).isoformat().replace('+00:00','Z')
def sha(b): return hashlib.sha256(b).hexdigest()
def roc(d): return f'{d.year-1911:03d}{d.month:02d}{d.day:02d}'
def classify(raw):
    try: p=json.loads(raw)
    except Exception: return {'json_valid':False,'api_code':None,'api_message':None,'tables':0,'rows':0,'min_date':None,'max_date':None}
    res=p.get('result') or []; rows=0; dates=[]
    if isinstance(res,list):
        for t in res:
            if not isinstance(t,dict): continue
            data=t.get('data') or []
            if isinstance(data,list): rows += len(data)
            titles=t.get('titles') or []
            idx=next((i for i,x in enumerate(titles) if isinstance(x,dict) and x.get('main')=='公告日期'),None)
            if idx is not None and isinstance(data,list):
                for row in data:
                    if isinstance(row,list) and idx < len(row): dates.append(str(row[idx]))
    return {'json_valid':True,'api_code':p.get('code'),'api_message':p.get('message'),'tables':len(res) if isinstance(res,list) else 0,'rows':rows,'min_date':min(dates) if dates else None,'max_date':max(dates) if dates else None}

def body_for(market,start,end):
    # Frozen from the official SPA/API contract qualification. Dict order is intentional and preserved in request bytes.
    return {'scopeType':'2','companyId':'','dateType':'1','firstDate':roc(start),'lastDate':roc(end),'marketKind':market,'announcementBasis':'0','dateRangeType':'','announcementType':'1','sort':'1'}

def request_once(market,start,end):
    body=body_for(market,start,end)
    qb=json.dumps(body,ensure_ascii=False,separators=(',',':')).encode('utf-8')
    req=urllib.request.Request(ENDPOINT,data=qb,method='POST',headers={'User-Agent':UA,'Accept':'application/json,*/*','Content-Type':'application/json','Origin':BASE,'Referer':BASE+'/mops/#/web/t146sb10'})
    last=None
    for attempt in range(1,9):
        at=now()
        try:
            with urllib.request.urlopen(req,timeout=90) as r:
                raw=r.read(); status=r.status; final_url=r.geturl(); headers=dict(r.headers)
            c=classify(raw)
            if status!=200 or not c['json_valid'] or c['api_code'] not in (200,406):
                retry_events.append({'market':market,'start':roc(start),'end':roc(end),'attempt':attempt,'at':at,'http_status':status,'classification':c,'response_sha256':sha(raw)})
                last=f'invalid status/code {status}/{c.get("api_code")}'
                time.sleep(min(20,1.5**attempt+random.random()))
                continue
            return qb,raw,status,final_url,headers,c,attempt-1
        except urllib.error.HTTPError as e:
            raw=e.read(); c=classify(raw)
            retry_events.append({'market':market,'start':roc(start),'end':roc(end),'attempt':attempt,'at':at,'http_status':e.code,'error':'HTTPError','response_bytes':len(raw),'response_sha256':sha(raw),'classification':c})
            last=f'HTTPError {e.code}'
        except Exception as e:
            retry_events.append({'market':market,'start':roc(start),'end':roc(end),'attempt':attempt,'at':at,'error':repr(e)})
            last=repr(e)
        time.sleep(min(20,1.5**attempt+random.random()))
    raise RuntimeError(f'terminal {market} {roc(start)} {roc(end)} {last}')

def save_capture(market,start,end,qb,raw,status,final_url,headers,c,retries,depth):
    stem=f'{market}_{roc(start)}_{roc(end)}'
    req_name=f'request/{stem}.json'; raw_name=f'raw/{stem}.response.bin'; gz_name=raw_name+'.gz'; meta_name=f'meta/{stem}.json'
    gzbuf=io.BytesIO()
    with gzip.GzipFile(filename='',fileobj=gzbuf,mode='wb',mtime=0) as g:g.write(raw)
    gz=gzbuf.getvalue()
    meta={'market':market,'start':roc(start),'end':roc(end),'depth':depth,'request_url':ENDPOINT,'method':'POST','retrieved_at':now(),'http_status':status,'final_url':final_url,'content_type':headers.get('Content-Type'),'request_bytes':len(qb),'request_sha256':sha(qb),'response_bytes':len(raw),'response_sha256':sha(raw),'gzip_bytes':len(gz),'gzip_sha256':sha(gz),'gzip_roundtrip':gzip.decompress(gz)==raw,'retry_count':retries,'classification':c,'request_file':req_name,'response_file':raw_name,'gzip_file':gz_name,'meta_file':meta_name}
    p=CAP/stem; p.mkdir(parents=True,exist_ok=True)
    (p/'request.json').write_bytes(qb); (p/'response.bin').write_bytes(raw); (p/'response.bin.gz').write_bytes(gz); (p/'meta.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')
    records.append(meta)
    return meta

def resolve(market,start,end,depth=0):
    try:
        qb,raw,status,final_url,headers,c,retries=request_once(market,start,end)
        meta=save_capture(market,start,end,qb,raw,status,final_url,headers,c,retries,depth)
    except Exception as e:
        failures.append({'market':market,'start':roc(start),'end':roc(end),'depth':depth,'error':repr(e),'at':now()})
        return False
    code=c['api_code']
    if code==200:
        meta['resolution']='DATA_OR_VALID_EMPTY_200'
        return True
    # 406 at a range cannot be trusted: qualification proved market-scope false negatives.
    if start==end:
        meta['resolution']='SOURCE_DECLARED_NO_DATA_DAY_406'
        anomalies.append({'type':'DAY_LEVEL_406_NO_DATA','market':market,'date':roc(start),'response_sha256':meta['response_sha256']})
        return True
    meta['resolution']='RANGE_406_SPLIT_FOR_FALSE_NEGATIVE_SAFETY'
    anomalies.append({'type':'RANGE_406_REQUIRES_SPLIT','market':market,'start':roc(start),'end':roc(end),'response_sha256':meta['response_sha256']})
    # v7c qualification proved a month-level false-negative can resolve at seven-day scope.
    # For wide ranges, jump directly to <=7-day slices; any slice still returning 406 is
    # recursively bisected until API 200 or a day-level source-declared 406.
    if (end-start).days > 6:
        cur=start; all_ok=True
        while cur<=end:
            sub_end=min(end,cur+dt.timedelta(days=6))
            time.sleep(0.12)
            child_ok=resolve(market,cur,sub_end,depth+1)
            all_ok=child_ok and all_ok
            cur=sub_end+dt.timedelta(days=1)
        return all_ok
    delta=(end-start).days; mid=start+dt.timedelta(days=delta//2)
    time.sleep(0.12)
    a=resolve(market,start,mid,depth+1)
    time.sleep(0.12)
    b=resolve(market,mid+dt.timedelta(days=1),end,depth+1)
    return a and b

def month_end(y,m):
    if m==12: return dt.date(y+1911,12,31)
    return dt.date(y+1911,m+1,1)-dt.timedelta(days=1)

monthly_targets=[]; ok=True
for y in range(YSTART,YEND+1):
    for m in range(1,13):
        s=dt.date(y+1911,m,1); e=month_end(y,m)
        for market in MARKETS:
            monthly_targets.append((market,roc(s),roc(e)))
            print(json.dumps({'segment':SEG,'target':len(monthly_targets),'market':market,'start':roc(s),'end':roc(e),'at':now()}),flush=True)
            if not resolve(market,s,e): ok=False
            time.sleep(0.18)

coverage={'schema':'w08_t146_jsonapi_formal_coverage_v8','runner_version':'8.1','work_unit_id':'W08-RAW-MOPS-STRUCTURED-T146','source_revision':'MOPS_T146_JSON_API_V2','authority':'MOPS official','endpoint':ENDPOINT,'segment':SEG,'roc_year_start':YSTART,'roc_year_end':YEND,'markets':list(MARKETS),'monthly_target_count':len(monthly_targets),'monthly_targets':monthly_targets,'capture_count':len(records),'api_200_captures':sum(1 for r in records if r['classification']['api_code']==200),'api_406_captures':sum(1 for r in records if r['classification']['api_code']==406),'row_count_across_200_responses':sum(r['classification']['rows'] for r in records if r['classification']['api_code']==200),'failure_count':len(failures),'anomaly_count':len(anomalies),'retry_event_count':len(retry_events),'status':'FORMAL_RAW_SEGMENT_COMPLETE' if ok and not failures else 'PARTIAL_FAILED','contract':{'scopeType':'2','companyId':'','dateType':'1','marketKind':'sii|otc|rotc|pub','announcementBasis':'0','dateRangeType':'','announcementType':'1','sort':'1','initial_partition':'calendar month','range_406_rule':'range 406 -> <=7-day slices; any 406 slice recursively bisected until API 200 or day-level source-declared 406'},'qualification_evidence':{'v7_run':34693727643,'v7_artifact':10298142663,'v7b_run':34694056871,'v7b_artifact':10297728630,'v7c_run':34694287992,'v7c_artifact':10297448827},'generated_at':now()}

manifest={'schema':'w08_t146_jsonapi_formal_manifest_v8','formal_raw':True,'work_unit_id':'W08-RAW-MOPS-STRUCTURED-T146','source_family':'MOPS_CA_ANNOUNCEMENT_T146_STRUCTURED_V1','source_revision':'MOPS_T146_JSON_API_V2','coverage':coverage,'records':records,'anomalies':anomalies,'retry_events':retry_events,'failures':failures}
(ROOT/'MANIFEST.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')
(ROOT/'COVERAGE.json').write_text(json.dumps(coverage,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')
(ROOT/'ANOMALY.json').write_text(json.dumps(anomalies,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')
(ROOT/'RETRY.json').write_text(json.dumps(retry_events,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')
(ROOT/'FAILURES.json').write_text(json.dumps(failures,ensure_ascii=False,indent=2,sort_keys=True)+'\n',encoding='utf-8')

out=pathlib.Path(f'RAW-W08_MOPS_T146_FORMAL_RAW_SEG{SEG:02d}_ROC{YSTART:03d}_{YEND:03d}_20260912.zip')
sha_lines=[]
def put(z,name,data,compress=zipfile.ZIP_DEFLATED):
    zi=zipfile.ZipInfo(name,(1980,1,1,0,0,0)); zi.compress_type=compress; zi.external_attr=0o100644<<16
    z.writestr(zi,data,compress_type=compress,compresslevel=6 if compress==zipfile.ZIP_DEFLATED else None); sha_lines.append(f'{sha(data)}  {name}')
with zipfile.ZipFile(out,'w',allowZip64=True) as z:
    for r in sorted(records,key=lambda x:(x['market'],x['start'],x['end'],x['depth'])):
        stem=f"{r['market']}_{r['start']}_{r['end']}"; p=CAP/stem
        put(z,r['request_file'],(p/'request.json').read_bytes())
        put(z,r['response_file'],(p/'response.bin').read_bytes())
        put(z,r['gzip_file'],(p/'response.bin.gz').read_bytes(),zipfile.ZIP_STORED)
        put(z,r['meta_file'],(p/'meta.json').read_bytes())
    for fn in ('MANIFEST.json','COVERAGE.json','ANOMALY.json','RETRY.json','FAILURES.json'):
        put(z,fn,(ROOT/fn).read_bytes())
    put(z,'SHA256.txt',('\n'.join(sorted(sha_lines))+'\n').encode())
info={'file':out.name,'bytes':out.stat().st_size,'sha256':sha(out.read_bytes()),'coverage':coverage}
pathlib.Path('PACKAGE_INFO.json').write_text(json.dumps(info,ensure_ascii=False,indent=2,sort_keys=True)+'\n')
print('PACKAGE_INFO',json.dumps(info,ensure_ascii=False),flush=True)
if failures: raise SystemExit(f'formal segment has {len(failures)} terminal failures')
