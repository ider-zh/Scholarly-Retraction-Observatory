"""Reader-facing labels and integer-safe narrative formatting."""

import re


POPULATIONS = {
    'A1_over_D': '撤稿标记论文 / 同口径发表论文', 'C_D_over_D': 'RW 记录论文 / 同口径发表论文',
    'A0': 'OpenAlex 撤稿标记记录', 'A1': '筛选后的撤稿标记论文',
    'B': 'RW 记录的撤稿原论文', 'C_D': '截至快照的匹配撤稿论文', 'C': '与 OpenAlex 匹配的 RW 论文',
    'D': '同口径发表论文',
}
TYPE_NAMES = {'article': '研究论文', 'review': '综述论文', 'retraction': '撤稿通知', 'erratum': '更正通知',
    'book': '书籍', 'book-chapter': '书籍章节', 'preprint': '预印本', 'dataset': '数据集', 'editorial': '社论',
    'letter': '读者来信', 'paratext': '封面、目录等附属记录', 'other': '其他文献', 'dissertation': '学位论文',
    'peer-review': '审稿报告', 'report': '研究报告', 'proceedings-article': '会议论文', 'conference-paper': '会议论文',
    'reference-entry': '参考条目', 'standard': '标准', 'supplementary-materials': '补充材料', 'Unknown': '类型缺失'}
LABELS = {'retained_A1': '保留：研究论文候选', 'excluded_work_type': '不属研究论文类型',
    'excluded_suspected_notice': '标题疑似通知：默认暂不纳入', 'excluded_known_notice': '已识别为通知',
    'excluded_conflict': '原论文与通知身份冲突', 'excluded_date': '日期不在研究范围',
    'multi_country_observed': '观察到多个国家', 'single_country_complete_observed': '单一国家且有完整性证据',
    'single_country_incomplete': '单一已知国家，但署名不完整', 'country_unknown': '无法识别国家',
    'completeness_unknown': '单一已知国家，完整性未知', 'Unknown': '未识别 / 缺失',
    'matched_flag_true': '匹配成功，OpenAlex 已标记撤稿', 'matched_flag_false': '匹配成功，OpenAlex 未标记撤稿',
    'matched_flag_missing': '匹配成功，OpenAlex 标记缺失', 'unmatched': '未找到对应记录',
    'ambiguous': '存在多个匹配候选', 'conflicting': '标识或文献身份冲突',
    'oa_flag_missing': 'OpenAlex 撤稿标记缺失', 'oa_corpus_unknown': '主体库/扩展库归属未知',
    'rw_publication_date_missing': 'RW 原论文发表日期缺失', 'rw_event_date_missing': 'RW 撤稿日期缺失',
    'rw_negative_lag': '撤稿日期早于发表日期', 'rw_publication_after_source_date': '发表日期晚于 RW 截止日',
    'rw_publication_date_conflict': '同篇原论文的发表日期存在冲突',
    'no_detected_truncation_not_proven_complete': '未发现署名截断，但不能证明完整',
    'detected_truncation': '作者总数大于已保存署名数', 'count_conflict': '作者数量与署名列表冲突',
    'unknown': '相关信息缺失'}


def readable(value):
    value = str(value)
    if value in LABELS:
        return LABELS[value]
    for key in sorted(POPULATIONS, key=len, reverse=True):
        value = re.sub(r'(?<![A-Za-z0-9_])'+re.escape(key)+r'(?![A-Za-z0-9_])', POPULATIONS[key], value)
    for source, target in [('core article', '主体库研究论文'), ('primary_topic', '主主题'),
        ('institution_country', '署名机构所在国'), ('authorship_country', '作者署名中的国家'),
        ('immediate_publisher', '直接出版商'), ('root_publisher', '出版集团'), ('common_5y', '共同五年随访队列'),
        ('window_specific', '各窗口独立随访队列'), ('reported_day', '按报告日期'),
        ('year_interval_sensitivity', '整年日期敏感性'), ('citing_article_review', '引用方限论文与综述')]:
        value = value.replace(source, target)
    return value


def format_value(value, unit):
    if unit in {'works', 'authors', 'edges', 'records'}:
        if int(value) != value:
            raise ValueError('A physical record count must be integral')
        return f'{int(value):,}'
    return f'{value:,.2f}'
