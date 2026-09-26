import argparse
import copy
import hashlib
import json
import math
from pathlib import Path

from sensitivity_reader import canonical_chart, enhance
from disruption_reader import conclusion, scatter_explanation
from ngd_reader import annotate_panorama

CD_SOURCE = 'Funk & Owen-Smith (2017), doi:10.1287/mnsc.2015.2366；Park, Leahey & Funk (2023), doi:10.1038/s41586-022-05543-x。'
RHO_SOURCE = 'Spearman：对两列平均秩计算Pearson相关；算法说明 https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.spearmanr.html 。'
NGD_SOURCE = 'Cilibrasi & Vitányi (2007), https://arxiv.org/abs/cs/0412098；本研究以OpenAlex标签共现替代网页命中数。'


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def teaching(title, subtitle, takeaway, source, **content):
    return dict(section='概念入口', title=title, subtitle=subtitle,
                takeaway=takeaway, source=source, **content)


def divider(number, title, subtitle, previous, next_question):
    return dict(section=f'SECTION {number}', section_number=number, section_break=True,
                title=title, subtitle=subtitle, body=[previous, next_question],
                takeaway='先理解问题与量尺，再阅读数据给出的答案。',
                source='阅读导航；章节过渡不代表新增统计结果。')


def empirical_signature(slides):
    figures = [slide['chart'] for slide in slides if slide.get('chart')]
    tables = [slide['table'] for slide in slides if slide.get('table')]
    return {'figures': figures, 'tables': tables}


def clarify_window_labels(value):
    if isinstance(value, str):
        for previous, current in [('RW撤稿前窗口', 'RW先结束组'),
                                  ('撤稿前有效n', '先结束组有效n'),
                                  ('撤稿前均值', '先结束组均值'),
                                  ('撤稿前窗口', '观察期先结束组')]:
            value = value.replace(previous, current)
        return value
    if isinstance(value, list):
        return [clarify_window_labels(item) for item in value]
    if isinstance(value, dict):
        return {key: clarify_window_labels(item) for key, item in value.items()}
    return value


def revise(original, original_path):
    if original.get('status') != 'verified' or len(original.get('slides', [])) != 37 or original.get('revision'):
        raise ValueError('This revision requires the verified original 37-slide report')
    for entry in original['source_manifests']:
        if digest(entry['path']) != entry['sha256']:
            raise ValueError('Original evidence changed')
    baseline = copy.deepcopy(original['slides'])
    slides = []
    moved_appendices = []
    for index, raw in enumerate(baseline, 1):
        slide = copy.deepcopy(raw)
        if index == 2:
            slides.append(divider('01', '从撤稿分布，走向两个新问题',
                '上一版告诉我们“哪里更多”；这一版探索“哪些学科特征与它一起变化”',
                '已知：不同学科的撤稿记录数量与占比并不相同。',
                '先统一读法：样本是谁、比例怎么算、这次增加了什么观察角度。'))
        if index == 3:
            slides.append(teaching('“标记比例”到底标记了什么？',
                '标记指OpenAlex数据库的撤稿状态，不是本研究给论文打的质量标签',
                '这个占比不是论文未来被撤稿的概率，也不代表所有撤稿都已被数据库发现。',
                'OA字段is_retracted；原研究发表队列2000–2025。下面20/10,000仅为教学示例。',
                columns=[['OA（OpenAlex）收录论文等学术记录；一条记录叫一个Work。',
                          'is_retracted=true：快照中该记录已被标为撤稿。未标记不等于永不撤稿。',
                          '“标记组/未标记组”就是按这个数据库状态分组。'],
                         ['学科内占比 = 该学科已标记撤稿数 n / 该学科全部合格发文数 N。',
                          '例如20篇 / 10,000篇 = 0.2%。不是20篇占全部撤稿论文的比例。',
                          'RW（Retraction Watch）匹配样本另算撤稿构成，不能拿它替代OA的分母。']]))
            moved = copy.deepcopy(slide)
            moved['appendix'] = True
            moved['section'] = '附录 · 原始发现概览'
            moved_appendices.append(moved)
            slide = teaching('两条新线索，不是两个“诚信评分”',
                '先用日常语言理解研究问题，后面再给出缩写和计算办法',
                '我们寻找共同变化的模式，不把关联直接当成原因。',
                '研究问题沿用已确认方案；未改变既有RW与OA数据范围。',
                columns=[['第一条线索：后来者怎样引用一篇论文？',
                          '是继续同时引用它的前人，还是主要转而引用它？',
                          '这个引用网络特征，用“巩固—颠覆指数”CD描述。'],
                         ['第二条线索：一个子学科与数学有多接近？',
                          '看同一篇论文被同时赋予这个学科和数学标签的情况。',
                          '这个相对共现距离，用NGD描述；不是阅读正文后的语义判断。']])
        if index == 4:
            slides.append(divider('02', '第一条线索：知识被接续，还是被改道？',
                '先认识颠覆度，再看它与撤稿分布有什么关系',
                '上一章区分了撤稿数量、样本构成与学科内占比。',
                '接下来先看一个引用网络，再解释CD、观察时间和图里的相关系数。'))
            slides.append(teaching('CD：把“巩固—颠覆”变成一个可计算的量',
                'CD = Consolidation–Disruption，通常译作“巩固—颠覆指数”；不是冷却期',
                'CD是颠覆度的一种网络测量，不等于创新质量，更不等于论文可靠性。', CD_SOURCE,
                columns=[['巩固：后来者引用这篇论文时，也继续引用它所依托的前人。',
                          '颠覆：后来者转而引用这篇论文，不再同时引用它的前人。',
                          '这里观察的是引用连接，不是判断前人的知识真的被推翻。'],
                         ['CD越接近+1，网络越偏向“转而引用焦点论文”。',
                          'CD越接近−1，越偏向“焦点论文与前人一起被引用”。',
                          '接近0可能是两类相抵或分母很大；不能解释成“没有价值”。']]))
            slide = teaching('先看三种引用关系，再看公式',
                '焦点论文＝正在被计算CD的论文；前人＝它的有效参考论文集合；箭头从引用者指向被引用者',
                'NF、NB、NR数的是三类不同的后续论文，不是引用箭头的条数。',
                CD_SOURCE + ' 本研究有效参考为可解析、去重、发表年严格更早的Work。', citation_demo=True)
            slides.append(slide)
            slides.append(teaching('从三类计数，读懂一个CD数值',
                '教学示例：假设有效参考存在，观察窗内共有20篇后续关联论文；不是研究发现',
                '正负号表达网络方向；0.30不是“30%创新”，也不是“30%撤稿风险”。', CD_SOURCE,
                columns=[['NF=8：只引用焦点论文。', 'NB=2：同时引用焦点和它的前人。', 'NR=10：只引用它的前人。'],
                         ['CD = (NF−NB) / (NF+NB+NR)',
                          '本例：(8−2)/(8+2+10) = 0.30。',
                          'no-NR是另一口径：去掉NR分母，本例为0.60；不能把两种数值混用。']]))
            slides.append(teaching('CD₅的“5”是观察时间，不是冷却时间',
                '时间下标与起止边界是两件事：CD的名称本身不规定自然年该怎样分桶',
                '两套自然年窗同时改变起止边界；都不等于从实际发表日滚动五周年。',
                CD_SOURCE + ' 本项目disruption/SPEC.md §5；示例假定论文发表于2020-07-01。',
                table={'columns': ['口径', '2020年论文的观察区间', '本报告如何使用'],
                       'column_widths': [4.1, 5.6, 4.7],
                       'rows': [['不含发表年：年龄1–5', '2021-01-01 至 2025-12-31', '默认用于主要结果'],
                                ['含发表年：年龄0–4', '2020-01-01 至 2024-12-31', '已计算的补充对照'],
                                ['按发表日滚动五周年', '2020-07-01 至 2025-07-01', '解释性对照；本研究未计算']]}))
            continue
        if index == 5:
            slide = teaching('本报告怎样选出可比较的CD？',
                '主口径＝首先用来读结果的一套测量约定，不是CD唯一的定义',
                '不含发表年是本项目的年份分桶选择，不是CD定义要求“等待一年再起作用”。',
                '原始统计与两套时间窗口均保留；本轮只补充解释，不改动任何结果或筛选条件。',
                body=['先固定看多久：主分析看发表年之后五个完整自然年，不含发表当年。',
                      '再判断看够没有：“成熟”表示这五年已完整结束，不是等五年后才开始计引用。',
                      '再设最低网络信息量：有效参考≥10篇，五年窗内被引≥5篇；两者不是同一数量。',
                      '年份数据难以确认同年引用的先后，因此主分析排除age=0；这也会漏掉真实的同年后续引用，故保留含发表年对照。'])
            slides.append(slide)
            slides.append(teaching('“敏感性分析”：换个约定，答案还在吗？',
                '不是统计“有多敏感”，而是检查结论是否过度依赖某一组研究选择',
                '若方向或强弱改变，应报告“不稳定”，而不是挑选最支持预期的版本。',
                '11种预设CD口径全部保留；CDX在本次沟通中指成熟窗口统计，并非独立公式。',
                body=['例如主口径要求参考≥10篇：改成≥5或≥20篇，学科之间的关系是否还相似？',
                      '再分别改变被引门槛、观察3/5/10年、是否包含发表年，或改用no-NR公式。',
                      '“无额外门槛”仍需分数可定义、固定窗口已成熟；不是把缺参考或缺分母填成零。',
                      '它是在同一批来源上做稳健性检查，不是新的独立证据，也不是因果验证。']))
            slides.append(teaching('图里的ρ：看两列学科排序是否一起变化',
                'ρ读作rho（罗）；Spearman ρ是秩相关系数，范围从−1到+1',
                'ρ不是比例、概率或因果效应；ρ=0.8也不代表解释了80%的差异。', RHO_SOURCE,
                columns=[['每个点是一门学科：一列是平均CD或数学NGD，另一列是撤稿占比。',
                          '先将两列各自从小到大排名，再计算两列名次的相关。',
                          '并列值取平均名次；无变化的一列不能计算相关，保留未定义。'],
                         ['+1：两列排序完全同向；−1：完全反向。',
                          '接近0：没有明显的单调排序关系，不代表不存在任何关系。',
                          '绝对值越大，排序关系越强，不表示数值差距更大；本报告每门学科权重相同。']]))
            slides.append(teaching('一个算例：ρ=0.8是怎样得到的？',
                '仅用四个假想学科演示：两列名次大体同向，丙与丁交换了位置',
                '无并列时：ρ=1−6Σd²/[m(m²−1)]；本例m=4、Σd²=2，得到0.8。',
                RHO_SOURCE + ' 教学数据，非OpenAlex统计。实际算法适用并列值：对平均秩计算Pearson相关。',
                table={'columns': ['假想学科', 'CD名次', '撤稿占比名次', '名次差d', 'd²'],
                       'rows': [['甲', 1, 1, 0, 0], ['乙', 4, 4, 0, 0], ['丙', 2, 3, -1, 1], ['丁', 3, 2, 1, 1]]}))
            continue
        if index == 6:
            slide['takeaway'] = '平均CD较低的主学科，标记占比倾向较高；这是学科间关系，不是单篇论文风险。'
            slide['subtitle'] += '；19个学科平均CD均为负，较高也可能只是更接近0'
        if index == 7:
            slide['takeaway'] = '主学科层级的单调关联接近零；Topics按primary_topic归类，不沿用Concepts多标签解释。'
        if index == 9:
            slide['takeaway'] = 'Topics子学科呈弱负向关联；主学科接近零不代表所有层级均无关联。'
        if index == 12:
            slides.append(teaching('引用观察期必须先结束，论文才进入这个子集',
                '“先结束组”＝引用观察期在撤稿前完整结束的论文；不是从撤稿日期倒推五年',
                '避免混入撤稿后的引用变化；这不是同一论文的前后比较，也不能证明CD能预测撤稿。',
                '既有规则：计划窗口结束日期严格早于最早可解析撤稿日期；仍需满足原定CD门槛。下列时间仅为教学示例。',
                columns=[['先按发表时间确定窗口：论文发表于2015年，主口径观察2016—2020年的引用。',
                          '若2022年撤稿：观察期已于2020年末结束，满足“先结束”的时间条件。',
                          '还需满足成熟5年、有效参考≥10、被引≥5等既定条件，才纳入本报告的对照。'],
                         ['若2019年撤稿：撤稿发生在2016—2020年观察期之内，不进入“先结束组”。',
                          '不会把窗口截到2019年后，仍冒充完整五年CD。',
                          '这篇论文仍保留在完整RW样本中；这里只增加一个对照子集，不删除原记录。']]))
            slide['title'] = '仅比较引用观察期在撤稿前完整结束的论文'
            slide['subtitle'] = '简称“先结束组”；RW主CD合格14,787篇，其中5,107篇满足时间条件（均含未分类论文）'
            slide['takeaway'] = '先结束组是更小、选择条件不同的样本，不是同一批论文撤稿前后的变化。'
        if index == 13 and slide.get('chart'):
            statistics_path = original_path.parent / 'report-statistics.json'
            manifest_path = original_path.parent / 'disruption_manifest.json'
            statistics = json.loads(statistics_path.read_text())
            variants = json.loads(manifest_path.read_text())['variants']
            expanded, _ = enhance(slide, statistics, variants)
            slides.extend(expanded)
            continue
        if index == 16:
            if baseline[13].get('chart'):
                slides.append(conclusion(statistics))
            slides.append(divider('03', '第二条线索：哪些子学科更接近数学？',
                '从“怎样被引用”切换到“哪些学科标签经常一起出现”',
                '上一章研究引用网络中的巩固—颠覆结构，得到了CD与撤稿占比的关系。',
                '这一章换一把量尺：先说明NGD如何定义“近”，再检验原先的数学邻近假设。'))
            slides.append(teaching('NGD：这里的“语义距离”从哪里来？',
                'NGD = Normalized Google Distance，归一化Google距离；名字来自其最初的网页共现应用',
                '本报告测量的是学科标签共现距离，不是语言模型语义距离，也不是数学方法使用强度。', NGD_SOURCE,
                body=['原理很直观：两个标签在同一篇论文上一起出现得越多，可能越接近。',
                      '但不能只看共同论文数：很大的学科本来就更容易和其他学科共同出现。',
                      'NGD把共同出现数、各自出现数与全库论文数一起比较，减轻标签规模差异的影响。',
                      '本研究不调用Google搜索，而是读取OpenAlex论文已有的Concepts或Topics标签。']))
            slides.append(teaching('固定规模后，共现更多意味着距离更小',
                '教学示例：全库1,000篇；标签A出现100篇，数学标签也出现100篇',
                '在边际频次相同时，共现更多则NGD更小；实际比较还必须考虑各标签规模。', NGD_SOURCE + ' 以下仅演示公式，不是生物学或OpenAlex实测数据。',
                table={'columns': ['教学情境', '同时带A与数学的论文', 'NGD', '怎样读'],
                       'column_widths': [3.0, 4.2, 2.0, 5.2],
                       'rows': [['较多共现', '50篇', '约0.301', '相对更近'], ['较少共现', '10篇', '1.000', '相对更远'],
                                ['没有共现', '0篇', '未定义', '本项目保留NULL，不写成0']]}))
        if index == 16:
            slide['title'] = '把直觉写成公式：NGD用了哪四个数？'
            slide['subtitle'] = 'N是全库论文数；f(A)、f(B)是各标签出现数；f(A∩B)是两者同时出现数'
        if index == 19:
            if slide.get('chart'):
                import pyarrow.parquet as parquet
                correlations_path = original_path.parent / 'ngd-ranked/correlations.parquet'
                slide = annotate_panorama(slide, parquet.read_table(correlations_path).to_pylist())
        if index == 20:
            slide['title'] = '数学距离与撤稿占比：ρ的年份调整对照'
            slide['subtitle'] = '上一页散点对应表中“粗比例ρ”；右列改用全OA发表年份权重标准化后的占比计算ρ'
            slide['takeaway'] = '调整前后，Concepts均弱负向、Topics均弱正向；系数均接近0，不构成普遍规律。'
        if slide['title'] == '近组与远组：比较的是子学科比例的中位数':
            slides.append(teaching('近数学、远数学：在同一主学科内部划分',
                'NGD越小代表标签共现意义上越近；不是按名字，也不是按数学方法使用量分组',
                '每个主学科单独定界：生物学的“近组”，不一定比物理学的“远组”更接近数学。',
                '既有ngd_analysis.py / distance_groups：全部有定义距离的子学科插值三分位；不改原分组或统计。',
                body=['先在每个主学科内部，收集其子学科与数学标签的NGD，计算第33.3%与第66.7%分位点。',
                      '近组：NGD≤下分位点；中组：下分位点<NGD≤上分位点；远组：NGD>上分位点。相同距离不拆开，三组不一定等大；未定义距离不分组。',
                      '分组后保留发文N≥1,000的子学科。每个子学科先计算自己的撤稿标记占比n/N，再取组内这些比例的中位数；不是合并分子、分母。',
                      '下一页只显示高比例主学科中近组、远组均非空的比较；中间组仍保留在数据中。Concepts多标签有重叠，子学科不能直接相加。']))
            slide['subtitle'] = '各主学科内部按数学NGD三分位分组：近组≤下分位点，远组>上分位点；完整规则见前页'
            slide['source'] += ' 先分组，再取N≥1,000子学科的n/N中位数；不是Σn/ΣN，只展示近远两组均非空的父级。'
        if slide['title'] == '每一个预设口径都留下记录':
            slide['subtitle'] = '本表ρ＝学科平均颠覆度指标 ↔ 同学科OA撤稿标记占比（n/N）的Spearman相关；不是NGD相关'
            slide['takeaway'] = '负ρ：平均指标越高，占比排名倾向越低；正ρ则相反。学科间关联，不是单篇论文风险。'
            slide['source'] = '每行按该分类层级与口径重选合格论文并求平均（CD或no-NR）；占比固定为2000–2025发表队列。N≥1,000、合格指标论文≥100，学科等权；report-statistics.json。'
        if index == 28:
            slides.append(divider('04', '把两条线索放在一起，也把边界留下',
                '从局部模式回到能够支持的研究结论',
                '已经看过：学科间相关、同学科论文对照，以及数学邻近的支持例与反例。',
                '最后区分哪些观察较稳定、哪些依赖定义，以及本次不能回答的问题。'))
        if index == 14 and slide.get('chart'):
            slide, explanation, _ = scatter_explanation(slide, statistics)
            slides.extend([slide, explanation])
            continue
        slides.append(slide)
    slides.extend(moved_appendices)
    slides = clarify_window_labels(slides)
    retained = [slide for slide in slides if slide.get('chart')]
    if [canonical_chart(slide['chart']) for slide in retained] != [canonical_chart(chart) for chart in empirical_signature(baseline)['figures']]:
        raise ValueError('Empirical chart data changed')
    for table in empirical_signature(baseline)['tables']:
        if clarify_window_labels(table) not in [slide.get('table') for slide in slides]:
            raise ValueError('Original evidence table lost')
    if not math.isclose(1 - 6 * 2 / (4 * (4 ** 2 - 1)), 0.8):
        raise ValueError('Rank example failed')
    result = copy.deepcopy(original)
    result.update({'slides': slides, 'max_main_slides': 50,
                   'revision': 'reader-context-v7-groups-and-rho', 'title': original['title'] + '（概念导读修订版）'})
    result['source_manifests'].append({'path': str(original_path.resolve()), 'sha256': digest(original_path)})
    if any(slide.get('section') == '敏感性分析 · 读图与解释' for slide in slides):
        result['source_manifests'].append({'path': str(statistics_path.resolve()), 'sha256': digest(statistics_path)})
    if baseline[18].get('chart'):
        result['source_manifests'].append({'path': str(correlations_path.resolve()), 'sha256': digest(correlations_path)})
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('root', type=Path)
    args = parser.parse_args()
    source = args.root / 'presentation.json'
    original = json.loads(source.read_text())
    revised = revise(original, source)
    output = args.root / 'reader-groups-rho-revision'
    output.mkdir(exist_ok=True)
    (output / 'presentation.json').write_text(json.dumps(revised, ensure_ascii=False, indent=2))
    statistics_path = args.root / 'report-statistics.json'
    _, _, contrasts = scatter_explanation(original['slides'][13], json.loads(statistics_path.read_text()))
    (output / 'interpretation-audit.json').write_text(json.dumps({
        'source': str(statistics_path), 'sha256': digest(statistics_path),
        'scatter_descriptive_summaries': contrasts,
        'original_graph_statistics_recomputed': False}, ensure_ascii=False, indent=2))
    audit = {'status': 'passed', 'original_payload_sha256': digest(source),
             'revised_payload_sha256': digest(output / 'presentation.json'),
             'original_chart_count': len(empirical_signature(original['slides'])['figures']),
             'empirical_charts_unchanged': True, 'original_tables_retained': True,
             'table_label_changes_only': True,
             'sensitivity_chart_labels_clarified': True,
             'main_slides': sum(not slide.get('appendix') for slide in revised['slides']),
             'section_dividers': sum(bool(slide.get('section_break')) for slide in revised['slides']),
             'total_slides': len(revised['slides']), 'analysis_recomputed': False}
    (output / 'revision-audit.json').write_text(json.dumps(audit, ensure_ascii=False, indent=2))
    print(json.dumps(audit, ensure_ascii=False))


if __name__ == '__main__':
    main()
