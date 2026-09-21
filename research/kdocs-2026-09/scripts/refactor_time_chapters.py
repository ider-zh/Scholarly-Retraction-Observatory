import os

os.environ['PPT_OUTPUT_DIR'] = '/tmp/retraction-kdocs-20260916/event-year'
source_code = open('/tmp/retraction-kdocs-20260916/build_deck.py').read().split("item=slide('撤稿集中在哪里？'")[0]
exec(compile(source_code, 'presentation-helpers', 'exec'))

import hashlib

SOURCE = BASE / 'event-year-v10-backup/retraction-event-year.pptx'
DECK = Presentation(SOURCE)
original = list(DECK.slides)

def replace_text(shape, value):
    frame = shape.text_frame
    paragraph = frame.paragraphs[0]
    if paragraph.runs:
        paragraph.runs[0].text = value
        for run in list(paragraph.runs)[1:]:
            run._r.getparent().remove(run._r)
    else:
        paragraph.text = value
    for extra in list(frame.paragraphs)[1:]:
        extra._p.getparent().remove(extra._p)

cover = original[0]
for shape in list(cover.shapes):
    shape._element.getparent().remove(shape._element)
text(cover, 'SCHOLARLY RETRACTION OBSERVATORY / 阅读地图', .75, .35, 14.5, .4, 13, True, BLUE)
text(cover, '撤稿集中在哪里，发生在什么时候？', .75, .95, 14.5, .7, 32, True)
text(cover, '同一研究，两个问题；按发表年与按撤稿年，分别建立样本。', .75, 1.80, 14.5, .5, 20, False, MUTED)
for left, shade, heading in [(.8, BLUE, '第一部分 / 发表年份视角'), (8.3, RED, '第二部分 / 撤稿年份视角')]:
    line(cover, left, 2.60, 6.8, shade)
    text(cover, heading, left, 2.85, 6.8, .5, 24, True, shade)
text(cover, '2000—2025 年发表的合格文献', .8, 3.52, 6.8, .5, 21)
text(cover, '77,414 条 OA 撤稿标记候选\n59,028 条 RW 匹配撤稿文献', .8, 4.23, 6.8, 1.25, 27, True, BLUE)
text(cover, '学科内已观测撤稿比例：\n除以同学科全部合格 OA 发文。\n原因分析仅在上述 RW 样本中开展。', .8, 5.85, 6.8, 1.35, 18)
text(cover, '2000—2025 年被记录撤稿的文献', 8.3, 3.52, 6.8, .5, 21)
text(cover, '58,345 条', 8.3, 4.23, 6.8, .75, 38, True, RED)
text(cover, 'RW 匹配文献；不再限制原文发表年', 8.3, 5.08, 6.8, .5, 18)
text(cover, '年度撤稿文献的学科构成：\n除以当年全部合格匹配撤稿文献。\n这一口径不开展原因分析。', 8.3, 5.85, 6.8, 1.35, 18)
text(cover, '两种视角的样本有交集，不能相加；OA 与 RW 也不能相加。比例均不是学术不端发生率。', .8, 7.55, 14.4, .4, 15, False, MUTED)
line(cover, .75, 8.2, 14.5, '#D1D8D8', .012)
text(cover, '阅读顺序：发表年份分析及原因 → 撤稿年份分析 → 两种视角的结论与边界', .8, 8.38, 13.5, .3, 12, False, MUTED)
text(cover, '01', 14.65, 8.32, .6, .35, 15, True, BLUE)

for index in list(range(1,24)) + list(range(31,36)):
    item = original[index]
    replace_text(item.shapes[0], '第一部分 · 发表年份视角 / ' + item.shapes[0].text)
    for shape in item.shapes:
        if shape.has_text_frame and shape.text.startswith('SCHOLARLY RETRACTION OBSERVATORY'):
            replace_text(shape, '发表年份样本 / 2000—2025 年发表 · OA 撤稿候选 77,414 / 匹配 RW 59,028')
replace_text(original[31].shapes[2], '仅分析发表年份样本：59,028 条匹配 RW 文献；不是 58,345 条撤稿年份样本。同篇原因标签取并集。')
replace_text(original[32].shapes[2], '仅分析 59,028 条发表年份样本；每列分母为该 Field 内匹配撤稿文献，不是全部发文。展示总体前 8 个原因族。')
for item in [original[31], original[32]]:
    for shape in item.shapes:
        if shape.has_text_frame and shape.text.startswith('发表年份样本 /'):
            replace_text(shape, '发表年份视角 / RW 原因分析总体 59,028 · 各图分母见图注，不使用撤稿年份样本')
replace_text(original[34].shapes[0], '第一部分 · 发表年份视角 / 本章小结')
for index in range(24,31):
    item = original[index]
    replace_text(item.shapes[0], '第二部分 · 撤稿年份视角 / RW × OPENALEX / 2000—2025 年')
    for shape in item.shapes:
        if shape.has_text_frame and shape.text.startswith('SCHOLARLY RETRACTION OBSERVATORY'):
            replace_text(shape, '撤稿年份样本 / 2000—2025 年撤稿 · 匹配 RW 58,345 · 不限制原文发表于该时间窗')
            for paragraph in shape.text_frame.paragraphs:
                paragraph.font.color.rgb = color(RED)
replace_text(original[24].shapes[2], '前一章的学科分布与原因分析到此结束；现在重新选样，观察每年发生撤稿的文献来自哪些学科。')

closing = slide('两条时间线，回答不同的问题', '综合结论 / 两种视角不混用',
    '数量、比例和原因都必须带上样本范围；不能把一种口径的结论移植到另一种口径。',
    '分类为快照时的标签，年度记录可能存在日期不确定性；不能据此裁定不端或推断因果。')
text_columns(closing, [
    ('发表年份视角', '哪些发表队列已被观察到撤稿？\nOA 候选 77,414；匹配 RW 59,028。\n学科内比例的分母是合格 OA 发文。\n原因覆盖率另以匹配撤稿样本为分母。'),
    ('撤稿年份视角', '各年撤稿记录的学科构成如何变化？\n匹配 RW 58,345。\n年度学科占比的分母是当年全部合格匹配撤稿文献。\n占比下降不等于数量减少。'),
    ('比较的边界', '两种视角不是独立样本，不能相加。\nConcepts 是多标签；主 Topics 是单一路径。\n原因分析仅针对发表年份样本。\n不同分母的百分比不能直接比较。')
], top=2.55)
closing.notes_slide.notes_text_frame.text = '结构性总结，不新增统计或改变任何数据。发表年份样本与撤稿年份样本的详细口径见各章节方法页。'
identifiers = list(DECK.slides._sldIdLst)
order = list(range(24)) + list(range(31,36)) + list(range(24,31)) + [37,36]
for identifier in identifiers:
    DECK.slides._sldIdLst.remove(identifier)
for index in order:
    DECK.slides._sldIdLst.append(identifiers[index])
for number, item in enumerate(DECK.slides, 1):
    for shape in item.shapes:
        if shape.has_text_frame and shape.left > Inches(14.5) and shape.top > Inches(8):
            replace_text(shape, f'{number:02d}')
        if shape.has_text_frame and '第 25—31 页' in shape.text:
            for paragraph in shape.text_frame.paragraphs:
                for run in paragraph.runs:
                    run.text = run.text.replace('第 25—31 页', '第 30—36 页')
    if item.has_notes_slide:
        frame = item.notes_slide.notes_text_frame
        for paragraph in frame.paragraphs:
            for run in paragraph.runs:
                run.text = run.text.replace('第 25—31 页', '第 30—36 页')
assert len(DECK.slides) == 38
for item in DECK.slides:
    for shape in item.shapes:
        assert shape.left >= 0 and shape.top >= 0
        assert shape.left + shape.width <= DECK.slide_width + 100
        assert shape.top + shape.height <= DECK.slide_height + 100
DECK.save(OUT / 'retraction-event-year.pptx')
before = Presentation(SOURCE)
after = Presentation(OUT / 'retraction-event-year.pptx')
for new_index, old_index in enumerate(order):
    if old_index == 37:
        continue
    old, new = before.slides[old_index], after.slides[new_index]
    image_hashes = lambda item: [hashlib.sha256(shape.image.blob).hexdigest() for shape in item.shapes if shape.shape_type == 13]
    tables = lambda item: [[[cell.text for cell in row.cells] for row in shape.table.rows] for shape in item.shapes if shape.has_table]
    assert image_hashes(old) == image_hashes(new)
    assert tables(old) == tables(new)
print(json.dumps({'slides': 38, 'publication_chapter': [2,29], 'reasons': [25,26], 'event_chapter': [30,36], 'closing': 37, 'sources': 38, 'all_chart_images_and_tables_unchanged': True, 'sha1':hashlib.sha1((OUT / 'retraction-event-year.pptx').read_bytes()).hexdigest()}))
