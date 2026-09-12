import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {parseReportRoute} from '../src/report/routes.js';
import {REPORT_PAGES} from '../src/report/sections.js';
import {validateChunk} from '../src/report/schema.js';
import {resolveStudy} from '../src/report/discipline.js';
import {countryStudy} from '../src/report/country.js';
import {disciplineEvidence, conceptTrendPlot, conceptProportionPlot, countryMapPlot} from '../scripts/presentation-figures.mjs';
import {countryProportionEvidence, countryProportionPlot} from '../scripts/presentation-country-proportion.mjs';
import {MAP_COLORS} from '../src/report/countryMap.js';
import {publicationBuilds} from '../src/publication-builds.js';

const html = await readFile('public/presentation-v2/index.html', 'utf8');
const evidence = JSON.parse(html.match(/id="presentation-evidence">([\s\S]*?)<\/script>/)[1]);
const manifest = JSON.parse(await readFile('public/data/snapshot/manifest.json', 'utf8'));

test('Generated index dates match report metadata and the exact presentation build', async () => {
  const report = JSON.parse(await readFile('public/data/report.json', 'utf8'));
  assert.equal(publicationBuilds.v1.builtAt, report.meta.generated_at);
  assert.equal(publicationBuilds.v2.builtAt, manifest.generated_at);
  assert.equal(publicationBuilds.ppt.builtAt, html.match(/<meta name="build-date" content="([^"]+)"/)[1]);
});

test('Deck figures preserve published charts or exact existing discipline projections', async () => {
  assert(evidence.some(entry => entry.chart.chart_id === 'discipline-distribution'));
  assert.equal(evidence.filter(entry => entry.chart.chart_id === 'discipline-time').length, 6);
  for (const entry of evidence) {
    const bytes = await readFile(`public/${entry.file}`);
    const section = entry.file.split('/').at(-1).replace('.json', '');
    const chunk = validateChunk(JSON.parse(bytes), manifest, section);
    assert.equal(createHash('sha256').update(bytes).digest('hex'), entry.sha256);
    assert.equal(entry.chart.release_id, manifest.release_id);
    if (entry.chart.chart_id.startsWith('discipline-')) {
      const {taxonomy, population, node, metric} = entry.chart.scope;
      assert.deepEqual(entry.chart, disciplineEvidence(chunk.discipline_explorer, taxonomy, population, node, metric));
    } else if (entry.chart.chart_id === 'country-distribution') {
      assert.deepEqual(entry.chart, countryProportionEvidence(chunk.country_explorer));
    } else {
      assert.deepEqual(entry.chart, chunk.charts.find(chart => chart.chart_id === entry.chart.chart_id && chart.slice_id === entry.chart.slice_id));
    }
  }
});

test('Fifteen slides have notes and source labels, with no external runtime dependencies', () => {
  assert.equal((html.match(/<section class="slide"/g) || []).length, 15);
  assert.equal((html.match(/class="notes"/g) || []).length, 15);
  assert.equal((html.match(/class="kicker"/g) || []).length, 15);
  assert(!/(?:src|href)="https?:\/\//.test(html));
  assert(html.includes('vendor/themes/academic-paper.css'));
  assert(html.includes('vendor/runtime.js'));
  assert(html.includes(manifest.release_id));
  assert(!html.includes('同名署名，不一定是同一位作者'));
  assert(!html.includes('带着范围，回到证据'));
  assert(html.includes('RW Subject'));
  assert(html.includes('OpenAlex Topic'));
  assert(html.includes('OpenAlex Concepts'));
  const titles = [...html.matchAll(/<section class="slide" data-title="([^"]+)"/g)].map(match => match[1]);
  assert(titles.slice(1,4).every(title => title.startsWith('研究综述：')));
  assert(!titles[4].startsWith('研究综述：'));
});

test('Presentation report links retain supported source, slice and discipline node contracts', async () => {
  const fields = validateChunk(JSON.parse(await readFile('public/data/snapshot/fields.json', 'utf8')), manifest, 'fields');
  const links = [...html.matchAll(/href="\.\.\/(#\/snapshot\/[^\"]+)"/g)].map(match => match[1].replaceAll('&amp;', '&'));
  assert(links.length >= 10);
  assert(links.filter(link => new URLSearchParams(link.split('?')[1]).get('metric') === 'proportion').length >= 4);
  for (const link of links) {
    const route = parseReportRoute(link, REPORT_PAGES);
    assert.equal(route.error, null, link);
    if (route.slice) assert(manifest.supported_slices.some(slice => `${slice.chart_id}/${slice.slice_id}` === route.slice), link);
    if (route.topic === 'discipline') assert(!resolveStudy(fields.discipline_explorer, route.sources, route.explorerSelection).error, link);
  }
});

test('Concept trends keep publication years, common scales and partial-year state', () => {
  const trends = evidence.filter(entry => entry.chart.chart_id === 'discipline-time').map(entry => entry.chart);
  assert.equal(new Set(trends.map(chart => chart.scope.node)).size, 3);
  assert.equal(trends.filter(chart => chart.scope.metric === 'count').length, 3);
  assert.equal(trends.filter(chart => chart.scope.metric === 'proportion').length, 3);
  for (const chart of trends) {
    assert.equal(chart.scope.taxonomy, 'concepts');
    assert.equal(chart.population_key, 'A1');
    assert.equal(chart.scope.date_basis, 'publication_year');
    assert.deepEqual(chart.rows.map(row => row.year), Array.from({length:27}, (_, offset) => 2000+offset));
    assert.equal(chart.rows.at(-1).partial, true);
  }
  assert(html.includes('三个面板使用同一纵轴'));
  assert(html.includes('不是该年撤稿数'));
});

test('Proportion evidence uses same-subject full publications, not retracted-sample coverage', () => {
  const proportions = evidence.filter(entry => entry.chart.scope?.metric === 'proportion' && entry.chart.scope?.taxonomy === 'concepts').map(entry => entry.chart);
  assert.equal(proportions.length, 4);
  assert(proportions.some(chart => chart.chart_id === 'discipline-distribution' && chart.rows.length > 6));
  for (const chart of proportions) {
    assert.equal(chart.scope.taxonomy, 'concepts');
    assert.equal(chart.population_key, 'A1');
    for (const row of chart.rows) {
      assert.equal(row.denominator, row.publication_denominator);
      assert.equal(row.value, row.denominator ? row.numerator / row.denominator * 100 : null);
      assert.equal(row.ranking_eligible, row.numerator >= 20 && row.publication_denominator >= 1000);
      assert.equal(row.unit, 'percent');
    }
  }
  assert(proportions.some(chart => chart.rows.some(row => row.denominator !== row.sample_denominator)));
});

test('Proportion projection preserves observed zero, missing denominator and small bases', () => {
  const taxonomy = {id:'concepts', label:'Concepts', levels:['main','sub'], populations:['A1'], counts:{A1:[100,100,100,100,100]}, denominator:[100000,100000,100000,100000,100000], method:'fixture', rate_policy:'fixture', nodes:[
    {id:'medicine', label:'Medicine', level:0, parents:[], counts:{A1:[49,0,25,5,19]}, denominator:[3000,1000,null,500,1500]},
  ]};
  const explorer = {taxonomies:[taxonomy], year_start:2000, year_end:2003, release_id:'fixture', oa_cutoff:'2026-06-26'};
  const original = structuredClone(explorer);
  const chart = disciplineEvidence(explorer, 'concepts', 'A1', 'medicine', 'proportion');
  assert.deepEqual(chart.rows.map(row => row.value), [0,null,1,19/1500*100]);
  assert.deepEqual(chart.rows.map(row => row.denominator), [1000,null,500,1500]);
  assert(chart.rows.every(row => row.sample_denominator === 100 && !row.ranking_eligible));
  assert.equal(chart.rows.at(-1).partial, true);
  const rendered = conceptTrendPlot([chart]);
  assert(!rendered.includes('NaN'));
  assert(!rendered.includes('Infinity'));
  assert(!/class="trend-line(?: partial-line)?"/.test(rendered));
  assert.deepEqual(explorer, original);
  assert.deepEqual(chart.rows.map(row => row.value), [0,null,1,19/1500*100]);
  assert.throws(() => disciplineEvidence({...explorer, taxonomies:[{...taxonomy, denominator:null}]}, 'concepts', 'A1', 'medicine', 'proportion'), /分母/);
});

test('Proportion figures compare selected subjects and never connect across suppressed years', () => {
  const chart = {metric_id:'proportion', scope:{node_label:'Medicine'}, rows:[
    {year:2000, value:0.1, ranking_eligible:true},
    {year:2001, value:0.2, ranking_eligible:true},
    {year:2002, value:2, ranking_eligible:false, numerator:2, denominator:100},
    {year:2003, value:0.3, ranking_eligible:true},
    {year:2004, value:null, ranking_eligible:false},
    {year:2005, value:0.4, ranking_eligible:true},
    {year:2006, value:0.5, ranking_eligible:true, partial:true},
  ]};
  const rendered = conceptTrendPlot([chart]);
  assert.equal((rendered.match(/class="trend-line(?: partial-line)?"/g) || []).length, 2);
  assert.equal((rendered.match(/class="small-base-mark"/g) || []).length, 1);
  assert.equal((rendered.match(/class="trend-line partial-line"/g) || []).length, 1);
  const distribution = {rows:[
    {id:'selected', label:'Selected subject', value:0.1, numerator:100, denominator:100000, ranking_eligible:true},
    {id:'outside', label:'Outside count leaders', value:5, numerator:500, denominator:10000, ranking_eligible:true},
  ]};
  const plotted = conceptProportionPlot(distribution, ['selected']);
  assert(plotted.includes('Selected subject'));
  assert(!plotted.includes('Outside count leaders'));
  assert(plotted.includes('0.1000%'));
  assert.equal(distribution.rows.length, 2);
});

test('Offline map distinguishes absent values and observed zero without changing rows', () => {
  const world = {viewBox:'0 0 10 10', regions:[{code:'CN', path:'M0 0', name:'China'}, {code:'US', path:'M1 1', name:'United States'}, {code:'FR', path:'M2 2', name:'France'}]};
  const chart = {rows:[{id:'CN', value:0, numerator:0, denominator:10}, {id:'FR', value:null, numerator:0, denominator:null}]};
  const original = structuredClone(chart);
  const rendered = countryMapPlot(world, chart);
  assert(rendered.includes(`data-country="CN" fill="${MAP_COLORS[0]}"`));
  assert(rendered.includes('data-country="US" fill="var(--map-missing)"'));
  assert(rendered.includes('data-country="FR" fill="var(--map-missing)"'));
  assert(rendered.includes('无对应数值，不代表零'));
  assert.deepEqual(chart, original);
  assert.equal((html.match(/data-country="/g) || []).length, 354);
});

test('Country proportion map preserves published projection and small-base evidence', async () => {
  const geography = validateChunk(JSON.parse(await readFile('public/data/snapshot/geography.json', 'utf8')), manifest, 'geography');
  const chart = evidence.find(entry => entry.chart.chart_id === 'country-distribution').chart;
  assert.deepEqual(chart.rows, countryStudy(geography.country_explorer, ['oa'], {population:'A1', metric:'proportion'}).ranked);
  assert.deepEqual(chart.scope.publication_year_range, [2000,2026]);
  assert.equal(chart.scope.attribution, 'institution_country');
  for (const row of chart.rows) {
    assert.equal(row.value, row.denominator ? row.numerator / row.denominator * 100 : null);
    assert.equal(row.ranking_eligible, row.numerator >= 20 && row.denominator >= 1000);
  }
  const world = {viewBox:'0 0 10 10', regions:[{code:'CN', path:'M0 0', name:'China'}, {code:'US', path:'M1 1', name:'United States'}, {code:'FR', path:'M2 2', name:'France'}, {code:'DE', path:'M3 3', name:'Germany'}]};
  const fixture = {rows:[{id:'CN', value:2, numerator:20, denominator:1000, ranking_eligible:true}, {id:'FR', value:0, numerator:0, denominator:1000, ranking_eligible:false}, {id:'DE', value:null, numerator:0, denominator:0, ranking_eligible:false}]};
  const original = structuredClone(fixture);
  const rendered = countryProportionPlot(world, fixture);
  for (const [country, status] of [['CN','value'],['US','missing'],['FR','small'],['DE','missing']]) {
    assert(new RegExp(`<path[^>]*data-country="${country}"[^>]*data-status="${status}"`).test(rendered), country);
  }
  assert.deepEqual(fixture, original);
});

test('Citation explanation keeps target coverage separate from cumulative mean edges', () => {
  const citation = evidence.find(entry => entry.chart.chart_id === 'C4').chart;
  const last = citation.rows.at(-1);
  assert(citation.rows.every(row => row.denominator === last.denominator));
  assert.deepEqual(citation.rows.map(row => row.window_years), [1,3,5]);
  assert(html.includes(Number(last.targets_with_edges).toLocaleString('zh-CN')));
  assert(html.includes('中位数'));
  assert(html.includes('至少被引用一次'));
  assert(html.includes('不是“第 5 年新增 9 次”'));
  assert(html.includes('引用可以用于批评或说明撤稿，不代表认可'));
});

test('Vendored runtime, base and theme match the installed skill', async () => {
  for (const asset of ['base.css', 'runtime.js', 'themes/academic-paper.css']) {
    assert.deepEqual(await readFile(`public/presentation-v2/vendor/${asset}`), await readFile(`.agents/skills/html-ppt-skill/assets/${asset}`));
  }
});
