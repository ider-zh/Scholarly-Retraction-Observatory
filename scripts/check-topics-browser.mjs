import assert from 'node:assert/strict';
import {mkdir, readFile, writeFile} from 'node:fs/promises';
import {decodeChartRows} from '../src/report/schema.js';
import {topicCatalog, topicHref, topicId} from '../src/report/topics.js';
import {reportHref} from '../src/report/sources.js';
import {chapterFinding} from '../src/report/chapter.js';
import {rowLabel} from '../src/report/reader.js';

const {chromium} = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const base = process.env.REPORT_QA_URL || 'http://127.0.0.1:4173/';
const output = process.env.REPORT_QA_OUT || '/tmp/sro-topic-review/after';
await mkdir(output, {recursive: true});
const browser = await chromium.launch({executablePath: process.env.CHROMIUM_PATH || undefined, args: ['--no-sandbox']});
const context = await browser.newContext({viewport: {width: 1440, height: 900}, reducedMotion: 'reduce'});
const page = await context.newPage(), checks = [], errors = [];
context.on('page', tab => tab.on('pageerror', error => errors.push(error.message)));
page.on('pageerror', error => errors.push(error.message));
const sections = ['overview', 'time', 'fields', 'reasons', 'geography', 'entities', 'publishing', 'citations', 'quality'];
const chunks = Object.fromEntries(await Promise.all(sections.map(async section => {
  const chunk = JSON.parse(await readFile(`public/data/snapshot/${section}.json`, 'utf8'));
  return [section, {...chunk, charts: chunk.charts.map(decodeChartRows), discipline_explorer: decodeExplorer(chunk.discipline_explorer)}];
})));
async function check(name, action) {try {await action(); checks.push({name, status: 'passed'});} catch (error) {checks.push({name, status: 'failed', error: error.stack});}}
async function audit() {
  if (!process.env.AXE_PATH) return;
  await page.addScriptTag({content: await readFile(process.env.AXE_PATH, 'utf8')});
  assert.deepEqual(await page.evaluate(async () => (await axe.run(document, {runOnly: {type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21aa']}})).violations.map(item => ({id: item.id, targets: item.nodes.slice(0, 3).map(node => node.target)}))), []);
}
async function capture(name) {
  await page.screenshot({path: `${output}/${name}.png`});
  await page.screenshot({path: `${output}/${name}-full.png`, fullPage: true});
  assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
  await audit();
}
function parseCSV(text) {
  const rows = []; let cells = [], cell = '', quoted = false;
  for (let index = 0; index < text.length; index++) {
    const character = text[index]; if (character === '\ufeff') continue;
    if (character === '"') {if (quoted && text[index + 1] === '"') {cell += '"'; index++;} else quoted = !quoted;}
    else if (character === ',' && !quoted) {cells.push(cell); cell = '';}
    else if (character === '\n' && !quoted) {cells.push(cell); rows.push(cells); cells = []; cell = '';}
    else if (character !== '\r' || quoted) cell += character;
  }
  if (cell || cells.length) {cells.push(cell); rows.push(cells);}
  const columns = rows.shift();
  return rows.map(row => Object.fromEntries(columns.map((column, index) => [column, row[index]])));
}
async function download(button) {const pending = page.waitForEvent('download'); await button.click(); return parseCSV(await readFile(await (await pending).path(), 'utf8'));}
function assertCSV(records, chart) {
  assert.equal(records.length, chart.rows.length);
  records.forEach((record, index) => {
    for (const [key, expected] of Object.entries({chart_id: chart.chart_id, slice_id: chart.slice_id, population: chart.population_key, metric: chart.metric_id, cutoff: chart.metric_observation_cutoff, release_id: chart.release_id, oa_date: chart.oa_snapshot_date, rw_date: chart.rw_snapshot_date})) assert.equal(record[key], expected);
    for (const key of ['numerator', 'denominator', 'value', 'unit']) assert.equal(record[key], String(chart.rows[index][key] ?? '').replace(/^[=+@\-\t\r]/, "'$&"));
  });
}
let exportsChecked = 0, legacyChecked = 0;
try {
  for (const section of sections) await check(`${section}: independent catalog filters, disabled ordering, search and modal`, async () => {
    await page.goto(base + reportHref(section, ['rw', 'oa'])); await page.locator('.report-evidence').waitFor();
    const before = await page.locator('.report-evidence').innerText(), originalURL = page.url();
    await page.getByRole('button', {name: '查找数据专题 ↓'}).click();
    const index = page.getByRole('region', {name: '本章数据专题目录'});
    assert.equal(await index.locator('select').count(), 0);
    for (const sources of [['rw'], ['rw', 'oa'], ['oa'], ['rw', 'oa']]) {
      for (const [source, label] of [['rw', 'Retraction Watch（RW）'], ['oa', 'OpenAlex']]) {const input = index.getByLabel(label, {exact: true}); if (await input.isChecked() !== sources.includes(source)) await input.setChecked(sources.includes(source));}
      const expected = topicCatalog(chunks[section].charts, sources, chunks[section].discipline_explorer, chunks[section].country_explorer);
      assert.deepEqual(await index.locator('.topic-card').evaluateAll(elements => elements.map(element => [element.dataset.topicId, element.dataset.enabled])), expected.map(topic => [topic.id, String(topic.enabled)]));
      assert.equal(await index.locator('.topic-card-disabled a').count(), 0);
      assert.equal(page.url(), originalURL); assert.equal(await page.locator('.report-evidence').innerText(), before);
    }
    await index.getByRole('searchbox').fill('nonexistent-xyz'); assert.equal(await index.locator('.topic-card').count(), 0); await index.getByRole('searchbox').fill('');
    const link = index.locator('.topic-card a').first(); assert.equal(await link.getAttribute('aria-haspopup'), 'dialog');
    await link.scrollIntoViewIfNeeded(); const previousScroll = await page.evaluate(() => scrollY);
    await link.click(); const dialog = page.locator('.topic-dialog[open]'); await dialog.waitFor();
    await dialog.locator('.topic-annual-comparison,.report-research-figure,.discipline-results,.country-explorer').first().waitFor();
    assert.equal(page.url(), originalURL); assert.equal(await page.locator('.report-evidence').innerText(), before);
    assert.equal(await dialog.locator('.report-opening,.report-sidebar,.topic-index').count(), 0);
    await page.keyboard.press('Escape'); await dialog.waitFor({state: 'hidden'});
    assert(await link.evaluate(element => element === document.activeElement));
    assert(Math.abs(await page.evaluate(() => scrollY) - previousScroll) < 2);

  });
  for (const [section, chunk] of Object.entries(chunks)) await check(`${section}: all topic slices, narratives and precise CSV; legacy links`, async () => {
    for (const chart of chunk.charts) {
      await page.goto(base + topicHref(section, topicId(chart), ['rw', 'oa'], `${chart.chart_id}/${chart.slice_id}`));
      if (chart.chart_id === 'T1') {
        await page.locator('.topic-annual-comparison').waitFor();
        const table = page.locator('.report-data-table'); if (!await table.evaluate(element => element.open)) await table.locator(':scope > summary').click();
        const region = page.getByRole('region', {name: `${chart.scope.date_basis === 'published' ? '按发表年' : '按撤稿年'}原始数据`, exact: true});
        assertCSV(await download(region.getByRole('button', {name: '导出本切片聚合 CSV', exact: true})), chart);
      } else {
        const figure = page.locator(`.report-research-figure[data-slice-id="${chart.slice_id}"]`); await figure.waitFor();
        assert.equal(await figure.locator('.report-finding-text').innerText(), chapterFinding({...chart, rows: chart.rows.map(row => ({...row, label: rowLabel(row, chart)}))}));
        const table = figure.locator('.report-data-table'); if (!await table.evaluate(element => element.open)) await table.locator(':scope > summary').click();
        assertCSV(await download(figure.getByRole('button', {name: '导出本切片聚合 CSV', exact: true})), chart);
      }
      exportsChecked++;
      await page.goto(base + reportHref(section, ['rw', 'oa'], `${chart.chart_id}/${chart.slice_id}`));
      await page.locator(chart.chart_id === 'T1' ? '.topic-annual-comparison' : section === 'overview' ? `.report-evidence[data-slice-id="${chart.slice_id}"]` : `.report-research-figure[data-slice-id="${chart.slice_id}"]`).waitFor();
      assert.equal(await page.locator('.report-topic').count(), 0); legacyChecked++;
    }
  });
  await check('dataset and method radios synchronize one figure and history', async () => {
    await page.goto(base + topicHref('fields', 'f1', ['rw', 'oa'], 'F1/A1-primary-field'));
    await page.locator('[data-slice-id="A1-primary-field"]').waitFor();
    await page.locator('input[type="radio"][name$="-population"][value="C"]').check(); await page.locator('[data-slice-id="C-primary-field"]').waitFor();
    assert.equal(await page.locator('.report-research-figure').count(), 1);
    await page.locator('input[type="radio"][name$="-variant"][value="F1/C-primary-subfield"]').check(); await page.locator('[data-slice-id="C-primary-subfield"]').waitFor();
    await page.goBack(); await page.locator('[data-slice-id="C-primary-field"]').waitFor(); await page.reload(); await page.locator('[data-slice-id="C-primary-field"]').waitFor();
  });
  await check('RW annual overlay preserves series, keyboard/touch path and zero/missing distinction', async () => {
    await page.goto(base + topicHref('time', 'annual-counts', ['rw'])); await page.locator('.topic-annual-comparison').waitFor();
    assert.equal(await page.locator('[data-annual-point]').count(), chunks.time.charts.filter(chart => chart.chart_id === 'T1').flatMap(chart => chart.rows.filter(row => row.year >= 2000 && row.value != null)).length);
    const point = page.locator('[data-annual-point]').first(); await point.focus(); await point.press('Enter'); assert.match(await page.locator('.topic-comparison-detail').innerText(), /已锁定/); await point.press('Escape');
    await page.getByLabel('按发表年', {exact: true}).uncheck(); assert.equal(await page.locator('[data-annual-point^="published/"]').count(), 0); assert.equal(await page.locator('.report-finding-text').count(), 1); await page.getByLabel('按发表年', {exact: true}).check();
  });
  await check('discipline links remain on their independent topic with node and parent', async () => {
    await page.goto(base + topicHref('fields', 'discipline', ['rw', 'oa'])); await page.locator('.discipline-results').waitFor();
    if (!await page.locator('.discipline-navigation').evaluate(element => element.open)) await page.getByText('选择分类、指标或主/子学科', {exact: true}).click();
    const branch = page.locator('.discipline-tree details').first(); await branch.locator('summary').click();
    const child = branch.locator('a').last(); assert((await child.getAttribute('href')).includes('/topic/discipline?')); await child.click();
    await page.waitForFunction(() => location.hash.includes('/topic/discipline?') && new URLSearchParams(location.hash.split('?')[1]).has('parent'));
    await page.getByLabel('查看指标', {exact: true}).selectOption('rate'); await page.reload(); await page.locator('.discipline-results').waitFor(); assert(page.url().includes('/topic/discipline?'));
  });
  for (const [size, width, height] of [['desktop', 1440, 900], ['tablet', 768, 1024], ['mobile', 390, 844]]) await check(`${size}: catalog and topic screenshot/accessibility`, async () => {
    await page.setViewportSize({width, height});
    await page.goto(base + reportHref('time', ['rw', 'oa'])); await page.locator('.report-evidence').waitFor(); await page.getByRole('button', {name: '查找数据专题 ↓'}).click(); await capture(`index-${size}`);
    await page.goto(base + topicHref('time', 'annual-counts', ['rw'])); await page.locator('.topic-annual-comparison').waitFor(); await page.evaluate(() => scrollTo(0, 0)); await capture(`annual-${size}`);
    await page.goto(base + topicHref('fields', 'f1', ['rw', 'oa'], 'F1/C-primary-field')); await page.locator('[data-slice-id="C-primary-field"]').waitFor(); await page.evaluate(() => scrollTo(0, 0)); await capture(`dataset-${size}`);
  });
  await check('invalid topic and incompatible slice/source never substitute a figure', async () => {
    for (const hash of [topicHref('time', 'unknown', ['rw']), topicHref('time', 'annual-counts', ['oa']), topicHref('fields', 'f1', ['oa'], 'F1/C-primary-field'), topicHref('fields', 'f1', ['rw', 'oa'], 'F3/A1_over_D-field-2000')]) {
      await page.goto(base + hash); await page.getByRole('alert').waitFor(); assert.equal(await page.locator('.report-research-figure,.topic-annual-comparison').count(), 0);
    }
  });
} finally {
  checks.push({name: 'uncaught page errors', status: errors.length ? 'failed' : 'passed', errors});
  const result = {browser: browser.version(), exportsChecked, legacyChecked, checks};
  await writeFile(`${output}/checks.json`, JSON.stringify(result, null, 2)); console.log(JSON.stringify(result, null, 2)); await browser.close();
}
if (checks.some(check => check.status === 'failed')) process.exitCode = 1;
import {decodeExplorer} from '../src/report/explorerCodec.js';
