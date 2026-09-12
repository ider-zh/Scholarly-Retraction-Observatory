import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {validateChunk} from '../src/report/schema.js';
import {sourceProfile} from '../src/report/sources.js';
import {topicCatalog, topicHref, topicId, selectTopicChart, annualSeries, variantKey, topicVariantLabel} from '../src/report/topics.js';
import {parseReportRoute} from '../src/report/routes.js';

const manifest = JSON.parse(readFileSync('public/data/snapshot/manifest.json'));
const pages = Object.fromEntries(['overview', 'time', 'fields', 'reasons', 'geography', 'entities', 'publishing', 'citations', 'quality'].map(section => [section, section]));
const chunks = Object.fromEntries(Object.keys(pages).map(section => [section, validateChunk(JSON.parse(readFileSync(`public/data/snapshot/${section}.json`)), manifest, section)]));

test('multi-label field and topic controls distinguish their aggregation level', () => {
  for (const population of ['A1', 'C']) {
    const field = chunks.fields.charts.find(chart => chart.slice_id === `${population}-any-topic-field`);
    const topic = chunks.fields.charts.find(chart => chart.slice_id === `${population}-any-topic-topic`);
    assert.match(topicVariantLabel(field), /按学科汇总/);
    assert.match(topicVariantLabel(topic), /按主题汇总/);
    assert.notEqual(topicVariantLabel(field), topicVariantLabel(topic));
  }
});

test('catalog covers all declared slices exactly once, preserves disabled topics and stable source ordering', () => {
  const before = JSON.stringify(chunks);
  let count = 0;
  for (const [section, chunk] of Object.entries(chunks)) {
    count += chunk.charts.length;
    for (const sources of [['rw'], ['oa'], ['rw', 'oa']]) {
      const topics = topicCatalog(chunk.charts, sources, chunk.discipline_explorer);
      assert.equal(topics.flatMap(topic => topic.charts).length, chunk.charts.length);
      let disabledSeen = false;
      for (const topic of topics) {
        if (!topic.enabled) disabledSeen = true; else assert(!disabledSeen);
        for (const chart of topic.charts) {
          assert.equal(topicId(chart), topic.id);
          const slice = `${chart.chart_id}/${chart.slice_id}`;
          const expected = sourceProfile(chart).required.every(source => sources.includes(source));
          assert.equal(selectTopicChart(topic, sources, slice), expected ? chart : null);
          const route = parseReportRoute(topicHref(section, topic.id, sources, slice), pages);
          assert.equal(route.topic, topic.id); assert.equal(route.slice, slice); assert.equal(route.page, section); assert.equal(route.error, null);
        }
        assert.equal(selectTopicChart(topic, sources, 'unknown/unknown'), null);
      }
    }
  }
  assert.equal(count, manifest.supported_slices.length); assert.equal(JSON.stringify(chunks), before);
});

test('topic paths and legacy slice/tree links remain separate, invalid paths fail closed', () => {
  const old = parseReportRoute('#/snapshot/time?sources=rw&slice=T1%2FB-retracted', pages);
  assert.equal(old.topic, ''); assert.equal(old.slice, 'T1/B-retracted'); assert.equal(old.error, null);
  const tree = parseReportRoute(topicHref('fields', 'discipline', ['oa'], '', {taxonomy: 'concepts', population: 'A1', node: 'https://openalex.org/C71924100', metric: 'rate'}), pages);
  assert.equal(tree.explorerSelection.node, 'https://openalex.org/C71924100'); assert.equal(tree.error, null);
  for (const hash of ['#/snapshot/time/topic/', '#/snapshot/time/unknown/path', '#/snapshot/time/topic/%XX', '#/snapshot/time/topic/t3?sources=invalid', '#/snapshot/time/topic/t3?taxonomy=topics', '#/snapshot/__proto__']) assert(parseReportRoute(hash, pages).error);
});

test('annual overlay binds exactly the two RW source slices and refuses incompatible series', () => {
  const series = annualSeries(chunks.time.charts);
  assert.deepEqual(series.map(chart => chart.slice_id), ['B-published', 'B-retracted']);
  assert.equal(series[0], chunks.time.charts[0]);
  assert.equal(annualSeries([series[0]]).length, 0);
  assert.equal(annualSeries([series[0], {...series[1], metric_observation_cutoff: 'different'}]).length, 0);
  assert.equal(annualSeries([series[0], {...series[1], status: 'not_computed'}]).length, 0);
});

test('population switching can preserve a matched method without joining incompatible country rates', () => {
  const topic = topicCatalog(chunks.fields.charts, ['rw', 'oa']).find(topic => topic.id === 'f1');
  const first = topic.charts.find(chart => chart.slice_id === 'A1-primary-field');
  const counterpart = topic.charts.find(chart => chart.population_key === 'C' && variantKey(chart) === variantKey(first));
  assert.equal(counterpart.slice_id, 'C-primary-field');
  const geography = topicCatalog(chunks.geography.charts, ['rw', 'oa']);
  assert(geography.find(topic => topic.id === 'country-rates').charts.every(chart => chart.metric_id.endsWith('_cohort_per_10k')));
  assert(geography.find(topic => topic.id === 'g1').charts.every(chart => !chart.metric_id.endsWith('_cohort_per_10k')));
});
