import assert from 'node:assert/strict';
import {mkdir, readFile, writeFile} from 'node:fs/promises';
import {decodeExplorer} from '../src/report/explorerCodec.js';
import {resolveStudy, studyAncestors, disciplineTimeChart} from '../src/report/discipline.js';

const {chromium} = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const base = process.env.REPORT_QA_URL || 'http://127.0.0.1:4173/';
const output = process.env.REPORT_QA_OUT || '/tmp/sro-topic-hierarchy-review/after';
await mkdir(output, {recursive: true});
const browser = await chromium.launch({executablePath: process.env.CHROMIUM_PATH || undefined, args: ['--no-sandbox']});
const page = await browser.newPage({viewport: {width: 1440, height: 900}, reducedMotion: 'reduce'});
page.setDefaultTimeout(12000);
const errors = [], checks = [];
page.on('pageerror', error => errors.push(error.message));
const data = decodeExplorer(JSON.parse(await readFile('public/data/snapshot/fields.json', 'utf8')).discipline_explorer);
const taxonomy = data.taxonomies.find(taxonomy => taxonomy.id === 'topics');
const topic = taxonomy.nodes.find(node => node.level === 3 && node.counts.A1[0] >= 20);
const initial = resolveStudy(data, ['rw', 'oa'], {taxonomy: 'topics', node: topic.id});
const path = [...studyAncestors(initial), topic];
async function check(name, action) {try {await action(); checks.push({name, status: 'passed'});} catch (error) {checks.push({name, status: 'failed', error: error.stack}); await page.keyboard.press('Escape');}}
async function visit(selection = {}, sources = 'rw,oa', section = 'topics') {
  await page.goto(`${base}#/snapshot/${section}?${new URLSearchParams({sources, ...selection})}`);
  await page.locator('.discipline-results,.report-unavailable,[role=alert]').first().waitFor();
}
async function capture(name) {
  await page.screenshot({path: `${output}/${name}.png`});
  assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth+1));
  if (process.env.AXE_PATH) {
    await page.addScriptTag({content: await readFile(process.env.AXE_PATH, 'utf8')});
    assert.deepEqual(await page.evaluate(async () => (await axe.run(document, {runOnly: {type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21aa']}})).violations.map(item => ({id: item.id, targets: item.nodes.map(node => node.target)}))), []);
  }
}
async function verifyAnnual(node, metric, population) {
  const expected = disciplineTimeChart(data, resolveStudy(data, ['rw', 'oa'], {taxonomy: 'topics', node: node.id, metric, population}));
  const pending = page.waitForEvent('download'); await page.getByRole('button', {name: '导出时间聚合 CSV', exact: true}).click();
  const text = (await readFile(await (await pending).path(), 'utf8')).replace(/^\ufeff/, '');
  const rows = text.split('\r\n').map(line => [...line.matchAll(/"((?:[^"]|"")*)"(?:,|$)/g)].map(match => match[1].replaceAll('""', '"')));
  const columns = rows.shift(); assert.equal(rows.length, 27);
  rows.forEach((cells, index) => {
    const record = Object.fromEntries(columns.map((column, offset) => [column, cells[offset]]));
    for (const key of ['year', 'numerator', 'denominator', 'value', 'unit']) assert.equal(record[key], String(expected.rows[index][key] ?? ''));
    assert.equal(record.selected_node, node.id); assert.equal(record.population, population); assert.equal(record.metric, metric); assert.equal(record.release_id, data.release_id);
  });
}
try {
  await check('four-level progressive tree reaches an actual Topic without rendering all topics initially', async () => {
    await visit(); assert.match(await page.locator('.discipline-results > h2').innerText(), /全部大领域/);
    await page.locator('.discipline-navigation > summary').click();
    assert.equal(await page.locator('.topic-tree > details').count(), taxonomy.nodes.filter(node => node.level === 0).length);
    assert(await page.locator('.topic-tree a').count() < 30);
    for (const node of path.slice(0, 3)) await page.locator(`details[data-topic-node="${node.id}"] > summary`).click();
    const leaf = page.locator('.topic-tree a').filter({hasText: topic.label}).first(); await leaf.click();
    await page.waitForFunction(identifier => new URLSearchParams(location.hash.split('?')[1]).get('node') === identifier, topic.id);
    for (const node of path) assert((await page.locator('.discipline-breadcrumb').innerText()).includes(node.label));
    assert((await page.locator('.discipline-results > h2').innerText()).includes(topic.label));
  });
  await check('all four levels: source and metric switches preserve exact yearly CSV and deep links', async () => {
    for (const node of path) for (const population of ['A1', 'C_D']) {
      await visit({node: node.id, population, metric: 'count'});
      for (const metric of ['count', 'proportion', 'share', 'rate']) {
        await page.locator(`.report-metric-choices input[value=${metric}]`).check();
        await verifyAnnual(node, metric, population);
      }
      const url = page.url(); await page.reload(); await page.locator('.discipline-results').waitFor(); assert.equal(page.url(), url);
    }
  });
  await check('topic search, legacy Field/Subfield routes, source restrictions and modal isolation', async () => {
    await visit(); await page.locator('.discipline-navigation > summary').click();
    await page.getByLabel('搜索学科或研究主题', {exact: true}).fill(topic.id);
    await page.locator('.topic-tree a').filter({hasText: topic.label}).click();
    assert((await page.locator('.discipline-results > h2').innerText()).includes(topic.label));
    const url = page.url(), heading = await page.locator('.discipline-results > h2').innerText();
    await page.locator('.topic-card[data-topic-id=discipline] a').click();
    const dialog = page.locator('.topic-dialog[open]'); await dialog.locator('.discipline-results').waitFor();
    await dialog.locator('.discipline-navigation > summary').click(); await dialog.getByLabel('搜索学科或研究主题', {exact: true}).fill(topic.id);
    await dialog.locator('.topic-tree a').filter({hasText: topic.label}).click(); await dialog.locator('.report-metric-choices input[value=proportion]').check();
    const href = await dialog.getByRole('link', {name: /在独立页面打开/}).getAttribute('href'); assert(href.includes('metric=proportion'));
    assert.equal(page.url(), url); await page.keyboard.press('Escape'); assert.equal(await page.locator('.discipline-results > h2').innerText(), heading);
    for (const node of path.slice(1, 3)) {await visit({taxonomy: 'topics', node: node.id}, 'oa', 'fields'); assert((await page.locator('.discipline-results > h2').innerText()).includes(node.label));}
    await visit({}, 'rw'); assert.equal(await page.locator('.discipline-results').count(), 0);
    await visit({population: 'C_D'}, 'oa'); await page.getByRole('alert').waitFor();
    await visit({node: topic.id, parent: path[0].id}); await page.getByRole('alert').waitFor();
  });
  for (const [size, width, height] of [['desktop', 1440, 900], ['tablet', 768, 1024], ['mobile', 390, 844]]) await check(`${size}: root, expanded tree, Topic plots and accessibility`, async () => {
    await page.setViewportSize({width, height}); await visit({metric: 'proportion'}); await page.evaluate(() => scrollTo(0, 0)); await capture(`${size}-root`);
    await visit({node: topic.id, metric: 'proportion'}); await page.locator('.discipline-navigation > summary').click();
    await page.locator('.topic-tree').scrollIntoViewIfNeeded(); await capture(`${size}-tree`);
    await page.locator('.discipline-results > h2').scrollIntoViewIfNeeded(); await capture(`${size}-topic`);
    await page.locator('.report-evidence .report-figure').last().scrollIntoViewIfNeeded(); await capture(`${size}-time`);
    await page.screenshot({path: `${output}/${size}-full.png`, fullPage: true});
  });
} finally {
  checks.push({name: 'browser errors', status: errors.length ? 'failed' : 'passed', errors});
  const result = {browser: browser.version(), release: data.release_id, topic: topic.id, checks};
  await writeFile(`${output}/checks.json`, JSON.stringify(result, null, 2)); console.log(JSON.stringify(result, null, 2)); await browser.close();
}
if (checks.some(check => check.status === 'failed')) process.exitCode = 1;
