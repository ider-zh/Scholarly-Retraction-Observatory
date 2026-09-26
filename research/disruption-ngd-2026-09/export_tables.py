import argparse
import json
from pathlib import Path

import pyarrow.parquet as pq
import xlsxwriter


def export(root):
    path = root / '研究数据表.xlsx'
    workbook = xlsxwriter.Workbook(path, {'strings_to_formulas': False, 'strings_to_urls': False})
    header = workbook.add_format({'bold': True, 'bg_color': '#142338', 'font_color': '#FFFFFF'})
    intro = workbook.add_worksheet('阅读说明')
    notes = [
        ['项目', '撤稿学科 × 成熟窗口颠覆度 × NGD；探索性关联'],
        ['RW样本', '58,345篇，最早可解析撤稿事件年2000–2025'],
        ['OA比例总体', '220,305,891篇，发表年2000–2025；撤稿标记77,414篇'],
        ['原始比例单位', 'rate为0–1比例，PPT展示时乘100为百分数；不得混为百分数'],
        ['n和N', 'NGD表n为标记数，N为学科发文数；多标签Concepts不能跨行相加为独立论文数'],
        ['CD合格数', 'qualified_count是该口径有效分数数，不是学科全部发文数'],
        ['零与未知', '空单元格是NULL或未定义，不等于0；无额外门槛也要求分数有定义'],
        ['NGD', '外部全core+xpac标签共现属性；Topics距离用全部标签，撤稿归属primary_topic'],
        ['间接标准化', 'O/E依赖学科自身年份/类型组成，仅作敏感性；不是因果效应'],
        ['日期', 'OA快照2026-06-26；RW快照2026-09-10'],
        ['RW学科映射', '84篇RW论文的旧报告Topics映射不同于全库缓存；RW保留旧报告映射，OA保留全库映射，不修改原数据'],
        ['population', 'oa_all为OA发表队列；oa_retracted为OA撤稿标记；oa_not_marked为未标记；rw为匹配样本；rw_pre_retraction为撤稿前窗口结束子集'],
        ['预设CD主口径', 'main_cd5_r10_c5：不含发表年，成熟5年，参考数≥10，窗口被引数≥5；全部变体参数见disruption_manifest.json'],
    ]
    for index, row in enumerate(notes):
        intro.write_row(index, 0, row)
    intro.set_column(0, 0, 22)
    intro.set_column(1, 1, 110)

    def sheet(name, rows):
        if not rows:
            raise ValueError(f'Empty evidence table: {name}')
        worksheet = workbook.add_worksheet(name)
        columns = list(dict.fromkeys(key for row in rows for key in row))
        worksheet.write_row(0, 0, columns, header)
        for row_index, row in enumerate(rows, 1):
            for column_index, key in enumerate(columns):
                value = row.get(key)
                if isinstance(value, (dict, list)):
                    value = json.dumps(value, ensure_ascii=False)
                if value is not None:
                    worksheet.write(row_index, column_index, value)
        worksheet.freeze_panes(1, 2)
        worksheet.autofilter(0, 0, len(rows), len(columns) - 1)
        worksheet.set_column(0, len(columns) - 1, 22)

    for directory, table, name in [
        ('ngd-ranked', 'subjects', '学科原始比例'),
        ('ngd-ranked', 'comparisons', 'NGD父级内比较'),
        ('ngd-ranked', 'correlations', 'NGD描述相关'),
        ('ngd-ranked', 'distance_bands', 'NGD近中远组'),
        ('ngd-controls-final', 'year_type_controls', 'NGD年份类型控制'),
        ('ngd-controls-final', 'concepts_parent_intersection', 'Concepts父子交集'),
    ]:
        sheet(name, pq.read_table(root / directory / f'{table}.parquet').to_pylist())
    combined = []
    for aggregate_path in sorted((root / 'aggregates').glob('*.parquet')):
        if 'baseline' not in aggregate_path.name and 'strata' not in aggregate_path.name:
            combined.extend(pq.read_table(aggregate_path).to_pylist())
    sheet('颠覆度全口径', combined)
    sheet('全队列主CD', json.loads((root / 'global_main_metrics.json').read_text())['metrics'])
    statistics = json.loads((root / 'report-statistics.json').read_text())
    sheet('CD学科相关', statistics['cd_correlations'])
    sheet('CD年份类型对照', statistics['year_type_cd_contrasts'])
    workbook.close()
    return path


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('root', type=Path)
    print(export(parser.parse_args().root))
