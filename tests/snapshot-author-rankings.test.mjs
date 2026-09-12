import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {validateChunk, validateManifest} from '../src/report/schema.js';
import {filterCharts} from '../src/report/sources.js';
import {topicCatalog, topicDatasetLabel} from '../src/report/topics.js';
import {chartName, chartMethod} from '../src/report/reader.js';

const manifest = validateManifest(JSON.parse(readFileSync('public/data/snapshot/manifest.json')));
const {charts} = validateChunk(JSON.parse(readFileSync('public/data/snapshot/entities.json')), manifest, 'entities');
const raw = charts.find(chart => chart.chart_id === 'rw-author-names');
const identities = charts.filter(chart => chart.chart_id === 'author-top');

test('mixed RW source and invalid name coverage are rejected', () => {
  for (const corrupt of [chart => {chart.rw_author_source_sha256 = '0'.repeat(64);}, chart => {chart.association_summary.unknown_works += 1;}, chart => {chart.rows[0].denominator -= 1;}]) {
    const chunk = structuredClone({schema_version: 3, release_id: manifest.release_id, section: 'entities', charts});
    corrupt(chunk.charts.find(chart => chart.chart_id === 'rw-author-names'));
    assert.throws(() => validateChunk(chunk, manifest, 'entities'), /RW/);
  }
});

test('RW strings and OpenAlex identities are separate source-scoped topics', () => {
  assert.equal(raw.population_key, 'B');
  assert.equal(raw.status, 'ready');
  assert.equal(identities.length, 2);
  assert(filterCharts([raw], ['rw']).length);
  assert.equal(filterCharts([raw], ['oa']).length, 0);
  assert.equal(filterCharts(identities, ['rw']).length, 0);
  assert.deepEqual(filterCharts(identities, ['oa']).map(chart => chart.population_key), ['A1']);
  for (const sources of [['rw'], ['oa'], ['rw', 'oa']]) {
    const catalog = topicCatalog(charts, sources);
    assert.equal(catalog.find(topic => topic.id === 'rw-author-names').enabled, sources.includes('rw'));
    assert.equal(catalog.find(topic => topic.id === 'author-top').enabled, sources.includes('oa'));
  }
});

test('ranked raw names retain counts, full scope, missingness and source evidence', () => {
  assert.equal(raw.rw_author_source_sha256, manifest.rw_csv_sha256);
  assert.equal(raw.metric_observation_cutoff, manifest.rw_snapshot_date);
  assert.equal(raw.scope.attribution, 'distinct_original_per_raw_author_name');
  assert.equal(raw.rows.length, 20);
  assert.equal(raw.quality.eligible_works, raw.association_summary.known_works + raw.association_summary.unknown_works);
  raw.rows.forEach((row, index) => {
    assert.equal(row.rank, index + 1);
    assert(Number.isSafeInteger(row.value));
    assert.equal(row.value, row.numerator);
    assert.equal(row.denominator, raw.quality.eligible_works);
    assert(!raw.association_summary.excluded_placeholders.includes(row.id.toLowerCase()));
    assert(!Object.hasOwn(row, 'author_id'));
    if (index) assert(raw.rows[index - 1].value >= row.value);
  });
  assert.match(chartName(raw), /RW 原始署名字符串/);
  assert.match(chartMethod(raw).join(''), /不是已消歧/);
  for (const chart of identities) {
    assert.match(chartName(chart), /OpenAlex 作者身份/);
    assert.match(topicDatasetLabel(chart), /OpenAlex 作者 ID/);
    assert(chart.rows.every(row => /^https:\/\/openalex.org\/A\d+$/.test(row.author_id)));
  }
});
