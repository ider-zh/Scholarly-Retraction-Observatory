"""Independent set construction from raw snapshot samples, not projected SQL."""

import argparse
from collections import Counter
from pathlib import Path

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq

from taxonomy_ngd import core
from taxonomy_ngd.engine import count_sql, literal
from taxonomy_ngd.publish import count_key


def verify(run):
    definition = core.read_json(run / 'definition.json.gz')
    lookups = {'concepts': {}, 'topics': {}}
    for source in definition['input']['inventory']:
        if source['entity'] not in lookups:
            continue
        columns = ['id', 'level'] if source['entity'] == 'concepts' else ['id', 'subfield', 'field', 'domain']
        if core.digest(source['path']) != source['sha256']:
            raise ValueError('Raw taxonomy checksum differs')
        for row in pq.ParquetFile(source['path']).read(columns=columns).to_pylist():
            lookups[source['entity']][row['id']] = row
    if lookups != core.read_json(run / 'lookups.json.gz'):
        raise ValueError('Cached taxonomy lookup differs from raw entity tables')
    sources = [entry for entry in definition['input']['inventory'] if entry['entity'] == 'works']
    indices = sorted({0, len(sources)//4, len(sources)//2, 3*len(sources)//4, len(sources)-1})
    checked = []
    for index in indices:
        source = sources[index]
        if core.source_identity(Path(source['path'])) != source['identity']:
            raise ValueError('Source changed')
        batch = next(pq.ParquetFile(source['path']).iter_batches(batch_size=2048, columns=core.COLUMNS), None)
        if batch is None:
            continue
        rows = batch.to_pylist()
        connection = duckdb.connect(config={'threads': '1', 'memory_limit': '3GiB'})
        connection.execute("SET temp_directory = ''")
        try:
            connection.register('wanted', pa.table({'work_id': [row['id'] for row in rows]}))
            path = run / 'final/membership' / f'part-{index:06d}.parquet'
            connection.execute(f'CREATE TABLE membership AS SELECT cached.* FROM read_parquet({literal(path)}) cached JOIN wanted USING (work_id)')
            cached = {row['work_id']: row for row in connection.execute('SELECT * FROM membership').fetch_arrow_table().to_pylist()}
            if len(cached) != len(rows):
                raise ValueError('Sample identity coverage differs')
            oracle = Counter()
            for row in rows:
                groups = [set(), set(), set(), set()]
                for label in row['concepts'] or []:
                    level = lookups['concepts'][label['id']]['level']
                    if level in (0, 1):
                        groups[level].add(label['id'])
                for label in row['topics'] or []:
                    topic = lookups['topics'][label['id']]
                    groups[2].add(topic['field']['id'])
                    groups[3].add(topic['subfield']['id'])
                actual = cached[row['id']]
                for column, labels in zip(core.GROUPS, groups):
                    if actual[column] != sorted(labels):
                        raise ValueError('Raw-source set oracle disagrees with membership')
                for raw, projected in [('publication_year', 'publication_year'), ('type', 'work_type'), ('is_retracted', 'is_retracted'), ('is_xpac', 'is_xpac')]:
                    if row[raw] != actual[projected]:
                        raise ValueError('Metadata preservation mismatch')
                for raw, projected in [('concepts', 'concept_source_list_state'), ('topics', 'topic_source_list_state')]:
                    expected = 'null' if row[raw] is None else ('empty' if not row[raw] else 'present')
                    if expected != actual[projected]:
                        raise ValueError('Source list state mismatch')
                for taxonomy, left, right in [('concepts', groups[0], groups[1]), ('topics', groups[2], groups[3])]:
                    for label in left:
                        oracle[(taxonomy, 'l0', label, None)] += 1
                    for label in right:
                        oracle[(taxonomy, 'l1', None, label)] += 1
                    for left_id in left:
                        for right_id in right:
                            oracle[(taxonomy, 'joint', left_id, right_id)] += 1
            measured = Counter({count_key(row): row['count'] for row in count_sql(connection)})
            if measured != oracle:
                raise ValueError('Selected sub-universe recount differs from raw source oracle')
            checked.append({'partition': index, 'works': len(rows), 'raw_source': source['path'],
                            'membership_sha256': core.digest(path)})
        finally:
            connection.close()
    return {'accepted': True, 'scope': 'deterministic samples, first up to 2048 Works in five spaced shards',
            'works': sum(item['works'] for item in checked), 'samples': checked,
            'taxonomy_lookups': 'all raw taxonomy rows compared', 'source_oracle_sha256': core.digest(__file__)}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run', type=Path)
    args = parser.parse_args()
    result = verify(args.run)
    core.save_json(args.run / 'source_oracle.json.gz', result)
    print(result)
