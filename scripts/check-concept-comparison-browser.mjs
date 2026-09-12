import assert from 'node:assert/strict';
import {mkdir, readFile, writeFile} from 'node:fs/promises';
import {decodeExplorer} from '../src/report/explorerCodec.js';
import {disciplineCell} from '../src/report/discipline.js';

const {chromium} = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const base = process.env.REPORT_QA_URL || 'http://127.0.0.1:5186/';
const output = process.env.REPORT_QA_OUT || '/tmp/sro-concept-comparison-review';
const data = decodeExplorer(JSON.parse(await readFile('public/data/snapshot/fields.json', 'utf8')).discipline_explorer);
const taxonomy = data.taxonomies.find(item => item.id === 'concepts');
const medicine = taxonomy.nodes.find(node => node.label === 'Medicine');
const browser = await chromium.launch({executablePath: process.env.CHROMIUM_PATH, args: ['--no-sandbox']});
const checks = [], errors = [];
async function exportedRows(section, metric, population) {
  const details = section.locator('details');
  if (await details.getAttribute('open') === null) await details.locator('summary').click();
  const pending = section.page().waitForEvent('download');
  await section.getByRole('button', {name: '导出全部对比序列 CSV'}).click();
  const csv = (await readFile(await (await pending).path(), 'utf8')).replace(/^\ufeff/, '');
  const records = csv.split('\r\n').map(line => [...line.matchAll(/"((?:[^"]|"")*)"(?:,|$)/g)].map(match => match[1].replaceAll('""', '"')));
  const [columns, ...values] = records;
  const rows = values.map(values => Object.fromEntries(columns.map((column, index) => [column, values[index]])));
  for (const row of rows) {
    assert.equal(row.metric, metric);
    assert.equal(row.population, population);
    assert.equal(row.release_id, data.release_id);
    assert.equal(row.date_basis, 'original_publication_year');
    const node = taxonomy.nodes.find(node => node.id === row.concept_id);
    const expected = disciplineCell(taxonomy, node, population, metric, Number(row.year) - data.year_start + 1);
    if (metric === 'proportion') {
      assert.equal(row.value, String(expected.value ?? ''));
      assert.equal(row.numerator, String(expected.numerator ?? ''));
      assert.equal(row.denominator, String(expected.denominator ?? ''));
      assert.equal(row.ranking_eligible, String(expected.ranking_eligible));
      assert.equal(row.unit, 'percent');
    } else assert.equal(row.count, String(expected.value ?? ''));
  }
  return rows;
}
await mkdir(output, {recursive: true});
try {
  for (const [device, width, height] of [['desktop', 1440, 900], ['tablet', 768, 1024], ['mobile', 390, 844]]) {
    const page = await browser.newPage({viewport: {width, height}, reducedMotion: 'reduce'});
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(`${base}#/snapshot/concepts?sources=oa&metric=count`);
    const roots = page.locator('[data-comparison-level="roots"]');
    await roots.waitFor();
    assert.equal(await roots.locator('[data-concept-series]').count(), 19);
    assert.equal(await page.locator('[data-comparison-level="children"]').count(), 0);
    await roots.evaluate(element => element.scrollIntoView({block: 'start'}));
    await page.screenshot({path: `${output}/${device}-roots.png`});
    const choice = roots.locator(`[data-concept-choice="${medicine.id}"]`);
    await choice.focus(); await choice.press('Enter');
    const children = page.locator('[data-comparison-level="children"]');
    await children.waitFor();
    assert.equal(await children.getAttribute('data-parent'), medicine.id);
    assert(new URLSearchParams(page.url().split('?')[1]).get('node') === medicine.id);
    assert.equal(await children.locator('[data-concept-series]').count(), taxonomy.nodes.filter(node => node.level === 1 && !node.missing && !node.navigation_only && node.parents.includes(medicine.id)).length);
    await children.locator('[data-concept-choice]').first().click();
    assert.equal(await children.locator('[aria-pressed="true"]').count(), 1);
    await children.evaluate(element => element.scrollIntoView({block: 'start'}));
    await page.screenshot({path: `${output}/${device}-children.png`});
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
    if (process.env.AXE_PATH) {
      await page.addScriptTag({content: await readFile(process.env.AXE_PATH, 'utf8')});
      assert.deepEqual(await page.evaluate(async () => (await axe.run('.concept-comparisons', {runOnly: {type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21aa']}})).violations.map(item => item.id)), []);
    }
    if (device === 'desktop') {
      assert.equal((await exportedRows(roots, 'count', 'A1')).length, 19 * (data.year_end - data.year_start + 1));
    }
    await page.goto(`${base}#/snapshot/concepts?sources=oa&node=${encodeURIComponent(medicine.id)}&metric=proportion`);
    await page.locator('[data-comparison-level="roots"][data-metric="proportion"]').waitFor();
    assert.equal(await roots.locator('[data-concept-series]').count(), 19);
    assert.match(await roots.locator('h2').innerText(), /学科内撤稿比例/);
    assert.match(await roots.locator('svg').first().textContent(), /%/);
    assert.equal(await children.getAttribute('data-metric'), 'proportion');
    assert.equal(await children.getAttribute('data-parent'), medicine.id);
    for (const [level, section] of [['roots', roots], ['children', children]]) {
      await section.evaluate(element => element.scrollIntoView({block: 'start'}));
      await page.screenshot({path: `${output}/${device}-${level}-proportion.png`});
    }
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
    if (process.env.AXE_PATH) {
      await page.addScriptTag({content: await readFile(process.env.AXE_PATH, 'utf8')});
      assert.deepEqual(await page.evaluate(async () => (await axe.run('.concept-comparisons', {runOnly: {type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21aa']}})).violations.map(item => item.id)), []);
    }
    if (device === 'desktop') {
      const ratioRows = await exportedRows(roots, 'proportion', 'A1');
      assert.equal(ratioRows.length, 19 * (data.year_end - data.year_start + 1));
      assert(ratioRows.some(row => row.ranking_eligible === 'false' && Number(row.value) > 0));
      const geometry = await roots.locator('.concept-comparison-canvas svg').evaluate(svg => ({width: svg.viewBox.baseVal.width, series: [...svg.querySelectorAll('[data-concept-series]')].map(group => ({id: group.getAttribute('data-concept-series'), positions: [...group.querySelectorAll('polyline')].flatMap(line => [...line.points].map(point => point.x))}))}));
      for (const group of geometry.series) for (const position of group.positions) {
        const year = Math.round(data.year_start + (position - 65) / (geometry.width - 90) * (data.year_end - data.year_start));
        const row = ratioRows.find(row => row.concept_id === group.id && Number(row.year) === year);
        assert.equal(row.ranking_eligible, 'true');
      }
      await exportedRows(children, 'proportion', 'A1');
      await page.goto(`${base}#/snapshot/concepts?sources=rw%2Coa&population=C_D&node=${encodeURIComponent(medicine.id)}&metric=proportion`);
      await page.locator('[data-comparison-level="roots"][data-population="C_D"][data-metric="proportion"]').waitFor();
      assert.match(await roots.locator('h2').innerText(), /学科内撤稿比例/);
      await exportedRows(roots, 'proportion', 'C_D');
      await page.reload(); await page.locator('[data-comparison-level="children"][data-population="C_D"]').waitFor();
      const controls = page.getByRole('group', {name: '全部学科年度对比指标'});
      await controls.getByRole('radio', {name: '撤稿记录论文数', exact: true}).check();
      await page.locator('[data-comparison-level="roots"][data-metric="count"]').waitFor();
      const route = new URLSearchParams(page.url().split('?')[1]);
      assert.equal(route.get('metric'), 'count');
      assert.equal(route.get('node'), medicine.id);
      assert.equal(route.get('population'), 'C_D');
      assert.equal(route.get('sources'), 'rw,oa');
      assert.equal(await children.getAttribute('data-metric'), 'count');
      await controls.getByRole('radio', {name: '学科内撤稿比例', exact: true}).check();
      await page.locator('[data-comparison-level="roots"][data-metric="proportion"]').waitFor();
      await page.goto(`${base}#/snapshot/concepts?sources=rw`);
      await page.locator('.report-unavailable').waitFor();
      assert.equal(await page.locator('.concept-comparisons').count(), 0);
    }
    checks.push(`${device}: all roots/children, count and within-subject proportion, selection, width, screenshots and accessibility`);
    await page.close();
  }
  assert.deepEqual(errors, []);
  await writeFile(`${output}/checks.json`, JSON.stringify({release: data.release_id, checks, errors}, null, 2));
  console.log('PASS: three viewports, all-series export, source/population/deep-link synchronization');
} finally {await browser.close();}
