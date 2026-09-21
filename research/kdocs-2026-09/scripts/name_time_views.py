from pathlib import Path
import hashlib
import re
import zipfile

from lxml import etree

BASE = Path('/tmp/retraction-kdocs-20260916')
source = BASE / 'event-year-v9-backup/retraction-event-year.pptx'
destination = BASE / 'event-year/retraction-event-year.pptx'
namespace = {'a': 'http://schemas.openxmlformats.org/drawingml/2006/main'}
replacements = {
    '原有分析：2000—2025 发表队列': '发表年份视角：2000—2025 年发表的文献',
    '新增第 25—31 页：2000—2025 撤稿发生年': '撤稿年份视角：2000—2025 年被记录撤稿的文献',
    '研究转场 / 从「何时发表」到「何时撤稿」': '两种时间视角 / 按发表年份观察 → 按撤稿年份观察',
    '新增 / RW × OPENALEX / 撤稿发生年 2000—2025': '撤稿年份视角 / RW × OPENALEX / 2000—2025 年',
    '新增 / RW × OPENALEX / 按撤稿发生年观察': '撤稿年份视角 / RW × OPENALEX / 2000—2025 年',
    '新增撤稿年份分析：2026-09-17': '报告更新：2026-09-17',
    '新增撤稿年聚合：': '撤稿年份视角聚合：',
    '不是在原有 59,028 条样本中改分组。': '不是将 59,028 条发表年份样本直接改分组。',
}
changed = []
with zipfile.ZipFile(source) as original, zipfile.ZipFile(destination, 'w', zipfile.ZIP_DEFLATED) as updated:
    for entry in original.infolist():
        payload = original.read(entry.filename)
        if re.fullmatch(r'ppt/slides/slide\d+\.xml', entry.filename):
            tree = etree.fromstring(payload)
            did_change = False
            for node in tree.findall('.//a:t', namespace):
                text = node.text or ''
                revised = text
                if entry.filename == 'ppt/slides/slide1.xml':
                    revised = revised.replace('OA 撤稿标记候选', '发表年份样本 · OA 候选').replace('匹配 RW 合格文献', '发表年份样本 · 匹配 RW')
                for old, new in replacements.items():
                    revised = revised.replace(old, new)
                if revised != text:
                    node.text = revised
                    did_change = True
            if did_change:
                payload = etree.tostring(tree, xml_declaration=True, encoding='UTF-8', standalone=True)
                changed.append(entry.filename)
        updated.writestr(entry, payload)
with zipfile.ZipFile(source) as original, zipfile.ZipFile(destination) as updated:
    for name in original.namelist():
        if name not in changed:
            assert original.read(name) == updated.read(name), name
    for name in changed:
        texts = etree.fromstring(updated.read(name)).findall('.//a:t', namespace)
        assert not any('新增' in (node.text or '') for node in texts)
print('Changed slide text only:', changed)
print('SHA1', hashlib.sha1(destination.read_bytes()).hexdigest())
