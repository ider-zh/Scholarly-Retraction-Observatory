import assert from 'node:assert/strict';
import {mkdir, readFile, writeFile} from 'node:fs/promises';
import {execFileSync} from 'node:child_process';
import {decodeChartRows} from '../src/report/schema.js';
import {filterCharts, reportHref, sourceProfile} from '../src/report/sources.js';
import {chapterFinding} from '../src/report/chapter.js';
import {rowLabel} from '../src/report/reader.js';
import {resolveStudy, disciplineTimeChart, distributionRows} from '../src/report/discipline.js';

const {chromium} = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const output = process.env.REPORT_QA_OUT || '/tmp/sro-chapters-review/after';
const base = process.env.REPORT_QA_URL || 'http://127.0.0.1:4173/';
const manifest = JSON.parse(await readFile('public/data/snapshot/manifest.json', 'utf8'));
const chapters = ['time', 'fields', 'reasons', 'geography', 'entities', 'publishing', 'citations', 'quality'];
await mkdir(output, {recursive: true});
const browser = await chromium.launch({executablePath: process.env.CHROMIUM_PATH || undefined, args: ['--no-sandbox']});
const context = await browser.newContext({viewport: {width: 1440, height: 900}, reducedMotion: 'reduce'});
const page = await context.newPage(), checks = [], captures = [], errors = [];
page.on('pageerror', error => errors.push(error.message));
async function check(name, action) {try {await action(); checks.push({name, status: 'passed'});} catch (error) {checks.push({name, status: 'failed', error: error.stack});}}
async function capture(name) {
  await page.screenshot({path: `${output}/${name}.png`});
  await page.screenshot({path: `${output}/${name}-full.png`, fullPage: true});
  const geometry = await page.evaluate(() => ({width: innerWidth, height: innerHeight, contentWidth: document.documentElement.scrollWidth, plotTop: document.querySelector('.report-figure')?.getBoundingClientRect().top}));
  captures.push({name, url: page.url(), ...geometry});
  assert(geometry.contentWidth <= geometry.width + 1, name+' overflow');
}
async function audit() {
  if (!process.env.AXE_PATH) return;
  await page.addScriptTag({content: await readFile(process.env.AXE_PATH, 'utf8')});
  const violations = await page.evaluate(async () => (await axe.run(document, {runOnly: {type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21aa']}})).violations.map(item => ({id: item.id, targets: item.nodes.slice(0, 5).map(node => node.target)})));
  assert.deepEqual(violations, []);
}
async function ready(section, sources, charts) {
  if (section === 'fields') await page.locator('.discipline-results').waitFor();
  else if (section === 'geography') await page.locator(sources.includes('oa') ? '.country-explorer' : '.report-unavailable').waitFor();
  else if (section === 'time' && sources.includes('rw')) await page.locator('.topic-annual-comparison').waitFor();
  else if (filterCharts(charts, sources).length) await page.locator('.report-research-figure').waitFor();
  else await page.locator('.report-unavailable').waitFor();
}
function parseCSV(text) {
  const result = []; let row = [], cell = '', quoted = false;
  for (let index = 0; index < text.length; index++) {
    const character = text[index];
    if (character === '\ufeff') continue;
    if (character === '"') {if (quoted && text[index+1] === '"') {cell += '"'; index++;} else quoted = !quoted;}
    else if (character === ',' && !quoted) {row.push(cell); cell = '';}
    else if (character === '\n' && !quoted) {row.push(cell); result.push(row); row = []; cell = '';}
    else if (character !== '\r' || quoted) cell += character;
  }
  if (cell || row.length) {row.push(cell); result.push(row);}
  const columns = result.shift();
  return result.map(row => Object.fromEntries(columns.map((column, index) => [column, row[index]])));
}
let exported = 0;
try {
  for (const section of chapters) {
    const chunk = JSON.parse(await readFile(`public/data/snapshot/${section}.json`, 'utf8'));
    const charts = chunk.charts.map(decodeChartRows);
    for (const [name, width, height] of [['desktop', 1440, 900], ['tablet', 768, 1024], ['mobile', 390, 844]]) await check(`${section} ${name} reading and accessibility`, async () => {
      await page.setViewportSize({width, height}); await page.goto(base+reportHref(section, ['rw', 'oa'])); await ready(section, ['rw', 'oa'], charts);
      await capture(`${section}-${name}`); await audit();
      assert.equal(await page.locator('.snapshot-controls,.snapshot-pagination,.snapshot-analysis-index').count(), 0);
      assert.equal(await page.locator('.report-explorer').evaluate(element => element.open), true);
    });
    await page.setViewportSize({width: 1440, height: 900});
    await check(`${section} source URLs`, async () => {
      for (const sources of [['rw'], ['rw', 'oa'], ['oa'], ['rw', 'oa']]) {
        await page.goto(base+reportHref(section, sources)); await ready(section, sources, charts);
        if (section === 'fields') assert.equal(await page.getByLabel('分类方法论', {exact: true}).inputValue(), sources.includes('oa') ? 'concepts' : 'subjects');
        else if (section === 'geography') assert.equal(await page.locator('.country-explorer').count(), sources.includes('oa') ? 1 : 0);
        else if (section === 'time' && sources.includes('rw')) assert.equal(await page.locator('.topic-annual-comparison').count(), 1);
        else {
          const allowed = filterCharts(charts, sources), figure = page.locator('.report-research-figure');
          assert.equal(await figure.count(), allowed.length ? 1 : 0);
          if (allowed.length) assert.equal(await figure.getAttribute('data-slice-id'), allowed[0].slice_id);
        }
      }
    });
    await check(`${section} every published deep link and CSV`, async () => {
      for (const chart of charts) {
        await page.goto(base+reportHref(section, ['rw', 'oa'], `${chart.chart_id}/${chart.slice_id}`));
        let figure;
        if (chart.chart_id === 'T1') {
          await page.locator('.topic-annual-comparison').waitFor();
          await page.locator('.report-data-table > summary').click();
          figure = page.getByRole('region', {name: `${chart.scope.date_basis === 'published' ? '按发表年' : '按撤稿年'}原始数据`, exact: true});
        } else {
        figure = page.locator(`.report-research-figure[data-slice-id="${chart.slice_id}"]`); await figure.waitFor();
        assert.equal(await figure.getAttribute('data-population'), chart.population_key);
        assert.equal(await figure.getAttribute('data-metric'), chart.metric_id);
        const display = {...chart, rows: chart.rows.map(row => ({...row, label: rowLabel(row, chart)}))};
        assert.equal(await figure.locator('.report-finding-text').innerText(), chapterFinding(display));
        assert((await figure.locator('.report-caption').last().innerText()).includes(chart.metric_observation_cutoff));
        assert((await figure.locator('.report-kicker').innerText()).includes(sourceProfile(chart).label));
        await figure.getByText('查看完整聚合数据与导出', {exact: true}).click();

        }
        const pending = page.waitForEvent('download'); await figure.getByRole('button', {name: '导出本切片聚合 CSV', exact: true}).click();
        const records = parseCSV(await readFile(await (await pending).path(), 'utf8'));
        assert.equal(records.length, chart.rows.length);
        records.forEach((record, index) => {
          assert.equal(record.release_id, chart.release_id); assert.equal(record.chart_id, chart.chart_id); assert.equal(record.slice_id, chart.slice_id);
          assert.equal(record.population, chart.population_key); assert.equal(record.metric, chart.metric_id); assert.equal(record.cutoff, chart.metric_observation_cutoff);
          assert.equal(record.oa_date, chart.oa_snapshot_date); assert.equal(record.rw_date, chart.rw_snapshot_date);
          for (const key of ['numerator', 'denominator', 'value', 'unit']) assert.equal(record[key], String(chart.rows[index][key] ?? '').replace(/^[=+@\-\t\r]/, "'$&"));
        }); exported++;
      }
    });
  }
  await check('geography metrics update narrative, unit and CSV together', async () => {
    await page.goto(base+reportHref('geography', ['oa'], 'G1/A1-institution_country')); await page.locator('.report-research-figure').waitFor();
    await page.getByText('切换本图计数方式', {exact: true}).click();
    for (const metric of ['paper_coverage_pct', 'association_share_pct', 'fractional_work_count', 'fractional_share_pct', 'linked_work_count']) {
      await page.getByLabel('本图计数方式', {exact: true}).selectOption(metric);
      await page.waitForFunction(metric => document.querySelector('.report-research-figure')?.dataset.metric === metric, metric);
      assert((await page.locator('.report-finding-text').innerText()).length > 0);
      if (metric === 'fractional_work_count') assert.match(await page.locator('.report-caption').last().innerText(), /篇等价值/);
      const table = page.locator('.report-data-table');
      if (!await table.evaluate(element => element.open)) await table.locator(':scope > summary').click();
      const pending = page.waitForEvent('download'); await page.getByRole('button', {name: '导出本切片聚合 CSV', exact: true}).click();
      const records = parseCSV(await readFile(await (await pending).path(), 'utf8'));
      const geography = JSON.parse(await readFile('public/data/snapshot/geography.json', 'utf8')).charts.map(decodeChartRows).find(chart => chart.chart_id === 'G1' && chart.slice_id === 'A1-institution_country');
      assert.equal(records.length, geography.rows.length);
      records.forEach((record, index) => {
        const row = geography.rows[index];
        assert.equal(record.metric, metric);
        assert.equal(record.value, String(metric === 'linked_work_count' ? row.value : row[metric]));
        assert.equal(record.numerator, String(metric.startsWith('fractional') ? row.fractional_work_count : row.numerator));
        assert.equal(record.denominator, String(metric === 'association_share_pct' ? geography.association_summary.association_total : metric.startsWith('fractional') ? geography.association_summary.known_works : row.denominator));
        assert.equal(record.unit, metric === 'linked_work_count' ? row.unit : metric === 'fractional_work_count' ? 'work_equivalents' : 'percent');
      });
    }
  });
  await check('discipline trees and all metrics, source-specific restrictions and export', async () => {
    await page.goto(base+reportHref('fields', ['rw', 'oa'])); await page.locator('.discipline-results').waitFor();
    await page.getByText('选择分类、指标或主/子学科', {exact: true}).click();
    for (const taxonomy of ['subjects', 'topics', 'concepts']) {
      await page.getByLabel('分类方法论', {exact: true}).selectOption(taxonomy);
      const branch = page.locator('.discipline-tree details').first(); await branch.locator('summary').click();
      await branch.locator('a').last().click(); await page.waitForFunction(() => new URLSearchParams(location.hash.split('?')[1]).has('node'));
      for (const metric of taxonomy === 'subjects' ? ['count', 'share'] : ['count', 'share', 'rate']) {
        await page.getByLabel('查看指标', {exact: true}).selectOption(metric);
        await page.waitForFunction(metric => new URLSearchParams(location.hash.split('?')[1]).get('metric') === metric, metric);
        assert.equal(await page.locator('.discipline-results .report-figure').count(), 2);
        const data = decodeExplorer(JSON.parse(await readFile('public/data/snapshot/fields.json', 'utf8')).discipline_explorer);
        const selection = Object.fromEntries(new URLSearchParams(page.url().split('?')[1]));
        const study = resolveStudy(data, ['rw', 'oa'], selection);
        for (const [label, expected] of [['时间', disciplineTimeChart(data, study).rows], ['分布', distributionRows(study)]]) {
          const pending = page.waitForEvent('download'); await page.getByRole('button', {name: `导出${label}聚合 CSV`, exact: true}).click();
          const records = parseCSV(await readFile(await (await pending).path(), 'utf8'));
          assert.equal(records.length, expected.length);
          records.forEach((record, index) => {
            assert.equal(record.metric, metric); assert.equal(record.taxonomy, taxonomy);
            assert.equal(record.selected_node, study.node.id); assert.equal(record.navigation_parent, study.parent);
            assert.equal(record.population, study.population); assert.equal(record.oa_cutoff, data.oa_cutoff); assert.equal(record.rw_cutoff, data.rw_cutoff);
            for (const key of ['numerator', 'denominator', 'value', 'unit']) assert.equal(record[key], String(expected[index][key] ?? ''));
          });
        }
      }
    }
    await audit(); await capture('discipline-child');
  });
  await check('history, source incompatibility and chart keyboard interaction', async () => {
    await page.goto(base+reportHref('time', ['rw'], 'T1/B-retracted')); await page.locator('.topic-annual-comparison').waitFor();
    const point = page.locator('[data-annual-point]').first(); await point.focus(); await point.press('Enter'); assert.match(await page.locator('.topic-comparison-detail').innerText(), /已锁定/); await point.press('Escape');
    await page.getByRole('button', {name: '查找数据专题 ↓'}).click();
    await page.goto(base+reportHref('time', ['rw'], 'T4/B-default')); await page.locator('[data-chart-id="T4"]').waitFor();
    await page.goBack(); await page.locator('.topic-annual-comparison').waitFor(); await page.reload(); await page.locator('.topic-annual-comparison').waitFor();
    await page.goto(base+reportHref('citations', ['rw'], 'C1/A1-core-article')); await page.locator('.report-unavailable').waitFor(); assert.equal(await page.locator('.report-research-figure').count(), 0);
  });
} finally {
  checks.push({name: 'uncaught page errors', status: errors.length ? 'failed' : 'passed', errors});
  const result = {commit: execFileSync('git', ['rev-parse', 'HEAD'], {encoding: 'utf8'}).trim(), release: manifest.release_id, browser: browser.version(), axe: process.env.AXE_PATH ? 'run' : 'not_run', exported, checks, captures};
  await writeFile(output+'/checks.json', JSON.stringify(result, null, 2)); console.log(JSON.stringify(result, null, 2)); await browser.close();
}
if (checks.some(check => check.status === 'failed')) process.exitCode = 1;
import {decodeExplorer} from '../src/report/explorerCodec.js';
