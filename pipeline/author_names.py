"""RW raw-name associations, separate from OpenAlex author identities."""

from collections import Counter
import csv
import io
from pathlib import Path

from .build import parts
from .validate_snapshot import digest


MISSING_NAMES = {'', 'unknown', 'unavailable', 'not available', 'n/a', 'na', 'none', 'null'}


def raw_name_counts(papers, csv_path, expected_sha256):
    raw = Path(csv_path).read_bytes()
    if digest(raw) != expected_sha256:
        raise ValueError('RW author source hash mismatch')
    reader = csv.DictReader(io.StringIO(raw.decode('utf-8-sig'), newline=''))
    if not {'Record ID', 'Author'}.issubset(reader.fieldnames or []):
        raise ValueError('RW author source columns missing')
    required_ids = {record_id for paper in papers for record_id in paper['rw_ids']}
    records = {}
    for row in reader:
        record_id = row['Record ID']
        if record_id not in required_ids:
            continue
        if record_id in records:
            raise ValueError('Duplicate RW source record ID')
        records[record_id] = row['Author'] or ''
    counts, seen = Counter(), set()
    missing, partial_missing = 0, 0
    for paper in papers:
        if paper['id'] in seen or not paper['rw_ids']:
            raise ValueError('Invalid canonical RW original')
        seen.add(paper['id'])
        names, has_missing = set(), False
        for record_id in paper['rw_ids']:
            if record_id not in records:
                raise ValueError('Canonical RW record absent from author source')
            values = parts(records[record_id]) or ['']
            has_missing |= any(value.casefold() in MISSING_NAMES for value in values)
            names.update(value for value in values if value.casefold() not in MISSING_NAMES)
        counts.update(names)
        missing += not names
        partial_missing += bool(names) and has_missing
    return counts, {'known_works': len(papers) - missing, 'unknown_works': missing,
                    'partially_missing_works': partial_missing, 'distinct_name_strings': len(counts),
                    'association_total': sum(counts.values()), 'excluded_placeholders': sorted(MISSING_NAMES)}


def build_chart(papers, csv_path, expected_sha256, rw_date, chart, count_row):
    scope = {'corpus': 'rw', 'work_types': ['all'], 'attribution': 'distinct_original_per_raw_author_name',
             'observation_cutoff': rw_date, 'slice_id': 'B-raw-author-names-top-20'}
    limitations = ['这是 RW 原始署名字符串排行，不是已消歧的个人排行；同名可能合并多人，拼写变体可能拆分同一人。',
                   '按已去重的 RW 原论文计数，合并同一原论文的撤稿记录；每篇对同一姓名字符串只计一次，不要求 OpenAlex 匹配。',
                   '只按分号拆分并去除首尾空白，不转换姓名顺序、大小写或拼写。缺失占位值不进 Top 20，覆盖情况另列。',
                   '完整总体不随 Top 20 缩小；多人署名计数可重叠，不能相加为论文总数。这不是责任或不端行为排名。']
    if csv_path is None:
        return chart('rw-author-names', 'B', 'linked_work_count', [], 'RW 原始署名字符串关联排行 · Top 20',
                     '哪些 RW 原始署名字符串关联了较多撤稿原论文？', scope=scope,
                     status='not_computed', unavailable_reason='未提供与快照哈希一致的 RW 原始 CSV，不能借用旧版排行。',
                     denominator=len(papers), limitations=limitations)
    counts, coverage = raw_name_counts(papers, csv_path, expected_sha256)
    names = sorted(counts, key=lambda name: (-counts[name], name))[:20]
    rows = [count_row(name, name, counts[name], len(papers), rank=index)
            for index, name in enumerate(names, 1)]
    result = chart('rw-author-names', 'B', 'linked_work_count', rows, 'RW 原始署名字符串关联排行 · Top 20',
                   '哪些 RW 原始署名字符串关联了较多撤稿原论文？', scope=scope,
                   denominator=len(papers), missing=coverage['unknown_works'], limitations=limitations,
                   extras={'association_summary': coverage, 'rw_author_source_sha256': expected_sha256})
    result['quality']['small_base_policy'] = 'count_order_only_no_rate_ranking'
    return result
