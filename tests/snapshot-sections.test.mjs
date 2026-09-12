import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {validateChunk} from '../src/report/schema.js';
import {REPORT_PAGES, aggregateSection, sectionData} from '../src/report/sections.js';
import {parseReportRoute} from '../src/report/routes.js';
import {topicCatalog} from '../src/report/topics.js';
import {chapterEvidence} from '../src/report/chapter.js';

const manifest = JSON.parse(readFileSync('public/data/snapshot/manifest.json'));
const chunk = validateChunk(JSON.parse(readFileSync('public/data/snapshot/fields.json')), manifest, 'fields');
const current = {charts: chunk.charts, explorer: chunk.discipline_explorer};

test('three top-level discipline routes share validated fields data without mixing classification', () => {
  const before = JSON.stringify(current), combined = [];
  for (const section of ['subjects', 'topics', 'concepts']) {
    const route = parseReportRoute(`#/snapshot/${section}?sources=rw%2Coa`, REPORT_PAGES);
    assert.equal(route.error, null); assert.equal(route.explorerSelection.taxonomy, section);
    assert.equal(aggregateSection(section), 'fields');
    const filtered = sectionData(current, section);
    assert.deepEqual(filtered.explorer.taxonomies.map(taxonomy => taxonomy.id), [section]);
    assert.equal(filtered.explorer.taxonomies[0], current.explorer.taxonomies.find(taxonomy => taxonomy.id === section));
    combined.push(...filtered.charts);
    for (const chart of filtered.charts) assert.equal(chapterEvidence(chart, section).aggregate, 'data/snapshot/fields.json');
    assert(parseReportRoute(`#/snapshot/${section}?taxonomy=${section === 'subjects' ? 'topics' : 'subjects'}`, REPORT_PAGES).error);
  }
  assert.equal(new Set(combined).size, current.charts.length);
  assert.equal(combined.length, current.charts.length);
  assert.equal(JSON.stringify(current), before);
  assert.equal(sectionData(current, 'fields'), current);
});

test('fixed taxonomy topic cards require their own source and legacy routes remain exact', () => {
  for (const [section, source] of [['subjects', 'rw'], ['topics', 'oa'], ['concepts', 'oa']]) {
    const filtered = sectionData(current, section);
    for (const sources of [[source], [source === 'rw' ? 'oa' : 'rw']]) {
      const tree = topicCatalog(filtered.charts, sources, filtered.explorer).find(topic => topic.tree);
      assert.equal(tree.enabled, sources.includes(source));
    }
    const route = parseReportRoute(`#/snapshot/${section}/topic/discipline?sources=rw%2Coa&population=${section === 'subjects' ? 'B' : 'A1'}&node=all&metric=count`, REPORT_PAGES);
    assert.equal(route.error, null); assert.equal(route.page, section);
  }
  const route = parseReportRoute('#/snapshot/fields?sources=oa&taxonomy=topics&node=all', REPORT_PAGES);
  assert.equal(route.error, null); assert.equal(route.page, 'fields'); assert.equal(route.explorerSelection.taxonomy, 'topics');
});
