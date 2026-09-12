"""Verified finite presets for additional denominator and followup analyses."""

from collections import Counter, defaultdict
import json
from pathlib import Path

import duckdb

from .snapshot import cohort_rate
from .validate_snapshot import digest
from .work_policy import is_broad


def build_charts(release_dir, provenance, entries, denominators, flagged, oa_date, chart, count_row):
    broad = is_broad(provenance)
    marker_path = Path(release_dir)/'supplement-complete.json'
    if not marker_path.exists():
        return {}, None
    marker = json.loads(marker_path.read_text())
    if marker['scan_config_sha256'] != provenance['config_sha256'] or marker['files'] != len(entries):
        raise ValueError('Supplement scan mismatch')
    paths = []
    for entry in entries:
        key = digest(entry['key'].encode())
        path = Path(marker['directory'])/(key+'.parquet')
        checkpoint = json.loads((path.with_suffix('.json')).read_text())
        if checkpoint['source_fingerprint'] != digest(json.dumps(entry, sort_keys=True).encode()) or checkpoint['sha256'] != digest(path.read_bytes()):
            raise ValueError('Supplement shard changed')
        paths.append(str(path))
    with duckdb.connect(config={'threads': 16, 'memory_limit': '32GB'}) as connection:
        connection.read_parquet(paths).create_view('supplement')
        rows = connection.execute('''SELECT dimension, group_id, type, publication_year,
            sum(denominator)::BIGINT, sum(flagged)::BIGINT, sum(recorded)::BIGINT FROM supplement GROUP BY ALL''').fetchall()
    for dimension in ('oa_status', 'language', 'observed_team_band', 'authorship_audit'):
        counts, flag_counts = Counter(), Counter()
        for key, group, kind, year, total, count, recorded in rows:
            if key == dimension:
                counts[(kind, year)] += total
                flag_counts[(kind, year)] += count
        if counts != denominators or flag_counts != flagged:
            raise ValueError('Supplement partition differs from full D/A1')
    charts = {'time': [], 'entities': [], 'quality': []}
    names = {'oa_status': '原论文快照 OA 状态', 'language': '元数据语言', 'observed_team_band': '已观察作者列表规模', 'authorship_audit': '作者列表截断与计数核对'}
    scope = {'corpus': 'core', 'work_types': ['article'], 'publication_year_range': [2000, int(oa_date[:4])],
             'observation_cutoff': oa_date, 'attribution': 'unique_work'}
    population_total = sum(count for (kind, year), count in denominators.items() if (broad or kind == 'article') and year >= 2000)
    for dimension in names:
        grouped = Counter()
        for key, group, kind, year, total, count, recorded in rows:
            if key == dimension and (broad or kind == 'article') and year >= 2000:
                grouped[(group, 'N')] += total
                grouped[(group, 'A1')] += count
        keys = sorted({key for key, metric in grouped})
        selected = sorted(keys, key=lambda key: (-grouped[(key, 'N')], key))[:20] if dimension == 'language' else keys
        if 'Unknown' in keys and 'Unknown' not in selected:
            selected.append('Unknown')
        rates = []
        for key in selected:
            numerator, denominator = grouped[(key, 'A1')], grouped[(key, 'N')]
            if numerator > denominator:
                raise ValueError('Supplement numerator exceeds denominator')
            rates.append(dict(count_row(key, key, numerator, denominator), **cohort_rate(numerator, denominator), unit='per_10k'))
        section = 'entities' if dimension == 'observed_team_band' else 'quality'
        charts[section].append(chart('cohort-'+dimension, 'A1_over_D', 'oa_flagged_cohort_per_10k', rates,
            names[dimension]+'：同口径计数与比例', '保留未知和覆盖状态后，分子与发表分母如何分布？',
            scope=dict(scope, slice_id='A1-'+dimension+'-2000', attribution=dimension), denominator=population_total,
            missing=grouped[('Unknown', 'N')] if dimension != 'authorship_audit' else grouped[('unknown', 'N')],
            limitations=['OA 状态是快照状态，不是发表时状态；元数据语言不等于全文语言。',
                '团队规模为已观察列表长度；未检测到截断不证明完整，不能解释为贡献或责任。',
                '未调整发表年代或学科；语言仅展示按 D 规模前 20 及 Unknown，展示选择不重算分母。']))
    for years in (1, 3, 5):
        cells = []
        yearly = defaultdict(Counter)
        for key, group, kind, year, total, count, recorded in sorted(rows):
            if key != 'fixed_window' or group != str(years) or (not broad and kind != 'article') or year < 2000:
                continue
            if recorded > total:
                raise ValueError('Fixed-window numerator exceeds eligible cohort')
            yearly[year]['total'] += total
            yearly[year]['recorded'] += recorded
            yearly[year]['excluded'] += denominators[(kind, year)] - total
        for year, values in sorted(yearly.items()):
            total, recorded = values['total'], values['recorded']
            cells.append(dict(count_row(str(year), str(year), recorded, total), **cohort_rate(recorded, total),
                unit='per_10k', year=year, excluded_missing_date_or_short_followup=values['excluded']))
        charts['time'].append(chart('T3', 'C_D_over_D', 'rw_recorded_cohort_per_10k', cells,
            f'发表后 {years} 年内的 RW 记录比例', '具备完整发表后观察窗的 OA 队列中，多少原论文被 RW 记录撤稿？',
            scope=dict(scope, slice_id=f'C_D-fixed-publication-{years}y', followup_years=years,
                date_basis='reported_oa_publication_day', event_policy='unique_first_rw_date_across_matches'),
            denominator=sum(row['denominator'] for row in cells),
            missing=population_total-sum(row['denominator'] for row in cells),
            limitations=['这是 OA 覆盖队列中的 RW 记录固定窗比例，不是完整观测的普遍风险。',
                '须有发表日且日历周年不晚于 OA 截止日；缺失发表日或随访不足排除。仅纳入发表日至周年日之间的有效 RW 日期。',
                '跨匹配原论文的首次事件日期冲突不计入分子；源日期原始精度未知，不能解释为无误差的事件时间。']))
    return charts, marker
