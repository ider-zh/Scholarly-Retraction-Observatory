"""Additional finite presets without claiming adjusted or causal inference."""

from collections import Counter
import datetime as dt
import json
import math
from pathlib import Path


def growth(current, prior):
    return 100 * (current-prior)/prior if prior else None


def month_index(value):
    year, month = map(int, value[:7].split('-'))
    return year*12 + month-1


def build_charts(papers, works, a1, by_work, oa_date, rw_date, chart, count_row):
    chapters = {'time': [], 'publishing': [], 'fields': []}
    years = Counter(int(paper['retracted'][:4]) for paper in papers if paper['retracted'])
    rows = [dict(count_row(str(year), str(year), years[year], years[year-1]), value=growth(years[year], years[year-1]),
        unit='percent', year=year, small_base=years[year-1]<20, partial=year==int(rw_date[:4]))
        for year in range(2000, int(rw_date[:4])+1)]
    chapters['time'].append(chart('annual-growth', 'B', 'annual_count_yoy_pct', rows, 'RW 首次记录撤稿数量同比',
        '当前记录的年度数量相对上一年如何变化？', scope={'corpus': 'rw', 'work_types': ['all'], 'attribution': 'unique_original',
        'observation_cutoff': rw_date, 'slice_id': 'B-event-yoy'}, denominator=len(papers),
        limitations=['这是数量同比，不是个体不端风险增长；前期为零时未定义，基数小于 20 标注小基数。',
            '当前年度不完整，不参与比较性解读；较晚补录和覆盖变化影响年度数量。']))
    policy_path = Path(__file__).resolve().parents[1]/'data/reference/snapshot-burst-policy-v1.json'
    policy = json.loads(policy_path.read_text())
    months = Counter(month_index(paper['retracted']) for paper in papers if paper['retracted'])
    end = month_index(rw_date)
    start = month_index(policy['display_start'])
    rows = []
    for index in range(start, end+1):
        baseline_months = policy['baseline_previous_complete_months']
        prior = [months[month] for month in range(index-baseline_months, index)]
        mean = sum(prior)/baseline_months
        threshold = max(policy['minimum_window_count'], mean+3*math.sqrt(mean))
        partial = index == end
        label = f'{index//12:04d}-{index%12+1:02d}'
        rows.append(count_row(label, label, months[index], len(papers), month=label, baseline_mean=mean,
            threshold=threshold, review_flag=not partial and months[index]>threshold, partial=partial))
    chapters['publishing'].append(chart('P2', 'B', 'work_count', rows, 'RW 月度记录数量与复核阈值',
        '哪些完整月份超过预先固定的描述性复核阈值？', scope={'corpus': 'rw', 'work_types': ['all'],
        'attribution': policy['version'], 'observation_cutoff': rw_date, 'slice_id': 'B-monthly-control'},
        denominator=len(papers), limitations=['按此前 24 个完整月计算基线，阈值为 max(20, 均值+3√均值)；缺月按当前文件中零记录补齐，当前月不标记。',
            '阈值不是经校准的显著性检验，只提示人工复核；峰值不能证明论文工厂或任何因果机制。',
            '规则在本次控制图计算前固定，这是回溯描述分析，不声称前瞻性研究预注册。'], extras={'control_policy': policy}))
    for population, identifiers in [('A1', a1), ('C', set(by_work))]:
        for level in ('field', 'topic'):
            counts, labels = Counter(), {}
            unknown = 0
            for identifier in identifiers:
                members = {}
                for topic in works[identifier].get('topics', []):
                    item = topic if level == 'topic' else topic.get(level) or {}
                    if item.get('id'):
                        members[item['id']] = item.get('display_name') or item['id']
                unknown += not members
                counts.update(members.keys())
                labels.update(members)
            selected = counts.most_common(15)
            rows = [count_row(identifier, labels[identifier], count, len(identifiers)) for identifier, count in selected]
            chapters['fields'].append(chart('F1', population, 'linked_work_count', rows, population+' · any-topic '+level,
                '按所有已分配 Topic 去重归属，哪些主题和学科被关联？', scope={'corpus': 'core', 'work_types': ['article'],
                'attribution': 'any_topic_deduplicated_'+level, 'observation_cutoff': oa_date if population=='A1' else rw_date,
                'slice_id': population+'-any-topic-'+level}, denominator=len(identifiers), missing=unknown,
                limitations=['每篇对同一层级同一 ID 只贡献一次；两个 Topic 共享 Field 时该 Field 不重复计数。',
                    '多归属全计数不可相加为唯一论文数；不是主主题可加总层级，Topic 得分不是贡献或概率。展示前 15，分母不重算。']))
    return chapters
