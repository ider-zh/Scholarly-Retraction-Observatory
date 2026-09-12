import assert from 'node:assert/strict';
import {mkdir, readFile, writeFile} from 'node:fs/promises';

const {chromium} = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const output = process.env.REPORT_QA_OUT || '/tmp/sro-range-review';
const base = process.env.REPORT_QA_URL || 'http://192.168.1.229:5173/';
await mkdir(output, {recursive: true});
const browser = await chromium.launch({executablePath: process.env.CHROMIUM_PATH, args: ['--no-sandbox']});
const page = await browser.newPage(), errors = [], checks = [];
page.on('pageerror', error => errors.push(error.message));
try {
  for (const [name, width, height] of [['desktop', 1440, 900], ['tablet', 768, 1024], ['mobile', 390, 844]]) {
    await page.setViewportSize({width, height});
    await page.goto(base+'#/snapshot/time?sources=rw&slice=T1%2FB-retracted');
    const range = page.locator('.snapshot-chart-range'); await range.waitFor();
    const start = range.getByRole('slider', {name: '显示起点'}), end = range.getByRole('slider', {name: '显示终点'});
    assert.equal(await range.locator('.rc-slider').count(), 1);
    const original = await page.locator('[data-chart-point]').count();
    await start.focus(); await start.press('ArrowRight'); await end.focus(); await end.press('ArrowLeft');
    assert.equal(await page.locator('[data-chart-point]').count(), original - 2);
    assert.equal(await start.getAttribute('aria-valuetext'), '2001');
    assert.equal(await end.getAttribute('aria-valuetext'), '2025');
    await start.press('End'); assert.equal(await start.getAttribute('aria-valuenow'), await end.getAttribute('aria-valuenow'));
    assert.equal(await page.locator('[data-chart-point]').count(), 1);
    await range.getByRole('button').click(); assert.equal(await page.locator('[data-chart-point]').count(), original);
    await range.scrollIntoViewIfNeeded();
    const handle = await start.boundingBox(), rail = await range.locator('.rc-slider').boundingBox();
    await page.mouse.move(handle.x+handle.width/2, handle.y+handle.height/2); await page.mouse.down();
    await page.mouse.move(rail.x+rail.width/3, handle.y+handle.height/2, {steps: 10}); await page.mouse.up();
    assert(Number(await start.getAttribute('aria-valuenow')) > 0);
    await range.getByRole('button').click();
    await range.screenshot({path: `${output}/after-${name}.png`});
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
    if (process.env.AXE_PATH) {
      await page.addScriptTag({content: await readFile(process.env.AXE_PATH, 'utf8')});
      assert.deepEqual(await page.evaluate(async () => (await axe.run(document, {runOnly: {type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21aa']}})).violations.map(item => item.id)), []);
    }
    checks.push({name, keyboard: true, drag: true, reset: true, singlePoint: true});
  }
  await page.getByText('查看完整聚合数据与导出', {exact: true}).click();
  async function download() {const pending = page.waitForEvent('download'); await page.getByRole('button', {name: '导出本切片聚合 CSV'}).click(); return readFile(await (await pending).path(), 'utf8');}
  const full = await download();
  await page.getByRole('slider', {name: '显示起点'}).press('ArrowRight');
  assert.equal(await download(), full); checks.push({exportUnchanged: true});
  const touchContext = await browser.newContext({viewport: {width: 390, height: 844}, hasTouch: true, isMobile: true});
  const touchPage = await touchContext.newPage();
  await touchPage.goto(base+'#/snapshot/time?sources=rw&slice=T1%2FB-retracted');
  const touchStart = touchPage.getByRole('slider', {name: '显示起点'});
  await touchStart.waitFor(); await touchStart.scrollIntoViewIfNeeded();
  const touchHandle = await touchStart.boundingBox(), touchRail = await touchPage.locator('.rc-slider').boundingBox();
  const client = await touchContext.newCDPSession(touchPage);
  const touchPoint = {x: touchHandle.x+touchHandle.width/2, y: touchHandle.y+touchHandle.height/2};
  await client.send('Input.dispatchTouchEvent', {type: 'touchStart', touchPoints: [touchPoint]});
  await client.send('Input.dispatchTouchEvent', {type: 'touchMove', touchPoints: [{...touchPoint, x: touchRail.x+touchRail.width/3}]});
  await client.send('Input.dispatchTouchEvent', {type: 'touchEnd', touchPoints: []});
  assert(Number(await touchStart.getAttribute('aria-valuenow')) > 0);
  checks.push({touchDrag: true}); await touchContext.close();
  await page.goto(base+'#/snapshot/citations?sources=oa&slice=C1%2FA1-core-article');
  await page.getByRole('slider', {name: '显示起点'}).waitFor();
  assert.match(await page.locator('.snapshot-range-heading output').innerText(), /引用/);
  checks.push({nonYearLabels: true}); assert.deepEqual(errors, []);
} finally {
  await writeFile(output+'/checks.json', JSON.stringify({checks, errors}, null, 2));
  await browser.close();
}
console.log(checks);
