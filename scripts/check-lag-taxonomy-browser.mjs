import assert from 'node:assert/strict';
import {mkdir, readFile, writeFile} from 'node:fs/promises';
import {decodeChartRows} from '../src/report/schema.js';
import {sectionData} from '../src/report/sections.js';

const {chromium} = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const base = process.env.REPORT_QA_URL || 'http://127.0.0.1:4173/';
const output = process.env.REPORT_QA_OUT || '/tmp/sro-lag-taxonomy/confirmation';
await mkdir(output, {recursive: true});
const browser = await chromium.launch({executablePath: process.env.CHROMIUM_PATH || undefined, args: ['--no-sandbox']});
const page = await browser.newPage({viewport: {width: 1440, height: 900}, reducedMotion: 'reduce'});
page.setDefaultTimeout(10000);
const checks = [], errors = [];
page.on('pageerror', error => errors.push(error.message));
const fields = JSON.parse(await readFile('public/data/snapshot/fields.json', 'utf8'));
const data = {charts: fields.charts.map(decodeChartRows), explorer: decodeExplorer(fields.discipline_explorer)};
const lag = JSON.parse(await readFile('public/data/snapshot/time.json', 'utf8')).charts.map(decodeChartRows).find(chart => chart.chart_id === 'T4');
async function check(name, action) {try {await action(); checks.push({name, status: 'passed'});} catch (error) {checks.push({name, status: 'failed', error: error.stack}); await page.keyboard.press('Escape');}}
async function capture(name) {
  await page.screenshot({path: `${output}/${name}.png`});
  assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
  if (process.env.AXE_PATH) {
    await page.addScriptTag({content: await readFile(process.env.AXE_PATH, 'utf8')});
    assert.deepEqual(await page.evaluate(async () => (await axe.run(document, {runOnly: {type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21aa']}})).violations.map(item => ({id: item.id, targets: item.nodes.map(node => node.target)}))), []);
  }
}
async function visit(section, query = 'sources=rw%2Coa') {await page.goto(`${base}#/snapshot/${section}?${query}`); await page.locator('.report-evidence,.report-unavailable,.report-topic').first().waitFor();}
try {
  await check('lag quantile bars use published days, proportional widths, keyboard and unchanged CSV', async () => {
    await visit('time', 'sources=rw&slice=T4%2FB-default'); await page.locator('.lag-summary').waitFor();
    for (const [key, days] of Object.entries(lag.quantiles)) {
      const point = page.locator(`[data-lag-quantile=${key}]`); assert((await point.innerText()).includes(days.toLocaleString('zh-CN')));
      assert(Math.abs(await point.locator('.lag-track > span').evaluate(element => parseFloat(element.style.width)) - 100 * days / lag.quantiles.p90_days) < 0.0001);
    }
    const first = page.locator('[data-lag-quantile=p25_days]'); await first.focus(); await first.press('ArrowDown');
    assert.equal(await page.locator('[data-lag-quantile=p50_days]').getAttribute('aria-pressed'), 'true');
    assert.match(await page.locator('.lag-explanation').innerText(), /490.*1.34/);
    await page.locator('.lag-advanced > summary').click(); await page.locator('[data-chart-point]').first().focus();
    const count = await page.locator('[data-chart-point]').count(); assert.equal(count, lag.rows.length);
    assert.match(await page.locator('.lag-advanced').innerText(), /不据连线推算/);
    await page.getByText('查看完整聚合数据与导出', {exact: true}).click();
    const pending = page.waitForEvent('download'); await page.getByRole('button', {name: '导出本切片聚合 CSV', exact: true}).click();
    const csv = await readFile(await (await pending).path(), 'utf8');
    for (const value of [lag.release_id, 'T4', 'B-default', 'lag_ecdf_pct', '66700', '29622']) assert(csv.includes(value));
  });
  for (const [section, source] of [['subjects', 'rw'], ['topics', 'oa'], ['concepts', 'oa']]) await check(`${section}: source isolation, fixed tree, child deep links, modal and published chart routes`, async () => {
    for (const sources of ['rw', 'oa', 'rw,oa']) {
      await visit(section, `sources=${encodeURIComponent(sources)}`);
      if (sources.includes(source)) {
        await page.locator('.discipline-results').waitFor();
        assert.equal(await page.getByLabel('分类方法论', {exact: true}).count(), 0);
        const label = data.explorer.taxonomies.find(taxonomy => taxonomy.id === section).label;
        assert((await page.locator('.discipline-results h2').first().innerText()).includes(label));
      } else {
        await page.getByRole('link', {name: '启用本章所需数据集'}).waitFor();
        assert.equal(await page.locator('.discipline-results,.report-research-figure').count(), 0);
        assert.equal(await page.locator('.topic-card[data-topic-id=discipline]').getAttribute('data-enabled'), 'false');
      }
    }
    await page.locator('.discipline-navigation > summary').click();
    const branch = page.locator('.discipline-tree details').first(); await branch.locator('summary').click(); await branch.locator('a').last().click();
    await page.waitForFunction(section => location.hash.startsWith(`#/snapshot/${section}?`) && location.hash.includes('parent='), section);
    const url = page.url(), title = await page.locator('.discipline-results h2').first().innerText();
    await page.reload(); await page.locator('.discipline-results').waitFor(); assert.equal(await page.locator('.discipline-results h2').first().innerText(), title);
    await page.locator('.topic-card[data-topic-id=discipline] a').click(); const dialog = page.locator('.topic-dialog[open]'); await dialog.locator('.discipline-results').waitFor();
    assert.equal(await dialog.getByLabel('分类方法论', {exact: true}).count(), 0);
    await dialog.locator('.discipline-navigation > summary').click();
    await dialog.getByLabel('查看指标', {exact: true}).selectOption('share');
    assert((await dialog.getByRole('link', {name: /在独立页面打开/}).getAttribute('href')).includes(`/snapshot/${section}/topic/discipline?`));
    assert.equal(page.url(), url); await page.keyboard.press('Escape');
    for (const chart of sectionData(data, section).charts) {
      await visit(section, `sources=rw%2Coa&slice=${encodeURIComponent(`${chart.chart_id}/${chart.slice_id}`)}`);
      await page.locator(`.report-research-figure[data-slice-id="${chart.slice_id}"]`).waitFor();
      assert.equal(await page.locator('.discipline-results').count(), 0);
    }
    await visit(`${section}/topic/discipline`); await page.locator('.discipline-results').waitFor();
    await visit(section, `sources=rw%2Coa&taxonomy=${section === 'subjects' ? 'topics' : 'subjects'}`); await page.getByRole('alert').waitFor(); assert.equal(await page.locator('.discipline-results').count(), 0);
  });
  await check('sidebar has three top-level chapters and old fields deep links remain exact', async () => {
    await visit('concepts'); await page.locator('.discipline-results').waitFor();
    const nav = page.getByRole('navigation', {name: '快照报告章节'});
    for (const section of ['subjects', 'topics', 'concepts']) assert.equal(await nav.locator(`a[href^="#/snapshot/${section}?"]`).count(), 1);
    assert.equal(await nav.locator('a[href^="#/snapshot/fields?"]').count(), 0);
    for (const taxonomy of ['subjects', 'topics', 'concepts']) {
      await visit('fields', `sources=rw%2Coa&taxonomy=${taxonomy}`); await page.locator('.discipline-results').waitFor();
      assert.equal(await page.getByLabel('分类方法论', {exact: true}).inputValue(), taxonomy);
    }
    await visit('concepts', 'sources=rw%2Coa&slice=F1%2FA1-primary-field'); await page.locator('.report-unavailable').waitFor(); assert.equal(await page.locator('.report-research-figure').count(), 0);
  });
  for (const [size, width, height] of [['desktop', 1440, 900], ['tablet', 768, 1024], ['mobile', 390, 844]]) await check(`${size}: lag and three chapters, screenshots and accessibility`, async () => {
    await page.setViewportSize({width, height}); await visit('time', 'sources=rw&slice=T4%2FB-default'); await page.locator('.lag-summary').scrollIntoViewIfNeeded(); await capture(`${size}-lag`);
    await page.screenshot({path: `${output}/${size}-lag-full.png`, fullPage: true});
    await page.locator('.topic-card[data-topic-id=t4] a').click(); await page.locator('.topic-dialog[open] .lag-summary').waitFor(); await capture(`${size}-lag-dialog`); await page.keyboard.press('Escape');
    for (const section of ['subjects', 'topics', 'concepts']) {
      await visit(section); await page.locator('.discipline-results').waitFor(); await page.evaluate(() => scrollTo(0, 0)); await capture(`${size}-${section}`);
      await page.locator('.discipline-results .report-figure').first().scrollIntoViewIfNeeded(); await capture(`${size}-${section}-chart`);
    }
  });
} finally {
  checks.push({name: 'uncaught page errors', status: errors.length ? 'failed' : 'passed', errors});
  const result = {browser: browser.version(), checks}; await writeFile(`${output}/checks.json`, JSON.stringify(result, null, 2)); console.log(JSON.stringify(result, null, 2)); await browser.close();
}
if (checks.some(check => check.status === 'failed')) process.exitCode = 1;
import {decodeExplorer} from '../src/report/explorerCodec.js';
