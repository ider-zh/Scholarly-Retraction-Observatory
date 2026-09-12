import assert from 'node:assert/strict';
import {mkdir, readFile, writeFile} from 'node:fs/promises';
import {decodeChartRows} from '../src/report/schema.js';
import {topicCatalog, variantKey} from '../src/report/topics.js';
import {reportHref} from '../src/report/sources.js';
import {chapterFinding} from '../src/report/chapter.js';
import {rowLabel} from '../src/report/reader.js';

const {chromium} = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const output = process.env.REPORT_QA_OUT || '/tmp/sro-reading-update/confirmation';
const base = process.env.REPORT_QA_URL || 'http://127.0.0.1:4173/';
await mkdir(output, {recursive: true});
const browser = await chromium.launch({executablePath: process.env.CHROMIUM_PATH || undefined, args: ['--no-sandbox']});
const page = await browser.newPage({viewport: {width: 1440, height: 900}, reducedMotion: 'reduce'});
page.setDefaultTimeout(10000);
const checks = [], errors = [];
page.on('pageerror', error => errors.push(error.message));
const sections = ['overview', 'time', 'fields', 'reasons', 'geography', 'entities', 'publishing', 'citations', 'quality'];
async function check(name, action) {try {await action(); checks.push({name, status: 'passed'});} catch (error) {checks.push({name, status: 'failed', error: error.stack}); await page.keyboard.press('Escape');}}
async function capture(name) {
  await page.screenshot({path: `${output}/${name}.png`});
  assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
  if (process.env.AXE_PATH) {
    await page.addScriptTag({content: await readFile(process.env.AXE_PATH, 'utf8')});
    assert.deepEqual(await page.evaluate(async () => (await axe.run(document, {runOnly: {type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21aa']}})).violations.map(item => ({id: item.id, targets: item.nodes.map(node => node.target)}))), []);
  }
}
async function visit(section, sources = ['rw', 'oa'], slice = '') {
  await page.goto(base + reportHref(section, sources, slice));
  await page.locator('.report-evidence,.report-unavailable').first().waitFor();
}
let modalCount = 0, switchedGroups = 0;
try {
  for (const section of sections) await check(`${section}: bottom directory, all cards open isolated analyses, body dataset controls`, async () => {
    const chunk = JSON.parse(await readFile(`public/data/snapshot/${section}.json`, 'utf8'));
    const charts = chunk.charts.map(decodeChartRows);
    await visit(section);
    assert(await page.locator('.report-explorer').evaluate(element => element.open && element.nextElementSibling.classList.contains('report-next')));
    assert.equal(await page.locator('.report-explorer').evaluate(element => getComputedStyle(element).borderTopWidth), '0px');
    const evidence = await page.locator('.report-evidence').innerText(), originalURL = page.url();
    for (const link of await page.locator('.topic-card a').all()) {
      await link.click(); const dialog = page.locator('.topic-dialog[open]'); await dialog.waitFor();
      await dialog.locator('.report-research-figure,.topic-annual-comparison,.discipline-results,.country-explorer').first().waitFor();
      assert.equal(page.url(), originalURL);
      assert.equal(await page.locator('.report-evidence').innerText(), evidence);
      assert.equal(await dialog.locator('.report-opening,.report-sidebar,.topic-index').count(), 0);
      assert.equal(await dialog.getByRole('link', {name: /在独立页面打开/}).getAttribute('target'), '_blank');
      await dialog.getByRole('button', {name: '关闭专题'}).click();
      await dialog.waitFor({state: 'hidden'}); assert(await link.evaluate(element => element === document.activeElement)); modalCount++;
    }
    for (const topic of topicCatalog(charts, ['rw', 'oa'], decodeExplorer(chunk.discipline_explorer), chunk.country_explorer)) {
      if (topic.tree) continue;
      const initial = topic.allowed[0], alternate = topic.allowed.find(chart => chart.population_key !== initial.population_key && variantKey(chart) === variantKey(initial));
      if (!alternate) continue;
      await visit(section, ['rw', 'oa'], `${initial.chart_id}/${initial.slice_id}`);
      await page.locator(`.report-evidence input[type=radio][value="${alternate.population_key}"]`).check();
      const figure = page.locator(`.report-evidence .report-research-figure[data-slice-id="${alternate.slice_id}"]`); await figure.waitFor();
      assert.equal(await figure.locator('.report-finding-text').innerText(), chapterFinding({...alternate, rows: alternate.rows.map(row => ({...row, label: rowLabel(row, alternate)}))}));
      assert.equal(new URLSearchParams(page.url().split('?')[1]).get('slice'), `${alternate.chart_id}/${alternate.slice_id}`);
      assert(!page.url().includes('/topic/'));
      await page.reload(); await figure.waitFor();
      await page.goBack(); await page.locator(`.report-evidence [data-slice-id="${initial.slice_id}"]`).waitFor(); switchedGroups++;
    }
  });
  await check('modal radios leave chapter evidence, source selection and URL untouched', async () => {
    await visit('fields', ['rw', 'oa'], 'F1/A1-primary-field');
    const before = await page.locator('.report-evidence').innerText(), url = page.url();
    await page.locator('.topic-card[data-topic-id=f1] a').click(); const dialog = page.locator('.topic-dialog[open]');
    await dialog.locator('input[type=radio][value=C]').check();
    await dialog.locator('input[type=radio][value="F1/C-primary-subfield"]').check();
    await dialog.locator('[data-slice-id="C-primary-subfield"]').waitFor();
    assert.equal(page.url(), url); assert.equal(await page.locator('.report-evidence').innerText(), before);
    assert((await dialog.getByRole('link', {name: /在独立页面打开/}).getAttribute('href')).includes('slice=F1%2FC-primary-subfield'));
    const close = dialog.getByRole('button', {name: '关闭专题'}), last = dialog.getByRole('link', {name: /在独立页面打开/});
    await close.focus(); await page.keyboard.press('Shift+Tab'); assert(await last.evaluate(element => element === document.activeElement));
    await page.keyboard.press('Tab'); assert(await close.evaluate(element => element === document.activeElement));
    await page.mouse.click(2, 2); await dialog.waitFor({state: 'hidden'});
  });
  await check('Concepts defaults, Subjects fallback, explicit Topics and modal tree navigation', async () => {
    for (const [sources, expected] of [[['rw', 'oa'], 'concepts'], [['oa'], 'concepts'], [['rw'], 'subjects']]) {
      await visit('fields', sources); assert.equal(await page.getByLabel('分类方法论', {exact: true}).inputValue(), expected);
    }
    await page.goto(base + '#/snapshot/fields?sources=rw%2Coa&taxonomy=topics&population=A1'); await page.locator('.discipline-results').waitFor();
    assert.equal(await page.getByLabel('分类方法论', {exact: true}).inputValue(), 'topics');
    const before = await page.locator('.report-evidence').innerText(), url = page.url();
    await page.locator('.topic-card[data-topic-id=discipline] a').click(); const dialog = page.locator('.topic-dialog[open]');
    assert.equal(await dialog.getByLabel('分类方法论', {exact: true}).inputValue(), 'concepts');
    await dialog.locator('.discipline-navigation > summary').click();
    const branch = dialog.locator('.discipline-tree details').first(); await branch.locator('summary').click(); await branch.locator('a').last().click();
    assert.equal(page.url(), url); assert.equal(await page.locator('.report-evidence').innerText(), before);
    assert((await dialog.getByRole('link', {name: /在独立页面打开/}).getAttribute('href')).includes('parent='));
    await page.keyboard.press('Escape');
  });
  for (const [size, width, height] of [['desktop', 1440, 900], ['tablet', 768, 1024], ['mobile', 390, 844]]) await check(`${size}: reading, annual body and modal screenshot/accessibility`, async () => {
    await page.setViewportSize({width, height}); await visit('overview'); await page.evaluate(() => scrollTo(0, 0));
    assert.match(await page.locator('h1').innerText(), /撤稿告诉我们什么/);
    await capture(`${size}-overview`); await page.screenshot({path: `${output}/${size}-overview-full.png`, fullPage: true});
    await visit('time', ['rw']); await page.locator('.report-evidence .topic-annual-comparison').waitFor();
    await page.evaluate(() => scrollTo(0, 0)); await capture(`${size}-annual-body`);
    const link = page.locator('.topic-card[data-topic-id=annual-counts] a'); await link.click(); const dialog = page.locator('.topic-dialog[open]'); await dialog.waitFor();
    await capture(`${size}-annual-dialog`);
    const point = dialog.locator('[data-annual-point]').first(); await point.focus(); await point.press('Enter'); assert.match(await dialog.locator('.topic-comparison-detail').innerText(), /已锁定/);
    await dialog.getByLabel('按发表年', {exact: true}).uncheck(); assert.equal(await dialog.locator('[data-annual-point^="published/"]').count(), 0);
    assert(await page.locator('.report-evidence [data-annual-point^="published/"]').count() > 0);
    await dialog.getByRole('button', {name: '关闭专题'}).click(); assert(await link.evaluate(element => element === document.activeElement));
    await visit('fields', ['rw', 'oa'], 'F1/A1-primary-field'); await page.locator('.topic-card[data-topic-id=f1] a').click(); await page.locator('.topic-dialog[open]').waitFor(); await capture(`${size}-dataset-dialog`); await page.keyboard.press('Escape');
  });
} finally {
  checks.push({name: 'uncaught page errors', status: errors.length ? 'failed' : 'passed', errors});
  const result = {browser: browser.version(), modalCount, switchedGroups, checks};
  await writeFile(`${output}/checks.json`, JSON.stringify(result, null, 2)); console.log(JSON.stringify(result, null, 2)); await browser.close();
}
if (checks.some(check => check.status === 'failed')) process.exitCode = 1;
import {decodeExplorer} from '../src/report/explorerCodec.js';
