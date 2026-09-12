import assert from 'node:assert/strict';
import {mkdir, readFile, writeFile} from 'node:fs/promises';
import {decodeChartRows} from '../src/report/schema.js';

const {chromium} = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const base = process.env.REPORT_QA_URL || 'http://127.0.0.1:4187/';
const output = process.env.REPORT_QA_OUT || '/tmp/sro-author-ranking-review/after';
await mkdir(output, {recursive: true});
const browser = await chromium.launch({executablePath: process.env.CHROMIUM_PATH || undefined, args: ['--no-sandbox']});
const page = await browser.newPage({viewport: {width: 1440, height: 900}, reducedMotion: 'reduce'});
page.setDefaultTimeout(12000);
const errors = [], checks = [];
page.on('pageerror', error => errors.push(error.message));
const data = JSON.parse(await readFile('public/data/snapshot/entities.json', 'utf8'));
const charts = data.charts.map(decodeChartRows);
const raw = charts.find(chart => chart.chart_id === 'rw-author-names');
async function check(name, action) {
  try {await action(); checks.push({name, status: 'passed'});}
  catch (error) {checks.push({name, status: 'failed', error: error.stack});}
}
async function visit(sources, topic = '', slice = '') {
  await page.goto(`${base}#/snapshot/entities${topic ? `/topic/${topic}` : ''}?${new URLSearchParams({sources, ...(slice ? {slice} : {})})}`);
  await page.locator('.report-research-figure,.report-unavailable[role=alert]').first().waitFor();
}
async function capture(name) {
  await page.screenshot({path: `${output}/${name}.png`});
  assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
  if (process.env.AXE_PATH) {
    await page.addScriptTag({content: await readFile(process.env.AXE_PATH, 'utf8')});
    assert.deepEqual(await page.evaluate(async () => (await axe.run(document, {runOnly: {type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21aa']}})).violations.map(item => ({id: item.id, targets: item.nodes.map(node => node.target)}))), []);
  }
}
async function verifyExport(chart) {
  await page.locator('.report-data-table > summary').click();
  const pending = page.waitForEvent('download');
  await page.getByRole('button', {name: /导出.*CSV/}).click();
  const csv = (await readFile(await (await pending).path(), 'utf8')).replace(/^\ufeff/, '');
  const rows = csv.split('\r\n').map(line => [...line.matchAll(/"((?:[^"]|"")*)"(?:,|$)/g)].map(match => match[1].replaceAll('""', '"')));
  const columns = rows.shift();
  assert.equal(rows.length, chart.rows.length);
  rows.forEach((cells, index) => {
    const record = Object.fromEntries(columns.map((column, offset) => [column, cells[offset]]));
    for (const key of ['id', 'label', 'rank', 'numerator', 'denominator', 'value', 'unit']) assert.equal(record[key], String(chart.rows[index][key]));
    assert.equal(record.population, chart.population_key);
    assert.equal(record.slice_id, chart.slice_id);
    assert.equal(record.cutoff, chart.metric_observation_cutoff);
    assert.equal(record.release_id, chart.release_id);
    assert.equal(record.scope, JSON.stringify(chart.scope));
  });
}
try {
  await check('RW / OA / joint filters retain two distinct topic entries', async () => {
    for (const sources of ['rw', 'oa', 'rw,oa']) {
      await visit(sources);
      for (const [topic, enabled] of [['rw-author-names', sources.includes('rw')], ['author-top', sources.includes('oa')]]) {
        assert.equal(await page.locator(`.topic-card[data-topic-id="${topic}"]`).getAttribute('data-enabled'), String(enabled));
      }
    }
  });
  await check('RW raw-name table and exact aggregate CSV; missing placeholders not ranked', async () => {
    await visit('rw', 'rw-author-names');
    const note = page.getByRole('complementary', {name: '同名署名与作者身份说明'});
    assert(await note.isVisible());
    assert.match(await note.innerText(), /同一姓名字符串在 RW 中汇总、在 OpenAlex 中按不同作者 ID 区分/);
    assert.match(await note.innerText(), /不据此清洗、合并、拆分或重新计算数据/);
    const ranking = page.getByRole('region', {name: 'RW 原始署名字符串排行', exact: true});
    assert.equal(await ranking.locator('tbody tr').count(), raw.rows.length);
    for (const row of raw.rows) assert((await ranking.innerText()).includes(row.label));
    assert.equal(await ranking.locator('a[href^="https://openalex.org/A"]').count(), 0);
    await verifyExport(raw);
  });
  await check('OpenAlex identity population switching and legacy slice reload', async () => {
    await visit('rw,oa', 'author-top');
    for (const population of ['C', 'A1']) {
      await page.locator(`.topic-controls input[value="${population}"]`).check();
      const figure = page.locator('.report-research-figure');
      assert.equal(await figure.getAttribute('data-population'), population);
      assert.match(await figure.getByRole('complementary', {name: '同名署名与作者身份说明'}).innerText(), /不等于已经逐篇核实/);
      const chart = charts.find(chart => chart.chart_id === 'author-top' && chart.population_key === population);
      assert((await figure.innerText()).includes(chart.rows[0].numerator.toLocaleString('zh-CN')));
      assert.equal(await figure.locator('a[href^="https://openalex.org/A"]').count(), 20);
      await verifyExport(chart);
    }
    await visit('rw,oa', '', 'author-top/C-author-top-20');
    await page.reload(); await page.locator('.report-research-figure').waitFor();
    assert.equal(await page.locator('.report-research-figure').getAttribute('data-population'), 'C');
    await visit('rw', 'author-top', 'author-top/C-author-top-20');
    assert.equal(await page.locator('.report-research-figure').count(), 0);
  });
  await check('cards open distinct modal analyses without replacing chapter', async () => {
    await visit('rw,oa');
    const initial = page.url();
    for (const topic of ['rw-author-names', 'author-top']) {
      await page.locator(`.topic-card[data-topic-id="${topic}"] a`).click();
      const dialog = page.locator('.topic-dialog[open]');
      await dialog.locator('.report-research-figure').waitFor();
      assert(await dialog.getByRole('complementary', {name: '同名署名与作者身份说明'}).isVisible());
      assert.equal(await dialog.locator('.report-research-figure').getAttribute('data-chart-id'), topic);
      await page.keyboard.press('Escape'); assert.equal(page.url(), initial);
    }
  });
  for (const [name, width, height] of [['desktop', 1440, 900], ['tablet', 768, 1024], ['mobile', 390, 844]]) {
    await check(`${name}: readable distinct rankings, no page overflow, WCAG`, async () => {
      await page.setViewportSize({width, height});
      for (const [topic, sources] of [['rw-author-names', 'rw'], ['author-top', 'rw,oa']]) {
        await visit(sources, topic);
        await capture(`${name}-${topic}`);
        await page.locator('.report-figure').first().scrollIntoViewIfNeeded();
        await capture(`${name}-${topic}-table`);
      }
    });
  }
  await check('no uncaught browser errors', async () => assert.deepEqual(errors, []));
} finally {
  await writeFile(`${output}/checks.json`, JSON.stringify({release: data.release_id, browser: browser.version(), checks}, null, 2));
  await browser.close();
}
console.log(JSON.stringify(checks, null, 2));
if (checks.some(check => check.status !== 'passed')) process.exitCode = 1;
