"""Manifest-scoped, local OpenAlex Parquet source validation (no publication)."""

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import resource
import tempfile
import time
import urllib.request

import duckdb
import pyarrow as pa
import pyarrow.parquet as pq


VERSION = 'snapshot-validation-v1'
PREFIX = 's3://openalex/data/parquet/'
MANIFEST_URL = 'https://openalex.s3.amazonaws.com/data/parquet/manifest.json'
CORE_FIELDS = {
    'id', 'doi', 'ids', 'publication_date', 'publication_year', 'type',
    'authorships', 'primary_topic', 'is_retracted', 'is_xpac',
}


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def atomic_bytes(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(dir=path.parent, prefix='.' + path.name)
    try:
        with os.fdopen(handle, 'wb') as output:
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def atomic_json(path, value):
    atomic_bytes(path, (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode())


def manifest_entries(manifest):
    if manifest.get('format') != 'parquet':
        raise ValueError('Expected a combined Parquet manifest')
    dt.date.fromisoformat(manifest['date'])
    seen = set()
    entities = set()
    totals = {'record_count': 0, 'content_length': 0}
    result = []
    for entity in manifest['entities']:
        name = entity['entity']
        if name in entities:
            raise ValueError('Duplicate manifest entity: ' + name)
        entities.add(name)
        subtotal = {'record_count': 0, 'content_length': 0}
        for entry in entity['files']:
            url = entry['url']
            if not url.startswith(PREFIX):
                raise ValueError('File outside intended source prefix: ' + url)
            key = url[len(PREFIX):]
            relative = PurePosixPath(key)
            if (relative.is_absolute() or '..' in relative.parts or
                    str(relative) != key or relative.parts[0] != name or
                    relative.suffix != '.parquet' or key in seen):
                raise ValueError('Unsafe or duplicate manifest key: ' + key)
            seen.add(key)
            for metric in subtotal:
                value = entry['meta'][metric]
                if type(value) is not int or value < 0:
                    raise ValueError('Invalid manifest size/count: ' + key)
                subtotal[metric] += value
            result.append({'entity': name, 'key': key, **entry['meta']})
        for metric in subtotal:
            if subtotal[metric] != entity[metric]:
                raise ValueError('Entity manifest total mismatch: ' + name + '/' + metric)
            totals[metric] += subtotal[metric]
    if not result or 'works' not in entities:
        raise ValueError('Manifest has no works population')
    if totals != manifest['meta']:
        raise ValueError('Combined manifest totals do not reconcile')
    return result


def inspect_file(root, entry):
    path = root / entry['key']
    result = dict(entry, errors=[])
    if not path.resolve().is_relative_to(root.resolve()):
        result['errors'].append('symlink_outside_snapshot')
        return result, None
    if not path.is_file():
        result['errors'].append('missing_file')
        return result, None
    stat = path.stat()
    result.update(actual_bytes=stat.st_size, mtime_ns=stat.st_mtime_ns)
    if stat.st_size != entry['content_length']:
        result['errors'].append('size_mismatch')
    try:
        parquet = pq.ParquetFile(path)
        result['actual_rows'] = parquet.metadata.num_rows
        if result['actual_rows'] != entry['record_count']:
            result['errors'].append('row_count_mismatch')
        schema = parquet.schema_arrow.remove_metadata()
        result['schema_sha256'] = digest(schema.serialize().to_pybytes())
        return result, schema
    except Exception as error:
        result['errors'].append('unreadable_parquet: ' + str(error))
        return result, None


def schema_paths(schema):
    result = {}

    def visit(path, kind):
        result[path] = str(kind)
        if pa.types.is_struct(kind):
            for field in kind:
                visit(path + '.' + field.name, field.type)
        elif pa.types.is_list(kind) or pa.types.is_large_list(kind):
            visit(path + '[]', kind.value_type)
        elif pa.types.is_map(kind):
            visit(path + '.key', kind.key_type)
            visit(path + '.value', kind.item_type)

    for field in schema:
        visit(field.name, field.type)
    return result


def core_schema_errors(schema):
    expected = {
        'id': pa.types.is_string, 'doi': pa.types.is_string,
        'ids': pa.types.is_map, 'publication_date': pa.types.is_date,
        'publication_year': pa.types.is_integer, 'type': pa.types.is_string,
        'authorships': pa.types.is_list, 'primary_topic': pa.types.is_struct,
        'is_retracted': pa.types.is_boolean, 'is_xpac': pa.types.is_boolean,
    }
    errors = [name for name, accepts in expected.items()
              if name not in schema.names or not accepts(schema.field(name).type)]
    paths = schema_paths(schema)
    for required in ('authorships[].author.id', 'authorships[].countries[]',
                     'authorships[].institutions[].id', 'authorships[].institutions[].country_code',
                     'primary_topic.id', 'primary_topic.field.id',
                     'primary_topic.subfield.id', 'primary_topic.domain.id'):
        if paths.get(required) != 'string':
            errors.append(required)
    return errors


def identity_audit(connection, paths, entity):
    connection.read_parquet(paths, hive_partitioning=False).create_view('source_records', replace=True)
    started = time.monotonic()
    record_count, unique_ids, missing_ids = connection.execute('''
        SELECT count(*), count(DISTINCT id) FILTER (WHERE id IS NOT NULL AND trim(id) <> ''),
               count(*) FILTER (WHERE id IS NULL OR trim(id) = '')
        FROM source_records
    ''').fetchone()
    duplicates = connection.execute('''
        SELECT id, count(*) AS records FROM source_records
        WHERE id IS NOT NULL AND trim(id) <> '' GROUP BY id HAVING count(*) > 1
        ORDER BY records DESC, id LIMIT 20
    ''').fetchall() if record_count != unique_ids + missing_ids else []
    result = {
        'records': record_count, 'unique_ids': unique_ids, 'missing_ids': missing_ids,
        'duplicate_excess': record_count - unique_ids - missing_ids,
        'duplicate_examples': [{'id': identifier, 'records': count} for identifier, count in duplicates],
    }
    print(f'{entity}: {record_count:,} records, {unique_ids:,} distinct nonempty IDs', flush=True)
    if entity == 'works':
        result['invalid_work_ids'] = connection.execute('''
            SELECT count(*) FROM source_records
            WHERE id IS NOT NULL AND NOT regexp_full_match(id, 'https://openalex[.]org/W[1-9][0-9]*')
        ''').fetchone()[0]
        result['flag_states'] = [
            {'is_retracted': retracted, 'is_xpac': xpac, 'records': count}
            for retracted, xpac, count in connection.execute('''
                SELECT is_retracted, is_xpac, count(*) FROM source_records
                GROUP BY ALL ORDER BY is_retracted NULLS LAST, is_xpac NULLS LAST
            ''').fetchall()
        ]
    result['elapsed_seconds'] = round(time.monotonic() - started, 3)
    return result


def transfer_gate(path, manifest_hash, validation_started):
    if path is None:
        return {'status': 'missing', 'reason': 'No pre-transfer manifest or retrieval timestamps supplied'}
    try:
        value = json.loads(Path(path).read_text())
        started = dt.datetime.fromisoformat(value['retrieval_started_at'])
        ended = dt.datetime.fromisoformat(value['retrieval_completed_at'])
        captured = dt.datetime.fromisoformat(value['manifest_captured_at'])
        if any(moment.tzinfo is None for moment in (started, ended, captured)):
            raise ValueError('Transfer timestamps require timezone offsets')
        if not captured <= started <= ended <= dt.datetime.fromisoformat(validation_started):
            raise ValueError('Invalid transfer timestamp order')
        frozen_path = Path(value['pre_transfer_manifest'])
        if not frozen_path.is_absolute():
            frozen_path = Path(path).resolve().parent / frozen_path
        if digest(frozen_path.read_bytes()) != manifest_hash or value['source_prefix'] != PREFIX:
            raise ValueError('Pre-transfer manifest/source differs from intended release')
        return {'status': 'passed', 'evidence': value, 'evidence_sha256': digest(Path(path).read_bytes())}
    except (KeyError, ValueError, OSError) as error:
        return {'status': 'failed', 'reason': str(error)}


def validate(root, output, *, scan_ids=False, check_remote=False, transfer=None,
             memory_limit='8GB', threads=4, accept_retrospective=False):
    root, output = Path(root).resolve(), Path(output).resolve()
    repository = Path(__file__).resolve().parents[1]
    if output.is_relative_to(root) or root.is_relative_to(output):
        raise ValueError('Validation output and snapshot directories must be separate')
    if output.is_relative_to(repository) and not output.is_relative_to(repository / 'data/processed'):
        raise ValueError('Use external output or ignored data/processed; audit files are local only')
    started = now()
    clock = time.monotonic()
    raw = (root / 'manifest.json').read_bytes()
    manifest = json.loads(raw)
    entries = manifest_entries(manifest)
    manifest_hash = digest(raw)
    config = {'version': VERSION, 'scan_ids': scan_ids, 'memory_limit': memory_limit, 'threads': threads}
    config_hash = digest(json.dumps(config, sort_keys=True).encode())
    run = output / manifest_hash / started.replace(':', '-')
    run.mkdir(parents=True)
    atomic_bytes(run / 'source-manifest.json', raw)
    report = {
        'validator_version': VERSION, 'status': 'blocked', 'started_at': started,
        'validator_source_sha256': digest(Path(__file__).read_bytes()),
        'schema_adapter_version': 'openalex-parquet-v1',
        'oa_snapshot_date': manifest['date'], 'source_prefix': PREFIX,
        'manifest_sha256': manifest_hash, 'config_sha256': config_hash,
        'snapshot_dir': str(root), 'output_dir': str(run), 'config': config,
        'engine_versions': {'duckdb': duckdb.__version__, 'pyarrow': pa.__version__},
        'transfer_provenance': transfer_gate(transfer, manifest_hash, started),
        'source_acceptance_policy': 'retrospective-v1' if accept_retrospective else 'strict-v1',
        'deletion_log': {'status': 'unavailable', 'reason': 'No deletion log declared by combined manifest; no survivor mappings inferred'},
        'entities': {}, 'schemas': {}, 'capabilities': {}, 'blockers': [],
    }
    if report['transfer_provenance']['status'] != 'passed' and not (
            accept_retrospective and report['transfer_provenance']['status'] == 'missing'):
        report['blockers'].append('transfer_provenance_missing_or_invalid')
    records = []
    for entry in entries:
        record, schema = inspect_file(root, entry)
        records.append(record)
        entity = report['entities'].setdefault(entry['entity'], {'files': 0, 'rows': 0, 'bytes': 0, 'errors': 0, 'schema_hashes': []})
        entity['files'] += 1
        entity['rows'] += record.get('actual_rows', 0)
        entity['bytes'] += record.get('actual_bytes', 0)
        entity['errors'] += bool(record['errors'])
        if schema is not None:
            schema_hash = record['schema_sha256']
            if schema_hash not in entity['schema_hashes']:
                entity['schema_hashes'].append(schema_hash)
                report['schemas'][schema_hash] = {'fields': {field.name: str(field.type) for field in schema},
                                                  'field_paths': schema_paths(schema)}
            if entry['entity'] == 'works':
                schema_errors = core_schema_errors(schema)
                if schema_errors:
                    record['errors'].append('unsupported_core_schema: ' + ', '.join(schema_errors))
                    entity['errors'] += 1
        if len(records) % 250 == 0:
            print(f'Inspected {len(records)}/{len(entries)} Parquet footers', flush=True)
    atomic_json(run / 'files.json', records)
    listed = {entry['key'] for entry in entries}
    report['unlisted_parquet_files'] = sorted(str(path.relative_to(root)) for path in root.rglob('*.parquet')
                                              if str(path.relative_to(root)) not in listed)
    for entity in manifest['entities']:
        name = entity['entity']
        details = report['entities'][name]
        per_entity_path = root / name / 'manifest.json'
        if per_entity_path.is_file():
            per_entity_raw = per_entity_path.read_bytes()
            atomic_bytes(run / 'entity-manifests' / (name + '.json'), per_entity_raw)
            per_entity = json.loads(per_entity_raw)
            details['entity_manifest_consistent'] = (
                per_entity.get('date') == manifest['date'] and per_entity.get('format') == 'parquet'
                and all(per_entity.get(key) == entity[key] for key in ('entity', 'record_count', 'content_length', 'files')))
            if not details['entity_manifest_consistent']:
                report['blockers'].append(name + ':entity_manifest_mismatch')
        if details['errors']:
            report['blockers'].append(name + ':file_errors')
        if len(details['schema_hashes']) != 1:
            report['blockers'].append(name + ':schema_drift_requires_adapter_review')
    work_schemas = [report['schemas'][key]['fields'] for key in report['entities']['works']['schema_hashes']]
    for capability, required in {
        'core_schema': CORE_FIELDS,
        'citation_edges_schema': {'id', 'publication_date', 'referenced_works'},
        'citation_summary_schema': {'cited_by_count'},
        'publisher_schema': {'primary_location'},
        'funding_schema': {'funders', 'awards'},
    }.items():
        report['capabilities'][capability] = bool(work_schemas) and all(required <= set(schema) for schema in work_schemas)
    report['capabilities']['core_schema'] = report['capabilities']['core_schema'] and not report['entities']['works']['errors']
    if scan_ids and not any(details['errors'] or len(details['schema_hashes']) != 1 for details in report['entities'].values()):
        spill = run / 'spill'
        spill.mkdir()
        connection = duckdb.connect(config={'memory_limit': memory_limit, 'threads': threads, 'temp_directory': str(spill)})
        try:
            benchmark_entry = next(entry for entry in entries if entry['entity'] == 'works')
            print('Benchmarking pinned work file: ' + benchmark_entry['key'], flush=True)
            report['benchmark'] = {
                'file_key': benchmark_entry['key'], 'manifest_sha256': manifest_hash,
                'file_bytes': benchmark_entry['content_length'],
                'scope': 'First manifest-listed work file; performance is not a full-corpus estimate',
                'result': identity_audit(connection, [str(root / benchmark_entry['key'])], 'works'),
                'peak_process_rss_kib': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
                'scratch_bytes_after_query': sum(path.stat().st_size for path in spill.rglob('*') if path.is_file()),
            }
            for name, details in report['entities'].items():
                print('Scanning IDs and flags: ' + name, flush=True)
                entity_records = [record for record in records if record['entity'] == name]
                fingerprint = digest(json.dumps(entity_records, sort_keys=True).encode())
                checkpoint = output / manifest_hash / 'checkpoints' / config_hash / (name + '.json')
                cached = json.loads(checkpoint.read_text()) if checkpoint.exists() else None
                if cached and cached.get('input_fingerprint') == fingerprint:
                    audit = cached['audit']
                    details['identity_checkpoint_reused'] = True
                else:
                    paths = [str(root / record['key']) for record in entity_records]
                    try:
                        audit = identity_audit(connection, paths, name)
                    except Exception as error:
                        details['identity'] = {'status': 'failed', 'reason': str(error)}
                        report['blockers'].append(name + ':identity_scan_failed')
                        atomic_json(run / 'validation-progress.json', report)
                        continue
                    atomic_json(checkpoint, {'input_fingerprint': fingerprint, 'audit': audit})
                details['identity'] = audit
                if audit['missing_ids'] or audit['duplicate_excess'] or audit.get('invalid_work_ids'):
                    report['blockers'].append(name + ':invalid_or_duplicate_ids')
                atomic_json(run / 'validation-progress.json', report)
        finally:
            connection.close()
    else:
        report['blockers'].append('identity_scan_not_completed')
    changed = [record['key'] for record in records if 'mtime_ns' in record and
               (not (root / record['key']).is_file() or
                (root / record['key']).stat().st_mtime_ns != record['mtime_ns'] or
                (root / record['key']).stat().st_size != record['actual_bytes'])]
    if changed or digest((root / 'manifest.json').read_bytes()) != manifest_hash:
        report['blockers'].append('local_inputs_changed_during_validation')
    report['changed_files'] = changed
    report['remote_manifest'] = {'status': 'not_checked'}
    if check_remote:
        try:
            with urllib.request.urlopen(MANIFEST_URL, timeout=45) as response:
                remote = response.read()
            atomic_bytes(run / 'post-transfer-manifest.json', remote)
            report['remote_manifest'] = {'status': 'matched' if remote == raw else 'changed',
                                         'sha256': digest(remote), 'checked_at': now(), 'url': MANIFEST_URL}
        except Exception as error:
            report['remote_manifest'] = {'status': 'unavailable', 'reason': str(error), 'checked_at': now()}
    if report['remote_manifest']['status'] != 'matched':
        report['blockers'].append('post_transfer_manifest_not_verified')
    report['source_accounting'] = {
        'listed_files': len(entries), 'expected_rows': manifest['meta']['record_count'],
        'footer_rows': sum(details['rows'] for details in report['entities'].values()),
        'expected_bytes': manifest['meta']['content_length'],
        'local_bytes': sum(details['bytes'] for details in report['entities'].values()),
        'unlisted_files_excluded': len(report['unlisted_parquet_files']),
    }
    report['integrity_limits'] = [
        'Parquet footer and projected ID/flag reads do not validate every column data page.',
        'No full-file content checksums computed; file size/mtime checkpoints assume immutable local storage.',
        'Manifest SHA-256 freezes metadata; S3 ETags are not treated as content MD5.',
        'Schema availability does not establish a ready analytical capability or adjudicate document roles.',
    ]
    report['finished_at'] = now()
    report['elapsed_seconds'] = round(time.monotonic() - clock, 3)
    report['peak_rss_kib'] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    report['status'] = 'validated' if not report['blockers'] else 'blocked'
    atomic_json(run / 'validation.json', report)
    atomic_json(output / 'latest-attempt.json', {'report': str(run / 'validation.json'), 'status': report['status']})
    if report['status'] == 'validated':
        atomic_json(output / 'validated-source.json', {'report': str(run / 'validation.json'), 'manifest_sha256': manifest_hash})
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot-dir', default=os.environ.get('OPENALEX_SNAPSHOT_DIR'))
    parser.add_argument('--output-dir', required=True)
    parser.add_argument('--scan-ids', action='store_true')
    parser.add_argument('--check-remote', action='store_true')
    parser.add_argument('--transfer-provenance', type=Path)
    parser.add_argument('--accept-retrospective', action='store_true',
                        help='Use the explicitly approved retrospective policy; preserve missing transfer evidence')
    parser.add_argument('--memory-limit', default='8GB')
    parser.add_argument('--threads', type=int, default=4)
    args = parser.parse_args()
    if not args.snapshot_dir:
        parser.error('Set OPENALEX_SNAPSHOT_DIR or --snapshot-dir')
    report = validate(args.snapshot_dir, args.output_dir, scan_ids=args.scan_ids,
                      check_remote=args.check_remote, transfer=args.transfer_provenance,
                      memory_limit=args.memory_limit, threads=args.threads,
                      accept_retrospective=args.accept_retrospective)
    print(json.dumps({'status': report['status'], 'blockers': report['blockers'], 'report': report['output_dir'] + '/validation.json'}, indent=2))
    return 0 if report['status'] == 'validated' else 2


if __name__ == '__main__':
    raise SystemExit(main())
