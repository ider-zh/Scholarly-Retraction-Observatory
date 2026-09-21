import collections
import csv
import datetime
import json
from pathlib import Path
import duckdb

OUT=Path('/tmp/retraction-dark-20260921')
OUT.mkdir(exist_ok=True)
root=Path('/home/ider/workspace/Scholarly-Retraction-Observatory')
manifest=json.loads((root/'public/data/snapshot/manifest.json').read_text())
source=Path('/mnt/hg02/openalex-snapshot/analysis/broad-runs')/manifest['scan_config_sha256']
raw=Path('/mnt/hg02/openalex-snapshot/data/parquet')
connection=duckdb.connect(config={'threads':32,'memory_limit':'128GB'})
connection.read_parquet(str(source/'shards/*/cohorts.parquet')).create_view('cohorts')
counts=connection.execute('SELECT is_xpac,sum(work_count),sum(CASE WHEN is_retracted THEN work_count ELSE 0 END) FROM cohorts GROUP BY is_xpac ORDER BY is_xpac').fetchall()
vocab={}
for name in ['concepts','domains','fields','subfields','topics']:
    vocab[name]=connection.execute('SELECT count(*) FROM read_parquet(?)',[str(raw/name/'**/*.parquet')]).fetchone()[0]
vocab['concept_levels']=connection.execute('SELECT level,count(*) FROM read_parquet(?) GROUP BY level ORDER BY level',[str(raw/'concepts/**/*.parquet')]).fetchall()
with open('/mnt/hg02/openalex-snapshot/analysis/rw/retraction_watch.csv') as handle:
    rows=list(csv.DictReader(handle))
rw_counts=collections.Counter(row['RetractionNature'] for row in rows)
papers=json.loads((source/'rw_original.json').read_text())
matches=json.loads((source/'rw_oa_match.json').read_text())
dates=collections.defaultdict(set)
for paper in papers:
    identifier=matches[paper['id']]['selected_id']
    if identifier:
        try:dates[identifier].add(datetime.date.fromisoformat(paper['retracted']))
        except (ValueError,TypeError):pass
earliest={identifier:min(values) for identifier,values in dates.items()}
concept_directory=json.loads((source/'concepts-complete.json').read_text())['directory']
connection.read_parquet(str(Path(concept_directory)/'*.parquet')).create_view('concept_records')
connection.read_parquet(str(source/'shards/*/identifiers.parquet')).create_view('identities')
missing_candidates=connection.execute("""SELECT id,concepts FROM concept_records
    WHERE len(list_filter(concepts, entry -> entry.level=0))=0 OR concepts IS NULL""").fetchall()
identifiers=[identifier for identifier,concepts in missing_candidates if identifier in earliest and 2000<=earliest[identifier].year<=2025]
eligible=connection.execute("""SELECT * FROM identities WHERE id IN (SELECT unnest(?)) AND is_xpac IS FALSE
    AND document_role IN ('original_supported','unresolved') AND publication_year BETWEEN 1 AND 2026
    AND (publication_date IS NULL OR publication_date<=DATE '2026-06-26')""",[identifiers]).fetchall()
columns=[item[0] for item in connection.description]
missing=[]
for values in eligible:
    record=dict(zip(columns,values));identifier=record['id']
    record['concepts']=next(concepts for candidate,concepts in missing_candidates if candidate==identifier)
    record['rw_records']=[paper for paper in papers if matches[paper['id']]['selected_id']==identifier]
    record['event_date']=earliest[identifier]
    connection.read_parquet(str(source/'shards/*/targets.parquet')).create_view('targets')
    record['primary_topic']=connection.execute('SELECT primary_topic FROM targets WHERE id=?',[identifier]).fetchone()[0]
    missing.append(record)
assert len(missing)==1
result={'oa_snapshot':manifest['oa_snapshot_date'],'corpus_counts':[{'expansion':row[0],'works':row[1],'flagged':row[2]} for row in counts],
    'vocabulary':vocab,'rw_csv_rows':len(rows),'rw_natures':rw_counts,'rw_deduplicated_originals':len(papers),'missing_l0':missing}
(OUT/'audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2,default=str))
print(json.dumps(result,ensure_ascii=False,default=str))
