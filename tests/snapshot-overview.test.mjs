import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {validateChunk, validateManifest} from '../src/report/schema.js';
import {overviewSelection, overviewNarrative, overviewEvidence, screeningRows} from '../src/report/overview.js';

const manifest = validateManifest(JSON.parse(readFileSync('public/data/snapshot/manifest.json')));
const {charts} = validateChunk(JSON.parse(readFileSync('public/data/snapshot/overview.json')), manifest, 'overview');
const screening = charts.find(chart => chart.chart_id === 'screening');

test('overview defaults to existing screening only for eligible sources and preserves exact deep links', () => {
  for (const sources of [['oa'], ['rw', 'oa']]) assert.equal(overviewSelection(charts, sources, ''), screening);
  assert.equal(overviewSelection(charts, ['rw'], ''), null);
  assert.equal(overviewSelection(charts, ['rw'], 'screening/A0-screening'), null);
  assert.equal(overviewSelection(charts, ['oa'], 'population-accounting/mixed_diagnostic-default'), null);
  for (const chart of charts) assert.equal(overviewSelection(charts, ['rw', 'oa'], `${chart.chart_id}/${chart.slice_id}`), chart);
  assert.equal(overviewSelection(charts, ['rw', 'oa'], 'missing/slice'), null);
});

test('finding, scope, cutoff and cells bind to the selected published slice without modifying data', () => {
  const before = JSON.stringify(charts);
  const narrative = overviewNarrative(screening);
  assert.match(narrative.finding, /50,331.*43.94%/);
  assert.equal(narrative.evidence.metric, screening.metric_id);
  assert.deepEqual(narrative.evidence.scope, screening.scope);
  assert.equal(narrative.evidence.cutoff, screening.metric_observation_cutoff);
  const changed = structuredClone(screening);
  const retained = changed.rows.find(row => row.id === 'retained_A1');
  Object.assign(retained, {numerator: 123, denominator: 1000, value: 12.3});
  changed.metric_observation_cutoff = '2025-01-01';
  assert.match(overviewNarrative(changed).finding, /1,000.*123.*12.3%/);
  assert.equal(overviewNarrative(changed).evidence.cutoff, '2025-01-01');
  for (const chart of charts) {
    const evidence = overviewEvidence(chart);
    assert.deepEqual(evidence.cells, chart.rows.map(row => ({id: row.id, n: row.numerator, N: row.denominator, value: row.value, unit: row.unit})));
    assert.equal(evidence.release_id, manifest.release_id);
  }
  screeningRows(screening);
  assert.equal(JSON.stringify(charts), before);
});

test('new slices cannot retain screening claims and unavailable values are not observations of zero', () => {
  const workTypes = charts.find(chart => chart.chart_id === 'work-types');
  assert.doesNotMatch(overviewNarrative(workTypes).finding, /43.94%/);
  assert.match(overviewNarrative(workTypes).finding, /88,913/);
  assert.equal(overviewNarrative(null), null);
  const unavailable = {...screening, status: 'missing_data', rows: [], unavailable_reason: '测试：信息缺失'};
  assert.equal(overviewNarrative(unavailable).boundary, '测试：信息缺失');
  assert.doesNotMatch(overviewNarrative(unavailable).finding, /50,331|43.94|0/);
  const values = {rows: [{id: 'zero', value: 0}, {id: 'missing', value: null}, {id: 'retained_A1', value: 12}]};
  assert.deepEqual(screeningRows(values).map(row => [row.id, row.value]), [['retained_A1', 12], ['zero', 0], ['missing', null]]);
});
