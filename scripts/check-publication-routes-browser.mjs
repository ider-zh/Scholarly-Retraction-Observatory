import assert from 'node:assert/strict';
import {mkdir, writeFile} from 'node:fs/promises';

const {chromium} = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const base = process.env.REPORT_QA_URL || 'http://127.0.0.1:8765/';
const output = process.env.REPORT_QA_OUT || '/tmp/sro-publication-routes';
await mkdir(output, {recursive: true});
const browser = await chromium.launch({executablePath: process.env.CHROMIUM_PATH || undefined, args: ['--no-sandbox', '--no-proxy-server']});
const context = await browser.newContext({viewport: {width: 1440, height: 900}, permissions: ['clipboard-read', 'clipboard-write']});
const page = await context.newPage();
page.setDefaultTimeout(15000);
const errors = [], failedRequests = [];
page.on('pageerror', error => errors.push(error.message));
page.on('response', response => {if (response.status() >= 400) failedRequests.push(response.url());});
async function visit(path, selector) {
  await page.goto(base + path);
  await page.locator(selector).first().waitFor();
}
try {
  await visit('', '.publication-list');
  const entries = await page.locator('.publication-list > a').evaluateAll(links => links.map(link => link.getAttribute('href')));
  assert.deepEqual(entries, ['reports/v1/', 'reports/v2/', 'slides/v2/'].map(path => new URL(path, base).pathname));
  await visit('reports/v1/', '.app .sidebar');
  await page.getByRole('button', {name: '学科与时滞', exact: true}).click();
  assert.equal(new URL(page.url()).hash, '#/disciplines');
  await page.reload(); await page.locator('.app .sidebar').waitFor();
  await page.getByRole('heading', {name: '学科与时滞', exact: true}).waitFor();
  await page.getByRole('button', {name: '分享当前内容'}).click();
  assert.equal(await page.evaluate(() => navigator.clipboard.readText()), page.url());
  await visit('#/report-v1', '.app .sidebar');
  assert.equal(new URL(page.url()).pathname, new URL('reports/v1/', base).pathname);
  await visit('#/snapshot/time?sources=rw&slice=T1%2FB-retracted', '.report-publication h1');
  assert.equal(new URL(page.url()).pathname, new URL('reports/v2/', base).pathname);
  assert.equal(new URL(page.url()).hash, '#/time?sources=rw&slice=T1%2FB-retracted');
  await page.reload(); await page.locator('.report-publication h1').waitFor();
  await page.getByRole('button', {name: '分享当前内容'}).click();
  assert.equal(await page.evaluate(() => navigator.clipboard.readText()), page.url());
  await page.locator('.report-sidebar a', {hasText: '研究概览'}).click();
  await page.waitForURL(url => url.hash === '#/overview?sources=rw');
  for (const sources of ['rw', 'oa', 'rw%2Coa']) {
    await visit(`reports/v2/#/overview?sources=${sources}`, '.report-opening h1');
    await page.locator('.report-scope-summary').waitFor();
    assert((await page.locator('.report-scope-summary').innerText()).includes(sources === 'oa' ? 'OpenAlex' : 'Retraction Watch'));
  }
  assert.equal(new URL(page.url()).hash, '');
  for (const [name, width, height] of [['desktop',1440,900], ['tablet',768,1024], ['mobile',390,844]]) {
    await page.setViewportSize({width,height});
    for (const [route, selector, label] of [['', '.publication-list', 'index'], ['reports/v1/', '.app .sidebar', 'v1'], ['reports/v2/', '.report-opening h1', 'v2'], ['slides/v2/#/13', '.slide.is-active', 'slides']]) {
      await visit(route, selector);
      await page.evaluate(() => document.fonts.ready);
      await page.waitForTimeout(600);
      await page.screenshot({path: `${output}/${name}-${label}.png`, animations: 'disabled'});
      assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), `${name}-${label}: overflow`);
    }
  }
  await page.setViewportSize({width:1440,height:900});
  await visit('presentation-v2/index.html?preview=1#/13', '.slide.is-active');
  assert.equal(new URL(page.url()).pathname, new URL('slides/v2/',base).pathname);
  assert.equal(new URL(page.url()).hash, '#/13');
  assert.equal(new URL(page.url()).search, '?preview=1');
  await visit('slides/v2/#/13', '.slide.is-active');
  assert.equal(await page.locator('#slide-picker').inputValue(), '13');
  await page.locator('#share-link').click();
  assert.equal(await page.evaluate(() => navigator.clipboard.readText()), page.url());
  await page.getByRole('link', {name: '在 v2 中探索此图'}).filter({visible:true}).first().click();
  await page.locator('.report-publication h1').waitFor();
  assert(new URL(page.url()).pathname.endsWith('/reports/v2/'));
  assert.deepEqual(errors, []); assert.deepEqual(failedRequests, []);
  await writeFile(`${output}/checks.json`, JSON.stringify({status:'passed', base, entries, errors, failedRequests}, null, 2));
  console.log('Publication routes: entry, legacy links, reload, source states, share, PPT evidence links, three viewport sizes passed.');
} finally {await browser.close();}
