"""Compact, versioned aggregate report from a completed local snapshot scan."""

from collections import Counter, defaultdict
import argparse
import datetime as dt
import json
import math
from itertools import combinations
from pathlib import Path
import subprocess

import duckdb
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

from .snapshot import METHODS, ROLE_POLICY, cohort_rate, country_sets, quantile, select_match
from .validate_snapshot import atomic_bytes, atomic_json, digest, now
from .citation_analysis import build_charts as citation_charts
from .reason_families import build_charts as reason_family_charts, VERSION as REASON_VERSION
from .publisher_analysis import build_charts as publisher_charts
from .supplement_analysis import build_charts as supplement_charts
from .extended_descriptive import build_charts as extended_charts


SECTIONS = ('overview', 'time', 'fields', 'reasons', 'geography', 'entities', 'publishing', 'citations', 'quality')
ELIGIBLE_ROLES = {'original_supported', 'unresolved'}
LIMITATIONS = {
    'source': 'OpenAlex 的撤稿标记源自 RW；这是覆盖核对与元数据补充，不是独立验证。',
    'role': 'A1 是角色筛选后的发表候选，未独立确认为原论文；标题疑似通知的纳入/排除敏感性另列。',
    'country': '国家表示论文署名关联地点，不是国籍或责任；已知国家分数计数可能高估部分缺失论文的已知成员。',
    'event': '当前 RW 文件记录的首次有效撤稿日期不等于完整历史事件日志；较晚补录与选择性匹配会影响构成。',
    'rate': '这是截至快照的已观测发表队列比例；近期队列观察时间较短，不能据此判断风险下降。',
    'reason': '同篇论文的 Retraction 记录原因取并集，可有多个标签；并非每个原因在首次撤稿日已知，也不都代表已证实不端。',
}


def count_row(identifier, label, numerator, denominator=None, **extra):
    return {'id': str(identifier), 'label': str(label), 'numerator': numerator,
            'denominator': denominator, 'value': numerator, 'unit': 'works', **extra}


def compact_numbers(value):
    if isinstance(value, float):
        return round(value, 6)
    if isinstance(value, dict):
        return {key: compact_numbers(child) for key, child in value.items()}
    if isinstance(value, list):
        return [compact_numbers(child) for child in value]
    return value


def top_rows(counts, labels=None, total=None, limit=100):
    return [count_row(identifier, (labels or {}).get(identifier, identifier), count, total)
            for identifier, count in sorted(counts.items(), key=lambda item: (-item[1], str(item[0])))[:limit]]


def associations(memberships):
    counts, weights, members = Counter(), Counter(), defaultdict(set)
    unknown = 0
    for work_id, values in memberships.items():
        values = set(values)
        if not values:
            unknown += 1
        for member in values:
            counts[member] += 1
            weights[member] += 1 / len(values)
            members[member].add(work_id)
    known = len(memberships) - unknown
    if not math.isclose(sum(weights.values()), known, rel_tol=1e-9, abs_tol=1e-7):
        raise ValueError('Fractional allocations do not sum to known works')
    ordered = sorted(counts, key=lambda member: (-counts[member], member))
    association_total = sum(counts.values())
    selected = ordered[:10]
    union = set().union(*(members[member] for member in selected)) if selected else set()
    shares = [counts[member] / association_total for member in ordered] if association_total else []
    ascending = sorted(counts.values())
    gini = ((2 * sum((index + 1) * count for index, count in enumerate(ascending)) /
             (len(ascending) * association_total)) - (len(ascending) + 1) / len(ascending)) if ascending else None
    summary = {'known_works': known, 'unknown_works': unknown, 'association_total': association_total,
               'real_entities_with_positive_associations': len(counts), 'top_k': len(selected),
               'top_k_union_works': len(union), 'top_k_associations': sum(counts[member] for member in selected),
               'hhi': sum(share ** 2 for share in shares) if shares else None, 'gini': gini,
               'zero_association_entities_included': False}
    cumulative = 0
    lorenz = [{'id': '0', 'label': '0% entities', 'numerator': 0, 'denominator': association_total,
               'value': 0 if association_total else None, 'unit': 'percent', 'entity_pct': 0}]
    stride = max(1, len(ascending) // 100)
    for index, count in enumerate(ascending, 1):
        cumulative += count
        if index % stride == 0 or index == len(ascending):
            lorenz.append({'id': str(index), 'label': f'{100 * index / len(ascending):.1f}% entities',
                           'numerator': cumulative, 'denominator': association_total,
                           'value': 100 * cumulative / association_total, 'unit': 'percent',
                           'entity_pct': 100 * index / len(ascending)})
    summary['lorenz'] = lorenz
    return counts, weights, summary


def chart(chart_id, population, metric, rows, title, question, *, scope=None, missing=0,
          denominator=None, limitations=None, status='ready', unavailable_reason=None, extras=None):
    scope = scope or {}
    result = {'chart_id': chart_id, 'slice_id': scope.get('slice_id', population + '-default'),
              'population_key': population, 'metric_id': metric, 'status': status,
              'title': title, 'question': question, 'scope': scope, 'rows': rows,
              'quality': {'eligible_works': denominator, 'missing_works': missing,
                          'small_base_policy': 'N>=1000_and_n>=20_for_ranking'},
              'limitations': limitations or [], 'insights': [], 'unavailable_reason': unavailable_reason,
              'methods_version': METHODS}
    if extras:
        result.update(extras)
    if rows and status == 'ready':
        candidates = [row for row in rows if row.get('value') is not None and not row.get('partial') and not row.get('small_base')]
        if metric.endswith('_cohort_per_10k'):
            candidates = [row for row in candidates if row.get('ranking_eligible')]
        ordered = sorted(candidates, key=lambda row: row['value'], reverse=True)
        peak = ordered[0] if ordered else next((row for row in rows if row.get('value') is not None), None)
        if peak:
            unit = {'works': '篇作品', 'authors': '位作者', 'percent': '%', 'per_10k': '每万篇', 'years': '年'}.get(peak.get('unit'), peak.get('unit', 'works'))
            observation = f"当前发布单元中，{peak['label']} 为 {peak['value']:,.2f} {unit}；分子 {peak['numerator']:,}"
            if peak.get('denominator') is not None:
                observation += f"，分母 {peak['denominator']:,}"
            evidence = [peak['id']]
            if len(ordered) > 1:
                other = ordered[1]
                observation += f"；{other['label']} 为 {other['value']:,.2f} {unit}（n={other['numerator']:,}"
                if other.get('denominator') is not None:
                    observation += f"，N={other['denominator']:,}"
                observation += '）'
                evidence.append(other['id'])
            if metric.endswith('_cohort_per_10k'):
                observation += '。比例比较仅限满足 n≥20、N≥1,000 门槛的单元' if candidates else '。没有单元满足排名门槛，不进行比例排名'
            observation += '。完整统计范围与缺失见下表；展示顺序不代表责任或因果判断。'
            result['insights'] = [{'insight_id': chart_id + '-' + result['slice_id'],
                'chart_id': chart_id, 'slice_id': result['slice_id'], 'status': 'ready',
                'evidence_cells': evidence, 'comparison_basis': 'eligible_displayed_cells' if candidates else 'single_cell_no_ranking',
                'template_id': 'displayed-cell-v1', 'text': observation, 'limitations': result['limitations']}]
    if chart_id == 'T4' and result.get('quantiles', {}).get('p50_days') is not None:
        quantiles = result['quantiles']
        result['insights'] = [{'insight_id': chart_id + '-' + result['slice_id'], 'chart_id': chart_id,
            'slice_id': result['slice_id'], 'status': 'ready', 'template_id': 'lag-quantiles-v1',
            'comparison_basis': 'within_recorded_retractions',
            'evidence_cells': ['quantiles:p25_days', 'quantiles:p50_days', 'quantiles:p75_days'],
            'text': f"有效日期样本 {denominator:,} 篇，中位时滞 {quantiles['p50_days']/365.25:.2f} 年；中间 50% 位于 {quantiles['p25_days']/365.25:.2f}–{quantiles['p75_days']/365.25:.2f} 年。该分布仅以已有撤稿记录的原论文为条件。",
            'limitations': result['limitations']}]
    if chart_id == 'C1' and result.get('quantiles', {}).get('median') is not None:
        result['insights'] = [{'insight_id': chart_id + '-' + result['slice_id'], 'chart_id': chart_id,
            'slice_id': result['slice_id'], 'status': 'ready', 'template_id': 'citation-quantiles-v1',
            'comparison_basis': 'snapshot_citation_distribution', 'evidence_cells': ['quantiles:median', 'quantiles:p90'],
            'text': f"当前范围 {denominator:,} 篇作品中，引用次数可用 {denominator-missing:,} 篇；中位数为 {result['quantiles']['median']:,.1f} 次，P90 为 {result['quantiles']['p90']:,.1f} 次。不同作品的引用机会随发表年龄而变化。",
            'limitations': result['limitations']}]
    return result


def build(release_dir):
    release_dir = Path(release_dir)
    report_source_hash = digest(Path(__file__).read_bytes())
    scan = json.loads((release_dir / 'scan-complete.json').read_text())
    provenance = json.loads((release_dir / 'provenance.json').read_text())
    if scan['config_sha256'] != provenance['config_sha256']:
        raise ValueError('Scan/provenance version mismatch')
    validation_path = Path(provenance['validation_report'])
    validation = json.loads(validation_path.read_text())
    entries = [entry for entry in json.loads((validation_path.parent / 'files.json').read_text()) if entry['entity'] == 'works']
    shards = [release_dir / 'shards' / digest(entry['key'].encode()) for entry in entries]
    if len(shards) != scan['files'] or any(not (shard / 'complete.json').exists() for shard in shards):
        raise ValueError('Incomplete scan; cannot build report')
    oa_date, rw_date = validation['oa_snapshot_date'], provenance['rw']['rw_snapshot_date']
    dimension_version = json.loads((release_dir / 'dimensions-complete.json').read_text())['code_sha256'] if (release_dir / 'dimensions-complete.json').exists() else None
    extension_hashes = {name: digest(Path(__file__).with_name(name + '.py').read_bytes())
                        for name in ('citation_analysis', 'reason_families', 'publisher_analysis', 'supplement_analysis', 'extended_descriptive')}
    citation_marker = json.loads((release_dir / 'citations-complete.json').read_text()) if (release_dir / 'citations-complete.json').exists() else None
    supplement_marker = json.loads((release_dir / 'supplement-complete.json').read_text()) if (release_dir / 'supplement-complete.json').exists() else None
    burst_policy_hash = digest((Path(__file__).resolve().parents[1] / 'data/reference/snapshot-burst-policy-v1.json').read_bytes())
    report_config_hash = digest(json.dumps({'scan_config_sha256': provenance['config_sha256'],
        'report_source_sha256': report_source_hash, 'dimension_source_sha256': dimension_version,
        'extensions': extension_hashes, 'burst_policy': burst_policy_hash,
        'supplement': supplement_marker['config_sha256'] if supplement_marker else None,
        'citations': citation_marker['config_sha256'] if citation_marker else None}, sort_keys=True).encode())
    release_id = 'oa-' + oa_date + '-' + report_config_hash[:12]
    papers = json.loads((release_dir / 'rw_original.json').read_text())
    works, by_doi, by_pmid = {}, defaultdict(set), defaultdict(set)
    for shard_index, shard in enumerate(shards, 1):
        identifiers = {row['id']: row for row in pq.ParquetFile(shard / 'identifiers.parquet').read().to_pylist()}
        detailed_ids = []
        for identifier, identity in identifiers.items():
            works[identifier] = dict(identity, countries={}, authors=[], institutions={}, topic={}, source={},
                                     citations=None, observed_authors=None, authors_count=None)
            if identity['doi']:
                by_doi[identity['doi']].add(identifier)
            if identity['pmid']:
                by_pmid[identity['pmid']].add(identifier)
            if (identity['is_xpac'] is False and identity['type'] == 'article'
                    and identity['document_role'] in ELIGIBLE_ROLES
                    and identity['publication_year'] is not None
                    and 1 <= identity['publication_year'] <= int(oa_date[:4])
                    and (identity['publication_date'] is None or str(identity['publication_date']) <= oa_date)):
                detailed_ids.append(identifier)
        if not detailed_ids:
            continue
        detailed_ids = pa.array(detailed_ids)
        for batch in pq.ParquetFile(shard / 'targets.parquet').iter_batches(batch_size=2048):
            selected = batch.filter(pc.is_in(batch.column('id'), value_set=detailed_ids))
            for raw in selected.to_pylist():
                identity = identifiers[raw['id']]
                modes, authors, institutions = country_sets(raw)
                topic = raw.get('primary_topic') or {}
                source = (raw.get('primary_location') or {}).get('source') or {}
                work = dict(identity, countries=modes, authors=authors, institutions=institutions,
                    topic=topic, topics=raw.get('topics') or [], source=source, citations=raw.get('cited_by_count'),
                    observed_authors=len(raw.get('authorships') or []), authors_count=raw.get('authors_count'))
                works[raw['id']] = work
        if shard_index % 250 == 0:
            print(f'Loaded report metadata: {shard_index}/{len(shards)} shards', flush=True)
    matches, reconciliation = {}, Counter()
    matched_ids, matched_by_cutoff = set(), set()
    for paper in papers:
        match = select_match(paper, by_doi, by_pmid)
        selected = works.get(match['selected_id'])
        if selected and (selected['document_role'] in {'known_notice', 'conflict'} or
                         (paper['doi'] and selected['doi'] and paper['doi'] != selected['doi']) or
                         (paper['pmids'] and selected['pmid'] and selected['pmid'] not in paper['pmids'])):
            match.update(match_outcome='conflicting', selected_id=None)
            selected = None
        matches[paper['id']] = match
        if selected:
            flag = selected['is_retracted']
            state = 'matched_flag_true' if flag is True else 'matched_flag_false' if flag is False else 'matched_flag_missing'
            matched_ids.add(selected['id'])
            if paper['retracted'] and paper['retracted'] <= oa_date:
                matched_by_cutoff.add(selected['id'])
        else:
            state = match['match_outcome']
        reconciliation[state] += 1
    atomic_json(release_dir / 'rw_oa_match.json', matches)
    with duckdb.connect(config={'memory_limit': '32GB', 'threads': 16}) as connection:
        connection.read_parquet([str(shard / 'cohorts.parquet') for shard in shards]).create_view('cohorts')
        cohort_rows = connection.execute('''SELECT is_xpac, type, publication_year, document_role,
            is_retracted, date_eligible, sum(work_count)::BIGINT AS count FROM cohorts GROUP BY ALL''').fetchall()
    corpus_counts, flag_counts, role_counts = Counter(), Counter(), Counter()
    denominators, flagged, suspected_denominators, suspected_flagged = Counter(), Counter(), Counter(), Counter()
    total_rows = 0
    for xpac, kind, year, role, flag, valid_date, count in cohort_rows:
        total_rows += count
        corpus = 'core' if xpac is False else 'expansion' if xpac is True else 'unknown'
        corpus_counts[corpus] += count
        flag_counts[(corpus, flag)] += count
        if flag is True:
            role_counts[(corpus, role)] += count
        if xpac is False and kind in {'article', 'review'} and valid_date:
            if role in ELIGIBLE_ROLES:
                denominators[(kind, year)] += count
                if flag is True:
                    flagged[(kind, year)] += count
            elif role == 'suspected_notice':
                suspected_denominators[(kind, year)] += count
                if flag is True:
                    suspected_flagged[(kind, year)] += count
    if total_rows != validation['entities']['works']['rows']:
        raise ValueError('Projected work accounting differs from validated source')
    dimension_rows = []
    dimension_path = release_dir / 'dimensions-complete.json'
    if dimension_path.exists():
        dimension_meta = json.loads(dimension_path.read_text())
        if dimension_meta['files'] != len(entries):
            raise ValueError('Incomplete dimension denominator scan')
        paths = [str(Path(dimension_meta['directory']) / (digest(entry['key'].encode()) + '.parquet')) for entry in entries]
        with duckdb.connect(config={'memory_limit': '32GB', 'threads': 16}) as connection:
            connection.read_parquet(paths).create_view('dimensions')
            dimension_rows = connection.execute('''SELECT dimension, group_id, type, publication_year,
                sum(denominator)::BIGINT, sum(weighted_denominator) FROM dimensions GROUP BY ALL''').fetchall()
        field_totals = Counter()
        for dimension, identifier, kind, year, count, weight in dimension_rows:
            if dimension == 'field':
                field_totals[(kind, year)] += count
        if field_totals != denominators:
            raise ValueError('Dimension D differs from the original publication-cohort D')

    def eligible(work, kind='article'):
        return (work['is_xpac'] is False and work['type'] == kind and work['document_role'] in ELIGIBLE_ROLES
                and work['publication_year'] is not None and 1 <= work['publication_year'] <= int(oa_date[:4])
                and (work['publication_date'] is None or str(work['publication_date']) <= oa_date))

    a0 = {identifier for identifier, work in works.items() if work['is_xpac'] is False and work['is_retracted'] is True}
    a1 = {identifier for identifier in a0 if eligible(works[identifier])}
    if len(a1) != sum(count for (kind, year), count in flagged.items() if kind == 'article'):
        raise ValueError('A1 target extraction does not reconcile to full-scan counts')
    cd = {identifier for identifier in matched_by_cutoff if eligible(works[identifier])}
    common_scope = {'corpus': 'core', 'work_types': ['article'], 'publication_year_range': None,
                    'observation_cutoff': oa_date, 'attribution': 'unique_work', 'date_basis': 'oa_publication_year'}
    chapters = {section: [] for section in SECTIONS}
    card_rows = [count_row('A0', 'A0 · core 标记 Work 记录', len(a0)),
                 count_row('A1', 'A1 · core article 筛选后候选', len(a1)),
                 count_row('B', 'B · RW 去重 Retraction 原论文', len(papers)),
                 count_row('C', 'C · 高置信匹配 OA Work', len(matched_ids)),
                 count_row('D', 'D · core article 发表候选', sum(value for (kind, year), value in denominators.items() if kind == 'article'))]
    chapters['overview'].append(chart('population-accounting', 'mixed_diagnostic', 'work_count', card_rows,
        '研究覆盖了哪些记录？', '标记记录、RW 原论文和匹配作品各有多少？',
        scope={'corpus': 'mixed_see_cell_labels', 'work_types': ['mixed'], 'attribution': 'separate_population_counts'},
        limitations=[LIMITATIONS['source'], '这些总体重叠、范围不同，不能相加。']))
    q1_rows = [count_row(state, state, reconciliation.get(state, 0), len(papers)) for state in
               ('matched_flag_true', 'matched_flag_false', 'matched_flag_missing', 'unmatched', 'ambiguous', 'conflicting')]
    if sum(row['numerator'] for row in q1_rows) != len(papers):
        raise ValueError('RW reconciliation does not partition B')
    doi_papers = [paper for paper in papers if paper['doi']]
    q1_extras = {'coverage': {'all_rw_originals': len(papers), 'matched_rw_originals': sum(row['numerator'] for row in q1_rows[:3]),
                             'doi_rw_originals': len(doi_papers),
                             'matched_doi_rw_originals': sum(matches[paper['id']]['match_outcome'] == 'unique' for paper in doi_papers),
                             'oa_core_flagged_without_rw_match': len(a0 - matched_ids),
                             'matched_unique_oa_works': len(matched_ids)}}
    chapters['quality'].append(chart('Q1', 'B', 'work_count', q1_rows, 'RW × OpenAlex 覆盖核对', '哪些 RW 原论文与 OA 唯一匹配？',
        denominator=len(papers), limitations=[LIMITATIONS['source'], 'C 的唯一 OA 作品数与匹配 RW 键数分别报告。'], extras=q1_extras))
    exclusions = Counter()
    for identifier in a0:
        work = works[identifier]
        if work['type'] != 'article':
            exclusions['excluded_work_type'] += 1
        elif work['document_role'] not in ELIGIBLE_ROLES:
            exclusions['excluded_' + work['document_role']] += 1
        elif not eligible(work):
            exclusions['excluded_date'] += 1
        else:
            exclusions['retained_A1'] += 1
    if sum(exclusions.values()) != len(a0):
        raise ValueError('Role/type/date exclusions do not partition A0')
    chapters['quality'].append(chart('Q3', 'A0', 'work_count', top_rows(exclusions, total=len(a0)),
        '从标记记录到 article 候选', '为什么标记数量不等于原论文数量？', scope=common_scope,
        denominator=len(a0), limitations=[LIMITATIONS['role'], '按作品类型→角色→日期的固定顺序互斥排除。']))
    quality_counts = Counter({'oa_flag_missing': sum(value for (corpus, flag), value in flag_counts.items() if flag is None),
                              'oa_corpus_unknown': corpus_counts['unknown'],
                              'rw_publication_date_missing': sum(paper['published'] is None for paper in papers),
                              'rw_event_date_missing': sum(paper['retracted'] is None for paper in papers),
                              'rw_negative_lag': sum(paper['negative_lag'] for paper in papers),
                              'rw_publication_after_source_date': sum(bool(paper['published'] and paper['published'] > rw_date) for paper in papers),
                              'rw_publication_date_conflict': sum(paper['publication_date_conflict'] for paper in papers)})
    chapters['quality'].append(chart('Q2', 'source_quality', 'work_count', top_rows(quality_counts),
        '缺失和日期冲突', '哪些字段缺失会影响解释？', limitations=['各项总体不同且可能重叠；未知状态没有转换为零。']))
    for dimension in ('publication_era', 'subjects', 'rw_countries'):
        total_by_group, matched_by_group = Counter(), Counter()
        for paper in papers:
            if dimension == 'publication_era':
                year = int(paper['published'][:4]) if paper['published'] else None
                groups = ['Unknown' if year is None else 'Before 2000' if year < 2000 else str(year // 10 * 10) + 's']
            else:
                groups = paper[dimension] or ['Unknown']
            for group in groups:
                total_by_group[group] += 1
                matched_by_group[group] += matches[paper['id']]['match_outcome'] == 'unique'
        coverage_rows = [dict(count_row(group, group, matched_by_group[group], count),
                              value=100 * matched_by_group[group] / count, unit='percent')
                         for group, count in total_by_group.most_common()]
        chapters['quality'].append(chart('Q2', 'B', 'match_coverage_pct', coverage_rows,
            'RW 匹配覆盖 · ' + dimension, '未匹配记录是否在原始来源分层中均匀分布？',
            scope={'slice_id': 'B-matching-' + dimension, 'corpus': 'rw', 'work_types': ['all'],
                   'attribution': 'raw_rw_' + dimension, 'observation_cutoff': rw_date}, denominator=len(papers),
            limitations=[LIMITATIONS['source'], '分层使用 RW 原始字段；未匹配作品不被赋予 OA 分类。多标签分组可重叠，匹配不是身份或撤稿状态的独立核验。']))
    for clock in ('published', 'retracted'):
        counts = Counter(int(paper[clock][:4]) for paper in papers if paper[clock] and paper[clock] <= rw_date)
        rows = [count_row(year, str(year), counts.get(year, 0), len(papers), year=year,
                         partial=year == int(rw_date[:4])) for year in range(2000, int(rw_date[:4]) + 1)]
        chapters['time'].append(chart('T1', 'B', 'work_count', rows,
            'RW 原论文发表年分布' if clock == 'published' else 'RW 首次记录撤稿年分布',
            '发表年与撤稿年分布有何不同？', scope={'slice_id': 'B-' + clock, 'date_basis': clock, 'corpus': 'rw', 'work_types': ['all'], 'observation_cutoff': rw_date},
            missing=sum(paper[clock] is None for paper in papers), denominator=len(papers),
            extras={'outside_display_range_works': sum(count for year, count in counts.items() if year < 2000),
                    'excluded_future_dates': sum(bool(paper[clock] and paper[clock] > rw_date) for paper in papers)},
            limitations=[LIMITATIONS['event'], '仅发布自 2000 年起的展示单元；更早作品保留在总体和范围外计数中。标记 partial 的年份未结束。']))
    matrix = Counter((int(paper['published'][:4]), int(paper['retracted'][:4])) for paper in papers
                     if paper['published'] and paper['retracted'] and not paper['negative_lag'])
    chapters['time'].append(chart('T2', 'B', 'work_count', [count_row(f'{published}-{event}', f'{published} → {event}', count,
        len(papers), publication_year=published, event_year=event) for (published, event), count in sorted(matrix.items()) if published >= 2000 and event >= 2000],
        '发表年 × 首次记录撤稿年', '撤稿年高峰来自哪些发表队列？', denominator=len(papers),
        missing=len(papers) - sum(matrix.values()),
        extras={'outside_display_range_works': sum(count for (published, event), count in matrix.items() if published < 2000 or event < 2000)},
        limitations=[LIMITATIONS['event'], '矩阵展示两个年份均自 2000 年起的单元，更早记录另列范围外计数。集中带不能据此归因于调查或论文工厂。']))
    lags = [paper['lag_days'] for paper in papers if paper['lag_days'] is not None]
    quantiles = {label: quantile(lags, fraction) for label, fraction in [('p25_days', .25), ('p50_days', .5), ('p75_days', .75), ('p90_days', .9)]}
    lag_counts = Counter(lags)
    ordered_lags = sorted(lag_counts)
    cumulative = 0
    ecdf = []
    stride = max(1, len(ordered_lags) // 150)
    for index, days in enumerate(ordered_lags):
        cumulative += lag_counts[days]
        if index % stride == 0 or index == len(ordered_lags) - 1:
            ecdf.append(dict(count_row(days, f'{days / 365.25:.2f} 年', cumulative, len(lags)),
                             value=100 * cumulative / len(lags), unit='percent', lag_days=days))
    chapters['time'].append(chart('T4', 'B', 'lag_ecdf_pct', ecdf, '已撤稿样本的时滞 ECDF',
        '有效日期样本中，有多少在某个年限内被撤稿？', missing=len(papers) - len(lags), denominator=len(lags),
        limitations=['只描述已记录撤稿样本，不是全部论文的生存或风险曲线；来源的原始日期精度无法完全恢复。'], extras={'quantiles': quantiles}))
    for kind in ('article', 'review'):
        cd_counts = Counter(works[identifier]['publication_year'] for identifier in matched_by_cutoff if eligible(works[identifier], kind))
        for population in ('A1_over_D', 'C_D_over_D'):
            rows = []
            for (work_type, year), denominator in sorted(denominators.items()):
                if work_type != kind or year < 2000:
                    continue
                numerator = flagged[(kind, year)] if population == 'A1_over_D' else cd_counts[year]
                if numerator > denominator:
                    raise ValueError('Cohort numerator exceeds denominator')
                rows.append(dict(count_row(year, str(year), numerator, denominator), **cohort_rate(numerator, denominator),
                                 unit='per_10k', year=year, partial=year == int(oa_date[:4]),
                                 suspected_notice_denominator=suspected_denominators[(kind, year)],
                                 suspected_notice_numerator=suspected_flagged[(kind, year)] if population == 'A1_over_D' else 0))
            chapters['time'].append(chart('T3', population,
                'oa_flagged_cohort_per_10k' if population == 'A1_over_D' else 'rw_recorded_cohort_per_10k', rows,
                ('OA 标记' if population == 'A1_over_D' else 'RW 记录') + f' · {kind} 发表队列每万篇比例',
                '同口径发文分母下，观察到的比例是多少？', scope=dict(common_scope, work_types=[kind], slice_id=population + '-' + kind,
                                                                            publication_year_range=[2000, int(oa_date[:4])]),
                denominator=sum(row['denominator'] for row in rows), limitations=[LIMITATIONS['rate'], LIMITATIONS['role'],
                '疑似通知敏感性：纳入时同时加入每行的 suspected_notice_numerator 与 suspected_notice_denominator；默认二者均排除。RW 原标识支持的匹配已有角色证据。']))

    for population, identifiers in [('A1', a1), ('C', {identifier for identifier in matched_ids if eligible(works[identifier])})]:
        population_scope = dict(common_scope, slice_id=population + '-core-article',
                                observation_cutoff=rw_date if population == 'C' else oa_date)
        for level in ('domain', 'field', 'subfield', 'topic'):
            counts, labels = Counter(), {}
            missing = 0
            for identifier in identifiers:
                topic = works[identifier]['topic']
                node = topic if level == 'topic' else topic.get(level) or {}
                if node.get('id'):
                    counts[node['id']] += 1
                    labels[node['id']] = node.get('display_name') or node['id']
                else:
                    missing += 1
            chapters['fields'].append(chart('F1', population, 'linked_work_count', top_rows(counts, labels, len(identifiers)),
                f'{population} · OA 主 Topic 的 {level} 分布', '哪个分类层次关联更多发表候选？',
                scope=dict(population_scope, slice_id=population + '-primary-' + level, taxonomy='oa_topic', attribution='primary_topic', level=level),
                denominator=len(identifiers), missing=missing, limitations=[LIMITATIONS['role'], 'OA Topic 与 RW Subject 是独立分类；Top 100 不改变总体分母。']))
        field_year = Counter()
        for identifier in identifiers:
            field = works[identifier]['topic'].get('field') or {}
            if field.get('id'):
                field_year[(field.get('display_name') or field['id'], works[identifier]['publication_year'])] += 1
        chapters['fields'].append(chart('F2', population, 'linked_work_count',
            [count_row(f'{label}-{year}', f'{label} · {year}', count, len(identifiers), year=year, field=label)
             for (label, year), count in sorted(field_year.items()) if year >= 2000],
            population + ' · OA Field × 发表年', '学科关联记录集中在哪些队列？', scope=population_scope,
            denominator=len(identifiers), extras={'outside_display_range_works': sum(count for (label, year), count in field_year.items() if year < 2000)},
            limitations=[LIMITATIONS['rate'], '展示自 2000 年起的单元，更早记录另列范围外计数。此图是数量，不是学科队列比例。']))
        for mode in ('institution_country', 'authorship_country'):
            membership = {identifier: works[identifier]['countries'][mode]['countries'] for identifier in identifiers}
            counts, weights, coverage = associations(membership)
            rows = []
            for country, count in counts.most_common():
                rows.append(dict(count_row(country, country, count, len(identifiers)),
                    paper_coverage_pct=100 * count / len(identifiers) if identifiers else None,
                    association_share_pct=100 * count / coverage['association_total'],
                    fractional_work_count=round(weights[country], 6),
                    fractional_share_pct=100 * weights[country] / coverage['known_works']))
            chapters['geography'].append(chart('G1', population, 'linked_work_count', rows, population + ' · 国家关联分布',
                '按署名地点统计，各国关联多少候选作品？', scope=dict(population_scope, slice_id=population + '-' + mode, attribution=mode),
                denominator=len(identifiers), missing=coverage['unknown_works'], limitations=[LIMITATIONS['country']],
                extras={'association_summary': {key: value for key, value in coverage.items() if key != 'lorenz'}}))
            collaboration = Counter(works[identifier]['countries'][mode]['collaboration'] for identifier in identifiers)
            chapters['geography'].append(chart('G2', population, 'work_count', top_rows(collaboration, total=len(identifiers)),
                population + ' · 已观测跨国关联与完整性', '单一已知国家是否意味着完整的单国署名？',
                scope=dict(population_scope, slice_id=population + '-collaboration-' + mode, attribution=mode),
                denominator=len(identifiers), limitations=[LIMITATIONS['country'], '缺乏完整性证据时标为 completeness_unknown，不称为国内合作。']))
            if mode == 'institution_country':
                pairs = Counter(pair for countries in membership.values() for pair in combinations(sorted(set(countries)), 2))
                selected_countries = [country for country, count in counts.most_common(15)]
                pair_rows = [count_row(first + '-' + second, first + ' / ' + second, pairs[(first, second)],
                                      collaboration['multi_country_observed'], country_left=first, country_right=second)
                             for first, second in combinations(sorted(selected_countries), 2)]
                chapters['geography'].append(chart('G3', population, 'linked_work_count', pair_rows,
                    population + ' · 机构署名国家共同关联', '哪些国家对在同一作品上共同出现？',
                    scope=dict(population_scope, attribution=mode, selected_group_ids=selected_countries),
                    denominator=collaboration['multi_country_observed'],
                    limitations=[LIMITATIONS['country'], '每篇对同一国家对仅计一次；国家对计数可能重叠。固定展示关联数前 15 个国家，不推断不端合作。']))
        for dimension, chart_id in [('institutions', 'E1'), ('authors', 'E2')]:
            membership = {identifier: works[identifier][dimension] for identifier in identifiers}
            counts, weights, coverage = associations(membership)
            if dimension == 'institutions':
                labels = {member: label for identifier in identifiers for member, label in works[identifier]['institutions'].items()}
                rows = top_rows(counts, labels, len(identifiers), 50)
            else:
                bands = Counter('1' if count == 1 else '2' if count == 2 else '3–5' if count <= 5 else '6–10' if count <= 10 else '>10' for count in counts.values())
                rows = [dict(count_row(band, band + ' 篇关联作品', bands[band], len(counts)), unit='authors') for band in ('1', '2', '3–5', '6–10', '>10')]
            chapters['entities'].append(chart(chart_id, population, 'linked_work_count' if dimension == 'institutions' else 'author_repeat_band_count',
                rows, population + (' · 直接署名机构关联' if dimension == 'institutions' else ' · 作者重复关联分布'),
                '关联记录在研究实体之间如何分布？', scope=dict(population_scope, attribution='direct_work_' + dimension),
                denominator=len(identifiers), missing=coverage['unknown_works'], limitations=['身份消歧可能拆分或合并实体；关联不是不端责任认定。',
                '集中度使用全部正关联实体；未包含零关联实体。Top-k 的唯一作品覆盖与关联份额分别计算。'],
                extras={'association_summary': {key: value for key, value in coverage.items() if key != 'lorenz'}}))
            chapters['entities'].append(chart('E3', population, 'association_lorenz_pct', coverage['lorenz'],
                population + ' · ' + dimension + ' 关联集中度', '关联记录是否集中在少数实体？',
                scope=dict(population_scope, slice_id=population + '-lorenz-' + dimension, attribution='full_count_' + dimension),
                denominator=coverage['association_total'], limitations=['Lorenz/Gini 使用全部正关联实体；未包括零关联实体。它不衡量实体责任。'],
                extras={'gini': coverage['gini'], 'hhi': coverage['hhi']}))
            union_rows = [dict(count_row('union', 'Top-k 唯一作品覆盖', coverage['top_k_union_works'], len(identifiers)),
                              value=100 * coverage['top_k_union_works'] / len(identifiers) if identifiers else None, unit='percent'),
                          dict(count_row('associations', 'Top-k 关联份额', coverage['top_k_associations'], coverage['association_total']),
                               value=100 * coverage['top_k_associations'] / coverage['association_total'] if coverage['association_total'] else None, unit='percent')]
            chapters['entities'].append(chart('E4', population, 'coverage_and_association_pct', union_rows,
                population + ' · ' + dimension + ' Top-k 覆盖', '相加的关联次数覆盖了多少不同作品？',
                scope=dict(population_scope, slice_id=population + '-top-k-' + dimension, attribution='full_count_' + dimension),
                denominator=len(identifiers), limitations=['两个单元使用不同分母，不能相加。k=' + str(coverage['top_k'])]))
        sources, labels = Counter(), {}
        for identifier in identifiers:
            source = works[identifier]['source']
            if source.get('id'):
                sources[source['id']] += 1
                labels[source['id']] = source.get('display_name') or source['id']
        chapters['publishing'].append(chart('source-counts', population, 'linked_work_count', top_rows(sources, labels, len(identifiers), 50),
            population + ' · 主要发表来源关联', '记录关联哪些主要发表来源？', scope=dict(population_scope, attribution='primary_source'),
            denominator=len(identifiers), missing=len(identifiers) - sum(sources.values()),
            limitations=['包含不同来源类型；未将所有仓储位置当作期刊。尚未发布来源发文分母，因此不能解释为期刊撤稿率。']))
        citation_values = [works[identifier]['citations'] for identifier in identifiers if works[identifier]['citations'] is not None and works[identifier]['citations'] >= 0]
        bins = Counter('0' if value == 0 else '1–9' if value < 10 else '10–49' if value < 50 else '50–99' if value < 100 else '100+' for value in citation_values)
        citation_counts = Counter(citation_values)
        cumulative, citation_ecdf = 0, []
        values = sorted(citation_counts)
        stride = max(1, len(values) // 150)
        for index, value in enumerate(values):
            cumulative += citation_counts[value]
            if index % stride == 0 or index == len(values) - 1:
                citation_ecdf.append(dict(count_row(value, str(value) + ' 次引用', cumulative, len(citation_values)),
                                         value=100 * cumulative / len(citation_values), unit='percent', cited_by_count=value))
        chapters['citations'].append(chart('C1', population, 'citation_ecdf_pct', citation_ecdf,
            population + ' · 快照引用次数分布', '这些发表候选的已索引引用次数如何分布？', scope=population_scope,
            denominator=len(identifiers), missing=len(identifiers) - len(citation_values),
            limitations=['这是快照 cited_by_count；不同发表年龄有不同引用机会。零引用与缺失分别保留，不据此比较质量。'],
            extras={'quantiles': {'median': quantile(citation_values, .5), 'p90': quantile(citation_values, .9)},
                    'zero_citation_works': bins['0']}))
    reason_counts = Counter(reason for paper in papers for reason in paper['reasons'])
    reason_rows = [dict(count_row(reason, reason, count, len(papers)), value=100 * count / len(papers), unit='percent')
                   for reason, count in reason_counts.most_common()]
    chapters['reasons'].append(chart('R1', 'B', 'paper_coverage_pct', reason_rows, 'RW 原始原因标签的论文覆盖比例',
        '哪些原因标签被记录得更多？', scope={'attribution': 'rw_raw_reasons_union', 'corpus': 'rw', 'work_types': ['all'], 'observation_cutoff': rw_date},
        denominator=len(papers), missing=sum(not paper['reasons'] for paper in papers), limitations=[LIMITATIONS['reason']]))
    reason_combinations = Counter(tuple(paper['reasons']) for paper in papers if paper['reasons'])
    unknown_reasons = sum(not paper['reasons'] for paper in papers)
    top_combinations = reason_combinations.most_common(10)
    combination_rows = [count_row(index, ' + '.join(labels), count, len(papers), reason_labels=list(labels))
                        for index, (labels, count) in enumerate(top_combinations)]
    combination_rows.append(count_row('other', 'Other · 其余互斥组合', len(papers) - unknown_reasons - sum(count for label, count in top_combinations), len(papers)))
    combination_rows.append(count_row('unknown', 'Unknown · 原因缺失', unknown_reasons, len(papers)))
    chapters['reasons'].append(chart('R3', 'B', 'work_count', combination_rows, '完整原因标签组合', '多标签原因如何共同出现？',
        denominator=len(papers), limitations=[LIMITATIONS['reason'], '每篇论文仅贡献一个完整组合；此切片使用原始标签，项目原因族为独立版本化切片。']))
    by_work = defaultdict(list)
    for paper in papers:
        selected = matches[paper['id']]['selected_id']
        if selected and eligible(works[selected]):
            by_work[selected].append(paper)
    field_members, field_reasons, field_missing, field_labels = Counter(), Counter(), Counter(), {}
    source_months, source_lags, source_labels = Counter(), defaultdict(list), {}
    event_scope_works = 0
    for identifier, linked in by_work.items():
        work = works[identifier]
        reasons = set().union(*(set(paper['reasons']) for paper in linked))
        field = work['topic'].get('field') or {}
        if field.get('id'):
            field_id = field['id']
            field_members[field_id] += 1
            field_labels[field_id] = field.get('display_name') or field_id
            field_missing[field_id] += not reasons
            for reason in reasons:
                field_reasons[(field_id, reason)] += 1
        source = work['source']
        events = sorted(paper['retracted'] for paper in linked if paper['retracted'])
        if events and events[0] >= '2021-01-01':
            event_scope_works += 1
        if source.get('id'):
            source_id = source['id']
            source_labels[source_id] = source.get('display_name') or source_id
            if events and events[0] >= '2021-01-01':
                source_months[(source_id, events[0][:7])] += 1
            lag_values = {paper['lag_days'] for paper in linked if paper['lag_days'] is not None}
            if len(lag_values) == 1:
                source_lags[source_id].append(next(iter(lag_values)))
    selected_reasons = [reason for reason, count in reason_counts.most_common(10)]
    reason_field_rows = []
    for field_id, count in field_members.most_common():
        for reason in selected_reasons:
            numerator = field_reasons[(field_id, reason)]
            reason_field_rows.append(dict(count_row(field_id + '-' + reason, field_labels[field_id] + ' · ' + reason, numerator, count),
                value=100 * numerator / count, unit='percent', field=field_labels[field_id], reason=reason,
                missing_reason_works=field_missing[field_id]))
    chapters['reasons'].append(chart('R2', 'C', 'reason_given_field_pct', reason_field_rows,
        'OA Field 内的 RW 原始原因标签比例', '各学科匹配作品中，哪些原始原因标签被记录？',
        scope={'corpus': 'core', 'work_types': ['article'], 'attribution': 'primary_field_raw_reason_union', 'observation_cutoff': rw_date},
        denominator=len(by_work), limitations=[LIMITATIONS['reason'], LIMITATIONS['source'],
            '先固定 B 中最常见的 10 个原始标签；不是已审定的原因族。每个学科分母包括原因缺失的匹配作品。']))
    reason_lags = defaultdict(list)
    for paper in papers:
        if paper['lag_days'] is not None:
            for reason in paper['reasons']:
                reason_lags[reason].append(paper['lag_days'])
    lag_rows = []
    for reason in selected_reasons:
        values = reason_lags[reason]
        enough = len(values) >= 20
        lag_rows.append(dict(count_row(reason, reason, len(values), len(papers)),
            value=quantile(values, .5) / 365.25 if enough else None, unit='years',
            p25=quantile(values, .25) / 365.25 if enough else None,
            p75=quantile(values, .75) / 365.25 if enough else None, small_base=not enough))
    chapters['reasons'].append(chart('R4', 'B', 'median_lag_years', lag_rows, '原始原因标签的时滞分布',
        '已有撤稿记录中，不同标签对应的时滞如何分布？',
        scope={'attribution': 'rw_raw_reasons_union', 'corpus': 'rw', 'work_types': ['all'], 'observation_cutoff': rw_date},
        denominator=len(papers), limitations=[LIMITATIONS['reason'], '点为中位数，线段为 P25–P75；不是置信区间。n<20 不显示区间；多标签组不独立。']))
    source_event_counts = Counter()
    for (source_id, month), count in source_months.items():
        source_event_counts[source_id] += count
    popular_sources = [identifier for identifier, count in source_event_counts.most_common(10)]
    month_rows = [count_row(source_id + '-' + month, source_labels[source_id] + ' · ' + month, count, event_scope_works,
                           source=source_labels[source_id], month=month)
                  for (source_id, month), count in sorted(source_months.items()) if source_id in popular_sources]
    chapters['publishing'].append(chart('P2', 'C', 'work_count', month_rows, '主要来源的首次记录撤稿月份',
        '撤稿记录在来源与月份上如何集中？', scope={'corpus': 'core', 'work_types': ['article'],
        'attribution': 'primary_source', 'observation_cutoff': rw_date, 'event_date_range': ['2021-01-01', rw_date]},
        denominator=event_scope_works, missing=event_scope_works - sum(source_months.values()),
        limitations=[LIMITATIONS['event'], '展示 2021 年起记录最多的 10 个来源；分母是该事件日期范围内的 C 作品，不重算为 Top-10。未执行突发检测，峰值不证明原因。']))
    publisher_lags = []
    for source_id, values in sorted(source_lags.items(), key=lambda item: (-len(item[1]), item[0]))[:10]:
        enough = len(values) >= 20
        publisher_lags.append(dict(count_row(source_id, source_labels[source_id], len(values), len(by_work)),
            value=quantile(values, .5) / 365.25 if enough else None, unit='years',
            p25=quantile(values, .25) / 365.25 if enough else None,
            p75=quantile(values, .75) / 365.25 if enough else None, small_base=not enough))
    chapters['publishing'].append(chart('P3', 'C', 'median_lag_years', publisher_lags,
        '主要来源的 RW 记录时滞', '不同来源关联样本的时滞如何分布？', scope={'corpus': 'core', 'work_types': ['article'],
        'attribution': 'primary_source_rw_dates', 'observation_cutoff': rw_date}, denominator=len(by_work),
        limitations=['使用 RW 有效原论文/事件日期；同一 OA 作品的时滞有冲突时排除。未按发表年龄和学科调整，不称为编辑效率排名。']))
    if dimension_rows:
        dimension_denominators = Counter()
        dimension_known_works = Counter()
        for dimension, identifier, kind, year, count, weight in dimension_rows:
            if identifier is not None and kind == 'article' and year >= 2000:
                dimension_denominators[(dimension, identifier)] += count
                dimension_known_works[dimension] += weight
        scope_denominator = sum(count for (kind, year), count in denominators.items() if kind == 'article' and year >= 2000)
        field_labels = {work['topic']['field']['id']: work['topic']['field'].get('display_name') or work['topic']['field']['id']
                        for work in works.values() if (work['topic'].get('field') or {}).get('id')}
        journal_labels = {work['source']['id']: work['source'].get('display_name') or work['source']['id']
                          for work in works.values() if work['source'].get('id')}
        journal_counts = Counter(works[identifier]['source']['id'] for identifier in a1
                                if works[identifier]['publication_year'] >= 2000 and works[identifier]['source'].get('type') == 'journal'
                                and works[identifier]['source'].get('id'))
        selected_journals = [identifier for identifier, count in journal_counts.most_common(20)]
        for population, identifiers in [('A1_over_D', a1), ('C_D_over_D', cd)]:
            numerators = Counter()
            for identifier in identifiers:
                work = works[identifier]
                if work['publication_year'] < 2000:
                    continue
                field = work['topic'].get('field') or {}
                if field.get('id'):
                    numerators[('field', field['id'])] += 1
                source = work['source']
                if source.get('id') and source.get('type') == 'journal':
                    numerators[('journal', source['id'])] += 1
                for country in work['countries']['institution_country']['countries']:
                    numerators[('institution_country', country)] += 1
            metric = 'oa_flagged_cohort_per_10k' if population == 'A1_over_D' else 'rw_recorded_cohort_per_10k'
            for dimension, section, chart_id, labels, title in [
                ('field', 'fields', 'F3', field_labels, 'OA Field 发文规模与观测比例'),
                ('institution_country', 'geography', 'G1', {}, '机构署名国家的队列比例'),
                ('journal', 'publishing', 'P1', journal_labels, '固定期刊比较集的队列比例'),
            ]:
                rows = []
                for (key, identifier), denominator in dimension_denominators.items():
                    if key != dimension or (dimension == 'journal' and identifier not in selected_journals):
                        continue
                    numerator = numerators[(dimension, identifier)]
                    if numerator > denominator:
                        raise ValueError('Dimension numerator exceeds identical-scope denominator')
                    rows.append(dict(count_row(identifier, labels.get(identifier, identifier), numerator, denominator),
                                     **cohort_rate(numerator, denominator), unit='per_10k'))
                rows.sort(key=lambda row: (-row['numerator'], row['id']))
                scope = dict(common_scope, slice_id=population + '-' + dimension + '-2000',
                             publication_year_range=[2000, int(oa_date[:4])], attribution=dimension)
                if dimension == 'journal':
                    scope['selected_group_ids'] = selected_journals
                chapters[section].append(chart(chart_id, population, metric, rows, population + ' · ' + title,
                    '控制同口径发文数量后，数量和比例有何不同？', scope=scope,
                    denominator=sum(row['denominator'] for row in rows) if dimension == 'journal' else scope_denominator,
                    missing=0 if dimension == 'journal' else scope_denominator - round(dimension_known_works[dimension]),
                    limitations=[LIMITATIONS['rate'], '所有单元使用 core article、2000 年起的发表队列；未做学科/时代调整，不解释为固有风险。',
                                 '固定期刊集由 A1 关联数前 20 个 journal 来源选定；不是全体期刊比例排名。' if dimension == 'journal' else '国家全计数分母可重叠；选择国家不重新分配权重。' if dimension == 'institution_country' else '未分类作品不进入已知 Field 单元。']))
                if dimension == 'field':
                    rankable = [row for row in rows if row['ranking_eligible']]
                    count_rank = {row['id']: index for index, row in enumerate(sorted(rankable, key=lambda row: (-row['numerator'], row['id'])), 1)}
                    rate_rank = {row['id']: index for index, row in enumerate(sorted(rankable, key=lambda row: (-row['value'], row['id'])), 1)}
                    rank_rows = [dict(row, count_rank=count_rank[row['id']], proportion_rank=rate_rank[row['id']]) for row in rankable]
                    chapters['fields'].append(chart('F4', population, metric, rank_rows, population + ' · 数量与比例顺序',
                        '在同一个可排名学科集合中，发文规模校正是否改变顺序？', scope=dict(scope, slice_id=population + '-rank-2000'),
                        limitations=[LIMITATIONS['rate'], '仅 n≥20 且 N≥1,000 的完整学科集合；数值并列时按稳定 ID 排序，不表示统计上存在差异。']))
    chapters['reasons'] = reason_family_charts(papers, by_work, works, rw_date, chart, count_row) + chapters['reasons']
    publisher_results, publisher_ready = publisher_charts(validation_path, works, a1, cd, by_work,
        dimension_rows, oa_date, rw_date, chart, count_row)
    chapters['publishing'].extend(publisher_results)
    incoming_results, incoming = citation_charts(release_dir, provenance, entries, works, chart, by_work)
    chapters['citations'].extend(incoming_results)
    supplementary, supplement = supplement_charts(release_dir, provenance, entries, denominators, flagged, oa_date, chart, count_row)
    for section, results in supplementary.items():
        chapters[section].extend(results)
    for section, results in extended_charts(papers, works, a1, by_work, oa_date, rw_date, chart, count_row).items():
        chapters[section].extend(results)
    unavailable = {
        'reasons': [],
        'fields': [] if dimension_rows else [('F3', '学科规模与比例', '学科分母未计算。'), ('F4', '数量与比例排名', '学科分母未计算。')],
        'geography': [],
        'publishing': [] if dimension_rows else [('P1', '期刊队列比例', '期刊分母尚未计算。')],
        'citations': [] if incoming else [('C2', '引用事件时间', '尚未扫描 incoming citation edges。'), ('C3', '撤稿后引用比例', '尚未扫描 incoming citation edges，不能显示为零。'), ('C4', '1/3/5 年引用持续', '尚未扫描 incoming citation edges 或验证完整随访。')],
    }
    for section, specifications in unavailable.items():
        for chart_id, title, reason in specifications:
            chapters[section].append(chart(chart_id, 'unavailable', 'not_computed', [], title, title,
                                            status='not_computed', unavailable_reason=reason))
    manifest = {
        'schema_version': 3, 'release_id': release_id, 'status': 'ready', 'delivery_phase': 'S3_incoming_citations' if incoming else 'S2_joined_cohort_report',
        'oa_snapshot_date': oa_date, 'oa_source_prefix': validation['source_prefix'], 'oa_manifest_sha256': validation['manifest_sha256'],
        **{key: provenance['rw'][key] for key in ('rw_snapshot_date', 'rw_source_commit', 'rw_csv_sha256')},
        'pipeline_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
        'pipeline_source_sha256': provenance['config']['pipeline_sha256'], 'config_sha256': report_config_hash,
        'scan_config_sha256': provenance['config_sha256'], 'report_builder_source_sha256': report_source_hash,
        'dimension_builder_source_sha256': dimension_version,
        'extension_source_sha256': extension_hashes,
        'burst_policy_sha256': burst_policy_hash,
        'supplement_scan': {key: supplement[key] for key in ('config_sha256', 'code_sha256', 'targets_sha256', 'files')} if supplement else None,
        'incoming_citation_scan': {key: incoming[key] for key in ('config_sha256', 'code_sha256', 'targets_sha256', 'files', 'targets', 'edges', 'citing_corpus')} if incoming else None,
        'schema_adapter_version': validation['schema_adapter_version'], 'role_policy_version': ROLE_POLICY,
        'reason_mapping_version': REASON_VERSION, 'country_attribution_mode': 'institution_country',
        'corpus': 'core', 'metric_observation_cutoff': oa_date, 'generated_at': now(),
        'source_acceptance_policy': validation['source_acceptance_policy'], 'transfer_provenance_status': validation['transfer_provenance']['status'],
        'capabilities': {'descriptive': True, 'publication_year_denominators': True, 'dimension_denominators': bool(dimension_rows),
                         'incoming_citations': bool(incoming), 'reason_families': True, 'publisher_rollups': publisher_ready,
                         'additional_denominators': bool(supplement), 'fixed_publication_followup': bool(supplement),
                         'monthly_descriptive_control': True, 'any_topic': True,
                         'historical_publisher_ownership': False, 'author_career': False,
                         'adjusted_or_causal_models': False, 'funding_exploration': False,
                         'self_citation_exclusion': False},
        'source_accounting': validation['source_accounting'],
        'quality_gates': {'source_validation': True, 'unique_work_ids': True, 'role_screening': True,
                          'numerator_subset_denominator': True, 'rw_reconciliation': True, 'fractional_conservation': True},
        'source_quality': dict(quality_counts), 'corpus_counts': dict(corpus_counts), 'files': [], 'supported_slices': [],
        'limitations': [LIMITATIONS['source'], LIMITATIONS['role'], LIMITATIONS['rate'],
                       '项目负责人接受回溯验证；下载前 manifest 与传输时间日志缺失，不声称完成历史传输原子性证明。'],
    }
    report_dir = release_dir / 'report'
    if incoming:
        manifest['quality_gates'].update(incoming_edge_partition=True, calendar_followup=True)
        atomic_json(release_dir / 'citation-summary.json', incoming['summary'])
    if supplement:
        manifest['quality_gates']['supplement_reproduces_D_A1'] = True
    for filename, captured in [('citations-complete.json', citation_marker), ('supplement-complete.json', supplement_marker)]:
        path = release_dir / filename
        current = json.loads(path.read_text()) if path.exists() else None
        if (current or {}).get('config_sha256') != (captured or {}).get('config_sha256'):
            raise ValueError('Completed scan changed during report generation')
    if digest((Path(__file__).resolve().parents[1] / 'data/reference/snapshot-burst-policy-v1.json').read_bytes()) != burst_policy_hash:
        raise ValueError('Burst policy changed during generation')
    if digest(Path(__file__).read_bytes()) != report_source_hash:
        raise ValueError('Report code changed during generation; rerun before publication')
    if any(digest(Path(__file__).with_name(name + '.py').read_bytes()) != value for name, value in extension_hashes.items()):
        raise ValueError('Report extension changed during generation')
    for section, charts in chapters.items():
        for item in charts:
            item.update(schema_version=3, release_id=release_id, oa_snapshot_date=oa_date,
                        rw_snapshot_date=rw_date, metric_observation_cutoff=item['scope'].get('observation_cutoff', rw_date if item['population_key'] == 'B' else oa_date))
            item['scope'].setdefault('corpus', 'rw' if item['population_key'] == 'B' else 'core')
            item['scope'].setdefault('work_types', ['all'])
            item['scope'].setdefault('attribution', 'unique_work')
            item['scope'].setdefault('observation_cutoff', rw_date if item['population_key'] == 'B' else oa_date)
            for insight in item['insights']:
                insight['release_id'] = release_id
            manifest['supported_slices'].append({'chart_id': item['chart_id'], 'slice_id': item['slice_id'], 'section': section, 'status': item['status']})
        chunk = {'schema_version': 3, 'release_id': release_id, 'section': section, 'charts': charts}
        raw = json.dumps(compact_numbers(chunk), ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode()
        atomic_bytes(report_dir / (section + '.json'), raw)
        manifest['files'].append({'path': 'data/snapshot/' + section + '.json', 'bytes': len(raw), 'sha256': digest(raw)})
    atomic_bytes(report_dir / 'manifest.json', json.dumps(manifest, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode())
    print('Built local aggregate report: ' + str(report_dir))
    return report_dir


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('release_dir', type=Path)
    build(parser.parse_args().release_dir)
