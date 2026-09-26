"""Carry verified immutable caches into a publisher-only implementation revision."""

import argparse
from pathlib import Path
import os

from taxonomy_ngd import core
from taxonomy_ngd.run import code_identity


def reuse(previous):
    definition = core.read_json(previous / 'definition.json.gz')
    current = code_identity()
    changed = {name for name in set(current) | set(definition['code']) if current.get(name) != definition['code'].get(name)}
    if changed != {'taxonomy_ngd/publish.py'}:
        raise ValueError('Only a publication-stage revision can reuse this projection/benchmark')
    if core.digest(core.ROOT / 'manifest.json') != definition['input']['manifest_sha256']:
        raise ValueError('Source manifest changed')
    updated_identity = core.identity({'input': definition['input'], 'code': current, 'version': definition['version']})
    destination = core.ARTIFACTS / updated_identity
    if destination.exists():
        raise ValueError('New run already exists; inspect rather than overwrite')
    destination.mkdir()
    updated = {**definition, 'identity': updated_identity, 'code': current}
    core.save_json(destination / 'definition.json.gz', updated)
    os.link(previous / 'lookups.json.gz', destination / 'lookups.json.gz')
    sources = [entry for entry in definition['input']['inventory'] if entry['entity'] == 'works']
    for index, source in enumerate(sources):
        if core.source_identity(Path(source['path'])) != source['identity']:
            raise ValueError('Source identity changed')
        old_part = previous / 'staging' / f'part-{index:06d}'
        saved = core.read_json(old_part / 'complete.json.gz')
        if saved['definition_hash'] != core.identity(definition) or saved['source'] != source:
            raise ValueError('Original checkpoint provenance mismatch')
        new_part = destination / 'staging' / old_part.name
        new_part.mkdir(parents=True)
        for name, metadata in saved['outputs'].items():
            if core.inspect_file(old_part / name) != metadata:
                raise ValueError('Original artifact failed integrity check')
            os.link(old_part / name, new_part / name)
        core.save_json(new_part / 'complete.json.gz', {**saved, 'definition_hash': core.identity(updated),
                      'cache_reused_from': str(old_part), 'original_checkpoint_sha256': core.digest(old_part / 'complete.json.gz')})
    report_path = previous / 'benchmark/report.json.gz'
    benchmark = core.read_json(report_path)
    if not benchmark['complete'] or benchmark['definition_hash'] != core.identity(definition):
        raise ValueError('Original benchmark identity mismatch')
    core.save_json(destination / 'benchmark/report.json.gz', {**benchmark, 'definition_hash': core.identity(updated),
        'reused_benchmark': {'path': str(report_path), 'sha256': core.digest(report_path),
                             'original_definition_hash': core.identity(definition),
                             'reason': 'projection and counting source unchanged; only bounded final validation changed'}})
    core.save_json(destination / 'reuse_provenance.json.gz', {'previous_run': str(previous), 'changed_sources': sorted(changed),
        'previous_definition_sha256': core.digest(previous / 'definition.json.gz'), 'new_definition_sha256': core.digest(destination / 'definition.json.gz'),
        'verified_parts': len(sources), 'reuse_tool_sha256': core.digest(__file__),
        'publication_change': 'exact per-part SQL recount and integer reduction replaces unbounded all-file correlated join'})
    return destination


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('previous', type=Path)
    args = parser.parse_args()
    print(reuse(args.previous.resolve()))
