import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {countryCell, countryStudy, countryTimeChart, validateCountryExplorer} from '../src/report/country.js';
import {disciplineCell, resolveStudy, disciplineTimeChart} from '../src/report/discipline.js';
import {decodeChartRows} from '../src/report/schema.js';
import {plotMaximum} from '../src/report/chartGeometry.js';

const fields = decodeExplorer(JSON.parse(readFileSync('public/data/snapshot/fields.json')).discipline_explorer);

test('small percentages use the plot space without changing other metrics or all-zero scales', () => {
  assert.equal(plotMaximum({metric_id: 'proportion'}, [{value: .03}, {value: .15}]), .15);
  assert.equal(plotMaximum({metric_id: 'proportion'}, [{value: 0}]), 1);
  assert.equal(plotMaximum({metric_id: 'count'}, [{value: .15}]), 1);
});

test('published country-year arrays validate and reproduce existing country cohort rates', () => {
  const chunk = JSON.parse(readFileSync('public/data/snapshot/geography.json'));
  const manifest = JSON.parse(readFileSync('public/data/snapshot/manifest.json'));
  const data = validateCountryExplorer(chunk.country_explorer, manifest);
  let checked = 0;
  for (const chart of chunk.charts.map(decodeChartRows).filter(chart => chart.chart_id === 'G1' && chart.slice_id.includes('institution_country') && chart.rows.some(row => row.unit === 'per_10k'))) {
    const population = chart.population_key === 'A1_over_D' ? 'A1' : 'C_D';
    for (const row of chart.rows) {
      const node = data.nodes.find(node => node.id === row.id);
      assert(node, row.id);
      const cell = countryCell(node, population, 'rate');
      assert.equal(cell.numerator, row.numerator);
      assert.equal(cell.denominator, row.denominator);
      assert(Math.abs(cell.value - row.value) <= .0000005);
      checked++;
    }
  }
  assert(checked > 100);
  const invalid = structuredClone(data);
  invalid.nodes[0].denominator[0]++;
  assert.throws(() => validateCountryExplorer(invalid, manifest), /count series/);
  assert.throws(() => validateCountryExplorer({...data, scan_config_sha256: 'wrong'}, manifest), /provenance/);
});

test('all Topics and Concepts nodes use within-node publication denominators for percentage and each year', () => {
  for (const taxonomy of fields.taxonomies.filter(taxonomy => taxonomy.id !== 'subjects')) for (const population of taxonomy.populations) for (const node of taxonomy.nodes) {
    for (let index = 0; index < node.denominator.length; index++) {
      const proportion = disciplineCell(taxonomy, node, population, 'proportion', index);
      const rate = disciplineCell(taxonomy, node, population, 'rate', index);
      assert.equal(proportion.denominator, node.denominator[index]);
      assert.equal(proportion.numerator, node.counts[population][index]);
      assert.equal(proportion.value, proportion.denominator ? proportion.numerator / proportion.denominator * 100 : null);
      if (proportion.value != null) assert(Math.abs(proportion.value - rate.value / 100) < 1e-10);
      assert.equal(proportion.ranking_eligible, rate.ranking_eligible);
    }
  }
  const study = resolveStudy(fields, ['oa'], {taxonomy: 'concepts', metric: 'proportion'});
  const time = disciplineTimeChart(fields, study);
  assert.equal(time.rows[0].denominator, study.node.denominator[1]);
  assert(resolveStudy(fields, ['rw'], {taxonomy: 'subjects', metric: 'proportion'}).error);
});

test('country metrics preserve publication-year denominators and unavailable states', () => {
  const data = {nodes: [{id: 'CN', denominator: [3000, 1000, 2000], counts: {A1: [30, 20, 10], C_D: [10, 5, 5]}}, {id: 'US', denominator: [0, 0, 0], counts: {A1: [0, 0, 0], C_D: [0, 0, 0]}}], year_start: 2020, year_end: 2021};
  const study = countryStudy(data, ['oa'], {node: 'CN', metric: 'proportion'});
  assert.equal(countryCell(study.node, 'A1', 'proportion').value, 1);
  assert.deepEqual(countryTimeChart(data, study).rows.map(row => [row.numerator, row.denominator, row.value]), [[20, 1000, 2], [10, 2000, .5]]);
  assert.equal(countryCell(data.nodes[1], 'A1', 'proportion').value, null);
  assert.equal(countryCell(data.nodes[1], 'A1', 'count').value, 0);
  assert(countryStudy(data, ['rw'], {}).error);
  assert(countryStudy(data, ['oa'], {population: 'C_D'}).error);
  assert(countryStudy(data, ['oa'], {node: 'XX'}).error);
  assert(countryStudy(data, ['oa'], {taxonomy: 'topics'}).error);
  assert.throws(() => validateCountryExplorer({...data, release_id: 'wrong'}, {release_id: 'new'}), /release/);
});
import {decodeExplorer} from '../src/report/explorerCodec.js';
