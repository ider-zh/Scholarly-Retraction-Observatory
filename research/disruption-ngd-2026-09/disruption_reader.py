import copy
import statistics


TAXONOMIES = {'Concepts 子学科': 'concepts_l1', 'Topics 子学科': 'topics_subfield'}


def scatter_explanation(slide, evidence):
    revised = copy.deepcopy(slide)
    summaries = {}
    for series in revised['chart']['series']:
        taxonomy = TAXONOMIES[series['name']]
        points = series['points']
        expected = [(row['crude_difference'], row['adjusted_difference'])
                    for row in evidence['year_type_cd_contrasts']
                    if row['taxonomy'] == taxonomy and row['common_retracted'] >= 20]
        if not points or sorted((point['x'], point['y']) for point in points) != sorted(expected):
            raise ValueError('Contrast chart differs from frozen evidence')
        summaries[taxonomy] = dict(
            total=len(points), positive=sum(point['y'] > 0 for point in points),
            same_sign=sum(point['x'] * point['y'] > 0 for point in points),
            lower=sum(point['y'] < point['x'] for point in points),
            median_shift=statistics.median(point['y'] - point['x'] for point in points))
    concepts, topics = summaries['concepts_l1'], summaries['topics_subfield']
    revised['subtitle'] = '每点一个子学科；横轴与纵轴是同一CD均值差的两种算法，不是CD与撤稿占比'
    revised['chart_display'] = {'number_format': '0.000'}
    revised['takeaway'] = f"分层后差值为正：Concepts {concepts['positive']}/{concepts['total']}；Topics {topics['positive']}/{topics['total']}。成线不等于因果规律。"
    revised['source'] += ' 图中共同层标记有效n≥20；数值未变。紧接下一页解释成线与分层。'
    explanation = dict(section='年份与类型 · 读图', title='为什么排成斜带？两轴在比较同一差值',
        subtitle='差值＝标记组平均CD − 未标记组平均CD；单位是CD分数，不是撤稿比例或百分比',
        body=[
            '横轴直接比较同一子学科的两组均值；纵轴先在相同发表年、相同文献类型内比较，再按共同层中标记组有效论文数加权。不是逐篇配对。',
            '两轴复用同一批来源和同一个比较问题，并非两个独立指标。差值原本大的学科，分层后通常仍较大，因此点形成斜带；y=x表示两种算法结果相同。',
            f"实测：Concepts {concepts['lower']}/{concepts['total']}、Topics {topics['lower']}/{topics['total']}个点满足y<x；y−x的中位数分别为{concepts['median_shift']:.5f}、{topics['median_shift']:.5f}，分层后差值总体下移。",
            f"但Concepts {concepts['same_sign']}/{concepts['total']}、Topics {topics['same_sign']}/{topics['total']}个学科仍保留原差值方向。年份/类型分层未消除多数正向差异；共同层筛选也会改变样本，不能把变化全归因于年份。"],
        takeaway='近直线说明前后差值接近，不证明撤稿由CD导致；学科间相关与学科内组间差异是不同问题。',
        source=f"由原图{concepts['total']}＋{topics['total']}个点计算描述性计数和中位数；report-statistics.json / year_type_cd_contrasts。未改动图中数据。")
    return revised, explanation, summaries


def conclusion(evidence):
    correlations = evidence['cd_correlations']
    main = {row['taxonomy']: row for row in correlations if row['variant'] == 'main_cd5_r10_c5'}
    if set(main) != {'concepts_l0', 'concepts_l1', 'topics_field', 'topics_subfield'}:
        raise ValueError('Missing main taxonomy results')
    ranges = {}
    for taxonomy in main:
        values = [row['rho'] for row in correlations if row['taxonomy'] == taxonomy]
        if len(values) != 11 or any(value is None for value in values):
            raise ValueError('Conclusion requires all 11 observed policies')
        ranges[taxonomy] = (min(values), max(values))
    if not (ranges['concepts_l0'][1] < 0 and ranges['topics_subfield'][1] < 0
            and ranges['concepts_l1'][0] < 0 < ranges['concepts_l1'][1]
            and -0.1 < main['topics_field']['rho'] < 0.1):
        raise ValueError('Observed directions no longer support this interpretation')
    concepts = main['concepts_l0']
    topics = main['topics_field']
    return dict(section='颠覆度 · 本章结论', title='负向线索存在，但不是跨学科通用规律',
        subtitle='比较的是学科平均CD与OA撤稿标记占比；主口径：成熟5年、参考≥10、被引≥5、不含发表年',
        body=[
            f"Concepts主学科：{concepts['subjects']}个学科ρ={concepts['rho']:.3f}，呈中等负向排序关系。平均CD较低、网络相对偏巩固的学科，撤稿占比倾向较高；11种口径均为负（{ranges['concepts_l0'][0]:.3f}至{ranges['concepts_l0'][1]:.3f}）。",
            f"Concepts细分后并不延续：子学科主口径ρ={main['concepts_l1']['rho']:.3f}，敏感性方向改变。主学科的负向关系不能直接套到每个子学科，更不能套到单篇论文。",
            f"Topics则不同：{topics['subjects']}个主学科ρ={topics['rho']:.3f}，接近零；子学科ρ={main['topics_subfield']['rho']:.3f}，11种口径均为负。信号出现在哪个层级，依赖分类体系，不能说Topics普遍不相关。",
            f"年代仍重要：仅将计算占比的发表队列收窄到2000–2020，主学科ρ变为Concepts {concepts['rate_2000_2020_rho']:.3f}、Topics {topics['rate_2000_2020_rho']:.3f}。结合学科内多数正向CD差异，证据不支持单一的‘CD越高越安全/危险’叙事。"],
        takeaway='可得结论：关联依赖分类、层级和年代；不可得结论：颠覆性保护论文免于撤稿，或巩固型研究更不可靠。',
        source='冻结report-statistics.json；学科等权，Concepts多标签重叠，Topics按primary_topic分类。描述性关联，未作因果或显著性认定。')
