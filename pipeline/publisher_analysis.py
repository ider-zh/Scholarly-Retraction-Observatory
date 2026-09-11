"""Current publisher rollups through validated journal source identities."""

from collections import Counter, defaultdict
import json
from pathlib import Path

import pyarrow.parquet as pq

from .snapshot import cohort_rate, quantile


def parent_root(identifier, publishers):
    seen = set()
    while identifier in publishers and identifier not in seen:
        seen.add(identifier)
        parent = (publishers[identifier].get('parent_publisher') or {}).get('id')
        if not parent:
            return identifier
        identifier = parent
    return None


def dictionaries(validation_path):
    validation_path = Path(validation_path)
    validation = json.loads(validation_path.read_text())
    entries = json.loads((validation_path.parent / 'files.json').read_text())
    result = {'sources': {}, 'publishers': {}}
    for entry in entries:
        entity = entry['entity']
        if entity not in result:
            continue
        path = Path(validation['snapshot_dir']) / entry['key']
        stat = path.stat()
        if stat.st_size != entry['actual_bytes'] or stat.st_mtime_ns != entry['mtime_ns']:
            raise ValueError('Entity dictionary changed after validation')
        columns = ['id', 'display_name', 'type', 'host_organization'] if entity == 'sources' else ['id', 'display_name', 'parent_publisher']
        for batch in pq.ParquetFile(path).iter_batches(columns=columns):
            for row in batch.to_pylist():
                if row['id'] in result[entity]:
                    raise ValueError('Duplicate dictionary identity')
                result[entity][row['id']] = row
    return result['sources'], result['publishers']


def build_charts(validation_path, works, a1, cd, by_work, dimensions, oa_date, rw_date, chart, count_row):
    sources, publishers = dictionaries(validation_path)
    if not sources or not publishers:
        return [], False
    charts = []
    labels = {identifier: row.get('display_name') or identifier for identifier, row in publishers.items()}
    for mode in ('immediate_publisher', 'root_publisher'):
        mapping = {}
        for identifier, source in sources.items():
            host = source.get('host_organization')
            if source['type'] == 'journal' and host in publishers:
                mapping[identifier] = host if mode == 'immediate_publisher' else parent_root(host, publishers)

        def member(identifier):
            source = works[identifier]['source']
            return mapping.get(source.get('id')) if source.get('type') == 'journal' else None

        scope = {'corpus': 'core', 'work_types': ['article'], 'attribution': mode,
                 'source_type': 'journal', 'ownership_basis': 'snapshot_current_not_historical', 'observation_cutoff': oa_date}
        limitations = ['仅验证为 publisher 实体的 journal 主来源宿主；仓储机构不当作出版商。',
            '当前快照归属不等于发表或撤稿时所有权，不能据此归责；缺失/循环/不完整父链不猜测。',
            '直接出版商与根集团为独立模式，每篇在同一模式最多贡献一次。']
        for population, identifiers in [('A1', a1), ('C', set(by_work))]:
            counts = Counter(member(identifier) for identifier in identifiers)
            known = sorted((key for key in counts if key), key=lambda key: (-counts[key], key))[:20]
            rows = [count_row(key, labels[key], counts[key], len(identifiers)) for key in known]
            charts.append(chart('publisher-counts', population, 'linked_work_count', rows, population+' · '+mode+' 关联作品',
                '按当前快照归属，哪些出版商关联更多候选作品？', scope=dict(scope, slice_id=population+'-'+mode,
                observation_cutoff=rw_date if population == 'C' else oa_date), denominator=len(identifiers),
                missing=counts[None], limitations=limitations))
        denominators = Counter()
        for dimension, source_id, kind, year, total, weight in dimensions:
            if dimension == 'journal' and kind == 'article' and year >= 2000 and mapping.get(source_id):
                denominators[mapping[source_id]] += total
        selected_counts = Counter(member(identifier) for identifier in a1 if works[identifier]['publication_year'] >= 2000)
        selected = sorted((key for key in selected_counts if key), key=lambda key: (-selected_counts[key], key))[:20]
        for population, identifiers in [('A1_over_D', a1), ('C_D_over_D', cd)]:
            numerators = Counter(member(identifier) for identifier in identifiers if works[identifier]['publication_year'] >= 2000)
            rows = []
            for identifier in selected:
                numerator, denominator = numerators[identifier], denominators[identifier]
                if numerator > denominator:
                    raise ValueError('Publisher numerator exceeds journal denominator')
                rows.append(dict(count_row(identifier, labels[identifier], numerator, denominator),
                                 **cohort_rate(numerator, denominator), unit='per_10k'))
            if dimensions:
                charts.append(chart('P1', population, 'oa_flagged_cohort_per_10k' if population == 'A1_over_D' else 'rw_recorded_cohort_per_10k',
                    rows, population+' · '+mode+' 队列比例', '固定出版商比较集中，同口径发文分母下的观测比例如何？',
                    scope=dict(scope, slice_id=population+'-'+mode+'-2000', publication_year_range=[2000, int(oa_date[:4])],
                        selected_group_ids=selected), denominator=sum(denominators[key] for key in selected),
                    limitations=limitations + ['固定集按 A1 数量取前 20，不是全体出版商的比例排名；分母由相同 journal Work 队列合并，不用实体 works_count。']))
        lags = defaultdict(list)
        for identifier, linked in by_work.items():
            values = {paper['lag_days'] for paper in linked}
            publisher = member(identifier)
            if publisher and len(values) == 1 and None not in values:
                lags[publisher].append(next(iter(values)))
        rows = []
        for identifier in sorted(lags, key=lambda key: (-len(lags[key]), key))[:10]:
            values = lags[identifier]
            enough = len(values) >= 20
            rows.append(dict(count_row(identifier, labels[identifier], len(values), len(by_work)),
                value=quantile(values, .5)/365.25 if enough else None, unit='years',
                p25=quantile(values, .25)/365.25 if enough else None, p75=quantile(values, .75)/365.25 if enough else None))
        charts.append(chart('P3', 'C', 'median_lag_years', rows, mode+' 的记录时滞', '当前出版商关联样本的时滞分布如何？',
            scope=dict(scope, slice_id='C-'+mode+'-lag', observation_cutoff=rw_date), denominator=len(by_work),
            missing=len(by_work)-sum(map(len, lags.values())), limitations=limitations + ['未做发表年龄/学科调整，不表示编辑效率；RW 日期不一致或缺失不纳入分位数。']))
    return charts, True
