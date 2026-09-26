"""Frozen taxonomy input, exact NGD mathematics, and compressed artifact utilities."""

import gzip
import hashlib
import json
import math
import os
from pathlib import Path
import re

import pyarrow as pa
import pyarrow.parquet as pq

from disruption.src.cache_foundation import source_identity
from pipeline.concept_tree_reference import PrimitiveUnpickler


VERSION = 'taxonomy-ngd-v1'
ROOT = Path('/mnt/hg02/openalex-snapshot/data/parquet')
ARTIFACTS = Path('/mnt/hg02/openalex-snapshot/analysis/taxonomy-ngd')
COLUMNS = ['id', 'publication_year', 'type', 'is_retracted', 'is_xpac', 'concepts', 'topics']
GROUPS = ['concept_l0_ids', 'concept_l1_ids', 'topic_field_ids', 'topic_subfield_ids']


def digest(path):
    value = hashlib.sha256()
    with open(path, 'rb') as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            value.update(chunk)
    return value.hexdigest()


def identity(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def save_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.tmp')
    with temporary.open('wb') as stream:
        with gzip.GzipFile(fileobj=stream, mode='wb', mtime=0) as compressed:
            compressed.write(json.dumps(value, sort_keys=True, ensure_ascii=False).encode())
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)
    descriptor = os.open(path.parent, os.O_DIRECTORY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def read_json(path):
    with gzip.open(path, 'rt') as stream:
        return json.load(stream)


def parquet(path, rows, schema=None):
    table = rows if isinstance(rows, pa.Table) else pa.Table.from_pylist(rows, schema=schema)
    pq.write_table(table, path, compression='zstd', compression_level=3, row_group_size=65536)


def inspect_file(path):
    source = pq.ParquetFile(path)
    codecs = {source.metadata.row_group(group).column(column).compression
              for group in range(source.metadata.num_row_groups)
              for column in range(source.metadata.num_columns)}
    if codecs - {'ZSTD'}:
        raise ValueError(f'Non-ZSTD artifact: {path}')
    return {'sha256': digest(path), 'bytes': path.stat().st_size,
            'rows': source.metadata.num_rows, 'schema': str(source.schema_arrow), 'codecs': sorted(codecs)}


def prepare(root=ROOT):
    manifest_path = root / 'manifest.json'
    manifest = json.loads(manifest_path.read_text())
    inventory, entities = [], {}
    for entity in manifest['entities']:
        name = entity['entity']
        if name not in ('works', 'concepts', 'topics', 'subfields', 'fields', 'domains'):
            continue
        rows = []
        entity_total = 0
        listed_paths = set()
        for entry in entity['files']:
            relative = entry['url'].split('/data/parquet/', 1)[1]
            path = root / relative
            if relative in listed_paths:
                raise ValueError('Duplicate source path')
            listed_paths.add(relative)
            source = pq.ParquetFile(path)
            if path.stat().st_size != entry['meta']['content_length'] or source.metadata.num_rows != entry['meta']['record_count']:
                raise ValueError(f'Manifest mismatch: {path}')
            entity_total += source.metadata.num_rows
            record = {'entity': name, 'path': str(path), 'rows': source.metadata.num_rows,
                      'identity': source_identity(path), 'schema_sha256': identity(str(source.schema_arrow))}
            inventory.append(record)
            if name == 'works':
                if set(COLUMNS) - set(source.schema_arrow.names):
                    raise ValueError('Missing Work columns')
            else:
                record['sha256'] = digest(path)
                rows.extend(source.read().to_pylist())
        if entity_total != entity['record_count']:
            raise ValueError('Entity count differs from manifest')
        if name != 'works':
            lookup = {row['id']: row for row in rows}
            patterns = {'concepts': 'C', 'topics': 'T', 'subfields': 'subfields/', 'fields': 'fields/', 'domains': 'domains/'}
            if len(lookup) != len(rows) or any(not re.fullmatch('https://openalex[.]org/' + patterns[name] + '[1-9][0-9]*', identifier) for identifier in lookup):
                raise ValueError('Taxonomy identity conflict')
            entities[name] = lookup
    for name in ('fields', 'subfields', 'topics'):
        for row in entities[name].values():
            if row['domain']['id'] not in entities['domains']:
                raise ValueError('Unresolved domain')
            if name in ('subfields', 'topics'):
                field = entities['fields'][row['field']['id']]
                if field['domain']['id'] != row['domain']['id']:
                    raise ValueError('Field/domain conflict')
            if name == 'topics':
                subfield = entities['subfields'][row['subfield']['id']]
                if subfield['field']['id'] != row['field']['id'] or subfield['domain']['id'] != row['domain']['id']:
                    raise ValueError('Topic chain conflict')
    reference_path = Path('data/reference/openalex-concept-tree-v3.json')
    reference = json.loads(reference_path.read_text())
    if reference['source_snapshot_manifest_sha256'] != digest(manifest_path):
        raise ValueError('Historical relationship snapshot mismatch')
    objects = {}
    for source in reference['sources']:
        path = Path('/mnt/hg02/openalex-snapshot/analysis/reference/concept-v3') / source['url'].rsplit('/', 1)[1]
        if digest(path) != source['sha256'] or path.stat().st_size != source['bytes']:
            raise ValueError('Historical source object mismatch')
        with path.open('rb') as stream:
            objects[path.name] = PrimitiveUnpickler(stream).load()
    vocab = objects['tag_id_vocab.pkl']
    parents = {}
    for predicted, entry in objects['ancestor_chains.pkl'].items():
        identifier = 'https://openalex.org/C' + str(vocab[predicted])
        if entities['concepts'].get(identifier, {}).get('level') == 1:
            ancestors = {'https://openalex.org/C' + str(vocab[parent]) for chain in entry['anc_ids'] for parent in chain}
            parents[identifier] = sorted(parent for parent in ancestors if entities['concepts'].get(parent, {}).get('level') == 0)
    if parents != reference['parents'] or any(not values for values in parents.values()):
        raise ValueError('Historical relationship reproduction failed')
    nodes, edges = [], []
    for taxonomy, table, level in [('concepts', 'concepts', 0), ('concepts', 'concepts', 1), ('topics', 'fields', 0), ('topics', 'subfields', 1)]:
        for row in sorted(entities[table].values(), key=lambda value: value['id']):
            if taxonomy == 'concepts' and row['level'] != level:
                continue
            relation = reference['version'] if taxonomy == 'concepts' else 'snapshot-subfield-field'
            parent_ids = (parents[row['id']] if taxonomy == 'concepts' else [row['field']['id']]) if level == 1 else []
            nodes.append({'taxonomy': taxonomy, 'level': level, 'id': row['id'], 'name': row['display_name'],
                          'parent_l0_ids': parent_ids, 'parent_relationship_source': relation})
            edges.extend({'taxonomy': taxonomy, 'l1_id': row['id'], 'l0_id': parent, 'relationship_source': relation} for parent in parent_ids)
    for taxonomy in ('concepts', 'topics'):
        matches = [node['id'] for node in nodes if node['taxonomy'] == taxonomy and node['level'] == 0 and node['name'] == 'Mathematics']
        if len(matches) != 1 or (taxonomy == 'topics' and matches[0] != 'https://openalex.org/fields/26'):
            raise ValueError('Mathematics identity ambiguous')
    pointer_path = Path('/mnt/hg02/openalex-snapshot/analysis/validation/validated-source.json')
    pointer = json.loads(pointer_path.read_text())
    validation_path = Path(pointer['report'])
    validation = json.loads(validation_path.read_text())
    if pointer['manifest_sha256'] != digest(manifest_path) or validation['manifest_sha256'] != digest(manifest_path) or validation['status'] != 'validated':
        raise ValueError('Snapshot validation evidence mismatch')
    evidence = {str(path): digest(path) for path in validation_path.parent.glob('*.json')}
    evidence[str(pointer_path)] = digest(pointer_path)
    return {'snapshot_date': manifest['date'], 'manifest_sha256': digest(manifest_path), 'inventory': inventory,
            'nodes': nodes, 'edges': edges, 'reference': reference, 'reference_sha256': digest(reference_path),
            'validation_evidence': evidence, 'provenance_policy': 'accepted-retrospective-transfer-evidence-gap'}, entities


def metrics(total, left, right, joint):
    if any(type(value) is not int or not 0 <= value < 2**63 for value in (total, left, right, joint)) or total == 0:
        raise ValueError('Invalid integer counts')
    if max(left, right) > total or not max(0, left + right - total) <= joint <= min(left, right):
        raise ValueError('Impossible set counts')
    score = None
    status = 'defined'
    if min(left, right) == 0:
        status = 'zero_marginal'
    elif joint == 0:
        status = 'zero_cooccurrence'
    elif left == right == total:
        status = 'zero_denominator'
    else:
        score = math.log(max(left, right) / joint) / math.log(total / min(left, right))
        if not math.isfinite(score) or score < -1e-12:
            raise ValueError('Invalid NGD value')
        if score < 0:
            status = 'numerical_warning'
    return {'ngd': score, 'ngd_status': status, 'zero_cooccurrence': joint == 0,
            'quality_flags': ['numerical_warning'] if status == 'numerical_warning' else [],
            'joint_over_l0': joint / left if left else None, 'joint_over_l1': joint / right if right else None,
            'jaccard': joint / (left + right - joint) if left + right - joint else None}


def rank_rows(rows):
    for identifier in sorted({row['l1_id'] for row in rows}):
        group = [row for row in rows if row['l1_id'] == identifier]
        for exclude, column in [(False, 'ngd_rank_for_l1'), (True, 'ngd_rank_excluding_parent')]:
            scores = sorted({row['ngd'] for row in group if row['ngd'] is not None and not (exclude and row['is_parent_pair'])})
            ranks = {score: index + 1 for index, score in enumerate(scores)}
            for row in group:
                row[column] = None if row['ngd'] is None or (exclude and row['is_parent_pair']) else ranks[row['ngd']]
    return rows
