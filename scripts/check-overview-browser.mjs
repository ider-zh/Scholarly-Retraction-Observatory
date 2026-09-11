import assert from 'node:assert/strict';
import {mkdir, readFile, writeFile} from 'node:fs/promises';
import {resolve} from 'node:path';
import {execFileSync} from 'node:child_process';

const {chromium} = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const output = resolve(process.env.REPORT_QA_OUT || '/tmp/sro-overview-review/after');
const base = process.env.REPORT_QA_URL || 'http://127.0.0.1:4173/';
const manifest = JSON.parse(await readFile('public/data/snapshot/manifest.json', 'utf8'));
const overview = JSON.parse(await readFile('public/data/snapshot/overview.json', 'utf8'));
await mkdir(output, {recursive: true});
const browser = await chromium.launch({executablePath: process.env.CHROMIUM_PATH || undefined, args: ['--no-sandbox']});
const context = await browser.newContext({viewport: {width: 1440, height: 900}, reducedMotion: 'reduce'});
const page = await context.newPage();
const errors = [], checks = [], captures = [];
page.on('pageerror', error => errors.push(error.message));
const route = (sources = 'rw,oa', slice = '') => base+'#/snapshot/overview?'+new URLSearchParams({sources, ...(slice ? {slice} : {})});
async function check(name, action) {
  try {await action(); checks.push({name, status: 'passed'});}
  catch (error) {checks.push({name, status: 'failed', error: error.stack});}
}
async function ready(identifier = 'screening') {
  if (identifier) await page.locator(`.report-evidence[data-chart-id="${identifier}"]`).waitFor();
  else await page.locator('.report-unavailable').waitFor();
}
async function capture(name, full = true) {
  await page.screenshot({path: output+'/'+name+'.png'});
  if (full) await page.screenshot({path: output+'/'+name+'-full.png', fullPage: true});
  const geometry = await page.evaluate(() => ({viewport: {width: innerWidth, height: innerHeight}, pageWidth: document.documentElement.scrollWidth, pageHeight: document.documentElement.scrollHeight, figureTop: document.querySelector('.report-screening-plot')?.getBoundingClientRect().top ?? null}));
  captures.push({name, url: page.url(), ...geometry});
  assert(geometry.pageWidth <= geometry.viewport.width + 1, name+' horizontal overflow');
}
async function audit(label) {
  if (!process.env.AXE_PATH) {checks.push({name: label+' axe', status: 'not_run'}); return;}
  await page.addScriptTag({content: await readFile(process.env.AXE_PATH, 'utf8')});
  const violations = await page.evaluate(async () => (await axe.run(document, {runOnly: {type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21aa']}})).violations.map(item => ({id: item.id, targets: item.nodes.map(node => node.target)})));
  assert.deepEqual(violations, [], label+' axe');
}
async function exportCSV(button) {
  const pending = page.waitForEvent('download');
  await button.click();
  return readFile(await (await pending).path(), 'utf8');
}
try {
  for (const [name, width, height] of [['desktop', 1440, 900], ['tablet', 768, 1024], ['mobile', 390, 844]]) {
    await check(name+' initial layout and accessibility', async () => {
      await page.setViewportSize({width, height}); await page.goto(route()); await ready();
      await capture(name); await audit(name);
      assert.equal(await page.locator('.report-explorer').getAttribute('open'), null);
      assert.equal(await page.locator('.report-overview').evaluate(element => getComputedStyle(element).backgroundColor), 'rgb(255, 254, 251)');
      assert.equal(await page.locator('.snapshot-pagination,.snapshot-analysis-index,.snapshot-controls').count(), 0);
      assert.match(await page.locator('.report-finding-text').innerText(), /50,331.*43.94%/);
      if (name === 'desktop') assert((await page.locator('.report-screening-plot').boundingBox()).y < height, 'chart begins below desktop fold');
      if (name === 'mobile') {const finding = await page.locator('.report-finding-text').boundingBox(); assert(finding.y+finding.height < height, 'finding below mobile fold');}
    });
  }
  await page.setViewportSize({width: 1440, height: 900});
  await check('source switches keep scope, narrative and figure synchronized', async () => {
    await page.goto(route()); await ready();
    await page.getByRole('button', {name: '更改数据集或分析 ↓'}).click();
    await page.getByLabel('OpenAlex', {exact: true}).uncheck(); await ready(null);
    assert.equal(await page.locator('.report-evidence,.report-screening-plot').count(), 0);
    assert.match(await page.locator('.report-unavailable').innerText(), /尚未发布只使用 RW/);
    await page.evaluate(() => scrollTo(0, 0)); await capture('rw'); await audit('rw');
    await page.getByLabel('OpenAlex', {exact: true}).check(); await ready();
    await page.getByLabel('Retraction Watch（RW）', {exact: true}).uncheck(); await ready();
    await page.waitForFunction(() => location.hash.endsWith('sources=oa'));
    assert.doesNotMatch(await page.locator('.report-scope-summary').innerText(), /RW 记录截至/);
    assert.equal(await page.getByLabel('选择本章分析', {exact: true}).locator('option').count(), 2);
    await page.evaluate(() => scrollTo(0, 0)); await capture('oa'); await audit('oa');
    await page.getByLabel('Retraction Watch（RW）', {exact: true}).check(); await ready();
    await page.waitForFunction(() => location.hash.endsWith('sources=rw%2Coa'));
    assert.match(await page.locator('.report-scope-summary').innerText(), /不是两库并集/);
    assert.match(await page.locator('.report-finding .report-kicker').innerText(), /OpenAlex/);
  });
  await check('representative figure values, hover, keyboard, table and precise CSV', async () => {
    await page.goto(route()); await ready();
    const rows = overview.charts.find(chart => chart.chart_id === 'screening').rows;
    for (const row of rows) {
      const mark = page.locator(`[data-screening-row="${row.id}"]`);
      assert((await mark.getAttribute('aria-label')).includes(row.numerator.toLocaleString('zh-CN')));
      const cssPercentage = await mark.locator('.report-bar-track>span').evaluate(element => Number.parseFloat(element.style.width));
      assert(Math.abs(cssPercentage - row.value) < 0.0001, 'CSSOM rounding exceeds visual precision tolerance');
    }
    const retained = page.locator('[data-screening-row="retained_A1"]');
    await retained.hover(); assert.match(await page.locator('.report-bar-detail').innerText(), /50,331.*114,538/);
    await retained.focus(); await retained.press('Enter'); assert.match(await page.locator('.report-bar-detail').innerText(), /已锁定/);
    await retained.press('Escape'); assert.doesNotMatch(await page.locator('.report-bar-detail').innerText(), /已锁定/);
    await retained.press('ArrowDown'); assert.equal(await page.locator('[data-screening-row="excluded_work_type"]').evaluate(element => element === document.activeElement), true);
    await page.getByText('查看本图数据表与导出', {exact: true}).click();
    const csv = await exportCSV(page.getByRole('button', {name: '导出本切片聚合 CSV', exact: true}));
    for (const expected of ['A0-screening', manifest.release_id, 'paper_coverage_pct', '114538', '43.942622', manifest.oa_snapshot_date, 'report-source-v1']) assert(csv.includes(expected), expected+' missing from CSV');
    assert.equal(await page.locator('.report-data-table tbody tr').count(), rows.length);
    await audit('figure with table open');
  });
  await check('all old overview deep links, selection, reload and history', async () => {
    for (const chart of overview.charts) {
      await page.goto(route('rw,oa', chart.chart_id+'/'+chart.slice_id)); await ready(chart.chart_id);
      assert.equal(await page.locator('.report-evidence').getAttribute('data-population'), chart.population_key);
      assert.equal(await page.locator('.report-evidence').getAttribute('data-metric'), chart.metric_id);
    }
    await capture('deep-link');
    assert.doesNotMatch(await page.locator('.report-finding-text').innerText(), /43.94%/);
    await page.reload(); await ready('work-types');
    await page.getByRole('button', {name: '更改数据集或分析 ↓'}).click();
    await page.getByLabel('选择本章分析', {exact: true}).selectOption('screening/A0-screening'); await ready();
    assert.match(await page.locator('.report-finding-text').innerText(), /43.94%/);
    await page.goBack(); await ready('work-types');
    await page.getByText('查看完整聚合数据与计算方法', {exact: true}).click();
    const csv = await exportCSV(page.getByRole('button', {name: '导出本切片聚合 CSV', exact: true}));
    assert(csv.includes('A0-work-types') && csv.includes('88913') && !csv.includes('retained_A1'));
  });
  await check('copy success, route change and clipboard failure', async () => {
    await page.goto(route()); await ready();
    await page.getByRole('button', {name: '更改数据集或分析 ↓'}).click();
    await context.grantPermissions(['clipboard-read', 'clipboard-write']);
    await page.getByRole('button', {name: '复制当前分析链接', exact: true}).click();
    await page.getByText('链接已复制，包含当前数据集与分析。', {exact: true}).waitFor();
    assert.equal(await page.evaluate(() => navigator.clipboard.readText()), page.url());
    await page.getByLabel('选择本章分析', {exact: true}).selectOption('work-types/A0-work-types'); await ready('work-types');
    assert.equal(await page.getByText('链接已复制，包含当前数据集与分析。', {exact: true}).count(), 0);
    await page.evaluate(() => {Object.defineProperty(navigator.clipboard, 'writeText', {configurable: true, value: async () => {throw Error('blocked for failure test');}});});
    await page.getByRole('button', {name: '复制当前分析链接', exact: true}).click();
    await page.getByText('无法自动复制，请复制浏览器地址栏中的完整链接。', {exact: true}).waitFor();
  });
  await check('unsupported source/slice and invalid source never show replacement evidence', async () => {
    for (const url of [route('rw', 'screening/A0-screening'), route('oa', 'population-accounting/mixed_diagnostic-default'), route('oa', 'unknown/slice'), route('invalid')]) {
      await page.goto(url); await ready(null);
      assert.equal(await page.locator('.report-evidence').count(), 0);
    }
    await capture('unavailable', false);
  });
  await check('enlarged text 200 percent', async () => {
    await page.goto(route()); await ready();
    await page.evaluate(() => {for (const element of document.querySelector('.report-overview').querySelectorAll('*')) {const size = getComputedStyle(element).fontSize; element.dataset.qaFontSize = size;} for (const element of document.querySelectorAll('[data-qa-font-size]')) element.style.fontSize = Number.parseFloat(element.dataset.qaFontSize)*2+'px';});
    await capture('text-200'); await audit('text-200');
  });
  await check('mobile touch interaction and chapter navigation', async () => {
    const touch = await browser.newContext({viewport: {width: 390, height: 844}, isMobile: true, hasTouch: true, reducedMotion: 'reduce'});
    const mobile = await touch.newPage(); await mobile.goto(route()); await mobile.locator('.report-screening-plot').waitFor();
    await mobile.locator('[data-screening-row="excluded_suspected_notice"]').tap();
    assert.match(await mobile.locator('.report-bar-detail').innerText(), /已锁定.*标题疑似/s);
    await mobile.getByRole('button', {name: '取消锁定', exact: true}).tap();
    await mobile.getByText('报告目录', {exact: true}).tap();
    assert.equal(await mobile.locator('.report-chapters nav a').count(), 10);
    await mobile.getByRole('link', {name: '学科与主题', exact: true}).tap(); await mobile.locator('.discipline-tree').waitFor();
    assert.equal(await mobile.locator('.report-overview').count(), 0);
    await mobile.goBack(); await mobile.locator('.report-screening-plot').waitFor(); await touch.close();
  });
} finally {
  checks.push({name: 'no uncaught page errors', status: errors.length ? 'failed' : 'passed', errors});
  const report = {commit: execFileSync('git', ['rev-parse', 'HEAD'], {encoding: 'utf8'}).trim(), release: manifest.release_id, oa_date: manifest.oa_snapshot_date, rw_date: manifest.rw_snapshot_date, browser: browser.version(), base, checks, captures};
  await writeFile(output+'/checks.json', JSON.stringify(report, null, 2));
  console.log(JSON.stringify(report, null, 2)); await browser.close();
}
if (checks.some(check => check.status === 'failed')) process.exitCode = 1;
