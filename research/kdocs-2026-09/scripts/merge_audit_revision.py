import json
from pathlib import Path
import posixpath
from zipfile import ZipFile
import xml.etree.ElementTree as ET

BASE = Path('/tmp/retraction-kdocs-20260916')
OUT = BASE / 'revision-audit'
selected = {3, 7, 8, 9, 10, 11, 14, 15, 16, 17, 20, 21, 22, 23, 26}
assert (BASE/'chart-evidence.csv').read_bytes() == (OUT/'chart-evidence.csv').read_bytes()
axis_audit = {entry['page']:entry for entry in json.loads((OUT/'axis-audit.json').read_text())}
for first, second in [(14,20),(15,21),(16,22),(17,23)]:
    for key in ['nodes','limits','ticks']:
        assert axis_audit[first][key] == axis_audit[second][key], (first, second, key)
replacements = {}
original = BASE/'updated-deck.pptx'
generated = OUT/'撤稿集中在哪里_学科专题_2000-2025.pptx'
target = OUT/'publication-reviewed.pptx'
with ZipFile(original) as old, ZipFile(generated) as new:
    for page in selected:
        name = f'ppt/slides/slide{page}.xml'
        replacements[name] = new.read(name)
        relations = f'ppt/slides/_rels/slide{page}.xml.rels'
        assert old.read(relations)==new.read(relations), relations
        for relationship in ET.fromstring(new.read(relations)):
            if relationship.attrib['Type'].endswith('/image'):
                media = posixpath.normpath(posixpath.join('ppt/slides',relationship.attrib['Target']))
                replacements[media] = new.read(media)
    with ZipFile(target,'w') as final:
        for entry in old.infolist():
            final.writestr(entry,replacements.get(entry.filename,old.read(entry.filename)))
with ZipFile(original) as old, ZipFile(target) as new:
    changed = [name for name in old.namelist() if old.read(name)!=new.read(name)]
    assert old.read('ppt/slides/slide27.xml')==new.read('ppt/slides/slide27.xml')
    assert all(name in replacements for name in changed)
(OUT/'revision-checks.json').write_text(json.dumps({'changed_parts':changed,'data_evidence_identical':True,
    'paired_axes_identical':True,'page27_preserved':True},ensure_ascii=False,indent=2))
print(json.dumps({'changed_parts':changed,'data_evidence_identical':True,'paired_axes_identical':True,'page27_preserved':True},ensure_ascii=False))
