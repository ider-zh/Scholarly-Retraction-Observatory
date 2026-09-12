import assert from 'node:assert/strict';
import {mkdir, readFile, writeFile} from 'node:fs/promises';

const {chromium} = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const base = process.env.REPORT_QA_URL || 'http://127.0.0.1:5186/';
const output = process.env.REPORT_QA_OUT || '/tmp/sro-screening-examples/after';
const manifest = JSON.parse(await readFile('public/data/snapshot/manifest.json', 'utf8'));
const overview = JSON.parse(await readFile('public/data/snapshot/overview.json', 'utf8'));
const screening = overview.charts.find(chart => chart.chart_id === 'screening');
const broad = manifest.role_policy_version === 'original-first-independent-notices-v2';
await mkdir(output, {recursive: true});
const browser = await chromium.launch({executablePath: process.env.CHROMIUM_PATH, args: ['--no-sandbox']});
const errors = [], checks = [];
try {
  const page = await browser.newPage({reducedMotion: 'reduce'});
  page.on('pageerror', error => errors.push(error.message));
  for (const [device, width, height] of [['desktop',1440,900],['tablet',768,1024],['mobile',390,844]]) {
    await page.setViewportSize({width, height});
    await page.goto(`${base}#/snapshot/overview?sources=rw%2Coa`);
    await page.reload();
    const examples = page.locator('.screening-examples');
    await examples.locator('.screening-example-group').first().waitFor();
    assert.equal(await examples.locator('.screening-example-group').count(), 5);
    assert.equal(await examples.locator('li').count(), 10);
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.screenshot({path: `${output}/${device}-overview.png`});
    if (broad) {
      assert.match(await page.locator('.report-scope-summary').innerText(), /宽口径候选/);
      assert.match(await examples.locator('h2').innerText(), /现在如何处理/);
      const retained = screening.rows.find(row => row.id === 'retained_A1');
      const mark = page.locator('[data-screening-row="retained_A1"]');
      assert((await mark.innerText()).includes(retained.numerator.toLocaleString('zh-CN')));
      await mark.focus(); await mark.press('Enter');
      assert.match(await page.locator('.report-bar-detail').innerText(), /已锁定/);
      assert.match(await page.locator('.report-bar-detail').innerText(), /身份不确定/);
      await mark.press('Escape');
      await page.getByText('查看本图数据表与导出', {exact: true}).click();
      const pending = page.waitForEvent('download');
      await page.getByRole('button', {name: '导出本切片聚合 CSV', exact: true}).click();
      const csv = await readFile(await (await pending).path(), 'utf8');
      for (const value of [manifest.release_id, manifest.role_policy_version, String(retained.numerator), String(retained.denominator)]) assert(csv.includes(value));
    }
    for (const group of await examples.locator('.screening-example-group').all()) {
      const shouldOpen = (await group.locator('summary').innerText()).includes('有通知身份证据');
      if ((await group.getAttribute('open') !== null) !== shouldOpen) await group.locator('summary').click();
    }
    await examples.scrollIntoViewIfNeeded();
    await page.screenshot({path: `${output}/${device}.png`});
    await examples.screenshot({path: `${output}/${device}-section.png`});
    assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
    const review = examples.locator('.screening-example-group').filter({hasText: '综述类型：范围排除'});
    await review.locator('summary').click();
    assert(await review.getByText('PubMed：原论文及撤稿通知', {exact: true}).isVisible());
    const suspected = examples.locator('.screening-example-group').filter({hasText: '标题疑似通知：需要保留'});
    await suspected.locator('summary').click();
    assert(await suspected.getByRole('link', {name: 'Retracted: A DNN based LSTM Model for Predicting Future Energy Consumption', exact: true}).isVisible());
    await suspected.screenshot({path: `${output}/${device}-uncertain.png`});
    if (process.env.AXE_PATH) {
      await page.addScriptTag({content: await readFile(process.env.AXE_PATH, 'utf8')});
      const violations = await page.evaluate(async () => (await axe.run('.screening-examples', {runOnly: {type: 'tag', values: ['wcag2a','wcag2aa','wcag21aa']}})).violations);
      assert.deepEqual(violations, []);
    }
    checks.push(`${device}: examples, boundaries, accordion, accessibility and width`);
  }
  for (const sources of ['rw','oa','rw,oa']) {
    await page.goto(`${base}#/snapshot/overview?${new URLSearchParams({sources})}`);
    await page.locator('.report-evidence,.report-unavailable').first().waitFor();
    if (sources === 'rw') assert.equal(await page.locator('.screening-examples').count(), 0);
    else await page.locator('.screening-example-group').first().waitFor();
  }
  await page.goto(`${base}#/snapshot/overview?sources=oa&slice=screening%2FA0-screening`);
  await page.locator('.screening-example-group').first().waitFor();
  await page.goto(`${base}#/snapshot/overview?sources=oa&slice=work-types%2FA0-work-types`);
  await page.locator('.report-evidence[data-chart-id="work-types"]').waitFor();
  assert.equal(await page.locator('.screening-examples').count(), 0);
  checks.push('RW/OA/joint sources and screening/work-type deep links');
  await page.goto(`${base}#/snapshot/overview?sources=oa`);
  await page.locator('.screening-example-group').first().waitFor();
  await page.getByText('如何抽样、如何复核？', {exact: true}).click();
  const download = page.waitForEvent('download');
  await page.getByRole('link', {name: '下载这 10 条案例及抽样来源', exact: true}).click();
  assert.deepEqual(JSON.parse(await readFile(await (await download).path(), 'utf8')), JSON.parse(await readFile('public/data/screening-examples.json', 'utf8')));
  checks.push('Sample export exactly matches the verified sidecar');
  await page.route('**/data/screening-examples.json', route => route.fulfill({status:200, contentType:'application/json', body:'{}'}));
  await page.goto(`${base}#/snapshot/overview?sources=oa`);
  await page.reload();
  await page.locator('.screening-examples').getByText(/未显示旧版或替代案例/).waitFor();
  assert.equal(await page.locator('.screening-example-group').count(), 0);
  assert(await page.locator('.report-screening-plot').isVisible());
  checks.push('Tampered sample rejected without replacing the main figure');
  assert.deepEqual(errors, []);
  await writeFile(`${output}/checks.json`, JSON.stringify({checks, errors}, null, 2));
  console.log(`PASS: ${checks.length} groups, no page errors`);
} finally {await browser.close();}
