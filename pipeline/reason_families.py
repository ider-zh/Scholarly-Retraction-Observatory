"""Exact, project-defined RW label families; not adjudications of misconduct."""

from collections import Counter, defaultdict

from .snapshot import quantile


VERSION = 'rw-exact-label-families-v1'
GROUPS = {
    'reported_error': ('记录为错误', 'substantive_reported',
        'Error by Journal/Publisher;Error by Third Party;Error in Analyses;Error in Cell Lines/Tissues;Error in Data;Error in Image;Error in Materials;Error in Methods;Error in Results and/or Conclusions;Error in Text;Duplication of Content through Error by Journal/Publisher'),
    'concern': ('疑虑 / 问题（非结论）', 'concern_not_finding',
        'Bias Issues or Lack of Balance;Concerns/Issues about Animal Welfare;Concerns/Issues about Article;Concerns/Issues about Authorship/Affiliation;Concerns/Issues about Data;Concerns/Issues about Human Subject Welfare;Concerns/Issues about Image;Concerns/Issues about Methods;Concerns/Issues about Peer Review;Concerns/Issues about Referencing/Attributions;Concerns/Issues about Results and/or Conclusions;Concerns/Issues about Third Party Involvement'),
    'unreliable': ('可靠性 / 可复现性问题', 'substantive_reported',
        'Contamination of Cell Lines/Tissues;Contamination of Materials;Original Data and/or Images not Provided and/or not Available;Results Not Reproducible;Unreliable Data;Unreliable Image;Unreliable Results and/or Conclusions'),
    'duplication': ('记录为重复 / 切分发表', 'substantive_reported',
        'Duplication of Data;Duplication of Text;Duplication of/in Article;Duplication of/in Image;Euphemisms for Duplication;Salami Slicing'),
    'plagiarism': ('记录为抄袭 / 内容挪用', 'substantive_reported',
        'Euphemisms for Plagiarism;Plagiarism of Data;Plagiarism of Image;Plagiarism of Text;Plagiarism of/in Article;Taken from Dissertation/Thesis;Taken via Peer Review;Taken via Translation'),
    'fabrication_manipulation': ('记录为伪造 / 操纵', 'substantive_reported',
        'Falsification/Fabrication of Data;Falsification/Fabrication of Image;Falsification/Fabrication of Results;Manipulation of Data;Manipulation of Images;Manipulation of Results;Hoax Paper;Sabotage of Materials/Methods'),
    'authorship_identity': ('记录为虚假作者 / 单位', 'substantive_reported',
        'False/Forged Affiliation;False/Forged Authorship'),
    'review_production': ('同行评审 / 生产机制记录', 'substantive_reported',
        'Compromised Peer Review;Computer-Aided Content or Computer-Generated Content;Paper Mill;Rogue Editor'),
    'ethics_approval': ('伦理 / 同意 / 审批记录', 'substantive_reported',
        'Breach of Policy by Author;Conflict of Interest;Ethical Violations by Author;Ethical Violations by Company/Institution/Third Party;Informed/Patient Consent - None/Withdrawn;Lack of Approval from Author;Lack of Approval from Company/Institution;Lack of Approval from Third Party;Lack of IRB/IACUC Approval and/or Compliance'),
    'misconduct_label': ('不端标签（沿用来源措辞）', 'source_assertion_not_independently_verified',
        'Euphemisms for Misconduct;Misconduct by Author;Misconduct by Company/Institution;Misconduct by Third Party'),
    'investigation': ('调查 / 调查或结论（程序）', 'procedure_not_finding',
        'Investigation by Company/Institution;Investigation by Journal/Publisher;Investigation by ORI;Investigation by Third Party;Misconduct - Official Investigation(s) and/or Finding(s)'),
    'complaint_objection': ('投诉 / 异议（非结论）', 'procedure_not_finding',
        'Complaints about Author;Complaints about Company/Institution;Complaints about Third Party;Objections by Author(s);Objections by Company/Institution;Objections by Third Party'),
    'legal_rights': ('法律 / 版权程序', 'procedure_not_finding',
        'Civil Proceedings;Copyright Claims;Criminal Proceedings;Legal Reasons and/or Threats;Transfer of Copyright and/or Ownership'),
    'communication': ('沟通 / 响应记录', 'procedure_not_finding',
        'Author Unresponsive;Miscommunication with/by Author;Miscommunication with/by Company/Institution;Miscommunication with/by Journal/Publisher;Miscommunication with/by Third Party'),
    'notice_information': ('通知 / 日期信息缺失', 'notice_descriptor',
        'Date of Article and/or Notice Unknown;Notice - Lack of;Notice - Limited or No Information;Notice - Unable to Access via current resources'),
    'notice_action': ('通知处理 / 更新描述', 'notice_descriptor',
        'Doing the Right Thing;No Further Action;Publishing Ban;Removed;Retract and Replace;Temporary Removal;Updated to Correction;Updated to Retraction;Upgrade/Update of Prior Notice(s)'),
    'publication_context': ('其他发表背景', 'context_not_finding',
        'Cites Retracted Work;Nonpayment of Fees and/or Refusal to Pay;Not Presented at Conference;Withdrawn as Out of Date;Withdrawn to Publish in Different Journal'),
}
MAPPING = {label: [family] for family, (name, kind, labels) in GROUPS.items() for label in labels.split(';')}


def families(labels):
    if not labels:
        return {'missing'}
    return set().union(*(set(MAPPING.get(label, ['unmapped'])) for label in labels))


def build_charts(papers, by_work, works, rw_date, chart, count_row):
    names = {key: value[0] for key, value in GROUPS.items()} | {'missing': '原因缺失', 'unmapped': '未映射标签'}
    policy = ['项目自定义标签归组，不是 RW 官方分类或独立裁定；错误、疑虑、调查和来源不端标签保持区分。',
        '原因采用同篇 Retraction 记录的并集，多标签比例可超过 100%；不能认为所有原因在首次日期已知。']
    scope = {'corpus': 'rw', 'work_types': ['all'], 'attribution': VERSION, 'observation_cutoff': rw_date}
    counts = Counter(family for paper in papers for family in families(paper['reasons']))
    rows = [dict(count_row(key, names[key], counts[key], len(papers)),
        value=100 * counts[key] / len(papers) if papers else None, unit='percent',
        label_class=GROUPS[key][1] if key in GROUPS else 'coverage') for key in names]
    observed = sorted({label for paper in papers for label in paper['reasons']})
    charts = [chart('R1', 'B', 'paper_coverage_pct', rows, '原因族与程序描述的论文覆盖', '哪些实质标签和程序描述被记录？',
        scope=dict(scope, slice_id='B-reason-families'), denominator=len(papers), missing=counts['missing'], limitations=policy,
        extras={'reason_mapping_version': VERSION, 'raw_to_family_mapping': {label: MAPPING.get(label, ['unmapped']) for label in observed}})]
    combinations = Counter(tuple(sorted(families(paper['reasons']))) for paper in papers if paper['reasons'])
    leading = combinations.most_common(10)
    combo_rows = [count_row(str(index), ' + '.join(names[key] for key in members), total, len(papers),
        reason_labels=[names[key] for key in members]) for index, (members, total) in enumerate(leading)]
    combo_rows += [count_row('other', 'Other · 其余完整组合', sum(combinations.values())-sum(total for members, total in leading), len(papers)),
                   count_row('missing', '原因缺失', counts['missing'], len(papers))]
    if sum(row['numerator'] for row in combo_rows) != len(papers):
        raise ValueError('Reason-family combinations must partition originals')
    charts.append(chart('R3', 'B', 'work_count', combo_rows, '完整原因族组合', '哪些原因族与程序描述共同记录？',
        scope=dict(scope, slice_id='B-family-combinations'), denominator=len(papers), limitations=policy))
    field_counts, cross, missing = Counter(), Counter(), Counter()
    field_names = {}
    for identifier, linked in by_work.items():
        field = works[identifier]['topic'].get('field') or {}
        field_id = field.get('id', 'Unknown')
        field_names[field_id] = field.get('display_name') or field_id
        field_counts[field_id] += 1
        union = set().union(*(set(paper['reasons']) for paper in linked))
        missing[field_id] += not union
        for family in families(union):
            cross[(field_id, family)] += 1
    selected = sorted(GROUPS, key=lambda key: (-counts[key], key))[:8]
    matrix = [dict(count_row(field_id+'-'+family, field_names[field_id]+' · '+names[family], cross[(field_id, family)], total),
        value=100 * cross[(field_id, family)] / total, unit='percent', field=field_names[field_id], reason=names[family],
        missing_reason_works=missing[field_id]) for field_id, total in field_counts.items() for family in selected]
    charts.append(chart('R2', 'C', 'reason_given_field_pct', matrix, '原因族 × OA Field', '同一学科全部匹配原论文中，原因族记录比例如何？',
        scope=dict(scope, corpus='core', work_types=['article'], slice_id='C-family-field', selected_family_ids=selected),
        denominator=len(by_work), limitations=policy + ['固定展示 B 中最常见的八个原因族；每个 Field 分母包括原因缺失。Unknown Field 单列。']))
    lag_values = defaultdict(list)
    for paper in papers:
        if paper['lag_days'] is not None:
            for family in families(paper['reasons']):
                lag_values[family].append(paper['lag_days'])
    lag_rows = []
    for family in GROUPS:
        values = lag_values[family]
        enough = len(values) >= 20
        lag_rows.append(dict(count_row(family, names[family], len(values), counts[family]),
            value=quantile(values, .5)/365.25 if enough else None, unit='years',
            p25=quantile(values, .25)/365.25 if enough else None, p75=quantile(values, .75)/365.25 if enough else None,
            excluded_dates=counts[family]-len(values), small_base=not enough))
    charts.append(chart('R4', 'B', 'median_lag_years', lag_rows, '不同原因族的撤稿时滞', '有效日期样本的中位时滞和四分位区间如何？',
        scope=dict(scope, slice_id='B-family-lag'), denominator=len(papers), limitations=policy + ['每组 n<20 不显示分位数；多标签组不独立，区间不是置信区间。']))
    return charts
