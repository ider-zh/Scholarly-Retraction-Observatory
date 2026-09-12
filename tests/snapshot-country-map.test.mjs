import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {validateChunk, validateManifest} from '../src/report/schema.js';
import {countryCell} from '../src/report/country.js';
import {topicCatalog, selectTopicChart} from '../src/report/topics.js';
import {MAP_COLORS, mapStatus, mapScale, mapColor, countryRateRows, mapCountryCode, mapRowsByCode} from '../src/report/countryMap.js';

const manifest = validateManifest(JSON.parse(readFileSync('public/data/snapshot/manifest.json')));
const geography = validateChunk(JSON.parse(readFileSync('public/data/snapshot/geography.json')), manifest, 'geography');
const rates = geography.charts.filter(chart => chart.chart_id === 'G1' && chart.metric_id.endsWith('_cohort_per_10k'));

test('legacy country rates share exact n/N and scope with the country explorer', () => {
  for (const chart of rates) {
    const population = chart.population_key === 'A1_over_D' ? 'A1' : 'C_D';
    assert.deepEqual(chart.scope.publication_year_range, [geography.country_explorer.year_start, geography.country_explorer.year_end]);
    assert.equal(chart.metric_observation_cutoff, geography.country_explorer.oa_cutoff);
    for (const row of chart.rows) {
      const node = geography.country_explorer.nodes.find(node => node.id === row.id);
      const cell = countryCell(node, population, 'rate');
      assert.equal(row.numerator, cell.numerator); assert.equal(row.denominator, cell.denominator);
      if (row.value == null) assert.equal(cell.value, null); else assert(Math.abs(row.value - cell.value) <= 0.000001);
    }
  }
});

test('merged topic retains exact legacy deep links and descending eligible bars without mutation', () => {
  const before = JSON.stringify(geography);
  const catalog = topicCatalog(geography.charts, ['rw', 'oa'], null, geography.country_explorer);
  const legacy = catalog.find(topic => topic.id === 'country-rates');
  assert.equal(legacy.supersededBy, 'countries');
  assert(!catalog.filter(topic => !topic.supersededBy).some(topic => topic.id === 'country-rates'));
  assert(catalog.find(topic => topic.id === 'countries').enabled);
  for (const chart of rates) {
    assert.equal(selectTopicChart(legacy, ['rw', 'oa'], `${chart.chart_id}/${chart.slice_id}`), chart);
    const ordered = countryRateRows(chart, chart.rows.filter(row => row.value != null));
    const eligible = ordered.filter(row => row.ranking_eligible);
    assert(eligible.every((row, index) => !index || eligible[index-1].value >= row.value));
    assert.deepEqual(ordered.slice(0, eligible.length), eligible);
  }
  assert.equal(JSON.stringify(geography), before);
});

test('map keeps missing, measured zero and small bases distinct and leaves statistics untouched', () => {
  const rows = [{id: 'AA', value: 0, ranking_eligible: false}, {id: 'BB', value: null, ranking_eligible: false}, {id: 'CC', value: 10, ranking_eligible: true}, {id: 'DD', value: 100, ranking_eligible: false}];
  assert.equal(mapStatus(undefined, 'count'), 'missing');
  assert.equal(mapStatus(rows[0], 'count'), 'value');
  assert.equal(mapStatus(rows[0], 'rate'), 'small');
  assert.equal(mapStatus(rows[1], 'count'), 'missing');
  assert.equal(mapScale(rows, 'rate').maximum, 10);
  assert.equal(mapScale(rows, 'count').maximum, 100);
  assert.equal(mapColor(0, 100), MAP_COLORS[0]);
  assert.equal(mapColor(100, 100), MAP_COLORS[4]);
  assert.deepEqual(mapScale([], 'rate').thresholds, [0, 0, 0, 0]);
});

test('offline basemap contains only vetted geometric paths and explicit codes', () => {
  const map = JSON.parse(readFileSync('src/report/assets/world-map.json'));
  assert.equal(map.regions.length, 177);
  assert.equal(map.sha256, '6866c877d39cba9c357620878839b336d569f8c662d3cfab4cb1dbe2d39c977f');
  for (const region of map.regions) {
    assert(region.code === null || /^[A-Z]{2}$/.test(region.code));
    assert.match(region.path, /^[MLZ0-9.,\-]+$/);
  }
  assert(map.regions.some(region => region.code === 'CN'));
  assert(map.regions.some(region => region.code === null));
});

test('map geometry and selection resolve Taiwan to the published merged China row', () => {
  const rows = [{id: 'CN', value: 30, numerator: 30, denominator: 1000}];
  const byCode = new Map(rows.map(row => [row.id, row]));
  assert.equal(mapCountryCode('TW'), 'CN');
  assert.equal(mapCountryCode('CN'), 'CN');
  assert.equal(mapCountryCode('HK'), 'HK');
  assert.equal(mapCountryCode(null), null);
  assert.equal(byCode.get(mapCountryCode('TW')), byCode.get(mapCountryCode('CN')));
  const component = readFileSync('src/report/CountryMap.jsx', 'utf8');
  assert(component.includes('onSelect(row.id)'));
  assert(component.includes('mapCountryCode(selected) === row.id'));
  assert(component.includes('setHovered(mapCountryCode(region.code))'));
  assert(component.includes('data-country={region.code'));
  assert(component.includes('mapRowsByCode(rows)'));
});

test('map lookup refuses old unmerged country rows rather than hiding Taiwan data', () => {
  assert.throws(() => mapRowsByCode([{id: 'CN', value: 30}, {id: 'TW', value: 5}]), /逐论文去重合并/);
  assert.throws(() => mapRowsByCode([{id: 'TW', value: 0}]), /逐论文去重合并/);
  assert.equal(mapRowsByCode([{id: 'US', value: 4}]).get('US').value, 4);
  assert.equal(mapRowsByCode([]).size, 0);
});
