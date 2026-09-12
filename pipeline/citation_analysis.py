"""Calendar-window summaries of validated incoming citation shards."""

from collections import Counter, defaultdict
import calendar
import datetime as dt
from functools import lru_cache
import json
from pathlib import Path

import pyarrow.parquet as pq

from .snapshot import quantile
from .validate_snapshot import digest


@lru_cache(maxsize=65536)
def date_interval(value, year=None):
    try:
        if value:
            text = str(value)
            if len(text) == 4:
                return dt.date(int(text), 1, 1), dt.date(int(text), 12, 31)
            if len(text) == 7:
                parsed_year, month = map(int, text.split('-'))
                return dt.date(parsed_year, month, 1), dt.date(parsed_year, month, calendar.monthrange(parsed_year, month)[1])
            parsed = dt.date.fromisoformat(text)
            return parsed, parsed
        if year and 1 <= year <= 9999:
            return dt.date(year, 1, 1), dt.date(year, 12, 31)
    except (ValueError, TypeError):
        pass
    return None


def classify(citing, event):
    if citing is None or event is None:
        return 'undated'
    if citing[1] < event[0]:
        return 'before'
    if citing[0] > event[1]:
        return 'after'
    return 'ambiguous'


def anniversary(date, years):
    year = date.year + years
    return date.replace(year=year, day=min(date.day, calendar.monthrange(year, date.month)[1]))


def windows(target, cutoff):
    event = date_interval(target['event_date'])
    publication = date_interval(target['publication_date'], target['publication_year'])
    if not event or event[0] != event[1] or event[1] > cutoff or not publication or publication[1] > event[0]:
        return {}, {}
    center = event[0]
    annual, fixed = {}, {}
    for offset in range(-5, 5):
        if not 1 <= center.year + offset <= 9998:
            continue
        start, end = anniversary(center, offset), anniversary(center, offset + 1)
        if offset >= 0:
            start += dt.timedelta(days=1)
            end += dt.timedelta(days=1)
        if publication[1] <= start and end - dt.timedelta(days=1) <= cutoff:
            annual[offset] = (start, end)
    for years in (1, 3, 5):
        if center.year + years <= 9999 and anniversary(center, years) <= cutoff:
            fixed[years] = (center + dt.timedelta(days=1), anniversary(center, years) + dt.timedelta(days=1))
    return annual, fixed


def summarize(targets, edge_batches, cutoff, static_counts=None, fields=None, excluded_citing_ids=None):
    cutoff = dt.date.fromisoformat(cutoff)
    static_counts, fields = static_counts or {}, fields or {}
    excluded_citing_ids = excluded_citing_ids or set()
    targets = {target['target_id']: target for target in targets}
    active = {key: target for key, target in targets.items() if not target['event_after_cutoff']}
    prepared = {key: windows(target, cutoff) for key, target in active.items()}
    annual_counts, fixed_counts = Counter(), Counter()
    states, coarse, filtered, field_states, totals = Counter(), Counter(), Counter(), defaultdict(Counter), Counter()
    future = 0
    for batch in edge_batches:
        for edge in batch:
            identifier = edge['target_id']
            if identifier not in targets:
                raise ValueError('Incoming edge outside target set')
            totals[identifier] += 1
            if identifier not in active:
                continue
            target = active[identifier]
            citing = date_interval(edge['publication_date'], edge['publication_year'])
            if citing and citing[1] > cutoff:
                citing = None
                future += 1
            event = date_interval(target['event_date'])
            state = classify(citing, event)
            states[state] += 1
            field_states[fields.get(identifier, 'Unknown')][state] += 1
            if edge['type'] in {'article', 'review'} and edge.get('citing_id') not in excluded_citing_ids:
                filtered[state] += 1
            coarse_event = date_interval(str(event[0].year)) if event else None
            coarse_citing = date_interval(str(citing[0].year)) if citing else None
            coarse[classify(coarse_citing, coarse_event)] += 1
            if not citing:
                continue
            annual, fixed = prepared[identifier]
            for offset, (start, end) in annual.items():
                if start <= citing[0] and citing[1] < end:
                    annual_counts[(identifier, offset)] += 1
            for years, (start, end) in fixed.items():
                if start <= citing[0] and citing[1] < end:
                    fixed_counts[(identifier, years)] += 1
    annual_rows = []
    for offset in range(-5, 5):
        eligible = [identifier for identifier, (annual, fixed) in prepared.items() if offset in annual]
        total = sum(annual_counts[(identifier, offset)] for identifier in eligible)
        annual_rows.append({'id': str(offset), 'label': f'{offset} 至 {offset + 1} 年', 'relative_year': offset,
            'numerator': total, 'denominator': len(eligible), 'value': total / len(eligible) if eligible else None,
            'unit': 'edges_per_target', 'excluded_targets': len(active) - len(eligible)})
    fixed_rows = []
    common = {identifier for identifier, (annual, fixed) in prepared.items() if 5 in fixed}
    for mode in ('common_5y', 'window_specific'):
        for years in (1, 3, 5):
            eligible = sorted(common if mode == 'common_5y' else
                              {identifier for identifier, (annual, fixed) in prepared.items() if years in fixed})
            counts = [fixed_counts[(identifier, years)] for identifier in eligible]
            fixed_rows.append({'id': f'{mode}-{years}', 'label': f'{years} 年', 'window_years': years, 'cohort_mode': mode,
                'numerator': sum(counts), 'denominator': len(eligible), 'value': sum(counts) / len(counts) if counts else None,
                'unit': 'edges_per_target', 'median': quantile(counts, .5), 'p25': quantile(counts, .25),
                'p75': quantile(counts, .75), 'targets_with_edges': sum(count > 0 for count in counts),
                'targets_with_edges_pct': 100 * sum(count > 0 for count in counts) / len(counts) if counts else None,
                'excluded_targets': len(active) - len(eligible)})
    common_rows = [row for row in fixed_rows if row['cohort_mode'] == 'common_5y']
    if len({row['denominator'] for row in common_rows}) > 1 or any(
            first['numerator'] > second['numerator'] for first, second in zip(common_rows, common_rows[1:])):
        raise ValueError('Common-cohort persistence is inconsistent')
    audit = Counter()
    for identifier in targets:
        stored = static_counts.get(identifier)
        audit['rebuilt_edges'] += totals[identifier]
        if stored is None:
            audit['static_missing_targets'] += 1
        else:
            audit['static_count_sum'] += stored
            audit['equal_targets' if stored == totals[identifier] else 'different_targets'] += 1
            audit['absolute_count_difference_sum'] += abs(stored - totals[identifier])
    if sum(states.values()) != sum(totals[key] for key in active):
        raise ValueError('Temporal categories do not partition edges')
    return {'target_count': len(active), 'all_targets': len(targets), 'later_event_targets_excluded': len(targets)-len(active),
        'event_unavailable_targets': sum(not target['event_date'] for target in active.values()),
        'event_conflict_targets': sum(target['event_date_conflict'] for target in active.values()),
        'future_or_cutoff_overlapping_citing_dates': future, 'states': dict(states), 'coarse_states': dict(coarse),
        'article_review_states': dict(filtered), 'field_states': dict(field_states), 'annual': annual_rows,
        'fixed': fixed_rows, 'static_audit': dict(audit)}


def build_charts(release_dir, provenance, entries, works, chart, expected_targets=None):
    path = Path(release_dir) / 'citations-complete.json'
    if not path.exists():
        return [], None
    marker = json.loads(path.read_text())
    if marker['scan_config_sha256'] != provenance['config_sha256'] or marker['files'] != len(entries):
        raise ValueError('Citation scan uses incomplete or different source')
    directory = Path(marker['directory'])
    targets = json.loads((directory / 'targets.json').read_text())
    if expected_targets is not None and {target['target_id'] for target in targets} != set(expected_targets):
        raise ValueError('Citation target population differs from the current matched cohort')
    if digest(json.dumps(targets, sort_keys=True).encode()) != marker['targets_sha256']:
        raise ValueError('Citation targets changed')

    def batches():
        count = 0
        for entry in entries:
            key = digest(entry['key'].encode())
            shard = directory / (key + '.parquet')
            checkpoint = json.loads((directory / (key + '.json')).read_text())
            if (checkpoint['config_sha256'] != marker['config_sha256'] or
                checkpoint['source_fingerprint'] != digest(json.dumps(entry, sort_keys=True).encode()) or
                checkpoint['output_sha256'] != digest(shard.read_bytes())):
                raise ValueError('Citation shard integrity failed')
            for batch in pq.ParquetFile(shard).iter_batches(batch_size=8192):
                count += batch.num_rows
                yield batch.to_pylist()
        if count != marker['edges']:
            raise ValueError('Citation edge accounting failed')

    validation = json.loads(Path(provenance['validation_report']).read_text())
    result = summarize(targets, batches(), validation['oa_snapshot_date'],
        {key: work.get('citations') for key, work in works.items()},
        {key: (work['topic'].get('field') or {}).get('display_name', 'Unknown') for key, work in works.items()},
        {key for key, work in works.items() if work['document_role'] in {'known_notice', 'conflict', 'suspected_notice'}})
    scope = {'corpus': 'core', 'work_types': ['article'], 'citing_corpus': 'all', 'citing_work_types': ['all'],
        'attribution': 'distinct_incoming_pairs', 'observation_cutoff': validation['oa_snapshot_date'],
        'date_precision': 'reported_day_with_year_interval_sensitivity', 'event_policy': 'unique_first_rw_event_across_matched_originals'}
    limitations = ['引用来自全量快照 referencing works 的去重入边，不是目标论文的 outgoing references。',
        '发表日期仅为引用时间代理；源日期原始精度不可恢复。默认按报告日，另列双方日期扩展到整年的敏感性。',
        '引用可用于批评或报告撤稿，不表示认同；这些描述不估计撤稿的因果影响。',
        '引用边不完整，零表示在已扫描图中未观察到；晚于快照或跨截止日的引用日期计入 undated。']
    charts = [chart('C2', 'C', 'mean_incoming_edges', result['annual'], '撤稿事件前后的可观察引用',
        '每个完整相对年度内，合格目标平均收到多少条引用？', scope=dict(scope, slice_id='C-incoming-relative-years'),
        denominator=result['target_count'], limitations=limitations + ['每个年度分母不同；要求目标已发表且整个窗口结束。跨窗口的粗日期不硬分配。同日不分入前后。'],
        extras={'citation_quality': {key: result[key] for key in ('all_targets', 'later_event_targets_excluded', 'event_unavailable_targets', 'event_conflict_targets')}})]
    labels = {'before': '明确之前', 'after': '明确之后', 'ambiguous': '日期重叠 / 同日', 'undated': '日期不可用'}
    for mode, counts in [('reported_day', result['states']), ('year_interval_sensitivity', result['coarse_states']),
                         ('citing_article_review', result['article_review_states'])]:
        total = sum(counts.values())
        rows = [{'id': state, 'label': label, 'numerator': counts.get(state, 0), 'denominator': total,
                 'value': counts.get(state, 0), 'unit': 'edges'} for state, label in labels.items()]
        classifiable = counts.get('before', 0) + counts.get('after', 0)
        ratio = {'numerator': counts.get('after', 0), 'denominator': classifiable,
                 'value': counts.get('after', 0) / classifiable if classifiable else None}
        charts.append(chart('C3', 'C', 'incoming_edge_count', rows, '引用时序可判定性 · ' + mode,
            '有多少观测引用在撤稿之前、之后，或无法判定？', scope=dict(scope, slice_id='C-incoming-' + mode,
                date_precision='both_dates_full_year_intervals' if mode == 'year_interval_sensitivity' else 'reported_day_or_available_year',
                citing_role_policy=('exclude_evidenced_independent_notices' if provenance['config']['role_policy'] == 'original-first-independent-notices-v2' else 'exclude_selected_known_conflict_suspected_notices') if mode == 'citing_article_review' else 'all_roles',
                citing_work_types=['article', 'review'] if mode == 'citing_article_review' else ['all']),
            denominator=result['target_count'], limitations=limitations,
            extras={'post_retraction_citation_ratio': ratio, 'static_count_audit': result['static_audit']}))
    field_rows = []
    for field, counts in sorted(result['field_states'].items()):
        classifiable = counts.get('before', 0) + counts.get('after', 0)
        field_rows.append({'id': field, 'label': field, 'numerator': counts.get('after', 0), 'denominator': classifiable,
            'value': 100 * counts.get('after', 0) / classifiable if classifiable else None, 'unit': 'percent',
            **{state: counts.get(state, 0) for state in labels}})
    charts.append(chart('C3', 'C', 'post_retraction_citation_pct', field_rows, '各 Field 的可判定边中撤稿后比例',
        '同时显示日期模糊和缺失时，各 Field 的观测边构成如何？',
        scope=dict(scope, slice_id='C-incoming-field', attribution='primary_field'), denominator=result['target_count'],
        limitations=limitations + ['比例为 after/(before+after)，不是除以静态 cited_by_count；无可判定边时为 null。']))
    for mode in ('common_5y', 'window_specific'):
        rows = [row for row in result['fixed'] if row['cohort_mode'] == mode]
        charts.append(chart('C4', 'C', 'mean_incoming_edges', rows, '撤稿后 1 / 3 / 5 年引用 · ' + mode,
            '完整随访目标中，后续引用的均值、中位数和非零覆盖如何？', scope=dict(scope, slice_id='C-incoming-' + mode,
                cohort_mode=mode), denominator=result['target_count'], limitations=limitations + [
                'common_5y 为共同满足五年随访的同一目标集合；window_specific 各窗分母不同，不连成增长曲线。',
                '使用日历周年；事件日排除、周年日纳入。跨边界粗日期不纳入固定窗，n 包含观测零引用目标。']))
    return charts, dict(marker, summary=result)
