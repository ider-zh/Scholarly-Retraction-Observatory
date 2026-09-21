import os

os.environ['PPT_OUTPUT_DIR'] = '/tmp/retraction-kdocs-20260916/event-year'
source_code = open('/tmp/retraction-kdocs-20260916/build_deck.py').read().split("item=slide('撤稿集中在哪里？'")[0]
exec(compile(source_code, 'existing-presentation-helpers', 'exec'))

import hashlib

BASELINE = BASE / 'revision-audit/publication-reviewed.pptx'
DECK = Presentation(BASELINE)
original_slides = list(DECK.slides)
EVENT = json.loads((OUT / 'analysis.json').read_text())
SUMMARY = EVENT['summary']
GROUPS = EVENT['groups']
YEARS = np.array(SUMMARY['years'])
DENOMINATORS = np.array(SUMMARY['annual_denominators'])
COLORS = [BLUE, RED, '#7C6B9B', '#5C8861', '#A7822F', '#477D81']
TRANSLATIONS.update({'Electrical and Electronic Engineering': '电气与电子工程',
    'General Medicine': '综合医学', 'General Engineering': '综合工程学', 'Computational Theory and Mathematics': '计算理论与数学', 'Law': '法学'})
evidence_rows = list(csv.DictReader((OUT / 'all-subjects.csv').open(encoding='utf-8-sig')))

def attach_notes(item, group, nodes):
    selected_ids = {node['id'] for node in nodes}
    selected_rows = [row for row in evidence_rows if row['system'] == group and row['id'] in selected_ids]
    item.notes_slide.notes_text_frame.text = json.dumps({'method': SUMMARY, 'group': group,
        'metric': 'share of matched retracted Works, NOT retraction/publication rate', 'evidence': selected_rows}, ensure_ascii=False)

def image_chart(item, figure, name):
    path = OUT / f'{name}.png'
    figure.savefig(path, dpi=180)
    plt.close(figure)
    item.shapes.add_picture(str(path), Inches(.72), Inches(2.3), width=Inches(14.55), height=Inches(5.2))

def distribution_event(group, title):
    nodes = GROUPS[group]['nodes']
    concepts = group.startswith('concepts')
    item = slide(title, '新增 / RW × OPENALEX / 撤稿发生年 2000—2025',
        f"全时期合格匹配撤稿文献 {SUMMARY['total']:,} 条；按数量排序。右图分母为这批撤稿文献，而非全部发文。",
        'Concepts 多标签可重叠，比例之和可超过 100%；缺失项仍保留在分母。' if concepts else
        '每条 Work 沿 primary_topic 归类；包括缺失项后，Field 数量与比例完整分割这批撤稿文献。')
    figure, axes = plt.subplots(1, 2, figsize=(14.55, 5.2))
    figure.subplots_adjust(left=.22 if not concepts else .13, right=.94, bottom=.09, top=.93, wspace=.24)
    positions = np.arange(len(nodes))
    numerators = np.array([node['total'] for node in nodes])
    for index, axis in enumerate(axes):
        values = numerators if index == 0 else numerators / SUMMARY['total'] * 100
        axis.barh(positions, values, color=[MUTED if node['id'] == 'missing' else BLUE for node in nodes], height=.7)
        axis.set_yticks(positions, [label(node) for node in nodes] if index == 0 else [''] * len(nodes), fontsize=10)
        axis.invert_yaxis()
        axis.grid(axis='x', color='#E4E8E6')
        axis.set_axisbelow(True)
        axis.tick_params(length=0)
        axis.set_xlim(0, max(values) * 1.27)
        axis.set_title('撤稿文献数（条）' if index == 0 else '全部匹配撤稿文献中的学科占比（%）', fontsize=12, loc='left')
        for position, value in zip(positions, values):
            formatted = f'{int(value):,}' if index == 0 else ('<0.01%' if 0 < value < .01 else f'{value:.2f}%')
            axis.text(value + max(values) * .015, position, formatted, va='center', fontsize=9)
    image_chart(item, figure, group + '-distribution')
    attach_notes(item, group, nodes)

def trends_event(group, title):
    nodes = [node for node in GROUPS[group]['nodes'] if node['id'] in GROUPS[group]['top6']]
    concepts = group.startswith('concepts')
    qualifier = 'Concepts 保留既有标签，不另设分数门槛；多标签重叠，L1 非父子交集。' if concepts else '采用 primary_topic；Subfield 分母也是全样本，不是所属 Field。'
    item = slide(title, '新增 / RW × OPENALEX / 按撤稿发生年观察',
        '按 2000—2025 年撤稿总量固定选取六个学科；左右图使用同一组标签，不按各年排名更换。',
        '右图 = 当年学科撤稿数 / 当年全部匹配撤稿数；空心点表示年度 N<100，不是显著性检验。' + qualifier)
    figure, axes = plt.subplots(1, 2, figsize=(14.55, 5.2))
    figure.subplots_adjust(left=.055, right=.98, bottom=.24, top=.76, wspace=.16)
    for node, shade in zip(nodes, COLORS):
        counts = np.array(node['counts'])
        shares = np.divide(counts * 100., DENOMINATORS, out=np.full(26, np.nan), where=DENOMINATORS > 0)
        axes[0].plot(YEARS, counts, color=shade, linewidth=1.9, label=label(node))
        axes[1].plot(YEARS, shares, color=shade, linewidth=1.9)
        small = (DENOMINATORS > 0) & (DENOMINATORS < 100)
        axes[1].scatter(YEARS[small], shares[small], s=29, facecolors=BG, edgecolors=shade, zorder=4)
    for axis, heading in zip(axes, ['当年发生撤稿的文献数（条）', '年度撤稿文献中的学科占比（%）']):
        axis.set_title(heading, loc='left', fontsize=12)
        axis.set_xlim(2000, 2025)
        axis.set_ylim(bottom=0)
        axis.set_xticks([2000, 2005, 2010, 2015, 2020, 2025])
        axis.set_xlabel('撤稿发生年', fontsize=11)
        axis.grid(axis='y', color='#E4E8E6')
        axis.tick_params(length=0)
    axes[0].yaxis.set_major_formatter(ticker.StrMethodFormatter('{x:,.0f}'))
    handles, labels = axes[0].get_legend_handles_labels()
    figure.legend(handles, labels, loc='upper center', bbox_to_anchor=(.5, 1.02), ncol=3, frameon=False, fontsize=12)
    figure.text(.055, .095, '占比下降不等于撤稿数量减少，也可能是其他学科增长更快。请对照左图阅读。', fontsize=14, color=INK)
    figure.text(.055, .018, '年度 N 含分类缺失；2000 / 2001 / 2003 年 N = 34 / 34 / 79。完整年度 n/N 见本页备注。', fontsize=11, color=MUTED)
    image_chart(item, figure, group + '-trend')
    attach_notes(item, group, nodes)

item = slide('这些文献，究竟在哪一年被撤稿？', '研究转场 / 从「何时发表」到「何时撤稿」',
    '前面按发表年比较学科内撤稿占比；接下来按撤稿年，观察每年撤稿文献的学科构成。',
    'RW 提供撤稿日期，OA 提供学科；分类为 2026-06-26 快照，RW 为 2026-09-10 快照，不代表撤稿当年的分类。')
text(item, '不是换一根横轴，而是重新选取样本', .76, 2.40, 14.4, .45, 23, True, BLUE)
text(item, '60,311 条匹配 Work  →  60,288 条通过共同资格筛选  →  58,345 条于 2000—2025 年撤稿', .76, 3.02, 14.4, .50, 22, True)
text(item, '取消原文发表于 2000—2025 年的限制，纳入 516 条更早发表的文献；不是在原有 59,028 条样本中改分组。', .76, 3.65, 14.4, .50, 17, False, MUTED)
line(item, .76, 4.30, 6.9)
line(item, 8.05, 4.30, 7.0)
text(item, '此前：学科文献中，多少已被观察到撤稿？', .76, 4.50, 6.9, .65, 20, True)
text(item, '按原文发表年分组。\nOA 分子：带撤稿标记的合格文献。\nRW 分子：符合事件截止的合格匹配撤稿文献，\n不要求 OA 同时标记撤稿。\n分母：同发表年、同学科全部合格 OA 发文。', .76, 5.17, 6.9, 1.95, 16)
text(item, '接下来：每年撤稿，哪些学科占得更多？', 8.05, 4.50, 7.0, .65, 20, True)
text(item, '按每条 Work 最早有效 RW 撤稿日期归年。\n分子：该年、该学科的合格匹配撤稿文献。\n分母：该年全部合格匹配撤稿文献，含分类缺失。\n这是撤稿样本的构成，不是学科撤稿风险。', 8.05, 5.17, 7.0, 1.95, 16)
text(item, '范围核对：最早撤稿年早于 2000 的 458 条、晚于 2025 的 1,485 条不纳入；无有效撤稿日期者 0 条。', .76, 7.15, 14.4, .28, 13, False, MUTED)
text(item, '质量提示：213 条 OA 发表日期晚于 RW 撤稿日期，保留并披露；尚未检验其对分学科年度结果的影响。', .76, 7.47, 14.4, .25, 13, False, RED)
item.notes_slide.notes_text_frame.text = json.dumps(SUMMARY, ensure_ascii=False, indent=2)
distribution_event('concepts_l0', '撤稿发生以后：哪些主学科标签最常出现？')
trends_event('concepts_l0', 'Concepts L0：数量变化，还是构成变化？')
trends_event('concepts_l1', 'Concepts L1：六个高数量标签的撤稿时间线')
distribution_event('topics_field', '按主主题归类：撤稿文献分布在哪些 Field？')
trends_event('topics_field', 'Topics Field：同一年撤稿，学科份额如何变化？')
trends_event('topics_subfield', 'Topics Subfield：把撤稿时间线推进到子学科')

identifiers = list(DECK.slides._sldIdLst)
for identifier in identifiers:
    DECK.slides._sldIdLst.remove(identifier)
for identifier in identifiers[:24] + identifiers[30:] + identifiers[24:30]:
    DECK.slides._sldIdLst.append(identifier)
for number, item in enumerate(DECK.slides, 1):
    for shape in item.shapes:
        if shape.has_text_frame and shape.left > Inches(14.5) and shape.top > Inches(8):
            shape.text_frame.paragraphs[0].runs[0].text = f'{number:02d}'
        if 25 <= number <= 31 and shape.has_text_frame and abs(shape.top - Inches(7.65)) < 100:
            shape.top = Inches(7.79)
            shape.height = Inches(.40)
            for paragraph in shape.text_frame.paragraphs:
                paragraph.font.size = Pt(13)

for shape in DECK.slides[0].shapes:
    if shape.has_text_frame and shape.text.startswith('2000—2025 发表队列'):
        shape.text_frame.paragraphs[0].runs[0].text = '原有分析：2000—2025 发表队列'
        shape.text_frame.paragraphs[1].runs[0].text = '新增第 25—31 页：2000—2025 撤稿发生年'
for shape in DECK.slides[-1].shapes:
    if shape.has_text_frame and '本专题制作：2026-09-16' in shape.text:
        shape.text_frame.paragraphs[0].runs[0].text = shape.text.replace('本专题制作：2026-09-16', '新增撤稿年份分析：2026-09-17')
    if shape.has_text_frame and shape.text.startswith('public/data/snapshot/manifest.json'):
        paragraph = shape.text_frame.add_paragraph()
        paragraph.text = '新增撤稿年聚合：精确 n/N 见第 25—31 页备注'
        paragraph.font.name = 'Noto Sans CJK SC'
        paragraph.font.size = Pt(16)
        paragraph.font.color.rgb = color(INK)
DECK.slides[-1].notes_slide.notes_text_frame.text += '\n新增分析：event-year/analysis.json、all-subjects.csv。旧聚合不变；新分母为年度合格匹配撤稿文献。\n' + json.dumps(SUMMARY, ensure_ascii=False)
DECK.core_properties.subject = '2000–2025 发表队列与撤稿发生年：不同时间轴、不同分母'
assert len(DECK.slides) == 37
for item in DECK.slides:
    for shape in item.shapes:
        assert shape.left >= 0 and shape.top >= 0
        assert shape.left + shape.width <= DECK.slide_width + 100
        assert shape.top + shape.height <= DECK.slide_height + 100
DECK.save(OUT / 'retraction-event-year.pptx')
print(json.dumps({'slides': len(DECK.slides), 'new_pages': [25,31], 'sha1': hashlib.sha1((OUT / 'retraction-event-year.pptx').read_bytes()).hexdigest()}))
