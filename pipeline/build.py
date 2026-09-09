"""Reproducible Retraction Watch cohort + optional OpenAlex enrichment. Python 3.11+."""
import argparse, collections, csv, datetime as dt, hashlib, io, json, os, pathlib, re, time
import urllib.request, urllib.error, urllib.parse
try:
    from .aggregate import aggregate
except ImportError:
    from aggregate import aggregate
ROOT = pathlib.Path(__file__).resolve().parents[1]
RW_URL = 'https://gitlab.com/crossref/retraction-watch-data/-/raw/main/retraction_watch.csv'

def atomic(path, data):
    path = pathlib.Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.tmp'); temp.write_text(json.dumps(data, ensure_ascii=False, separators=(',', ':'))); temp.replace(path)

def request(url, key=None):
    for attempt in range(5):
        try:
            headers = {'User-Agent': 'retraction-observatory/1.0 (research)'}
            if key: headers['Authorization'] = 'Bearer ' + key
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=60) as r: return r.read()
        except urllib.error.HTTPError as e:
            if e.code not in (429, 500, 502, 503, 504) or attempt == 4: raise RuntimeError(f'HTTP {e.code}; fetch failed, previous output preserved') from None
            time.sleep(min(30, 2 ** attempt * 2))
        except (urllib.error.URLError, TimeoutError):
            if attempt == 4: raise RuntimeError('Network request failed; previous output preserved') from None
            time.sleep(2 ** attempt)

def doi(value):
    value = urllib.parse.unquote(value or '').strip().lower()
    value = re.sub(r'^(?:https?://(?:dx\.)?doi\.org/|doi:\s*)', '', value)
    return value if re.match(r'^10\.\d{4,9}/\S+$', value) else None

def date(value):
    value = (value or '').strip().split(' ')[0]
    for fmt in ('%m/%d/%Y', '%Y-%m-%d'):
        try: return dt.datetime.strptime(value, fmt).date().isoformat()
        except ValueError: pass
    return None

def parts(value): return sorted(set(x.strip() for x in (value or '').split(';') if x.strip()))

def normalize(rows, as_of):
    papers = {}; quality = collections.Counter(); notices = []
    for r in rows:
        quality['source_rows'] += 1
        nature = r.get('RetractionNature', '').strip().lower()
        if nature != 'retraction':
            quality['excluded_' + (nature or 'unknown')] += 1; continue
        d = doi(r.get('OriginalPaperDOI')); pmid = (r.get('OriginalPaperPubMedID') or '').strip()
        key = 'doi:' + d if d else ('pmid:' + pmid if pmid.isdigit() and int(pmid) > 0 else 'rw:' + r['Record ID'])
        rd, pd = date(r.get('RetractionDate')), date(r.get('OriginalPaperDate'))
        if rd and rd > as_of: quality['future_retraction_rows'] += 1; continue
        notice = {'id': r['Record ID'], 'paper': key, 'date': rd, 'doi': doi(r.get('RetractionDOI'))}
        notices.append(notice)
        item = {'id': key, 'doi': d, 'title': r.get('Title') or '(untitled)', 'published': pd, 'retracted': rd,
                'subjects': parts(r.get('Subject')), 'institutions': parts(r.get('Institution')),
                'authors': parts(r.get('Author')), 'countries': parts(r.get('Country')), 'journal': r.get('Journal') or '未知',
                'publisher': r.get('Publisher') or '未知', 'reasons': parts(r.get('Reason')),
                'rw_ids': [r['Record ID']], 'oa': None}
        if key in papers:
            quality['duplicate_paper_rows'] += 1; old = papers[key]
            old['rw_ids'] = sorted(set(old['rw_ids'] + item['rw_ids']))
            for field in ('subjects', 'institutions', 'authors', 'countries', 'reasons'): old[field] = sorted(set(old[field] + item[field]))
            for field in ('retracted', 'published'):
                dates = [x for x in (old[field], item[field]) if x]
                if len(set(dates)) > 1: quality[field + '_conflicts'] += 1
                old[field] = min(dates) if dates else None
        else: papers[key] = item
    for p in papers.values():
        p['lag_days'] = (dt.date.fromisoformat(p['retracted']) - dt.date.fromisoformat(p['published'])).days if p['published'] and p['retracted'] else None
        if p['lag_days'] is not None and p['lag_days'] < 0: quality['negative_lag_papers'] += 1; p['lag_days'] = None
        quality['missing_doi_papers'] += int(not p['doi'])
        quality['missing_retraction_date_papers'] += int(not p['retracted'])
    return list(papers.values()), notices, dict(quality)

def enrich(papers, limit, corpus, cache_dir):
    # Deterministic DOI order: partial enrichment is NOT a representative sample.
    targets = sorted({p['doi'] for p in papers if p['doi']})
    if limit: targets = targets[:limit]
    hits = {}; queried = 0; cache_dir.mkdir(parents=True, exist_ok=True)
    for offset in range(0, len(targets), 50):
        batch = targets[offset:offset + 50]
        params = {'filter': 'doi:' + '|'.join(batch), 'corpus': corpus, 'per_page': 100,
                  'select': 'id,doi,display_name,publication_date,authorships,primary_topic,is_retracted,cited_by_count'}
        url = 'https://api.openalex.org/works?' + urllib.parse.urlencode(params)
        f = cache_dir / (hashlib.sha256(url.encode()).hexdigest() + '.json')
        if f.exists(): payload = json.loads(f.read_text())
        else: payload = json.loads(request(url, os.getenv('OPENALEX_API_KEY'))); atomic(f, payload); time.sleep(.15)
        for w in payload.get('results', []):
            d = doi(w.get('doi'))
            if not d: continue
            authors, institutions = {}, {}
            for a in w.get('authorships', []):
                person = a.get('author') or {}
                if person.get('id'): authors[person['id']] = person.get('display_name') or person['id']
                for i in a.get('institutions', []):
                    if i.get('id'): institutions[i['id']] = i.get('display_name') or i['id']
            topic = w.get('primary_topic') or {}; field = topic.get('field') or {}
            obj = {'id': w['id'], 'field': field.get('display_name'), 'field_id': field.get('id'),
                   'authors': authors, 'institutions': institutions, 'is_retracted': w.get('is_retracted'),
                   'citations': w.get('cited_by_count'), 'publication_date': w.get('publication_date')}
            # Stable ID selection; duplicate matches retained in audit count.
            if d in hits: obj['duplicate_doi_match'] = True
            if d not in hits or obj['id'] < hits[d]['id']: hits[d] = obj
        queried += len(batch)
        print(f'OpenAlex DOI lookup: {queried}/{len(targets)}, matched {len(hits)}', flush=True)
    for p in papers: p['oa'] = hits.get(p['doi'])
    return {'attempted_dois': queried, 'matched_papers': sum(bool(p['oa']) for p in papers), 'eligible_dois': len({p['doi'] for p in papers if p['doi']}), 'corpus': corpus, 'selection': 'all DOI' if not limit else 'lexicographic DOI prefix; not representative'}

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--download', action='store_true'); ap.add_argument('--enrich', action='store_true')
    ap.add_argument('--rw', type=pathlib.Path, default=ROOT / 'data/raw/retraction_watch.csv')
    ap.add_argument('--oa-limit', type=int, default=0, help='0 = all DOI; >0 partial, not random')
    ap.add_argument('--corpus', choices=['core','all'], default='all'); ap.add_argument('--as-of', default=dt.date.today().isoformat())
    args = ap.parse_args()
    if args.download:
        raw = request(RW_URL)
        if not raw.startswith(b'Record ID,'): raise RuntimeError('Unexpected RW CSV schema')
        args.rw.parent.mkdir(parents=True, exist_ok=True); tmp = args.rw.with_suffix('.tmp'); tmp.write_bytes(raw); tmp.replace(args.rw)
    raw = args.rw.read_bytes()
    rows = list(csv.DictReader(io.StringIO(raw.decode('utf-8-sig'))))
    if not rows or 'RetractionNature' not in rows[0]: raise RuntimeError('Required columns missing')
    papers, notices, quality = normalize(rows, args.as_of)
    enrichment = {'attempted_dois':0, 'matched_papers':0, 'corpus':args.corpus, 'selection':'not requested'}
    if args.enrich: enrichment = enrich(papers, args.oa_limit, args.corpus, ROOT / 'data/cache' / args.as_of / args.corpus)
    meta = {'schema_version':2, 'generated_at':dt.datetime.now(dt.timezone.utc).isoformat(), 'as_of':args.as_of,
            'cohort':'Retraction Watch: Retraction notices, unique original papers', 'source_url':RW_URL,
            'raw_sha256':hashlib.sha256(raw).hexdigest(), 'paper_count':len(papers), 'notice_count':len(notices),
            'quality':quality, 'openalex':enrichment, 'license':'Retraction Watch / Crossref: CC0; OpenAlex: CC0',
            'partial_year':int(args.as_of[:4])}
    # Full records and evidence remain local; only aggregates and a bounded sample are public.
    atomic(ROOT/'data/processed/papers.json', papers)
    atomic(ROOT/'data/processed/notices.json', notices)
    atomic(ROOT/'data/processed/quality.json', meta)
    audit_path = ROOT/'data/reference/openalex-audit.json'
    audit = json.loads(audit_path.read_text()) if audit_path.exists() else None
    report, samples = aggregate(papers, meta, audit)
    atomic(ROOT/'public/data/report.json', report)
    atomic(ROOT/'public/data/samples.json', samples)
    print(json.dumps(meta,ensure_ascii=False,indent=2))
if __name__ == '__main__': main()
