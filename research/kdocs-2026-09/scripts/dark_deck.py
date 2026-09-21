import os
import json
import pathlib
import re
import shutil

DEST=pathlib.Path('/tmp/retraction-dark-20260921')
os.environ['PPT_OUTPUT_DIR']=str(DEST)
helper=pathlib.Path('/tmp/retraction-kdocs-20260916/build_deck.py').read_text().split("item=slide('撤稿集中在哪里？'")[0]
palette={'#176B87':'#65D8EA','#B45C42':'#FFAC8B','#182B35':'#F0F5FA','#61717A':'#B7C8D8',
    '#FAFAF7':'#101C2D','#7C6B9B':'#C5ABFA','#5C8861':'#8CDEAE','#A7822F':'#F2D175',
    '#477D81':'#78A8F0','#CAD1D3':'#41566F','#E4E8E6':'#2B3D53','#E5EFEE':'#1B3048'}
def dark_code(value):
    for old,new in palette.items():value=value.replace(old,new)
    return value
exec(compile(dark_code(helper),'dark-figure-helpers','exec'))
OUT=DEST
AUDIT=json.loads((OUT/'audit.json').read_text())
EVENT=json.loads(pathlib.Path('/tmp/retraction-nick-20260920/analysis.json').read_text())
SUMMARY=EVENT['summary'];GROUPS=EVENT['groups'];groups=GROUPS
DENOMINATORS=np.array(SUMMARY['annual_denominators']);base=DENOMINATORS
YEARS=np.array(SUMMARY['years'])
COLORS=[BLUE,RED,'#C5ABFA','#8CDEAE','#F2D175','#78A8F0'];colors=COLORS
TRANSLATIONS.update({'World Wide Web':'万维网','Physiology':'生理学','Biomedical Engineering':'生物医学工程',
    'Industrial and Manufacturing Engineering':'工业与制造工程','Control and Systems Engineering':'控制与系统工程',
    'Mechanical Engineering':'机械工程','Civil and Structural Engineering':'土木与结构工程',
    'Electrical and Electronic Engineering':'电气与电子工程','Law':'法学'})
evidence_rows=list(csv.DictReader(open('/tmp/retraction-nick-20260920/all-subjects.csv',encoding='utf-8-sig')))
event_code=pathlib.Path('/tmp/retraction-kdocs-20260916/event_deck.py').read_text()
exec(compile(dark_code(event_code[event_code.index('def attach_notes'):event_code.index("item = slide('这些文献")]),'event-chart-functions','exec'))
distribution_event('concepts_l0','Concepts')
trends_event('concepts_l0','Concepts trend')
distribution_event('topics_field','Field')
trends_event('topics_field','Field trend')
selection=[];evidence=evidence_rows
child_code=pathlib.Path('/tmp/retraction-kdocs-20260916/nick_refine.py').read_text()
exec(compile(dark_code(child_code[child_code.index('def child_slide'):child_code.index('for parent_group,child_group')]),'child-chart-functions','exec'))
images={4:OUT/'concepts_l0-distribution.png',5:OUT/'concepts_l0-trend.png',9:OUT/'topics_field-distribution.png',10:OUT/'topics_field-trend.png'}
for parent_group,child_group,pages in [('concepts_l0','concepts_l1',[6,7,8]),('topics_field','topics_subfield',[11,12,13])]:
    for parent,number in zip(GROUPS[parent_group]['nodes'][:3],pages):
        child_slide(parent,child_group)
        images[number]=OUT/f"children-{child_group}-{parent['id'].split('/')[-1]}.png"
for number,taxonomy,nodes,mode in [(16,'concepts',CONCEPTS,'distribution'),(17,'concepts',TOP_CONCEPTS,'trend'),
    (18,'topics',FIELDS,'distribution'),(19,'topics',TOP_FIELDS,'trend')]:
    if mode=='distribution':distribution('Appendix','OA',nodes,'A1',taxonomy)
    else:trend_slide('Appendix','OA',nodes,'A1',taxonomy)
    images[number]=OUT/f'figure-{len(DECK.slides):02d}-{mode}.png'

source=pathlib.Path('/tmp/retraction-nick-20260920/学科撤稿研究_尼克简报_20260920.pptx')
shutil.copy2(source,OUT/'before-dark.pptx')
DECK=Presentation(source)
baseline_notes=[item.notes_slide.notes_text_frame.text for item in DECK.slides]
for number,item in enumerate(DECK.slides,1):
    item.background.fill.solid();item.background.fill.fore_color.rgb=color(BG)
    for element in item._element.xpath('.//a:srgbClr'):
        value='#'+element.get('val').upper()
        element.set('val',palette.get(value,'#344B65' if value in ['#D1D8D8','#FFFFFF'] else value).lstrip('#'))
    for shape in item.shapes:
        if shape.has_text_frame:
            for paragraph in shape.text_frame.paragraphs:
                if paragraph.font.color.type is None:paragraph.font.color.rgb=color(INK)
    if number in images:
        pictures=[shape for shape in item.shapes if shape.shape_type==13]
        assert len(pictures)==1
        picture=pictures[0]
        position=(picture.left,picture.top,picture.width,picture.height)
        item.shapes.add_picture(str(images[number]),*position[:2],width=position[2],height=position[3])
        picture._element.getparent().remove(picture._element)

def clear(item):
    for shape in list(item.shapes):shape._element.getparent().remove(shape._element)

def header(item,number,title,subtitle):
    text(item,'研究数据与分类 / 固定快照口径',.75,.36,14.5,.30,12,True,BLUE)
    text(item,title,.75,.93,14.5,.65,32,True)
    text(item,subtitle,.75,1.75,14.5,.5,17,False,MUTED)
    line(item,.75,8.2,14.5,'#344B65',.012)
    text(item,'OA 2026-06-26 · RW 2026-09-10 · 正文按 2000—2025 撤稿记录年',.75,8.38,13.6,.30,11,False,MUTED)
    text(item,f'{number:02d}',14.65,8.32,.6,.35,15,True,BLUE)

def linked(item,value,url,left,top,width):
    shape=text(item,value,left,top,width,.3,11,False,MUTED)
    shape.text_frame.paragraphs[0].runs[0].hyperlink.address=url

item=DECK.slides[1];clear(item)
header(item,2,'数据样本：下载了多少，分析了哪些？','下载清单统计与正文匹配样本分开报告；Work 是文献记录，不仅指期刊论文。')
for left,heading in [(.75,'OpenAlex：学科与文献'),(5.7,'RW：补充撤稿时间'),(10.65,'匹配后：正文研究样本')]:
    line(item,left,2.43,4.5,BLUE,.025)
    text(item,heading,left,2.66,4.55,.6,23,True)
text(item,'510,372,821',.75,3.43,4.55,.65,33,True,BLUE)
text(item,'快照 Work 总数（core + expansion）',.75,4.1,4.55,.42,15,False,MUTED)
text(item,'115,627',.75,4.69,4.55,.58,29,True)
text(item,'其中：带撤稿标记的 Work',.75,5.3,4.55,.40,16,False,MUTED)
text(item,'研究主体 core：317,820,190 条\n其中撤稿标记：114,538 条\nOA 撤稿标记也来源于 RW，\n并非独立发现的第二批撤稿。',.75,5.96,4.55,1.62,17)
text(item,'66,700',5.7,3.43,4.55,.65,33,True,BLUE)
text(item,'按原文身份去重的撤稿文献',5.7,4.1,4.55,.42,16,False,MUTED)
text(item,'原始 CSV：72,476 条事件记录\n其中 Retraction：66,869 条\n去重后：66,700 条原文',5.7,4.83,4.55,1.5,18)
text(item,'原始表还含更正、关注声明等；\n不能将 CSV 行数直接称为论文数。\nRW 为正文提供撤稿日期。',5.7,6.39,4.55,1.22,17)
text(item,'58,345',10.65,3.43,4.55,.65,33,True,BLUE)
text(item,'2000—2025 年的匹配撤稿文献',10.65,4.1,4.55,.42,16,False,MUTED)
text(item,'原文 DOI / PMID 精确匹配\n60,311 条不同 OA Work\n→ 60,288 条通过共同资格筛选\n→ 58,345 条落在撤稿研究期',10.65,4.83,4.55,1.85,18)
text(item,'不要求 OA 同时标记撤稿；\n附录另用 OA 发表年份样本。',10.65,6.82,4.55,.8,17)
linked(item,'来源：本地验收清单、RW 原始表及去重结果；OA 撤稿字段说明',
    'https://help.openalex.org/data/works/attributes/',.75,7.79,14.5)
item.notes_slide.notes_text_frame.text=json.dumps({'snapshot_audit':AUDIT,'method':SUMMARY,
    'source':'https://help.openalex.org/data/works/attributes/','expanded_works':192552631,'expanded_flagged':1089,
    'warning':'The 649096577 rows in the all-entity manifest are NOT a Work count. Totals here are Work records only.'},ensure_ascii=False)

item=DECK.slides[2];clear(item)
header(item,3,'同一批文献，两套学科分类','Concepts 与 Topics 是两套体系；L0、L1 是 Concepts 内的层级，不是四个并列层级。')
line(item,.75,2.43,6.9,BLUE,.025);line(item,8.1,2.43,7.1,RED,.025)
text(item,'Concepts｜原有概念标签',.75,2.64,6.8,.5,25,True,BLUE)
text(item,'2022-01：随 OpenAlex 启用\n承接 MAG 概念分类；OpenAlex 于 2022-01-03 上线。\n2024 年起由 Topics 接替；现为已停更旧体系。',.75,3.35,6.8,1.23,18)
text(item,'65,026 个概念 · L0—L5 六层',.75,4.89,6.8,.6,25,True)
text(item,'本报告使用：L0 19 个主学科\n                       L1 284 个二级概念',.75,5.65,6.8,.94,23,True,BLUE)
text(item,'一篇文献可关联多标签，分类之间可重叠。\nL1 按标签全体文献计数，非与父 L0 取交集。',.75,6.88,6.8,.82,17)
text(item,'Topics｜研究主题路径',8.1,2.64,7.1,.5,25,True,RED)
text(item,'2024-02-12：官方宣布 API 上线\n基于研究主题分类；网页与快照随后接入。\n本文仅选 primary_topic，沿主主题路径归类。',8.1,3.35,7.1,1.23,18)
text(item,'4 Domain → 26 Field',8.1,4.89,7.1,.6,25,True)
text(item,'→ 252 Subfield → 4,516 Topic',8.1,5.65,7.1,.6,25,True,RED)
text(item,'本报告研究 Field 与 Subfield。\n主路径同层互斥；缺失分类仍保留在总分母。',8.1,6.88,7.1,.82,17)
linked(item,'历史来源：OpenAlex 上线公告', 'https://blog.openalex.org/openalex-launch/',.75,7.79,4.0)
linked(item,'Topics 官方发布公告','https://groups.google.com/g/openalex-users/c/-A0Q-cxDzCs',4.9,7.79,3.8)
text(item,'类别数：本地 2026-06-26 分类实体表',9.0,7.79,6.2,.3,11,False,MUTED)
item.notes_slide.notes_text_frame.text=json.dumps({'vocabulary':AUDIT['vocabulary'],
    'history_sources':['https://blog.openalex.org/openalex-launch/','https://help.openalex.org/data/concepts/',
    'https://groups.google.com/g/openalex-users/c/-A0Q-cxDzCs','https://help.openalex.org/data/topics/'],
    'scope':'65,026 includes all Concept levels. L0=19,L1=284 in this snapshot; counts of categories, not documents.',
    'history_caveat':'Topics launch date is the official API announcement, not an exact snapshot deployment date.'},ensure_ascii=False)

item=DECK.slides[3]
for shape in item.shapes:
    if shape.shape_type==13:shape.top=Inches(2.15);shape.height=Inches(4.30)
    elif shape.has_text_frame and Inches(7.0)<shape.top<Inches(8.2):
        if '数量 n' in shape.text:shape.top=Inches(7.65)
        else:shape._element.getparent().remove(shape._element)
text(item,'分类缺失：1 条 / 58,345（0.0017%）',.75,6.5,14.5,.35,17,True,BLUE)
text(item,'W4210257207 · Bistability in the polarity circuit of yeast · RW 撤稿日期：2022-02-01',.75,6.96,14.5,.34,15)
text(item,'本地 concepts=[]，而 Topics 有分类；保留在总分母，不按题名或 Topics 补填。缺失原因尚未核实。',.75,7.34,14.5,.28,14,False,MUTED)
original_note=json.loads(item.notes_slide.notes_text_frame.text)
original_note['missing_l0_audit']=AUDIT['missing_l0']
original_note['case_sources']=['https://pubmed.ncbi.nlm.nih.gov/35104150/','https://pmc.ncbi.nlm.nih.gov/articles/PMC9236149/']
original_note['missing_explanation']='Empty concepts list in local snapshot. This is a document-level missing label, not missing L0 categories. No inferred labels or record removals.'
item.notes_slide.notes_text_frame.text=json.dumps(original_note,ensure_ascii=False)

for number,item in enumerate(DECK.slides,1):
    if number not in [2,3,4]:assert item.notes_slide.notes_text_frame.text==baseline_notes[number-1]
    assert item.background.fill.fore_color.rgb==color(BG)
assert len(DECK.slides)==19
from lxml import etree
for part in DECK.part.package.iter_parts():
    if str(part.partname).startswith('/ppt/theme/') and str(part.partname).endswith('.xml'):
        theme=etree.fromstring(part.blob)
        for element in theme.xpath('//a:clrScheme/a:hlink/a:srgbClr | //a:clrScheme/a:folHlink/a:srgbClr',
            namespaces={'a':'http://schemas.openxmlformats.org/drawingml/2006/main'}):
            element.set('val',BLUE.lstrip('#'))
        part._blob=etree.tostring(theme,xml_declaration=True,encoding='UTF-8',standalone=True)
DECK.save(OUT/'OpenAlex撤稿的学科分布与年度变化_深色版.pptx')
(OUT/'chart-build.json').write_text(json.dumps({'images':{number:str(path) for number,path in images.items()},
    'unchanged_notes_pages':[number for number in range(1,20) if number not in [2,3,4]],
    'palette':palette,'category_counts':AUDIT['vocabulary']},ensure_ascii=False,indent=2))
print('Built 19-slide dark deck; 14 charts regenerated; underlying statistics unchanged.')
