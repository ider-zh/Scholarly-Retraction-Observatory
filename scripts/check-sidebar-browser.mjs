import assert from 'node:assert/strict';
import {mkdir, readFile, writeFile} from 'node:fs/promises';

const {chromium} = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const output = process.env.REPORT_QA_OUT || '/tmp/sro-sidebar-review/after';
const base = process.env.REPORT_QA_URL || 'http://127.0.0.1:4173/';
await mkdir(output, {recursive: true});
const browser = await chromium.launch({executablePath: process.env.CHROMIUM_PATH || undefined, args: ['--no-sandbox']});
const page = await browser.newPage({reducedMotion: 'reduce'}), errors = [], checks = [];
page.on('pageerror', error => errors.push(error.message));
const route = '#/snapshot/overview/topic/screening?sources=rw%2Coa';
async function check(name, action) {try {await action(); checks.push({name, status: 'passed'});} catch (error) {checks.push({name, status: 'failed', error: error.stack});}}
async function audit() {
  if (!process.env.AXE_PATH) return;
  await page.addScriptTag({content: await readFile(process.env.AXE_PATH, 'utf8')});
  assert.deepEqual(await page.evaluate(async () => (await axe.run(document, {runOnly: {type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21aa']}})).violations.map(item => ({id: item.id, targets: item.nodes.slice(0, 3).map(node => node.target)}))), []);
}
async function capture(name) {
  await page.screenshot({path: `${output}/${name}.png`});
  assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
  await audit();
}
try {
  for (const [size, width, height] of [['desktop', 1440, 900], ['tablet', 768, 1024], ['mobile', 390, 844]]) await check(`${size}: single directory, breadcrumb and accessible responsive navigation`, async () => {
    await page.goto('about:blank'); await page.setViewportSize({width, height}); await page.goto(base + route); await page.locator('.report-research-figure').waitFor();
    assert.equal(await page.locator('.report-masthead,.report-chapters').count(), 0);
    assert.equal(await page.getByRole('navigation', {name: '数据专题路径'}).count(), 1);
    await page.evaluate(() => scrollTo(0, 0)); await capture(`${size}-topic`);
    if (size === 'desktop') {
      const sidebar = page.getByRole('complementary', {name: '报告导航'});
      const bounds = await sidebar.boundingBox(), content = await page.locator('.report-reading').boundingBox();
      assert(bounds.x + bounds.width <= content.x + 1); assert.equal(bounds.y, 0);
      const nav = page.getByRole('navigation', {name: '快照报告章节'});
      assert.equal(await nav.locator('a').count(), 12); assert.equal(await nav.locator('[aria-current=page]').innerText(), '研究概览');
      for (const link of await nav.locator('a:not(.report-legacy-link)').all()) assert((await link.getAttribute('href')).includes('sources=rw%2Coa'));
      await page.evaluate(() => scrollTo(0, 1000)); assert.equal((await sidebar.boundingBox()).y, 0);
    } else {
      const trigger = page.getByRole('button', {name: '报告目录', exact: true});
      assert.equal(await page.getByRole('navigation', {name: '快照报告章节'}).count(), 0);
      await trigger.click(); const dialog = page.getByRole('dialog', {name: '报告目录'}); await dialog.waitFor();
      assert.equal(await trigger.getAttribute('aria-expanded'), 'true');
      assert.equal(await dialog.getByRole('navigation').locator('a').count(), 12);
      await capture(`${size}-drawer`);
      for (const direction of ['Tab', 'Shift+Tab']) for (let index = 0; index < 15; index++) {await page.keyboard.press(direction); assert(await dialog.evaluate(element => element.contains(document.activeElement)));}
      await page.keyboard.press('Escape'); await dialog.waitFor({state: 'hidden'}); await page.waitForFunction(() => document.querySelector('.report-mobile-header button')?.getAttribute('aria-expanded') === 'false'); assert(await trigger.evaluate(element => element === document.activeElement));
      await trigger.click(); await dialog.getByRole('link', {name: '时间与观察期', exact: true}).click();
      await page.locator('.topic-annual-comparison').waitFor(); assert.equal(await page.getByRole('dialog').count(), 0); assert(page.url().includes('sources=rw%2Coa'));
      await page.getByRole('button', {name: '报告目录', exact: true}).click(); assert.equal(await page.locator('.report-sidebar [aria-current=page]').innerText(), '时间与观察期');
      await page.getByRole('button', {name: '关闭报告目录'}).click(); await page.goBack(); await page.locator('.report-topic').waitFor();
    }
  });
  await check('all chapter destinations and legacy report remain available', async () => {
    await page.setViewportSize({width: 1440, height: 900});
    for (const section of ['overview', 'time', 'subjects', 'topics', 'concepts', 'reasons', 'geography', 'entities', 'publishing', 'citations', 'quality']) {
      await page.goto(base + `#/snapshot/${section}?sources=rw%2Coa`); await page.locator('.report-evidence').waitFor();
      const active = page.locator('.report-sidebar [aria-current=page]'); assert.equal(await active.count(), 1); assert((await active.getAttribute('href')).includes(`/snapshot/${section}?`));
    }
    await page.getByRole('link', {name: '当前 RW 报告（原版）', exact: true}).click(); await page.locator('.snapshot-app').waitFor({state: 'detached'}); await page.goBack(); await page.locator('.report-sidebar').waitFor();
  });
  await check('breakpoint changes close modal and do not leave scrolling locked', async () => {
    await page.setViewportSize({width: 390, height: 844}); await page.getByRole('button', {name: '报告目录', exact: true}).click();
    await page.setViewportSize({width: 1440, height: 900}); await page.locator('.report-sidebar').waitFor(); assert.equal(await page.locator('dialog[open]').count(), 0);
    assert.notEqual(await page.evaluate(() => getComputedStyle(document.documentElement).overflow), 'hidden');
    await page.setViewportSize({width: 768, height: 1024}); await page.getByRole('button', {name: '报告目录', exact: true}).waitFor(); assert.equal(await page.getByRole('navigation', {name: '快照报告章节'}).count(), 0);
  });
  await check('touch drawer opens, closes, navigates, and leaves data visible', async () => {
    const context = await browser.newContext({viewport: {width: 390, height: 844}, isMobile: true, hasTouch: true}); const mobile = await context.newPage();
    await mobile.goto(base + route); await mobile.locator('.report-research-figure').waitFor(); await mobile.getByRole('button', {name: '报告目录', exact: true}).tap();
    await mobile.getByRole('dialog').getByRole('link', {name: 'OpenAlex · Concepts 旧体系', exact: true}).tap(); await mobile.locator('.discipline-results').waitFor(); assert.equal(await mobile.getByRole('dialog').count(), 0); await context.close();
  });
} finally {
  checks.push({name: 'uncaught page errors', status: errors.length ? 'failed' : 'passed', errors});
  const result = {browser: browser.version(), checks}; await writeFile(`${output}/checks.json`, JSON.stringify(result, null, 2)); console.log(JSON.stringify(result, null, 2)); await browser.close();
}
if (checks.some(check => check.status === 'failed')) process.exitCode = 1;
