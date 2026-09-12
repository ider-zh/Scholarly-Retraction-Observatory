"""Report-specific geographic grouping, applied before per-work deduplication."""

VERSION = 'country-grouping-cn-includes-tw-v1'
METHOD = '本报告将来源国家代码 TW 并入 CN（中国）；每篇论文先归组再去重，数量、分数计数、合作对及发文分母均使用该口径。原始快照保留不变。'


def country_code(value):
    return 'CN' if value == 'TW' else value


def country_list_sql(expression):
    return f"list_distinct(list_transform({expression}, country -> CASE WHEN country = 'TW' THEN 'CN' ELSE country END))"
