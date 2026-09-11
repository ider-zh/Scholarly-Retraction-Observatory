"""Extract a frozen two-level graph from official V3 classifier artifacts."""

import argparse
import json
from pathlib import Path
import pickle

import pyarrow.parquet as pq

from .validate_snapshot import atomic_json, digest, now


class PrimitiveUnpickler(pickle.Unpickler):
    def find_class(self, module, name):
        raise ValueError('Executable pickle globals are prohibited')

    def persistent_load(self, identifier):
        raise ValueError('External pickle references are prohibited')


def build(release_dir, artifacts, output):
    release_dir, artifacts = Path(release_dir), Path(artifacts)
    provenance = json.loads((release_dir/'provenance.json').read_text())
    validation_path = Path(provenance['validation_report'])
    validation = json.loads(validation_path.read_text())
    levels = {}
    for entry in json.loads((validation_path.parent/'files.json').read_text()):
        if entry['entity'] == 'concepts':
            for row in pq.ParquetFile(Path(validation['snapshot_dir'])/entry['key']).read(columns=['id', 'level']).to_pylist():
                if row['level'] in (0, 1):
                    levels[row['id']] = row['level']
    values, sources = {}, []
    for name in ('ancestor_chains.pkl', 'tag_id_vocab.pkl'):
        source = artifacts/name
        with source.open('rb') as stream:
            values[name] = PrimitiveUnpickler(stream).load()
        sources.append({'url': 'https://openalex-concept-tagger-model-files.s3.amazonaws.com/V3/'+name,
                        'sha256': digest(source.read_bytes()), 'bytes': source.stat().st_size})
    vocabulary = values['tag_id_vocab.pkl']
    if not all(isinstance(key, int) and isinstance(value, int) for key, value in vocabulary.items()):
        raise ValueError('Unexpected concept vocabulary')
    parents = {}
    for predicted_id, entry in values['ancestor_chains.pkl'].items():
        identifier = 'https://openalex.org/C'+str(vocabulary[predicted_id])
        if levels.get(identifier) != 1:
            continue
        ancestors = {'https://openalex.org/C'+str(vocabulary[parent]) for chain in entry['anc_ids'] for parent in chain}
        parents[identifier] = sorted(parent for parent in ancestors if levels.get(parent) == 0)
    for identifier, level in levels.items():
        if level == 1:
            parents.setdefault(identifier, [])
    reference = {'version': 'official-concept-tagger-v3-2023-11-06', 'retrieved_at': now(),
        'documentation': 'https://github.com/ourresearch/openalex-concept-tagging/blob/49fd88916c80d75e7e889533b0458fa8a58bd730/V3/README.md',
        'source_snapshot_manifest_sha256': validation['manifest_sha256'], 'sources': sources, 'parents': parents,
        'policy': 'Historical official ancestor chains for navigation only; snapshot ancestors are null. No retagging, inferred co-occurrence parents, or sum-of-children rollups.',
        'missing_parent_concepts': sorted(identifier for identifier, values in parents.items() if not values)}
    atomic_json(Path(output), reference)
    print(f'Concept graph: {len(parents)} level-1 nodes; {sum(len(values) for values in parents.values())} links; {len(reference["missing_parent_concepts"])} missing parents')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('release_dir', type=Path)
    parser.add_argument('artifacts', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    build(args.release_dir, args.artifacts, args.output)
