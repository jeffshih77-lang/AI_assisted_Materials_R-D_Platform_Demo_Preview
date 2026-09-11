import datetime as dt
import gzip
import hashlib
import json
import os
import pathlib
import random
import re
import time
import urllib.error
import urllib.parse
import urllib.request

START_ROC = int(os.environ['START_ROC'])
END_ROC = int(os.environ['END_ROC'])
ROOT = pathlib.Path(f'out_roc{START_ROC}_{END_ROC}')
(ROOT / 'list').mkdir(parents=True, exist_ok=True)
(ROOT / 'detail').mkdir(parents=True, exist_ok=True)
UA = 'Mozilla/5.0 (compatible; W08FormalRawCollector/1.1)'
LIST = 'https://mopsov.twse.com.tw/mops/web/ajax_t51sb10'
DETAIL = 'https://mopsov.twse.com.tw/mops/web/ajax_t05st01'
KEY_RE = re.compile(r'document\.fm\.seq_no\.value="([^"]+)";document\.fm\.spoke_time\.value="([^"]+)";document\.fm\.spoke_date\.value="([^"]+)";document\.fm\.i\.value="([^"]+)";document\.fm\.co_id\.value="([^"]+)";document\.fm\.TYPEK\.value="([^"]+)";')
PAGE_RE = re.compile(r"document\.fm\.pagenum\.value='(\d+)'")
GENERIC_SHELL_MARKERS = ('<div id="div01"></div>', 'FOR SECURITY REASONS, THIS PAGE CAN NOT BE ACCESSED')
manifest = []
anomalies = []
detail_seen = {}
list_request_seen = set()
retry_events = []


def utc_now():
    return dt.datetime.now(dt.timezone.utc).isoformat().replace('+00:00', 'Z')


def write_state(stage, extra=None):
    state = {
        'schema': 'raw_w08_mops_t51_t05_segment_state_v1',
        'start_roc': START_ROC,
        'end_roc': END_ROC,
        'stage': stage,
        'updated_at': utc_now(),
        'list_capture_count': sum(1 for x in manifest if x['stage'] == 'LIST'),
        'detail_capture_count': sum(1 for x in manifest if x['stage'] == 'DETAIL'),
        'unique_detail_key_count': len(detail_seen),
        'retry_event_count': len(retry_events),
    }
    if extra:
        state.update(extra)
    (ROOT / 'RUN_STATE.json').write_text(json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')


def request_exact(url, validator=None, max_attempts=6):
    last = None
    for attempt in range(1, max_attempts + 1):
        ts = utc_now()
        try:
            req = urllib.request.Request(url, method='GET', headers={'User-Agent': UA, 'Accept': '*/*'})
            with urllib.request.urlopen(req, timeout=75) as resp:
                body = resp.read()
                status = getattr(resp, 'status', None)
                final = resp.geturl()
                headers = dict(resp.headers.items())
            if status != 200 or not body:
                raise RuntimeError(f'bad response status={status} bytes={len(body)}')
            if validator is not None:
                validator(body)
            if attempt > 1:
                retry_events.append({'url': url, 'success_attempt': attempt, 'at': ts})
            return body, status, final, headers, ts, attempt
        except Exception as exc:
            last = exc
            retry_events.append({'url': url, 'attempt': attempt, 'error': repr(exc), 'at': ts})
            if attempt >= max_attempts:
                break
            delay = min(45.0, (2 ** (attempt - 1)) + random.random())
            print('retry', attempt, 'url', url[:150], 'error', repr(exc), 'sleep', round(delay, 2), flush=True)
            time.sleep(delay)
    raise RuntimeError(f'exhausted retries for {url}: {last!r}')


def reject_generic_shell(body):
    text = body.decode('utf-8', 'replace')
    if len(body) < 5000 and any(m in text for m in GENERIC_SHELL_MARKERS):
        raise RuntimeError('generic/security MOPS shell')


def save(stage, stem, url, body, status, final, headers, ts, attempt, extra=None):
    folder = ROOT / stage
    raw = folder / (stem + '.response.bin')
    gz = folder / (stem + '.response.bin.gz')
    raw.write_bytes(body)
    with gzip.GzipFile(gz, 'wb', mtime=0) as f:
        f.write(body)
    assert gzip.decompress(gz.read_bytes()) == body
    rec = {
        'stage': stage.upper(),
        'request_method': 'GET',
        'request_url': url,
        'retrieved_at': ts,
        'http_status': status,
        'final_url': final,
        'content_type': headers.get('Content-Type'),
        'payload_bytes': len(body),
        'payload_sha256': hashlib.sha256(body).hexdigest(),
        'raw_path': str(raw.relative_to(ROOT)),
        'gzip_path': str(gz.relative_to(ROOT)),
        'gzip_sha256': hashlib.sha256(gz.read_bytes()).hexdigest(),
        'transport_attempt': attempt,
        'gzip_roundtrip_match': True,
    }
    if extra:
        rec.update(extra)
    manifest.append(rec)
    return rec


def list_url(kind, keyword, year, pagenum=None):
    params = [
        ('encodeURIComponent', '1'), ('firstin', 'true'), ('id', ''), ('key', ''),
        ('TYPEK', ''), ('Stp', '4'), ('go', 'false'), ('COMPANY_ID', ''), ('r1', '1'),
        ('KIND', kind), ('CODE', ''), ('keyWord', keyword), ('year', str(year)),
        ('month1', '0'), ('begin_day', '1'), ('end_day', '31'), ('PCount', '100'),
    ]
    if pagenum is not None:
        params.append(('pagenum', str(pagenum)))
    return LIST + '?' + urllib.parse.urlencode(params)


def capture_list(kind, keyword, year, pagenum=None):
    url = list_url(kind, keyword, year, pagenum)
    if url in list_request_seen:
        return [], []
    list_request_seen.add(url)
    body, status, final, headers, ts, attempt = request_exact(url, reject_generic_shell)
    text = body.decode('utf-8', 'replace')
    keys = KEY_RE.findall(text)
    pages = sorted({int(x) for x in PAGE_RE.findall(text)})
    safe_kw = 'reduction' if keyword == '減資' else 'merger'
    stem = f'ROC{year}_{kind}_{safe_kw}_p' + ('initial' if pagenum is None else str(pagenum))
    save('list', stem, url, body, status, final, headers, ts, attempt, {
        'roc_year': year,
        'kind': kind,
        'keyword': keyword,
        'pagenum': pagenum,
        'onclick_key_count': len(keys),
        'discovered_page_numbers': pages,
    })
    return keys, pages


write_state('LIST_CAPTURE')
for year in range(START_ROC, END_ROC + 1):
    for kind in ('L', 'O'):
        for keyword in ('減資', '合併'):
            keys, pages = capture_list(kind, keyword, year, None)
            all_keys = list(keys)
            for pg in pages:
                k2, _ = capture_list(kind, keyword, year, pg)
                all_keys.extend(k2)
                time.sleep(0.04)
            for tup in all_keys:
                seq_no, spoke_time, spoke_date, i, co_id, typek = tup
                dkey = (co_id, spoke_date, spoke_time, seq_no, i, typek)
                detail_seen.setdefault(dkey, {'discoveries': []})['discoveries'].append({
                    'roc_year': year, 'kind': kind, 'keyword': keyword,
                })
    write_state('LIST_CAPTURE', {'last_completed_roc': year})
    print('completed ROC', year, 'list_requests', len(list_request_seen), 'unique_details', len(detail_seen), flush=True)

write_state('DETAIL_CAPTURE')
for n, (dkey, disc) in enumerate(detail_seen.items(), 1):
    co_id, spoke_date, spoke_time, seq_no, i, typek = dkey
    params = [
        ('step', '2'), ('colorchg', '1'), ('co_id', co_id), ('TYPEK', typek),
        ('off', '1'), ('firstin', '1'), ('i', i), ('year', '2018'), ('month', '6'),
        ('spoke_date', spoke_date), ('spoke_time', spoke_time), ('seq_no', seq_no),
        ('b_date', '1'), ('e_date', '1'), ('t51sb10', 't51sb10'),
    ]
    url = DETAIL + '?' + urllib.parse.urlencode(params)
    body, status, final, headers, ts, attempt = request_exact(url, max_attempts=6)
    text = body.decode('utf-8', 'replace')
    stem = f'{co_id}_{spoke_date}_{spoke_time}_{seq_no}_{i}_{typek}'
    provider = '本資料由' in text
    security_shell = len(body) < 5000 and any(m in text for m in GENERIC_SHELL_MARKERS)
    rec = save('detail', stem, url, body, status, final, headers, ts, attempt, {
        'key': {'co_id': co_id, 'spoke_date': spoke_date, 'spoke_time': spoke_time, 'seq_no': seq_no, 'i': i, 'TYPEK': typek},
        'has_company_provider_marker': provider,
        'security_or_generic_shell': security_shell,
        'discoveries': disc['discoveries'],
    })
    if security_shell:
        raise RuntimeError(f'generic/security shell detail response: {url}')
    if not provider:
        anomalies.append({
            'type': 'SOURCE_DETAIL_EMPTY_OR_NONSTANDARD',
            'key': rec['key'],
            'payload_bytes': len(body),
            'payload_sha256': rec['payload_sha256'],
            'request_url': url,
            'disposition': 'PRESERVE_RAW_DO_NOT_ZERO_FILL',
        })
    if n % 50 == 0:
        write_state('DETAIL_CAPTURE', {'last_detail_index': n})
        print('detail', n, '/', len(detail_seen), 'anomalies', len(anomalies), flush=True)
    time.sleep(0.04)

assertions = {
    'segment_start_roc': START_ROC,
    'segment_end_roc': END_ROC,
    'initial_query_matrix_count': (END_ROC - START_ROC + 1) * 2 * 2,
    'list_request_count': sum(1 for x in manifest if x['stage'] == 'LIST'),
    'unique_detail_key_count': len(detail_seen),
    'detail_capture_count': sum(1 for x in manifest if x['stage'] == 'DETAIL'),
    'detail_provider_marker_count': sum(1 for x in manifest if x['stage'] == 'DETAIL' and x['has_company_provider_marker']),
    'source_empty_or_nonstandard_detail_count': len(anomalies),
    'retry_event_count': len(retry_events),
    'generic_or_security_shell_count': sum(1 for x in manifest if x.get('security_or_generic_shell')),
    'all_http_200': all(x['http_status'] == 200 for x in manifest),
    'all_payload_nonempty': all(x['payload_bytes'] > 0 for x in manifest),
    'all_gzip_roundtrip_match': all(x['gzip_roundtrip_match'] for x in manifest),
    'detail_count_matches_unique_keys': sum(1 for x in manifest if x['stage'] == 'DETAIL') == len(detail_seen),
}
if not all([
    assertions['all_http_200'], assertions['all_payload_nonempty'], assertions['all_gzip_roundtrip_match'],
    assertions['detail_count_matches_unique_keys'], assertions['generic_or_security_shell_count'] == 0,
]):
    raise SystemExit('segment formal raw assertions failed')

package = {
    'schema': 'raw_w08_mops_t51_t05_formal_raw_segment_v5',
    'work_unit_id': 'W08-RAW-MOPS-HIST-GET',
    'source_family': 'MOPS_CA_MAJOR_EVENT_T51_T05_REPLAY_V1',
    'classification': 'FORMAL_RAW_SEGMENT_CANDIDATE_PENDING_DRIVE_READBACK',
    'qualification_basis': 'Source Contract v1.9 + exact Google Sheets IMPORTXML request URLs',
    'retrieval_scope': {
        'roc_year_start': START_ROC, 'roc_year_end': END_ROC,
        'KIND': ['L', 'O'], 'keywords': ['減資', '合併'], 'PCount': 100,
        'pagination': 'all pagenum values exposed by official response',
    },
    'captures': manifest,
    'anomalies': anomalies,
    'retry_events': retry_events,
    'assertions': assertions,
}
(ROOT / 'MANIFEST.json').write_text(json.dumps(package, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')
(ROOT / 'ANOMALY.json').write_text(json.dumps({'schema': 'raw_w08_mops_t51_t05_anomaly_v2', 'anomalies': anomalies}, ensure_ascii=False, indent=2, sort_keys=True) + '\n', encoding='utf-8')
write_state('COMPLETE', {'assertions': assertions})
print(json.dumps(assertions, ensure_ascii=False, indent=2))
