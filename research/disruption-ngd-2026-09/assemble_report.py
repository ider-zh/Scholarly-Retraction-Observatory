import argparse
import gzip
import hashlib
import json
from pathlib import Path

import pyarrow.parquet as pq

from ngd_analysis import spearman


GROUPS = [('concepts_l0', 'concepts', 0, 'Concepts 主学科'),
          ('topics_field', 'topics', 0, 'Topics 主学科'),
          ('concepts_l1', 'concepts', 1, 'Concepts 子学科'),
          ('topics_subfield', 'topics', 1, 'Topics 子学科')]
MAIN = 'main_cd5_r10_c5'
DISPLAY_NAMES = {
    'Biochemistry, Genetics and Molecular Biology': '生物化学、遗传学与分子生物学',
    'Pharmacology, Toxicology and Pharmaceutics': '药理学、毒理学与药剂学',
    'Immunology and Microbiology': '免疫学与微生物学',
    'Economics, Econometrics and Finance': '经济学、计量经济学与金融',
    'Business, Management and Accounting': '商业、管理与会计',
    'Agricultural and Biological Sciences': '农业与生物科学',
    'Earth and Planetary Sciences': '地球与行星科学',
    'Physics and Astronomy': '物理学与天文学',
    'Chemical Engineering': '化学工程', 'Materials Science': '材料科学',
    'Environmental Science': '环境科学', 'Decision Sciences': '决策科学',
    'Arts and Humanities': '艺术与人文学科', 'Social Sciences': '社会科学',
    'Computer Science': '计算机科学', 'Computer science': '计算机科学',
    'Computational biology': '计算生物学', 'Bioinformatics': '生物信息学',
    'Mathematics': '数学', 'Medicine': '医学', 'Biology': '生物学',
    'Chemistry': '化学', 'Engineering': '工程学', 'Physics': '物理学',
    'Neuroscience': '神经科学', 'Psychology': '心理学', 'Energy': '能源',
    'Nursing': '护理学', 'Veterinary': '兽医学', 'Dentistry': '牙科学',
    'Health Professions': '卫生专业', 'Multidisciplinary': '多学科',
}
VARIANTS = [(MAIN, '主口径'), ('cd5_no_extra_threshold', '无额外门槛'),
            ('cd5_r5_c5', '参考≥5'), ('cd5_r20_c5', '参考≥20'),
            ('cd5_r10_c0', '被引≥0'), ('cd5_r10_c10', '被引≥10'),
            ('cd3_r10_c5', '3年'), ('cd10_r10_c5', '10年'),
            ('cd_lifetime_r10_c5', 'lifetime'),
            ('cd5_include_year_r10_c5', '含发表年'), ('no_nr5_r10_c5', 'no-NR')]


def digest(path):
    checksum = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            checksum.update(block)
    return checksum.hexdigest()


def verify_table_manifest(directory):
    manifest = json.loads((directory / 'manifest.json').read_text())
    if manifest['status'] != 'complete':
        raise ValueError(f'Incomplete analysis: {directory}')
    for entry in manifest['outputs']:
        if digest(directory / entry['path']) != entry['sha256']:
            raise ValueError('Table checksum mismatch')
    for entry in manifest['sources']:
        if digest(entry['path']) != entry['sha256']:
            raise ValueError('Table source changed')
    return manifest


def read_rows(path):
    if str(path).endswith('.parquet'):
        return pq.read_table(path).to_pylist()
    return json.loads(gzip.decompress(Path(path).read_bytes()))


def number(value, digits=3):
    return '不可计算' if value is None else f'{value:.{digits}f}'


def percent(value):
    return '不可计算' if value is None else f'{value * 100:.3f}%'


def display(value):
    if isinstance(value, str):
        for original, translated in sorted(DISPLAY_NAMES.items(), key=lambda item: -len(item[0])):
            value = value.replace(original, translated)
        return value
    if isinstance(value, list):
        return [display(item) for item in value]
    if isinstance(value, dict):
        return {key: display(item) for key, item in value.items()}
    return value


def chart(kind, xlabel, ylabel, series, **kwargs):
    return {'type': kind, 'x_label': xlabel, 'y_label': ylabel, 'series': series, **kwargs}


def series(name, points):
    return {'name': name, 'points': [{'x': horizontal, 'y': vertical, 'subject': label}
                                    for horizontal, vertical, label in points
                                    if horizontal is not None and vertical is not None]}


def build(root):
    ngd = root / 'ngd-ranked'
    verify_table_manifest(ngd)
    manifest_path = root / 'disruption_manifest.json'
    manifest = json.loads(manifest_path.read_text())
    if manifest['status'] != 'complete':
        raise ValueError('Disruption analysis is incomplete')
    for entry in manifest['files']:
        if digest(entry['path']) != entry['sha256']:
            raise ValueError('Aggregate checksum mismatch')
    global_path = root / 'global_main_metrics.json'
    global_payload = json.loads(global_path.read_text())
    global_metrics = {row['population']: row for row in global_payload['metrics']}
    subjects = read_rows(ngd / 'subjects.parquet')
    comparisons = read_rows(ngd / 'comparisons.parquet')
    correlations = read_rows(ngd / 'correlations.parquet')
    bands = read_rows(ngd / 'distance_bands.parquet')
    subject_lookup = {(row['taxonomy'], row['subject_id']): row for row in subjects}
    metrics = {}
    for taxonomy, system, level, label in GROUPS:
        for variant, _ in VARIANTS:
            metrics[taxonomy, variant] = read_rows(root / 'aggregates' / f'{taxonomy}-{variant}.parquet')
    summaries = []
    for taxonomy, system, level, label in GROUPS:
        baseline = read_rows(root / 'aggregates' / f'{taxonomy}-baseline.parquet')
        mature_rates = {}
        for row in baseline:
            if 2000 <= row['publication_year'] <= 2020:
                counts = mature_rates.setdefault(row['subject_id'], [0, 0])
                counts[0] += row['retracted_count']
                counts[1] += row['work_count']
        for variant, variant_label in VARIANTS:
            pairs = []
            adjusted = []
            for metric in metrics[taxonomy, variant]:
                if metric['population'] != 'oa_all' or metric['qualified_count'] < 100:
                    continue
                subject = subject_lookup.get((system, metric['subject_id']))
                if not subject or subject['N'] < 1000:
                    continue
                pairs.append((metric['mean_cd'], subject['rate']))
                events, population = mature_rates.get(metric['subject_id'], [0, 0])
                if population >= 1000:
                    adjusted.append((metric['mean_cd'], events / population))
            summaries.append({'taxonomy': taxonomy, 'variant': variant, 'subjects': len(pairs),
                              'rho': spearman(pairs), 'rate_2000_2020_rho': spearman(adjusted)})
    controlled = []
    for taxonomy, system, level, label in GROUPS:
        strata = read_rows(root / 'aggregates' / f'{taxonomy}-main-strata.parquet')
        groups = {}
        for row in strata:
            counts = groups.setdefault(row['subject_id'], {'total': 0, 'common': 0, 'difference_sum': 0.0})
            counts['total'] += row['retracted_qualified_count']
            if row['retracted_qualified_count'] and row['not_marked_qualified_count']:
                counts['common'] += row['retracted_qualified_count']
                counts['difference_sum'] += row['retracted_qualified_count'] * (row['retracted_mean_cd'] - row['not_marked_mean_cd'])
        lookup = {(row['subject_id'], row['population']): row for row in metrics[taxonomy, MAIN]}
        for identifier, counts in groups.items():
            if not counts['common']:
                continue
            retracted = lookup.get((identifier, 'oa_retracted'))
            other = lookup.get((identifier, 'oa_not_marked'))
            if not retracted or not other or retracted['mean_cd'] is None or other['mean_cd'] is None:
                continue
            controlled.append({'taxonomy': taxonomy, 'subject_id': identifier,
                               'crude_difference': retracted['mean_cd'] - other['mean_cd'],
                               'adjusted_difference': counts['difference_sum'] / counts['common'],
                               'common_retracted': counts['common'], 'all_retracted': counts['total'],
                               'coverage': counts['common'] / counts['total']})
    topic_metrics = {(row['subject_id'], row['population']): row for row in metrics['topics_subfield', MAIN]}
    topic_contrasts = [row for row in controlled if row['taxonomy'] == 'topics_subfield'
                       and row['common_retracted'] >= 20
                       and topic_metrics.get((row['subject_id'], 'oa_not_marked'), {}).get('qualified_count', 0) >= 100]
    positive_contrasts = sum(row['adjusted_difference'] > 0 for row in topic_contrasts)
    contrast_summary = {'taxonomy': 'topics_subfield', 'subjects': len(topic_contrasts),
                        'adjusted_positive': positive_contrasts,
                        'eligibility': 'common_retracted >= 20 and oa_not_marked qualified_count >= 100'}
    evidence = {'cd_correlations': summaries, 'year_type_cd_contrasts': controlled,
                'within_topics_contrast_summary': contrast_summary}
    (root / 'report-statistics.json').write_text(json.dumps(evidence, ensure_ascii=False, indent=2))
    slides = []
    source_cd = 'OA发表队列2000–2025；CD：成熟5年、不含发表年、有效参考≥10、被引≥5。相关按学科等权；N≥1,000、合格CD≥100。'
    source_ngd = '复用全库510,372,821 Works的标签共现NGD；比例来自既有OA发表队列。Topics归属primary_topic；NGD用全部Topics。'

    def add(section, title, subtitle, takeaway, source, **content):
        slides.append(dict(section=section, title=title, subtitle=subtitle, takeaway=takeaway, source=source, **content))

    add('研究综述', '撤稿的学科地图，能被颠覆度与数学距离解释吗？',
        '两套既定样本 · 两套学科分类 · 一项不预设答案的探索',
        '寻找可重复的关联，也把反例留在报告里。', 'OA 2026-06-26；RW 2026-09-10；研究口径沿用已确认金山综述。',
        body=['从“哪些学科撤稿多”，走向“哪些学科特征与撤稿记录一起变化”。',
              '第一条线索：引用网络中的颠覆度；第二条线索：学科标签与数学的共现距离。',
              '研究不是质量评判、风险预测或因果识别。'])
    add('研究范围', '两套样本，回答两个不同的问题', '数量、构成占比与学科内标记比例不能互换',
        '58,345篇匹配撤稿样本不作为学科发文分母。', 'https://www.kdocs.cn/l/cgrIJBxx1mWs',
        columns=[['RW–OA匹配样本：58,345篇。', '最早可解析RW撤稿事件年2000–2025；不要求OA也标记撤稿。', '用于撤稿学科构成、CD分布及撤稿前窗口对照。'],
                 ['OA发表队列：220,305,891篇。', '发表年2000–2025；其中77,414篇带撤稿标记。', '用于同学科标记数 / 同学科全部合格发文数。']])
    main_rhos = [next(row for row in summaries if row['taxonomy'] == group and row['variant'] == MAIN) for group, _, _, _ in GROUPS]
    main_rho_lookup = {row['taxonomy']: row['rho'] for row in main_rhos}
    add('发现概览', '先看完整关系，再看最吸引人的案例', '所有相关系数都是描述性结果，不是独立样本验证或因果效应',
        '学科间的关系与同学科内的论文对照，不能混为一谈。', source_cd + ' ' + source_ngd,
        body=[f"CD与标记比例：{label} ρ={number(row['rho'])}（{row['subjects']}个学科）。" for row, (_, _, _, label) in zip(main_rhos, GROUPS)] +
             ['数学NGD：Topics整体弱正相关，Concepts整体弱负相关；不存在跨体系一致方向。'])
    add('颠覆度方法', '后来者是绕开前人，还是连接前人？', '统计单位是不同的后续引用论文，而不是引用路径数',
        'CD描述引用网络结构，不直接衡量论文质量或研究诚信。', 'Funk & Owen-Smith, Management Science；本项目Disruption SPEC与完整图缓存。',
        columns=[['NF：引用焦点论文，但不引用其有效参考集合。', 'NB：既引用焦点论文，也引用至少一篇有效参考。', 'NR：不引用焦点论文，只引用其有效参考集合。'],
                 ['CD = (NF − NB) / (NF + NB + NR)', 'no-NR = (NF − NB) / (NF + NB)', '有效参考：可解析、去重、发表年严格早于焦点论文。无有效分母保持NULL。']])
    add('颠覆度方法', '先固定主口径，不在结果里寻找门槛', '用户所称CDX在本研究中指成熟观察窗口CD，并非另一公式',
        '完整观察不等于完整收录；合格子集不代表全部学科论文。', source_cd,
        body=['主分析：CD₅，不含发表年；五个自然年全部结束；参考≥10、五年被引≥5。',
              '敏感性：参考5/20、被引0/10、无额外门槛、3/10年、含发表年、lifetime和no-NR。',
              '未成熟结果保留观察计数，但不当成成熟CD；lifetime只表示截至快照。',
              '原始网络覆盖全部core+xpac；本研究只筛选焦点论文，不裁剪引用邻域。'])
    for taxonomy, system, level, label in GROUPS:
        selected = []
        for metric in metrics[taxonomy, MAIN]:
            subject = subject_lookup.get((system, metric['subject_id']))
            if metric['population'] == 'oa_all' and metric['qualified_count'] >= 100 and subject and subject['N'] >= 1000:
                selected.append((metric['mean_cd'], subject['rate'] * 100, subject['name']))
        statistic = next(row for row in summaries if row['taxonomy'] == taxonomy and row['variant'] == MAIN)
        add('颠覆度与学科', label + '：颠覆度与标记比例的完整关系',
            f"每点一个学科；{len(selected)}点；Spearman ρ={number(statistic['rho'])}",
            '相关方向不是单篇论文的撤稿风险；多标签学科相互重叠。', source_cd,
            chart=chart('scatter', '合格论文平均 CD₅', 'OA撤稿标记比例（%）', [series(label, selected)]))
    coverage_rows = []
    for taxonomy, system, level, label in GROUPS:
        values = []
        for row in metrics[taxonomy, MAIN]:
            subject = subject_lookup.get((system, row['subject_id']))
            if row['population'] == 'oa_all' and subject and subject['N']:
                values.append(row['qualified_count'] / subject['N'])
        import statistics
        coverage_rows.append([label, len(values), percent(statistics.median(values)), '逐学科中位覆盖率'])
    add('选择效应', '颠覆度门槛筛选了哪些论文？',
        f"全OA队列合格 {global_metrics['oa_all']['qualified_count']:,} / 220,305,891篇（{percent(global_metrics['oa_all']['qualified_count'] / 220305891)}）；表内为各学科覆盖率中位数",
        '解释的是合格子集的网络结构，不能省略被筛掉的论文。',
        '覆盖率=主口径合格CD数/全部OA发表队列数；本表保留全部有总体记录的学科，不施加相关分析的合格CD≥100门槛。',
        table={'columns': ['分类层级', '有记录学科', '覆盖率中位数', '统计量'], 'rows': coverage_rows})
    selected_fields = sorted([row for row in subjects if row['taxonomy'] == 'topics' and row['level'] == 0], key=lambda row: -row['N'])[:7]
    field_lookup = {(row['subject_id'], row['population']): row for row in metrics['topics_field', MAIN]}
    contrast_rows = []
    for subject in selected_fields:
        marked, other = [field_lookup.get((subject['subject_id'], population), {}) for population in ['oa_retracted', 'oa_not_marked']]
        contrast_rows.append([subject['name'], marked.get('qualified_count', '未估计'), number(marked.get('mean_cd'), 4),
                              number(other.get('mean_cd'), 4), number(marked.get('median_cd'), 4)])
    add('论文层面对照', '同一主学科中，标记与未标记论文有何差异？', '按发文规模选择前七个Topics主学科，不按效应大小挑选',
        '均值更高可能只是负值更接近0；“未标记”不等于永不撤稿。', source_cd,
        table={'columns': ['主学科', '标记组有效n', '标记组均值', '未标记均值', '标记组中位数'], 'rows': contrast_rows})
    rw_fields = sorted([row for row in metrics['topics_field', MAIN] if row['population'] == 'rw'], key=lambda row: -row['qualified_count'])[:7]
    rw_rows = []
    for row in rw_fields:
        before = field_lookup.get((row['subject_id'], 'rw_pre_retraction'), {})
        name = subject_lookup['topics', row['subject_id']]['name']
        rw_rows.append([name, row['qualified_count'], number(row['mean_cd'], 4), before.get('qualified_count', '未估计'), number(before.get('mean_cd'), 4)])
    add('时间顺序检查', '撤稿前窗口，留下的是另一批论文',
        f"RW全样本58,345篇；主CD合格{global_metrics['rw']['qualified_count']:,}篇；其中撤稿前窗口{global_metrics['rw_pre_retraction']['qualified_count']:,}篇（均含未分类论文）",
        '不能把跨越撤稿后的CD，反过来解释成撤稿前的预测信号。', 'RW 58,345篇原样保留；日期异常只影响本页限制子集；主CD门槛不变。',
        table={'columns': ['主学科', 'RW有效n', 'RW均值', '撤稿前有效n', '撤稿前均值'], 'rows': rw_rows})
    sensitivity_series = []
    for taxonomy, system, level, label in GROUPS[2:]:
        selected = [next(row for row in summaries if row['taxonomy'] == taxonomy and row['variant'] == variant) for variant, _ in VARIANTS]
        sensitivity_series.append(series(label, [(variant_label, row['rho'], variant) for row, (variant, variant_label) in zip(selected, VARIANTS)]))
    add('敏感性分析', '改变门槛以后，相关方向还在吗？', '每个口径重新统计合格子集；不是把同一批论文重新命名',
        '先展示全部预设口径，不仅挑选最支持故事的一种。', '完整参数与每组学科数见report-statistics.json；lifetime并非成熟固定窗口。',
        chart=chart('bar', '颠覆度口径', 'CD与标记比例的Spearman ρ', sensitivity_series, y_min=-1, y_max=1))
    controlled_series = []
    for taxonomy, system, level, label in GROUPS[2:]:
        points = [(row['crude_difference'], row['adjusted_difference'], subject_lookup[system, row['subject_id']]['name'])
                  for row in controlled if row['taxonomy'] == taxonomy and row['common_retracted'] >= 20]
        if points:
            controlled_series.append(series(label, points))
    add('年份与类型', '把标记论文放回相近的发表背景', '同学科×发表年×文献类型；按共同层内标记组有效n加权；仅展示共同标记n≥20的学科',
        f'Topics子学科中，另限未标记有效n≥100后，{positive_contrasts}/{len(topic_contrasts)}个分层均值差为正；不是因果效应。', '横轴：标记−未标记CD均值；纵轴：共同年份/类型层内均值差的加权平均；源为main-strata。',
        chart=chart('scatter', '未分层CD均值差', '年份/类型分层CD均值差', controlled_series))
    add('年代范围敏感性', '如果发文比例也只看成熟年代？', '原始2000–2025比例不覆盖；新增2000–2020发表队列作为敏感性',
        '观察年限不同可以影响学科比较，不能把年份控制省略。', source_cd,
        table={'columns': ['学科层级', '全部发表队列ρ', '2000–2020比例ρ', '学科数'],
               'rows': [[label, number(row['rho']), number(row['rate_2000_2020_rho']), row['subjects']] for row, (_, _, _, label) in zip(main_rhos, GROUPS)]})
    add('NGD方法', 'NGD：共同出现，不是文字含义的直线距离', '以Work标签集合替换搜索命中集合；两套体系分别计算',
        'NGD小表示相对更多共现；不能直接读成数学训练、数学含量或因果保护。', 'Cilibrasi & Vitányi, The Google Similarity Distance, arXiv:cs/0412098；taxonomy_ngd/SPEC.md。',
        body=['NGD(A,B) = [max(log f(A), log f(B)) − log f(A∩B)] / [log N − min(log f(A), log f(B))]',
              'N = 510,372,821；f(A)、f(B)、f(A∩B)均按不同Work计数，不按重复标签计数。',
              '数学锚：Concept C33923547；Topics Field 26。对全部二级学科计算同一锚距离。',
              '零共现或未定义结果保持NULL；NGD并不保证落在0到1之间。'])
    add('NGD方法', '距离与撤稿比例，来自不同但明确的集合', '复用现成NGD，不为得到更好看的关联重算总体',
        '这是外部学科属性与既有撤稿指标的关联，不是两个独立数据源的验证。', source_ngd,
        columns=[['Concepts：原生L0/L1；全部附带标签，不补祖先，不按分数删除。', '历史父级映射用于组织；多父级保留，不把子学科数相加为父级数。'],
                 ['Topics距离：全部topics映射Field/Subfield；撤稿归属：primary_topic。', 'NGD包含core+xpac；撤稿比例仍是原先core发表队列，不能互换分母。']])
    add('观察设计', '如果数学邻近真的相关，应该看到什么？', '先写可被否定的观察要求，再看各个学科的结果',
        '同一套规则保留支持例与反例，避免只展示名字里有“计算”的学科。', '已确认访谈Q10–Q17；预先指定数学主问题、计算机和物理参照。',
        body=['连续距离为主：NGD越大，比例是否越高？正ρ才符合“近数学、低比例”的方向。',
              '在高比例一级学科内部再比较：是否只是不同一级学科之间的差异？',
              '近/中/远仅按NGD三分位划分；并列距离不拆开；低事件数保留并标记。',
              '高比例：N≥1,000一级学科中的最高四分之一；不把数量多误读成比例高。'])
    math_rows = [row for row in comparisons if row['reference'] == 'Mathematics']
    unique_math = {(row['taxonomy'], row['subject_id']): row for row in math_rows}
    math_series = []
    for system in ['concepts', 'topics']:
        for low in [False, True]:
            points = [(row['ngd'], row['rate'] * 100, row['name']) for row in unique_math.values()
                      if row['taxonomy'] == system and row['eligible_ranking'] and row['low_events'] == low]
            if points:
                math_series.append(series(system + (' · 撤稿n<20' if low else ' · 撤稿n≥20'), points))
    add('NGD全景', '放到所有子学科中，关系并不整齐', 'Concepts 284个、Topics 252个；全部已有数学距离覆盖；一学科一点，不重复父级',
        '整体关联方向不同，不支持“接近数学普遍对应较低撤稿比例”的统一结论。', source_ngd,
        chart=chart('scatter', '与数学的NGD（越小越近）', 'OA撤稿标记比例（%）', math_series))
    global_math = [row for row in correlations if row['scope'] == 'all_unique_children' and row['reference'] == 'Mathematics']
    add('NGD全景', '年份调整没有把两套分类变成同一个答案', '直接按全OA发表年份分布加权；有缺失年份支撑时不强行补齐',
        '这里的弱相关是描述，不用显著性星号放大它。', source_ngd + ' 完整权重覆盖才给直接标准化值。',
        table={'columns': ['体系', '子学科数', '粗比例ρ', '年份标准化ρ'],
               'rows': [[row['taxonomy'], row['children'], number(row['spearman_crude']), number(row['spearman_year_standardized'])] for row in global_math]})
    parent_math = [row for row in correlations if row['scope'] == 'within_parent' and row['reference'] == 'Mathematics' and row['parent_is_high_rate']]
    parent_math.sort(key=lambda row: (row['taxonomy'], row['spearman_crude'] if row['spearman_crude'] is not None else 0))
    add('高比例主学科内部', '有些主学科支持假设，有些方向相反', '只在预先确定的高比例父级内比较；子学科数量少时秩相关容易波动',
        '总体叙事必须容纳异质性，而不是用一个主学科代表全部。', source_ngd,
        chart=chart('bar', '分类体系 / 主学科', '数学NGD与子学科比例的ρ',
                    [series('父级内ρ', [(row['taxonomy'][0].upper() + ':' + row['parent_name'] + f" ({row['children']}个)", row['spearman_crude'], str(row['children']) + '个子学科') for row in parent_math])], y_min=-1, y_max=1))
    biology = [row for row in math_rows if row['taxonomy'] == 'concepts' and row['parent_name'] == 'Biology']
    add('生物学内观察', '在生物学里，距离需要逐个标签测量', '完整展示Biology下的子学科，不只选择支持假设的点',
        '一项局部关系不能自动推广到其他主学科。', source_ngd,
        chart=chart('scatter', '与数学的NGD', '子学科撤稿标记比例（%）', [series('Biology子学科', [(row['ngd'], row['rate'] * 100, row['name']) for row in biology])]))
    examples = [row for row in biology if row['name'] in ['Bioinformatics', 'Computational biology']]
    add('预期与反例', '“计算”之名，并不保证在这个NGD中更近', '原先举出的两个例子，按同一套规则检验',
        '标签共现不等于方法论中的数学含量；例子提醒我们谨慎解释指标。', source_ngd,
        table={'columns': ['Concepts子学科', '数学NGD', '生物学内距离组', '标记n / 发文N', '标记比例'],
               'rows': [[row['name'], number(row['ngd']), {'near': '近', 'middle': '中', 'far': '远'}[row['distance_group']], f"{row['n']:,} / {row['N']:,}", percent(row['rate'])] for row in examples]})
    band_lookup = {(row['taxonomy'], row['parent_id'], row['distance_group']): row for row in bands if row['reference'] == 'Mathematics'}
    complete_parents = [row for row in parent_math if all(band_lookup.get((row['taxonomy'], row['parent_id'], band), {}).get('median_child_rate') is not None for band in ['near', 'far'])]
    band_series = [series(label, [(row['taxonomy'][0].upper() + ':' + row['parent_name'], band_lookup[row['taxonomy'], row['parent_id'], band]['median_child_rate'] * 100, '') for row in complete_parents]) for band, label in [('near', '近数学'), ('far', '远数学')]]
    add('高比例主学科内部', '近组与远组：比较的是子学科比例的中位数', 'Concepts有重叠，不能合并各标签的n/N冒充独立论文总体；只展示两组均非空的父级',
        '并非所有高比例主学科都呈现“近组更低”。', source_ngd,
        chart=chart('bar', '高比例主学科', '组内子学科比例中位数（%）', band_series))
    reference_rows = [row for row in correlations if row['scope'] == 'all_unique_children']
    add('其他领域参照', '换一个参照学科，关联方向也会变化', '数学为主问题；计算机、物理是预先指定的补充',
        '参照选择本身影响故事，因此同时报告预设的全部参照。', source_ngd,
        chart=chart('bar', '体系 / 参照学科', 'NGD与标记比例的Spearman ρ', [series('ρ', [(row['taxonomy'] + '/' + row['reference'], row['spearman_crude'], '') for row in reference_rows])], y_min=-1, y_max=1))
    controls_root = root / 'ngd-controls-final'
    controls_manifest = verify_table_manifest(controls_root)
    controlled_correlations = read_rows(controls_root / 'correlations_controlled.parquet')
    global_controls = [row for row in controlled_correlations if row.get('parent_id') is None]
    add('NGD年份与类型', '发文组成调整，是另一道敏感性检查',
        '间接标准化：期望标记数=Σ学科分层发文数×全OA同年同类型标记比例；O/E为观察/期望',
        '这是组成参照，不是相同权重的直接比较，更不是因果效应。', source_ngd + ' ngd-controls；直接标准化缺支持的单元保持NULL。',
        table={'columns': ['体系', '参照', '子学科数', '年份/类型间接调整ρ'],
               'rows': [[row['taxonomy'], row['reference'], row['children'], number(row['spearman_indirect_year_type'])] for row in global_controls]})
    strict = read_rows(controls_root / 'concepts_parent_intersection.parquet')
    strict_summary = []
    for parent in parent_math:
        if parent['taxonomy'] != 'concepts':
            continue
        selected = [row for row in strict if row['parent_id'] == parent['parent_id'] and row['reference'] == 'Mathematics' and row['intersection_N'] >= 1000]
        coverage = [row['intersection_coverage'] for row in selected if row['intersection_coverage'] is not None]
        coverage_range = f'{min(coverage)*100:.1f}–{max(coverage)*100:.1f}%' if coverage else '不可计算'
        strict_summary.append([parent['parent_name'], len(selected), number(parent['spearman_crude']),
                               number(spearman([(row['ngd'], row['intersection_rate']) for row in selected])), coverage_range])
    add('Concepts父子边界', '如果严格要求论文同时带父、子标签？',
        '单独的敏感性总体；原报告子标签分母不变；交集后按N≥1,000重新选取分析学科',
        '主分析与交集分析可能包含不同论文和学科，差异本身需要披露。', source_ngd + ' concepts_parent_intersection.parquet；数学锚不重算。',
        table={'columns': ['高比例父学科', '交集子学科数', '子标签原ρ', '父子交集ρ', '交集覆盖范围'], 'rows': strict_summary})
    add('不确定性', '小样本与缺标签，不应该消失在图里', '数据完整保存；主要分析资格与原始记录保留分离',
        '观察到零不等于零风险；有定义的指标也不等于可靠解释。', '研究规则：发文N≥1,000；主要CD合格n≥100；撤稿事件n<20仅标记。',
        body=['所有子学科表保留小样本、零事件、未定义NGD与CD覆盖情况。',
              'Wilson区间描述给定n/N的二项不确定性，不覆盖收录误差、撤稿认定差异或多标签依赖。',
              '分类体系不是独立重复样本；OA标记与RW并非完全独立来源。',
              '84篇RW论文在旧报告与全库缓存中Topics归属不同；两套分析分别保留原映射。'])
    add('研究结论', '两条线索，都没有给出跨分类的一致答案', '颠覆度、标签距离与撤稿记录，各自只描述研究过程的一部分',
        '研究价值在于识别哪些关联稳定、哪些会随定义改变。', source_cd + ' ' + source_ngd,
        body=[f"主CD与比例：Topics子学科ρ={number(main_rho_lookup['topics_subfield'])}，Concepts子学科ρ={number(main_rho_lookup['concepts_l1'])}。",
              f'同学科内：{positive_contrasts}/{len(topic_contrasts)}个符合对照条件的Topics子学科，标记组分层平均CD较高。',
              '数学邻近：整体方向跨体系不一致，高比例主学科内部存在支持与反例。',
              '生物信息学例子未满足预设“近数学”的直觉，不能用学科名称替代实际距离。',
              ])
    add('下一步', '把探索结果变成可重复的研究问题', '新假设与新阈值必须另行版本化，不覆盖本次结果',
        '本次不声称预测、因果效应，也不为学科或论文作诚信标签。', '完整学科表、参数、来源哈希和压缩缓存随报告保留。',
        body=['对稳定方向做独立时间段或外部数据检验；不把当前快照的敏感性分析当作独立复现。',
              '进一步考虑撤稿时滞、期刊与国家结构、类型内差异及引用覆盖。',
              '如要研究真实数学方法使用程度，需要另建文本或方法变量；NGD不能独自回答。'])
    group_labels = {taxonomy: label for taxonomy, _, _, label in GROUPS}
    variant_labels = dict(VARIANTS)
    for subset in [summaries[:22], summaries[22:]]:
        for start in range(0, len(subset), 8):
            selected = subset[start:start + 8]
            add('附录 · 敏感性全表', '每一个预设口径都留下记录', 'ρ为学科层面的等权秩相关；不是论文层面回归系数',
                '无额外门槛仍要求分数有定义；缺失不填零。', 'report-statistics.json；完整分位数、正值比例、n/N在aggregates/。', appendix=True,
                table={'columns': ['分类', '口径', '有效学科数', 'ρ'], 'rows': [[group_labels[row['taxonomy']], variant_labels[row['variant']], row['subjects'], number(row['rho'])] for row in selected]})
    population_labels = [('oa_all', 'OA全部'), ('oa_retracted', 'OA标记'),
                         ('oa_not_marked', 'OA未标记'), ('rw', 'RW匹配'), ('rw_pre_retraction', 'RW撤稿前窗口')]
    add('附录 · 分布与选择', '均值之外，保留分布形状', '包含未分类论文；全部按主口径，RW撤稿前窗口另有限制；各组并非互斥集合',
        'CD较高不等于CD为正；正值比例也不是质量或诚信指标。', 'global_main_metrics.json；逐学科四分位数与正值比例见研究数据表.xlsx。',
        appendix=True,
        table={'columns': ['样本', '有效n', '均值', '中位数', '四分位数Q25 / Q75', 'CD>0占比'],
               'column_widths': [3.2, 2.0, 1.9, 1.9, 3.4, 2.0],
               'rows': [[label, global_metrics[key]['qualified_count'], number(global_metrics[key]['mean_cd'], 5),
                         number(global_metrics[key]['median_cd'], 5),
                         number(global_metrics[key]['q25_cd'], 5) + ' / ' + number(global_metrics[key]['q75_cd'], 5),
                         percent(global_metrics[key]['positive_fraction'])] for key, label in population_labels]})
    sources = [manifest_path, ngd / 'manifest.json', root / 'cohort.json', controls_root / 'manifest.json', global_path]
    return {'status': 'verified', 'title': '撤稿的学科地图：颠覆度与数学距离的探索研究',
            'source_manifests': [{'path': str(path), 'sha256': digest(path)} for path in sources], 'slides': display(slides)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('root', type=Path)
    args = parser.parse_args()
    payload = build(args.root)
    path = args.root / 'presentation.json'
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
    print(json.dumps({'payload': str(path), 'main_slides': sum(not row.get('appendix') for row in payload['slides']), 'total_slides': len(payload['slides'])}))


if __name__ == '__main__':
    main()
