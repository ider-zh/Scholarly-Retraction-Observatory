import assert from 'node:assert/strict';
import {readFile, mkdir, writeFile} from 'node:fs/promises';
import {validateManifest, validateChunk} from '../src/report/schema.js';
import {countryStudy} from '../src/report/country.js';
import {countryRateRows} from '../src/report/countryMap.js';
import {rowLabel, number} from '../src/report/reader.js';

const {chromium} = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const base = process.env.REPORT_QA_URL || 'http://127.0.0.1:5173/';
const output = process.env.REPORT_QA_OUT || '/tmp/sro-geomap-review/after';
await mkdir(output, {recursive: true});
const manifest = validateManifest(JSON.parse(await readFile('public/data/snapshot/manifest.json', 'utf8')));
const geography = validateChunk(JSON.parse(await readFile('public/data/snapshot/geography.json', 'utf8')), manifest, 'geography');
const browser = await chromium.launch({executablePath: process.env.CHROMIUM_PATH, args: ['--no-sandbox']});
const page = await browser.newPage(), errors = [], external = [], checks = [];
page.on('pageerror', error => errors.push(error.message));
await page.route('**/*', route => {if (!route.request().url().startsWith(new URL(base).origin)) {external.push(route.request().url()); return route.abort();} return route.continue();});
async function visit(sources = 'rw,oa', extra = '') {
  await page.goto(base+'#/snapshot/geography/topic/countries?sources='+encodeURIComponent(sources)+'&node=CN'+extra);
  if (sources.includes('oa')) await page.getByRole('button', {name: '离线地图', exact: true}).click();
}
try {
  for (const [name, width, height] of [['desktop', 1440, 900], ['tablet', 768, 1024], ['mobile', 390, 844]]) {
    await page.setViewportSize({width, height}); await visit(); await page.locator('.country-map svg').waitFor();
    assert.equal(await page.locator('.country-map svg > path').count(), 177);
    await page.locator('.country-map').screenshot({path: `${output}/${name}-map.png`});
    await page.screenshot({path: `${output}/${name}-full.png`, fullPage: true});
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
    if (process.env.AXE_PATH) {
      await page.addScriptTag({content: await readFile(process.env.AXE_PATH, 'utf8')});
      assert.deepEqual(await page.evaluate(async () => (await axe.run(document, {runOnly: {type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21aa']}})).violations.map(item => item.id)), []);
    }
    const usa = page.locator('.country-map [data-country="US"]'); await usa.focus(); await usa.press('Enter');
    assert.equal(await page.getByLabel('趋势国家/地区', {exact: true}).inputValue(), 'US');
    assert.equal(await usa.getAttribute('aria-pressed'), 'true');
    assert.match(await page.locator('.country-map-detail').innerText(), /美国/);
    checks.push(`${name}: map, keyboard selection, overflow, accessibility`);
  }
  for (const population of ['A1', 'C_D']) for (const metric of ['count', 'proportion', 'rate']) {
    await visit('rw,oa', `&population=${population}&metric=${metric}`); await page.locator('.country-map svg').waitFor();
    const study = countryStudy(geography.country_explorer, ['rw', 'oa'], {node: 'CN', population, metric});
    const row = study.ranked.find(row => row.id === 'CN');
    assert((await page.locator('.country-map [data-country="CN"]').getAttribute('aria-label')).includes(`n=${number(row.numerator)}，N=${number(row.denominator)}`));
    const data = page.locator('details').filter({has: page.locator(':scope > summary', {hasText: '查看国家分布数据与导出'})});
    if (!await data.evaluate(element => element.open)) await data.locator(':scope > summary').click();
    async function csv() {
      const [download] = await Promise.all([page.waitForEvent('download'), page.getByRole('button', {name: '导出国家分布聚合 CSV', exact: true}).click()]);
      return readFile(await download.path(), 'utf8');
    }
    const mapCSV = await csv(); await page.getByRole('button', {name: '排序条形图', exact: true}).click();
    const labels = await page.locator('.country-explorer .discipline-bar > span:first-child').allTextContents();
    assert.equal(labels.length, 20);
    assert(labels[0].includes(study.ranked[0].id));
    assert.equal(await csv(), mapCSV);
    checks.push(`${population}/${metric}: map, ranking and CSV synchronized`);
  }
  await page.goto(base+'#/snapshot/geography?sources=rw%2Coa'); await page.locator('.topic-card[data-topic-id="countries"]').waitFor();
  assert.equal(await page.locator('.topic-card[data-topic-id="country-rates"]').count(), 0);
  await page.locator('.topic-card[data-topic-id="countries"] a').click();
  await page.locator('.topic-dialog[open] .country-map svg').waitFor(); await page.getByRole('button', {name: '关闭专题', exact: true}).click();
  for (const chart of geography.charts.filter(chart => chart.metric_id.endsWith('_cohort_per_10k'))) {
    await page.goto(base+'#/snapshot/geography/topic/country-rates?sources=rw%2Coa&slice='+encodeURIComponent(`${chart.chart_id}/${chart.slice_id}`));
    await page.locator('.snapshot-bars').waitFor();
    const expected = countryRateRows(chart, chart.rows.filter(row => row.value != null)).slice(0, 15).map(row => rowLabel(row, chart));
    assert.deepEqual(await page.locator('.snapshot-bar-row > span').allTextContents(), expected);
    assert.match(await page.locator('.topic-analysis > .report-key-boundary').innerText(), /已合并/);
  }
  await visit('rw'); await page.locator('.report-unavailable').waitFor(); assert.equal(await page.locator('.country-map').count(), 0);
  await visit('oa'); await page.locator('.country-map').waitFor();
  assert(await page.locator('select[aria-label="国家分析研究总体"] option[value="C_D"]').evaluate(element => element.disabled));
  await page.goto(base+'#/snapshot/overview?sources=rw%2Coa'); await page.locator('.report-screening-plot').waitFor();
  assert.equal(await page.getByText('为什么选 article？journal 类型的论文被排除了吗？', {exact: true}).count(), 0);
  assert.deepEqual(errors, []);
  assert.deepEqual(external.filter(url => !url.startsWith('https://fonts.googleapis.com/css2?')), []);
  checks.push('merged catalog, legacy links, modal, RW/OA restrictions, removed explanation; map works with all external requests blocked (legacy font requests recorded)');
} finally {
  await writeFile(output+'/checks.json', JSON.stringify({checks, errors, external}, null, 2)); await browser.close();
}
console.log(checks);
