import copy


LABELS = {
    'main_cd5_r10_c5': '5年主口径',
    'cd5_no_extra_threshold': '放宽两项数量门槛',
    'cd5_r5_c5': '仅参考门槛≥5',
    'cd5_r20_c5': '仅参考门槛≥20',
    'cd5_r10_c0': '仅被引门槛≥0',
    'cd5_r10_c10': '仅被引门槛≥10',
    'cd3_r10_c5': '后续3年（已成熟）',
    'cd10_r10_c5': '后续10年（已成熟）',
    'cd_lifetime_r10_c5': '截至快照（非固定年限）',
    'cd5_include_year_r10_c5': '5年窗口含发表年',
    'no_nr5_r10_c5': '5年改用no-NR',
}


def canonical_chart(chart):
    result = copy.deepcopy(chart)
    series = result.get('series', [])
    points = [point for group in series for point in group.get('points', [])]
    if result.get('type') == 'bar' and points and all(point.get('subject') in LABELS for point in points):
        for point in points:
            point['x'] = point['subject']
        result.pop('x_label', None)
        result.pop('y_label', None)
    return result


def enhance(slide, statistics, variants):
    definitions = {row[0]: row for row in variants}
    if set(definitions) != set(LABELS):
        raise ValueError('Unexpected sensitivity policies')
    summary = {(row['taxonomy'], row['variant']): row for row in statistics['cd_correlations']}
    systems = {'Concepts 子学科': 'concepts_l1', 'Topics 子学科': 'topics_subfield'}
    revised = copy.deepcopy(slide)
    observed = {}
    if {group['name'] for group in revised['chart']['series']} != set(systems):
        raise ValueError('Unexpected chart populations')
    for group in revised['chart']['series']:
        taxonomy = systems[group['name']]
        if len(group['points']) != 11 or {point['subject'] for point in group['points']} != set(LABELS):
            raise ValueError('Incomplete sensitivity chart')
        records = []
        for point in group['points']:
            identifier = point['subject']
            record = summary[taxonomy, identifier]
            if point['y'] != record['rho'] or record['rho'] is None:
                raise ValueError('Chart and statistics differ')
            point['x'] = LABELS[identifier]
            records.append(record)
        values = [record['rho'] for record in records]
        observed[taxonomy] = {'negative': sum(value < 0 for value in values),
                              'positive': sum(value > 0 for value in values),
                              'minimum': min(values), 'maximum': max(values),
                              'subjects_min': min(record['subjects'] for record in records),
                              'subjects_max': max(record['subjects'] for record in records)}
    topics, concepts = observed['topics_subfield'], observed['concepts_l1']
    if topics['negative'] != 11 or concepts['positive'] != 8 or concepts['negative'] != 3:
        raise ValueError('Revisit the narrative: empirical directions changed')
    revised.update(title='Topics子学科负向较稳定，Concepts方向随口径变化',
                   subtitle='比较的是“各子学科平均CD”与“同学科撤稿标记占比”；不是Topics与学科之间的相关',
                   takeaway='Topics：11种口径均为负；Concepts：8正3负。方向稳定不等于关联强，也不代表因果关系。',
                   source=f"Concepts均为{concepts['subjects_min']}个子学科；Topics为{topics['subjects_min']}–{topics['subjects_max']}个。每行重新筛选论文，不是11次独立验证；完整条件见前两页。")
    revised['chart']['x_label'] = '统计口径（每一行是一整套条件，不与其他行叠加）'
    revised['chart']['y_label'] = '学科平均CD与撤稿标记占比的Spearman ρ'
    if canonical_chart(slide['chart']) != canonical_chart(revised['chart']):
        raise ValueError('Numerical chart content changed')

    def page(title, subtitle, takeaway, **content):
        return dict(section='敏感性分析 · 读图与解释', title=title, subtitle=subtitle,
                    takeaway=takeaway, source='冻结计算参数：disruption_manifest.json；关联与学科数：report-statistics.json。只补充解释，不重算数据。', **content)

    threshold_ids = list(LABELS)[:6]
    threshold_rows = []
    for identifier in threshold_ids:
        _, policy, window, references, citations, metric = definitions[identifier]
        if (policy, window, metric) != ('ex', '5y', 'cd'):
            raise ValueError('Threshold teaching table assumes exclude-year mature5y CD')
        threshold_rows.append([LABELS[identifier], '后续5年，已成熟', f'≥{references}', f'≥{citations}', 'CD'])
    thresholds = page('每一行的条件同时生效，各行是替代方案',
        '例如“仅参考≥20”＝成熟5年 AND 参考≥20 AND 该窗口被引≥5 AND CD有定义；默认不含发表年',
        '多数行只改变一个设置；“放宽两项”同时降低参考与被引门槛。各行不是累积叠加。',
        table={'columns': ['图中类别', '观察窗', '有效参考数', '窗口被引数', '公式'],
               'column_widths': [4.6, 3.3, 2.3, 2.4, 1.8], 'rows': threshold_rows})

    intervals = {'3y': '2011–2013；完整3年', '5y': '2011–2015；完整5年',
                 '10y': '2011–2020；完整10年', 'lifetime': '2011年至2026-06-26快照'}
    time_rows = []
    for identifier in ['main_cd5_r10_c5'] + list(LABELS)[6:]:
        _, policy, window, references, citations, metric = definitions[identifier]
        if policy not in ['ex', 'in'] or (policy == 'in' and window != '5y'):
            raise ValueError('Unsupported teaching interval')
        interval = '2010–2014；含发表年的5年' if policy == 'in' else intervals[window]
        time_rows.append([LABELS[identifier], interval, f'≥{references}', f'≥{citations}', 'no-NR' if metric == 'no_nr' else 'CD'])
    windows = page('3年、10年与lifetime，都在数哪段引用？',
        '以2010年发表为例：固定年窗须完整结束；被引门槛应用于该行的窗口，不沿用5年被引数',
        'lifetime仅指截至快照，没有统一观察长度，也不要求固定窗口成熟；不是论文最终一生。',
        table={'columns': ['图中类别', '后续引用观察区间', '参考数', '被引数', '公式'],
               'column_widths': [4.6, 5.0, 1.6, 1.6, 1.6], 'rows': time_rows})
    conclusions = page('能说方向是否稳定，不能说“普遍没有关系”',
        '结论只针对本图的子学科层级、OA发表队列和11种预设口径，不外推到所有学科或单篇论文',
        '这些是描述性关联，不是显著性或因果结论；未计算的组合不能从现有条形图推算。',
        body=[f"Topics子学科：11/11种口径为负，ρ在{topics['minimum']:.3f}至{topics['maximum']:.3f}之间；平均CD排名较高的子学科，撤稿占比排名倾向较低。",
              f"Concepts子学科：8正3负，ρ在{concepts['minimum']:.3f}至{concepts['maximum']:.3f}之间；整体较弱，方向不稳定，不能反过来证明完全没有关系。",
              f"Topics参与相关的子学科数由{topics['subjects_min']}到{topics['subjects_max']}不等；Concepts虽均为{concepts['subjects_min']}个，内部合格论文也会改变。差异不全是单个参数的纯效应。",
              '这不是所有参数的全组合实验。例如“参考≥20＋10年”没有在本图计算；“改用no-NR”则保留5年、参考≥10、被引≥5，只改变公式。'])
    return [thresholds, windows, revised, conclusions], observed
