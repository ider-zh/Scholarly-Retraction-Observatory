import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {validateManifest, validateChunk} from '../src/report/schema.js';
import {CHAPTERS, chapterFinding, chapterEvidence, chapterCaption, chapterMetricNote} from '../src/report/chapter.js';
import {filterCharts, sourceProfile, reportHref, parseSources} from '../src/report/sources.js';
import {selectChart, rowLabel, number} from '../src/report/reader.js';
import {plotKind} from '../src/report/chartGeometry.js';
import {aggregateSection} from '../src/report/sections.js';

const manifest = validateManifest(JSON.parse(readFileSync('public/data/snapshot/manifest.json')));
const sections = Object.fromEntries([...new Set(Object.keys(CHAPTERS).map(aggregateSection))].map(section => [section, validateChunk(JSON.parse(readFileSync(`public/data/snapshot/${section}.json`)), manifest, section)]));

test('all declared chapter analyses preserve source filtering and exact deep links', () => {
  assert.equal(Object.values(sections).reduce((total, chunk) => total + chunk.charts.length, 0), manifest.supported_slices.filter(slice => slice.section !== 'overview').length);
  for (const [section, chunk] of Object.entries(sections)) for (const sources of [['rw'], ['oa'], ['rw', 'oa']]) {
    const charts = filterCharts(chunk.charts, sources);
    for (const chart of chunk.charts) {
      const slice = `${chart.chart_id}/${chart.slice_id}`;
      const allowed = sourceProfile(chart).required.every(source => sources.includes(source));
      assert.equal(selectChart(charts, slice), allowed ? chart : null);
      const params = new URLSearchParams(reportHref(section, sources, slice).split('?')[1]);
      assert.equal(params.get('slice'), slice); assert.deepEqual(parseSources(params.get('sources')).sources, sources);
    }
  }
});

test('all chapter narratives, captions and evidence retain exact n/N, metric and cutoff without data mutation', () => {
  const before = JSON.stringify(sections);
  for (const [section, chunk] of Object.entries(sections)) for (const original of chunk.charts) {
    const chart = {...original, rows: original.rows.map(row => ({...row, label: rowLabel(row, original)}))};
    const evidence = chapterEvidence(chart, section);
    assert.equal(evidence.aggregate, `data/snapshot/${section}.json`);
    assert.equal(evidence.cutoff, original.metric_observation_cutoff);
    assert.equal(evidence.metric, original.metric_id);
    assert.deepEqual(evidence.cells, original.rows.map(row => ({id: row.id, n: row.numerator, N: row.denominator, value: row.value, unit: row.unit})));
    assert(chapterFinding(chart)); assert(chapterMetricNote(chart));
    assert(chapterCaption(chart).includes(original.metric_observation_cutoff));
    assert(chapterCaption(chart).includes(sourceProfile(original).label));
  }
  assert.equal(JSON.stringify(sections), before);
});

test('changed fractional metrics and unavailable states cannot retain old findings', () => {
  const original = sections.geography.charts.find(chart => chart.chart_id === 'G1');
  const changed = {...original, metric_id: 'fractional_work_count', insights: [], rows: original.rows.map(row => ({...row, value: row.fractional_work_count, unit: 'work_equivalents'}))};
  assert(chapterFinding(changed).includes(number(changed.rows[0].value)));
  assert(chapterCaption(changed).includes('篇等价值'));
  assert.match(chapterMetricNote(changed), /不重新分配/);
  assert.equal(chapterFinding({...original, status: 'missing_data', unavailable_reason: '数据未提供'}), '数据未提供');
  assert.match(chapterFinding({...original, insights: [], rows: [{label: '零记录', value: 0, numerator: 0, denominator: 20, unit: 'works'}]}), /0 篇/);
  assert.match(chapterFinding({...original, insights: [], rows: [{label: '缺失', value: null}]}), /不等于观测为零/);
});

test('plot grammar remains specific to research questions', () => {
  for (const [identifier, kind] of [['T1', 'line'], ['T4', 'line'], ['F3', 'scatter'], ['R4', 'interval'], ['P1', 'scatter'], ['E3', 'line'], ['C1', 'line']]) assert.equal(plotKind({chart_id: identifier}), kind);
  assert.equal(plotKind({chart_id: 'P2', control_policy: {}}), 'control');
  assert.equal(plotKind({chart_id: 'T2'}), null);
});
