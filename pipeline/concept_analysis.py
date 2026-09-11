"""Legacy classification counts with explicit coverage, separate from Topics."""

from collections import Counter
import json
from pathlib import Path
import re

import pyarrow.parquet as pq

from .validate_snapshot import digest


def concept_members(values, level):
    return {item['id']: item.get('display_name') or item['id'] for item in values or []
            if item.get('level') == level and re.fullmatch(r'https://openalex[.]org/C[1-9][0-9]*', item.get('id') or '')}


def build_charts(release_dir, provenance, entries, works, populations, oa_date, rw_date, chart, count_row):
    marker_path = Path(release_dir)/'concepts-complete.json'
    if not marker_path.exists():
        return [chart('concepts', 'C', 'linked_work_count', [], '旧学科标签：Concepts', '这批论文在旧分类体系中如何分布？',
            status='not_computed', unavailable_reason='尚未完成这份快照的 Concepts 字段读取；不是没有旧学科标签。')], None
    marker = json.loads(marker_path.read_text())
    if marker['scan_config_sha256'] != provenance['config_sha256'] or marker['files'] != len(entries):
        raise ValueError('Concept scan mismatch')
    needed = set().union(*populations.values())
    concepts = {}
    for entry in entries:
        path = Path(marker['directory'])/(digest(entry['key'].encode())+'.parquet')
        checkpoint = json.loads(path.with_suffix('.json').read_text())
        if checkpoint['source_fingerprint'] != digest(json.dumps(entry, sort_keys=True).encode()) or checkpoint['sha256'] != digest(path.read_bytes()):
            raise ValueError('Concept shard integrity failed')
        for batch in pq.ParquetFile(path).iter_batches():
            for row in batch.to_pylist():
                if row['id'] in needed:
                    if row['id'] in concepts:
                        raise ValueError('Duplicate Concept work identity')
                    concepts[row['id']] = row['concepts'] or []
    if set(concepts) != needed:
        raise ValueError('Concept extraction does not cover the selected populations')
    results = []
    for population, identifiers in populations.items():
        scope = {'corpus': 'core', 'work_types': ['article'], 'taxonomy': 'oa_concepts_legacy',
            'attribution': 'distinct_attached_concept_per_work', 'score_policy': 'all_attached_including_zero_score_no_new_inference',
            'observation_cutoff': oa_date if population == 'A1' else rw_date}
        limitations = ['Concepts 是 OpenAlex 已停止更新的旧分类，不是现行 Topics，也不能把两套层级拼在一起。',
            '只统计快照中已有的标签，包含已附带的低分/零分祖先标签；不另设阈值、不补推祖先，每篇对同一 ID 只计一次。',
            '一篇可有多个概念，数量之和可能大于论文数；标签缺失不代表没有学科，新旧年份覆盖差异不能解释为研究趋势。']
        for level in (0, 1):
            counts, labels = Counter(), {}
            missing = 0
            for identifier in identifiers:
                members = concept_members(concepts[identifier], level)
                counts.update(members.keys())
                labels.update(members)
                missing += not members
            ordered = sorted(counts, key=lambda key: (-counts[key], key))[:30]
            rows = [count_row(key, labels[key], counts[key], len(identifiers), level=level) for key in ordered]
            results.append(chart('concepts', population, 'linked_work_count', rows,
                ('撤稿标记论文' if population == 'A1' else 'RW 匹配论文') + f'：Concepts 第 {level} 级分类',
                '按旧分类标签查看，这些论文涉及哪些研究领域？', scope=dict(scope, slice_id=population+f'-concepts-level-{level}', level=level),
                denominator=len(identifiers), missing=missing, limitations=limitations,
                extras={'concept_coverage': {'known_works': len(identifiers)-missing, 'missing_works': missing,
                    'distinct_concepts': len(counts), 'displayed_concepts': len(ordered)}}))
        total_by_era, known_by_era = Counter(), Counter()
        for identifier in identifiers:
            year = works[identifier]['publication_year']
            era = '2000 年以前' if year < 2000 else '2000–2009' if year < 2010 else '2010–2019' if year < 2020 else '2020 年起'
            total_by_era[era] += 1
            known_by_era[era] += any(concept_members(concepts[identifier], level) for level in range(6))
        rows = [dict(count_row(era, era, known_by_era[era], count), value=100*known_by_era[era]/count,
                     unit='percent', missing_works=count-known_by_era[era]) for era, count in sorted(total_by_era.items())]
        results.append(chart('concepts-coverage', population, 'paper_coverage_pct', rows, '旧分类标签的覆盖率',
            '不同发表时期的论文，有多少仍带有 Concepts 标签？', scope=dict(scope, slice_id=population+'-concepts-coverage'),
            denominator=len(identifiers), limitations=limitations))
    return results, marker
