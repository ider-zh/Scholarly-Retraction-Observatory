"""Read every final artifact and independently verify matrix mathematics and projections."""

import argparse
from datetime import datetime, timezone
import math
from pathlib import Path

import pyarrow.parquet as pq

from taxonomy_ngd import core


def verify(final):
    completion = core.read_json(final / 'completion.json.gz')
    if not completion['complete']:
        raise ValueError('Incomplete publication')
    files = 0
    compressed_bytes = 0
    membership_rows = 0
    for relative, expected in completion['outputs'].items():
        path = final / relative
        if not path.resolve().is_relative_to(final.resolve()):
            raise ValueError('Escaping artifact path')
        actual = core.inspect_file(path) if path.suffix == '.parquet' else {'sha256': core.digest(path), 'bytes': path.stat().st_size}
        if actual != expected:
            raise ValueError('Artifact integrity mismatch: ' + relative)
        files += 1
        compressed_bytes += expected['bytes']
        if relative.startswith('membership/'):
            membership_rows += expected['rows']
    if membership_rows != completion['N']:
        raise ValueError('Membership coverage mismatch')
    nodes = pq.read_table(final / 'taxonomy_nodes.parquet').to_pylist()
    summary = {}
    for taxonomy in ('concepts', 'topics'):
        matrix = pq.read_table(final / f'{taxonomy}_l0_l1_ngd.parquet').to_pylist()
        left = {node['id']: node for node in nodes if node['taxonomy'] == taxonomy and node['level'] == 0}
        right = {node['id']: node for node in nodes if node['taxonomy'] == taxonomy and node['level'] == 1}
        lookup = {(row['l1_id'], row['l0_id']): row for row in matrix}
        if len(lookup) != len(matrix) or set(lookup) != {(right_id, left_id) for right_id in right for left_id in left}:
            raise ValueError('Incomplete Cartesian matrix')
        for row in matrix:
            total, first, second, joint = row['N'], row['f_l0'], row['f_l1'], row['f_joint']
            if total != completion['N'] or first != left[row['l0_id']]['frequency'] or second != right[row['l1_id']]['frequency']:
                raise ValueError('Marginal identity mismatch')
            if not max(0, first + second - total) <= joint <= min(first, second) <= total:
                raise ValueError('Impossible counts')
            expected = None
            if min(first, second) == 0:
                status = 'zero_marginal'
            elif joint == 0:
                status = 'zero_cooccurrence'
            elif first == second == total:
                status = 'zero_denominator'
            else:
                expected = (max(math.log(first), math.log(second)) - math.log(joint)) / (math.log(total) - min(math.log(first), math.log(second)))
                status = 'defined' if row['ngd'] >= 0 else 'numerical_warning'
            if row['ngd_status'] != status or row['zero_cooccurrence'] != (joint == 0):
                raise ValueError('NGD status mismatch')
            if expected is None:
                if row['ngd'] is not None:
                    raise ValueError('Undefined NGD not NULL')
            elif not math.isclose(row['ngd'], expected, rel_tol=1e-12, abs_tol=1e-12):
                raise ValueError('Independent NGD formula mismatch')
            for column, denominator in [('joint_over_l0', first), ('joint_over_l1', second), ('jaccard', first + second - joint)]:
                ratio = joint / denominator if denominator else None
                if row[column] != ratio:
                    raise ValueError('Derived ratio mismatch')
            if row['is_parent_pair'] != (row['l0_id'] in right[row['l1_id']]['parent_l0_ids']):
                raise ValueError('Parent relation mismatch')
            if taxonomy == 'topics' and row['is_parent_pair'] and joint != second:
                raise ValueError('Topic containment mismatch')
        for right_id in right:
            group = [row for row in matrix if row['l1_id'] == right_id]
            for column, exclude in [('ngd_rank_for_l1', False), ('ngd_rank_excluding_parent', True)]:
                eligible = [row for row in group if row['ngd'] is not None and not (exclude and row['is_parent_pair'])]
                values = sorted({row['ngd'] for row in eligible})
                for row in group:
                    expected_rank = values.index(row['ngd']) + 1 if row in eligible else None
                    if row[column] != expected_rank:
                        raise ValueError('Dense rank mismatch')
        ranked = pq.read_table(final / f'{taxonomy}_l1_l0_ranking.parquet').to_pylist()
        if {(row['l1_id'], row['l0_id']): row for row in ranked} != lookup or len(ranked) != len(matrix):
            raise ValueError('Ranking projection mismatch')
        selected = pq.read_table(final / f'{taxonomy}_l1_math_distance.parquet').to_pylist()
        if len(selected) != len(right) or len({row['l1_id'] for row in selected}) != len(right):
            raise ValueError('Mathematics coverage mismatch')
        rename = {'math_l0_id': 'l0_id', 'math_l0_name': 'l0_name', 'f_math': 'f_l0', 'ngd_to_math': 'ngd'}
        for row in selected:
            restored = {rename.get(key, key): value for key, value in row.items()}
            if restored != lookup[(row['l1_id'], row['math_l0_id'])] or row['math_l0_name'] != 'Mathematics':
                raise ValueError('Mathematics projection mismatch')
        summary[taxonomy] = {'l0': len(left), 'l1': len(right), 'pairs': len(matrix), 'math_rows': len(selected)}
    return {'accepted': True, 'checked_files': files, 'compressed_bytes': compressed_bytes,
            'N': membership_rows, 'matrices': summary, 'completion_sha256': core.digest(final / 'completion.json.gz'),
            'verifier_sha256': core.digest(__file__), 'verified_at': datetime.now(timezone.utc).isoformat()}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('final', type=Path)
    args = parser.parse_args()
    result = verify(args.final)
    core.save_json(args.final.parent / 'independent_acceptance.json.gz', result)
    print(result)
