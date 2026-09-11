import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync, readdirSync} from 'node:fs';
import {sourceProfile, filterCharts, parseSources, reportHref} from '../src/report/sources.js';
import {plotKind, plotRows, lineSegments} from '../src/report/chartGeometry.js';
import {decodeChartRows} from '../src/report/schema.js';

const charts = readdirSync('public/data/snapshot').filter(name => name !== 'manifest.json').flatMap(name => JSON.parse(readFileSync(`public/data/snapshot/${name}`)).charts.map(decodeChartRows));

test('all published analyses have explicit source scopes; multiple sources never imply union', () => {
  assert.equal(charts.length, 109);
  assert(charts.every(chart => sourceProfile(chart).key !== 'unclassified'));
  assert.equal(filterCharts(charts, ['rw', 'oa']).length, charts.length);
  assert.equal(filterCharts(charts, []).length, 0);
  assert(filterCharts(charts, ['rw']).every(chart => chart.population_key === 'B' && !['Q1', 'Q2'].includes(chart.chart_id)));
  assert(filterCharts(charts, ['oa']).every(chart => ['A0', 'A1', 'A1_over_D', 'D'].includes(chart.population_key)));
  assert(charts.filter(chart => chart.population_key === 'C').every(chart => sourceProfile(chart).key === 'matched'));
});

test('Concepts is never mislabeled as RW-only; matching diagnostics need both sources', () => {
  assert.equal(filterCharts(charts, ['rw']).filter(chart => chart.chart_id.startsWith('concepts')).length, 0);
  assert.equal(filterCharts(charts, ['oa']).filter(chart => chart.chart_id.startsWith('concepts')).length, 3);
  assert.equal(filterCharts(charts, ['rw', 'oa']).filter(chart => chart.chart_id.startsWith('concepts')).length, 6);
  assert(charts.filter(chart => ['Q1', 'Q2'].includes(chart.chart_id)).every(chart => sourceProfile(chart).required.length === 2));
});

test('dataset selection is canonical, shareable and invalid values fail closed', () => {
  assert.deepEqual(parseSources(null).sources, ['rw', 'oa']);
  assert.deepEqual(parseSources('oa,rw').sources, ['rw', 'oa']);
  for (const value of ['', 'union', 'rw,rw', 'rw,unknown']) assert(parseSources(value).error);
  const url = reportHref('fields', ['oa'], 'concepts/A1-concepts-level-0');
  const params = new URLSearchParams(url.split('?')[1]);
  assert.equal(params.get('sources'), 'oa');
  assert.equal(params.get('slice'), 'concepts/A1-concepts-level-0');
});

test('interactive charts retain published counts and finite sorted coordinates', () => {
  for (const chart of charts.filter(chart => plotKind(chart))) {
    const rows = plotRows(chart);
    assert(rows.every(row => Number.isFinite(row.position)));
    assert(rows.every((row, index) => index === 0 || row.position >= rows[index - 1].position));
    for (const row of rows) {
      const original = chart.rows.find(candidate => candidate.id === row.id);
      assert.equal(row.value, original.value);
      assert.equal(row.denominator, original.denominator);
    }
  }
});

test('missing annual cells do not become zero or an invented connecting line', () => {
  const chart = {chart_id: 'T1', rows: [{id: '1', year: 2000, value: 2}, {id: '2', year: 2001, value: null}, {id: '3', year: 2002, value: 0}]};
  const rows = plotRows(chart);
  assert.equal(rows.length, 2);
  assert.equal(lineSegments(rows).length, 2);
  assert.equal(rows[1].value, 0);
});
