"""Full-coverage audit and immutable publication of exact taxonomy matrices."""

from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
import os
import multiprocessing
from pathlib import Path
import shutil
import subprocess

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq

from taxonomy_ngd import core
from taxonomy_ngd.engine import count_sql, literal


MATRIX_SCHEMA = pa.schema([
    *[(name, pa.string()) for name in ('taxonomy', 'snapshot_version', 'run_identity', 'l0_id', 'l0_name', 'l1_id', 'l1_name')],
    ('parent_l0_ids', pa.list_(pa.string())), ('parent_l0_names', pa.list_(pa.string())),
    ('parent_relationship_source', pa.string()), ('is_parent_pair', pa.bool_()),
    *[(name, pa.int64()) for name in ('N', 'f_l0', 'f_l1', 'f_joint')],
    ('ngd', pa.float64()), ('ngd_status', pa.string()), ('zero_cooccurrence', pa.bool_()),
    ('quality_flags', pa.list_(pa.string())),
    *[(name, pa.float64()) for name in ('joint_over_l1', 'joint_over_l0', 'jaccard')],
    ('ngd_rank_for_l1', pa.int64()), ('ngd_rank_excluding_parent', pa.int64())])


def count_key(row):
    return row['taxonomy'], row['kind'], row['l0_id'], row['l1_id']


def recount_partition(path):
    connection = duckdb.connect(config={'threads': '1', 'memory_limit': '6GiB'})
    connection.execute("SET temp_directory = ''")
    try:
        connection.execute(f'CREATE VIEW membership AS SELECT * FROM read_parquet({literal(path)})')
        return {count_key(row): row['count'] for row in count_sql(connection)}
    finally:
        connection.close()


def make_matrix(nodes, counts, total, taxonomy, snapshot, run_identity):
    selected = [node for node in nodes if node['taxonomy'] == taxonomy]
    left_nodes = [node for node in selected if node['level'] == 0]
    right_nodes = [node for node in selected if node['level'] == 1]
    names = {node['id']: node['name'] for node in selected}
    rows = []
    for right in right_nodes:
        for left in left_nodes:
            left_count = counts[(taxonomy, 'l0', left['id'], None)]
            right_count = counts[(taxonomy, 'l1', None, right['id'])]
            joint = counts[(taxonomy, 'joint', left['id'], right['id'])]
            row = {'taxonomy': taxonomy, 'snapshot_version': snapshot, 'run_identity': run_identity,
                   'l0_id': left['id'], 'l0_name': left['name'], 'l1_id': right['id'], 'l1_name': right['name'],
                   'parent_l0_ids': right['parent_l0_ids'], 'parent_l0_names': [names[parent] for parent in right['parent_l0_ids']],
                   'parent_relationship_source': right['parent_relationship_source'],
                   'is_parent_pair': left['id'] in right['parent_l0_ids'], 'N': total,
                   'f_l0': left_count, 'f_l1': right_count, 'f_joint': joint,
                   **core.metrics(total, left_count, right_count, joint)}
            if row['is_parent_pair'] and joint != right_count:
                if taxonomy == 'topics':
                    raise ValueError('Topic parent containment failed')
                row['quality_flags'].append('historical_parent_containment_warning')
            rows.append(row)
    return core.rank_rows(rows)


def publish(run, definition, parts):
    destination = run / 'final'
    if destination.exists():
        complete = core.read_json(destination / 'completion.json.gz')
        if complete['run_identity'] != definition['identity']:
            raise ValueError('Final identity mismatch')
        for name, meta in complete['outputs'].items():
            if core.digest(destination / name) != meta['sha256']:
                raise ValueError('Final checksum mismatch')
        return complete
    total = sum(part['rows'] for part in parts)
    expected = sum(entry['rows'] for entry in definition['input']['inventory'] if entry['entity'] == 'works')
    if total != expected or total == 0:
        raise ValueError('Incomplete or empty universe')
    blockers = Counter()
    audits = Counter()
    coverage = {taxonomy: Counter() for taxonomy in ('concepts', 'topics')}
    counts = Counter()
    for index, part in enumerate(parts):
        for audit in part['audit']:
            audits[audit['kind']] += audit['rows']
            if audit['blocking']:
                blockers[audit['kind']] += audit['rows']
        for taxonomy in coverage:
            coverage[taxonomy].update(part['coverage'][taxonomy])
        for name, metadata in part['outputs'].items():
            if core.inspect_file(run / 'staging' / f'part-{index:06d}' / name) != metadata:
                raise ValueError('Committed output changed')
        for row in pq.read_table(run / 'staging' / f'part-{index:06d}' / 'counts.parquet').to_pylist():
            counts[count_key(row)] += row['count']
    core.save_json(run / 'scan_quality.json.gz', {'N': total, 'coverage': coverage, 'audits': audits, 'blocking': blockers})
    if blockers:
        raise ValueError(f'Structural anomalies block publication: {dict(blockers)}')
    connection = duckdb.connect(config={'threads': '32', 'memory_limit': '256GiB'})
    connection.execute("SET temp_directory = ''")
    try:
        connection.execute(f"CREATE VIEW membership AS SELECT * FROM read_parquet({literal(run / 'staging/part-*/membership.parquet')})")
        measured_total, distinct_total, null_numeric = connection.execute('SELECT count(*), count(DISTINCT work_id), count(*) FILTER (WHERE work_id_numeric IS NULL) FROM membership').fetchone()
        if measured_total != total or distinct_total != total or null_numeric:
            raise ValueError('Global Work identity conflict')
        malformed_lists = ' OR '.join(f'len({column}) != len(list_distinct({column})) OR {column} != list_sort({column}) OR {column} IS NULL' for column in core.GROUPS)
        if connection.execute(f'SELECT count(*) FROM membership WHERE {malformed_lists}').fetchone()[0]:
            raise ValueError('Invalid canonical membership')
    finally:
        connection.close()
    independent = Counter()
    paths = [str(run / 'staging' / f'part-{index:06d}' / 'membership.parquet') for index in range(len(parts))]
    if len(paths) < 32:
        for path in paths:
            independent.update(recount_partition(path))
    else:
        with ProcessPoolExecutor(max_workers=32, mp_context=multiprocessing.get_context('spawn')) as pool:
            for index, values in enumerate(pool.map(recount_partition, paths, chunksize=1)):
                independent.update(values)
                if (index + 1) % 100 == 0:
                    print(f'independent recount {index + 1}/{len(paths)} shards', flush=True)
    if independent != counts:
        raise ValueError('Full membership recount differs from shard aggregation')
    for source in definition['input']['inventory']:
        if core.source_identity(Path(source['path'])) != source['identity']:
            raise ValueError('Input identity changed before publication')
    temporary = run / 'final.tmp'
    if temporary.exists():
        shutil.rmtree(temporary)
    temporary.mkdir()
    matrices = {}
    nodes = definition['input']['nodes']
    for taxonomy in ('concepts', 'topics'):
        rows = make_matrix(nodes, counts, total, taxonomy, definition['input']['snapshot_date'], definition['identity'])
        matrices[taxonomy] = rows
        core.parquet(temporary / f'{taxonomy}_l0_l1_ngd.parquet', rows, MATRIX_SCHEMA)
        ranked = sorted(rows, key=lambda row: (row['l1_id'], row['ngd'] is None, row['ngd'] or 0, row['l0_id']))
        core.parquet(temporary / f'{taxonomy}_l1_l0_ranking.parquet', ranked, MATRIX_SCHEMA)
        math_rows = [row for row in rows if row['l0_name'] == 'Mathematics']
        math_table = pa.Table.from_pylist(math_rows, schema=MATRIX_SCHEMA)
        rename = {'l0_id': 'math_l0_id', 'l0_name': 'math_l0_name', 'f_l0': 'f_math', 'ngd': 'ngd_to_math'}
        core.parquet(temporary / f'{taxonomy}_l1_math_distance.parquet', math_table.rename_columns([rename.get(name, name) for name in math_table.column_names]))
    node_rows = [{**node, 'frequency': counts[(node['taxonomy'], 'l0' if node['level'] == 0 else 'l1',
                  node['id'] if node['level'] == 0 else None, node['id'] if node['level'] == 1 else None)]} for node in nodes]
    core.parquet(temporary / 'taxonomy_nodes.parquet', node_rows)
    names = {node['id']: node['name'] for node in nodes}
    core.parquet(temporary / 'taxonomy_parent_edges.parquet', [{**edge, 'l0_name': names[edge['l0_id']], 'l1_name': names[edge['l1_id']]} for edge in definition['input']['edges']])
    for category in ('membership', 'counts', 'audit'):
        (temporary / category).mkdir()
        for index in range(len(parts)):
            os.link(run / 'staging' / f'part-{index:06d}' / (category + '.parquet'), temporary / category / f'part-{index:06d}.parquet')
    metadata = {'version': core.VERSION, 'run_identity': definition['identity'], 'definition': definition,
                'N': total, 'universe': 'all-core-and-xpac-including-unlabelled', 'compression': 'zstd-level-3',
                'formula': 'ln(max(f_l0,f_l1)/f_joint)/ln(N/min(f_l0,f_l1))', 'negative_tolerance': 1e-12,
                'mathematics_ids': {taxonomy: next(row['l0_id'] for row in matrices[taxonomy] if row['l0_name'] == 'Mathematics') for taxonomy in matrices},
                'generated_at': datetime.now(timezone.utc).isoformat(),
                'git_head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
                'git_dirty': subprocess.check_output(['git', 'status', '--short'], text=True),
                'dependencies': {'duckdb': duckdb.__version__, 'pyarrow': pa.__version__}}
    quality = {'N': total, 'unique_work_ids': distinct_total, 'coverage': coverage, 'audits': audits,
               'full_membership_independent_recount': 'passed', 'input_identity_recheck': 'passed',
               'matrices': {taxonomy: {'pairs': len(rows), 'statuses': dict(Counter(row['ngd_status'] for row in rows)),
                                      'historical_containment_warning_pairs': sum('historical_parent_containment_warning' in row['quality_flags'] for row in rows)} for taxonomy, rows in matrices.items()}}
    core.save_json(temporary / 'ngd_metadata.json.gz', metadata)
    core.save_json(temporary / 'quality_report.json.gz', quality)
    outputs = {}
    for path in sorted(temporary.rglob('*')):
        if path.is_file():
            outputs[str(path.relative_to(temporary))] = core.inspect_file(path) if path.suffix == '.parquet' else {'sha256': core.digest(path), 'bytes': path.stat().st_size}
    completion = {'complete': True, 'run_identity': definition['identity'], 'N': total, 'outputs': outputs,
                  'quality_sha256': core.digest(temporary / 'quality_report.json.gz'),
                  'benchmark_sha256': core.digest(run / 'benchmark/report.json.gz'), 'generated_at': datetime.now(timezone.utc).isoformat()}
    core.save_json(temporary / 'completion.json.gz', completion)
    os.rename(temporary, destination)
    descriptor = os.open(run, os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    core.save_json(run / 'progress.json.gz', {'status': 'complete', 'parts': len(parts), 'rows': total, 'final': str(destination)})
    return completion
