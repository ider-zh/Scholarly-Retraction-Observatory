import assert from 'node:assert/strict';
import {mkdir, readFile, writeFile} from 'node:fs/promises';
import {countryStudy, countryTimeChart} from '../src/report/country.js';
import {resolveStudy, disciplineTimeChart} from '../src/report/discipline.js';

const {chromium} = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const base = process.env.REPORT_QA_URL || 'http://127.0.0.1:4173/';
const output = process.env.REPORT_QA_OUT || '/tmp/sro-cohort-review/confirmation';
await mkdir(output, {recursive: true});
const browser = await chromium.launch({executablePath: process.env.CHROMIUM_PATH || undefined, args: ['--no-sandbox']});
const page = await browser.newPage({viewport: {width: 1440, height: 900}, reducedMotion: 'reduce'});
page.setDefaultTimeout(10000);
const checks = [], errors = [];
page.on('pageerror', error => errors.push(error.message));
const fields = decodeExplorer(JSON.parse(await readFile('public/data/snapshot/fields.json', 'utf8')).discipline_explorer);
const country = JSON.parse(await readFile('public/data/snapshot/geography.json', 'utf8')).country_explorer;
async function check(name, action) {try {await action(); checks.push({name, status: 'passed'});} catch (error) {checks.push({name, status: 'failed', error: error.stack}); await page.keyboard.press('Escape');}}
async function visit(section, selection = {}, sources = 'rw,oa') {
  await page.goto(`${base}#/snapshot/${section}?${new URLSearchParams({sources, ...selection})}`);
  await page.locator('.report-evidence,.report-topic,.report-unavailable').first().waitFor();
}
function parseCSV(text) {
  const lines = text.replace(/^\ufeff/, '').split('\r\n').map(line => [...line.matchAll(/"((?:[^"]|"")*)"(?:,|$)/g)].map(match => match[1].replaceAll('""', '"')));
  const columns = lines.shift();
  return lines.map(line => Object.fromEntries(columns.map((column, index) => [column, line[index]])));
}
async function exportCheck(root, expected, metric, population, countryView = false) {
  if (countryView) {
    const disclosure = root.locator('.report-data-table').last();
    if (!await disclosure.evaluate(element => element.open)) await disclosure.locator('summary').click();
  }
  const pending = page.waitForEvent('download');
  await root.getByRole('button', {name: countryView ? '导出国家年度聚合 CSV' : '导出时间聚合 CSV', exact: true}).click();
  const rows = parseCSV(await readFile(await (await pending).path(), 'utf8'));
  assert.equal(rows.length, expected.rows.length);
  rows.forEach((row, index) => {
    for (const key of ['year', 'numerator', 'denominator', 'value', 'unit']) assert.equal(row[key], String(expected.rows[index][key] ?? ''));
    assert.equal(row.metric, metric); assert.equal(row.population, population);
    assert.equal(row.release_id, fields.release_id);
    assert.equal(row.date_basis, 'original_publication_year');
  });
}
async function capture(name) {
  await page.screenshot({path: `${output}/${name}.png`});
  assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
  if (process.env.AXE_PATH) {
    await page.addScriptTag({content: await readFile(process.env.AXE_PATH, 'utf8')});
    assert.deepEqual(await page.evaluate(async () => (await axe.run(document, {runOnly: {type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21aa']}})).violations.map(item => ({id: item.id, targets: item.nodes.map(node => node.target)}))), []);
  }
}
try {
  for (const taxonomy of ['topics', 'concepts']) await check(`${taxonomy}: both hierarchy levels, four metrics, both populations and annual CSV`, async () => {
    const tree = fields.taxonomies.find(candidate => candidate.id === taxonomy);
    const root = tree.nodes.find(node => node.label === 'Medicine') || tree.nodes.find(node => node.level === 0 && !node.navigation_only);
    const child = tree.nodes.find(node => node.level === root.level+1 && node.parents.includes(root.id));
    for (const node of [root, child]) {
      const selection = {taxonomy, node: node.id, ...(node.id !== root.id ? {parent: root.id} : {}), metric: 'proportion', population: 'A1'};
      await visit(taxonomy, selection); await page.locator('.discipline-results').waitFor();
      assert((await page.locator('.discipline-results > h2').innerText()).includes(node.label));
      for (const metric of ['proportion', 'count', 'share', 'rate']) {
        await page.locator(`.report-metric-choices input[value=${metric}]`).check();
        await exportCheck(page.locator('.discipline-results'), disciplineTimeChart(fields, resolveStudy(fields, ['rw', 'oa'], {...selection, metric})), metric, 'A1');
      }
      await page.locator('.report-metric-choices input[value=proportion]').check();
      await page.locator('.discipline-navigation > summary').click();
      await page.getByLabel('研究总体', {exact: true}).selectOption('C_D');
      await exportCheck(page.locator('.discipline-results'), disciplineTimeChart(fields, resolveStudy(fields, ['rw', 'oa'], {...selection, population: 'C_D'})), 'proportion', 'C_D');
      const url = page.url(); await page.reload(); await page.locator('.discipline-results').waitFor();
      assert.equal(page.url(), url); assert(await page.locator('.report-metric-choices input[value=proportion]').isChecked());
    }
  });
  await check('countries: same-year denominators, metrics, CN/US switching and matched subset CSV', async () => {
    await visit('geography', {node: 'CN', metric: 'proportion'}); await page.locator('.country-explorer').waitFor();
    for (const node of ['CN', 'US']) {
      await page.getByLabel('趋势国家/地区', {exact: true}).selectOption(node);
      for (const population of ['A1', 'C_D']) {
        await page.getByLabel('国家分析研究总体', {exact: true}).selectOption(population);
        for (const metric of ['proportion', 'count', 'rate']) {
          await page.locator(`.report-metric-choices input[value=${metric}]`).check();
          const study = countryStudy(country, ['rw', 'oa'], {node, population, metric});
          await exportCheck(page.locator('.country-explorer'), countryTimeChart(country, study), metric, population, true);
        }
      }
    }
    await page.getByRole('button', {name: '排序条形图', exact: true}).click();
    await page.getByLabel('搜索国家/地区', {exact: true}).fill('CN');
    await page.locator('.discipline-bar').click();
    assert.equal(await page.getByLabel('趋势国家/地区', {exact: true}).inputValue(), 'CN');
    await page.getByLabel('搜索国家/地区', {exact: true}).fill('');
    const point = page.locator('[data-chart-point]').first(); await point.focus(); await point.press('Enter');
    assert.match(await page.locator('.snapshot-point-detail').innerText(), /已锁定.*2000/s);
  });
  await check('source restrictions are explicit; RW has no substituted publication denominator', async () => {
    for (const section of ['topics', 'concepts', 'geography']) {
      await visit(section, {}, 'rw'); await page.locator('.report-unavailable').waitFor();
      assert.equal(await page.locator('.discipline-results,.country-explorer').count(), 0);
      await visit(section, {metric: 'proportion'}, 'oa'); await page.locator('.report-metric-choices').waitFor();
      assert(await page.locator('.report-metric-choices input[value=proportion]').isChecked());
    }
    assert(await page.locator('select[aria-label="国家分析研究总体"] option[value=C_D]').evaluate(element => element.disabled));
    await visit('geography', {population: 'C_D'}, 'oa'); await page.locator('.report-unavailable').waitFor();
    assert.equal(await page.locator('.country-explorer').count(), 0);
    await visit('subjects', {}, 'rw'); await page.locator('.discipline-results').waitFor();
    assert(await page.locator('.report-metric-choices input[value=proportion]').isDisabled());
  });
  await check('country modal selections stay local, share exact state and restore chapter focus', async () => {
    await visit('geography', {node: 'CN', metric: 'proportion'}); await page.locator('.country-explorer').waitFor();
    const original = page.url(), content = await page.locator('.report-evidence').innerText();
    const trigger = page.locator('.topic-card[data-topic-id=countries] a'); await trigger.click();
    const dialog = page.locator('.topic-dialog[open]'); await dialog.locator('.country-explorer').waitFor();
    await dialog.getByLabel('趋势国家/地区', {exact: true}).selectOption('US');
    await dialog.locator('.report-metric-choices input[value=count]').check();
    assert.equal(page.url(), original); assert.equal(await page.locator('.report-evidence').innerText(), content);
    const href = await dialog.getByRole('link', {name: /在独立页面打开/}).getAttribute('href');
    assert(href.includes('node=US') && href.includes('metric=count'));
    await page.keyboard.press('Escape'); assert(await trigger.evaluate(element => element === document.activeElement));
    await page.goto(base + href); await page.locator('.country-explorer').waitFor();
    assert.equal(await page.getByLabel('趋势国家/地区', {exact: true}).inputValue(), 'US');
    assert(await page.locator('.report-metric-choices input[value=count]').isChecked());
    await visit('geography', {slice: 'G1/A1_over_D-institution_country-2000'});
    await page.locator('.report-research-figure[data-slice-id="A1_over_D-institution_country-2000"]').waitFor();
    assert.equal(await page.locator('.country-explorer').count(), 0);
  });
  for (const [size, width, height] of [['desktop', 1440, 900], ['tablet', 768, 1024], ['mobile', 390, 844]]) await check(`${size}: percentage charts, zero baseline, screenshots and WCAG checks`, async () => {
    await page.setViewportSize({width, height});
    for (const section of ['topics', 'concepts', 'geography']) {
      await visit(section, {metric: 'proportion', ...(section === 'geography' ? {node: 'CN'} : {})});
      await page.locator('.report-metric-choices').waitFor();
      await page.locator('.report-metric-choices').scrollIntoViewIfNeeded(); await capture(`${size}-${section}-metrics`);
      await page.locator('.report-evidence .report-figure').first().scrollIntoViewIfNeeded(); await capture(`${size}-${section}-distribution`);
      await page.locator('.report-evidence .report-figure').last().scrollIntoViewIfNeeded(); await capture(`${size}-${section}-time`);
      const positions = await page.locator('[data-chart-point]').evaluateAll(elements => elements.map(element => Number(element.getAttribute('cy'))));
      assert(Math.min(...positions) < 40); assert(Math.max(...positions) <= 285);
      await page.evaluate(() => scrollTo(0, 0)); await page.screenshot({path: `${output}/${size}-${section}-full.png`, fullPage: true});
    }
    await page.locator('.topic-card[data-topic-id=countries] a').click();
    await page.locator('.topic-dialog[open] .country-explorer').waitFor(); await capture(`${size}-country-modal`); await page.keyboard.press('Escape');
  });
} finally {
  checks.push({name: 'uncaught browser errors', status: errors.length ? 'failed' : 'passed', errors});
  const result = {browser: browser.version(), release: fields.release_id, checks};
  await writeFile(`${output}/checks.json`, JSON.stringify(result, null, 2)); console.log(JSON.stringify(result, null, 2)); await browser.close();
}
if (checks.some(check => check.status === 'failed')) process.exitCode = 1;
import {decodeExplorer} from '../src/report/explorerCodec.js';
