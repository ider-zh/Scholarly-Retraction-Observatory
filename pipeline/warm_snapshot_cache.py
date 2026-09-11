"""Sequentially warm projected Parquet columns before a RAM-rich local scan."""

import argparse
import json
import os
from pathlib import Path
import time

import pyarrow.parquet as pq

from .validate_snapshot import atomic_json, digest, now


COLUMNS = {'id', 'doi', 'ids', 'publication_year', 'publication_date', 'type',
           'is_retracted', 'is_xpac', 'title', 'authorships', 'authors_count',
           'primary_topic', 'topics', 'primary_location', 'cited_by_count'}


def ranges(metadata):
    spans = []
    for group_index in range(metadata.num_row_groups):
        group = metadata.row_group(group_index)
        for column_index in range(group.num_columns):
            column = group.column(column_index)
            if column.path_in_schema.split('.')[0] in COLUMNS:
                start = min(offset for offset in (column.dictionary_page_offset, column.data_page_offset)
                            if offset is not None and offset >= 0)
                spans.append((start, start + column.total_compressed_size))
    merged = []
    for start, end in sorted(spans):
        if merged and start <= merged[-1][1] + 262144:
            merged[-1] = (merged[-1][0], max(end, merged[-1][1]))
        else:
            merged.append((start, end))
    return merged


def warm(validation_path, skip_completed_run=None):
    validation_path = Path(validation_path)
    validation = json.loads(validation_path.read_text())
    if validation['status'] != 'validated' or validation['blockers']:
        raise ValueError('Source validation must pass first')
    root = Path(validation['snapshot_dir'])
    if digest((root / 'manifest.json').read_bytes()) != validation['manifest_sha256']:
        raise ValueError('Source manifest changed')
    completed_run = Path(skip_completed_run) if skip_completed_run else None
    if completed_run:
        config = json.loads((completed_run / 'provenance.json').read_text())['config']
        if config['oa_manifest_sha256'] != validation['manifest_sha256']:
            raise ValueError('Resume directory uses another snapshot')
    entries = json.loads((validation_path.parent / 'files.json').read_text())
    started, total, files = time.monotonic(), 0, 0
    for entry in entries:
        if entry['entity'] != 'works':
            continue
        if completed_run and (completed_run / 'shards' / digest(entry['key'].encode()) / 'complete.json').exists():
            continue
        path = root / entry['key']
        stat = path.stat()
        if stat.st_size != entry['actual_bytes'] or stat.st_mtime_ns != entry['mtime_ns']:
            raise ValueError('Source file changed after validation: ' + entry['key'])
        spans = ranges(pq.ParquetFile(path).metadata)
        with path.open('rb', buffering=0) as source:
            if hasattr(os, 'posix_fadvise'):
                os.posix_fadvise(source.fileno(), 0, 0, os.POSIX_FADV_SEQUENTIAL)
            for start, end in spans:
                while start < end:
                    block = os.pread(source.fileno(), min(8 * 1024 * 1024, end - start), start)
                    if not block:
                        raise ValueError('Unexpected source EOF')
                    start += len(block)
                    total += len(block)
        files += 1
        if files % 25 == 0:
            elapsed = time.monotonic() - started
            print(f'Cached {files} files, {total / 2**30:.1f} GiB; {total / 2**20 / elapsed:.1f} MiB/s', flush=True)
    report = {'manifest_sha256': validation['manifest_sha256'], 'files': files,
              'projected_bytes_read': total, 'elapsed_seconds': time.monotonic() - started,
              'completed_at': now(), 'columns': sorted(COLUMNS),
              'meaning': 'OS cache warming only; not a new source-integrity gate or analytical result'}
    atomic_json(validation_path.parent / 'cache-warm.json', report)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--validation-report', type=Path, required=True)
    parser.add_argument('--skip-completed-run', type=Path)
    args = parser.parse_args()
    warm(args.validation_report, args.skip_completed_run)
