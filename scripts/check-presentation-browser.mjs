import assert from 'node:assert/strict';
import {mkdir, readFile, writeFile} from 'node:fs/promises';

const {chromium} = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const base = process.env.REPORT_QA_URL || 'http://127.0.0.1:5173/';
const output = process.env.REPORT_QA_OUT || '/tmp/sro-presentation-review';
await mkdir(output, {recursive: true});
const browser = await chromium.launch({executablePath: process.env.CHROMIUM_PATH || undefined, args: ['--no-sandbox']});
const page = await browser.newPage({viewport: {width: 1440, height: 900}, reducedMotion: 'reduce'});
page.setDefaultTimeout(15000);
const errors = [], checks = [];
page.on('pageerror', error => errors.push(error.message));
async function capture(name) {
  await page.screenshot({path: `${output}/${name}.png`});
  assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), `${name}: horizontal overflow`);
  if (process.env.AXE_PATH) {
    await page.addScriptTag({content: await readFile(process.env.AXE_PATH, 'utf8')});
    const violations = await page.evaluate(async () => (await axe.run(document, {runOnly: {type: 'tag', values: ['wcag2a', 'wcag2aa', 'wcag21aa']}})).violations.map(item => ({id: item.id, targets: item.nodes.map(node => node.target)})));
    assert.deepEqual(violations, [], name);
  }
}
async function check(name, action) {
  try {await action();checks.push({name, status: 'passed'});console.log(`PASS: ${name}`);}
  catch (error) {checks.push({name, status: 'failed', error: error.stack});console.error(`FAIL: ${name}\n${error.stack}`);}
}
async function checkSlideBounds(name) {
  const slide = page.locator('.deck>.slide.is-active');
  await slide.evaluate(element => {element.scrollTop = 0;});
  const top = await slide.evaluate(element => {
    const bounds = element.getBoundingClientRect();
    return {start: bounds.top, end: bounds.bottom, heading: element.querySelector('h1,h2')?.getBoundingClientRect().top, kicker: element.querySelector('.kicker')?.getBoundingClientRect().top};
  });
  assert(top.heading >= top.start && top.heading < top.end, `${name}: heading clipped at slide start ${JSON.stringify(top)}`);
  assert(top.kicker >= top.start && top.kicker < top.end, `${name}: source label clipped at slide start ${JSON.stringify(top)}`);
  await capture(name);
  const end = await slide.evaluate(element => {
    element.scrollTop = element.scrollHeight;
    const bounds = element.getBoundingClientRect();
    const content = [...element.children].filter(child => !child.matches('.notes,.deck-footer'));
    const last = content.at(-1).getBoundingClientRect();
    const footer = element.querySelector('.deck-footer').getBoundingClientRect();
    const overlaps = [...element.querySelectorAll('.caution,.evidence-actions')].some(child => {
      const rect = child.getBoundingClientRect();
      return rect.bottom > footer.top + 1 && rect.top < footer.bottom - 1 && rect.top < bounds.bottom && rect.bottom > bounds.top;
    });
    return {start:bounds.top, end:bounds.bottom, lastTop:last.top, lastBottom:last.bottom, footerTop:footer.top, footerBottom:footer.bottom, overlaps, scrollable:element.scrollHeight > element.clientHeight + 1};
  });
  if (end.scrollable) await capture(`${name}-bottom`);
  assert(end.lastTop < end.end && end.lastBottom <= end.end + 1, `${name}: final explanation unreachable ${JSON.stringify(end)}`);
  assert(end.footerTop >= end.lastBottom - 1 && !end.overlaps, `${name}: footer overlaps report content ${JSON.stringify(end)}`);
}
try {
  await check('Three-entry index, v1, v2 sources and existing slice routes', async () => {
    await page.goto(base);
    assert.equal(await page.locator('.publication-list>a').count(), 3);
    const timestamps = await page.locator('.publication-list>a .publication-build time').evaluateAll(elements => elements.map(element => ({value:element.dateTime, label:element.textContent})));
    assert.equal(timestamps.length, 3);
    for (const timestamp of timestamps) {
      assert(Number.isFinite(Date.parse(timestamp.value)));
      assert(/\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} UTC\+8/.test(timestamp.label));
    }
    await page.getByRole('link', {name: /Report v1/}).click();
    await page.getByRole('heading', {name: '统计概览', exact: true}).waitFor();
    await page.getByRole('link', {name: '报告首页', exact: true}).click();
    await page.getByRole('link', {name: /Report v2/}).click();
    await page.locator('.report-scope-summary').waitFor();
    for (const sources of ['rw', 'oa', 'rw,oa']) {
      await page.goto(`${base}#/snapshot/overview?${new URLSearchParams({sources})}`);
      await page.locator('.report-scope-summary').waitFor();
      assert(!(await page.locator('[role=alert]').count()), sources);
      const scope = await page.locator('.report-scope-summary').innerText();
      assert(scope.includes(sources === 'rw' ? 'RW' : 'OpenAlex'));
    }
    await page.goto(`${base}#/snapshot/time/topic/annual-counts?sources=rw&slice=T1%2FB-retracted`);
    await page.locator('figure').first().waitFor();
    assert(!(await page.locator('[role=alert]').count()));
  });
  await check('Index and every slide: desktop, tablet, mobile + accessibility', async () => {
    const layoutErrors = [];
    for (const [device, width, height] of [['desktop',1440,900],['tablet',768,1024],['mobile',390,844]]) {
      await page.setViewportSize({width, height});
      await page.goto(base);
      await capture(`${device}-index`);
      await page.goto(`${base}presentation-v2/index.html`);
      const slideCount = await page.locator('.deck>.slide').count();
      assert.equal(slideCount, 15);
      for (let slide = 1; slide <= slideCount; slide++) {
        await page.selectOption('#slide-picker', String(slide));
        await page.waitForFunction(expected => document.querySelector('.deck>.slide.is-active')?.dataset.title === document.querySelectorAll('.deck>.slide')[expected-1]?.dataset.title, slide);
        try {await checkSlideBounds(`${device}-slide-${slide}`);}
        catch (error) {layoutErrors.push(error.message);}
        assert.equal(await page.locator('.deck>.slide:not([inert])').count(), 1);
      }
    }
    assert.deepEqual(layoutErrors, []);
  });
  await check('Keyboard navigation, direct link, evidence modal, export and return links', async () => {
    await page.setViewportSize({width:1440,height:900});
    await page.goto(`${base}presentation-v2/index.html#/6`);
    await page.locator('.deck>.slide.is-active [data-evidence]').waitFor();
    await page.keyboard.press('ArrowRight');
    await page.waitForFunction(() => document.querySelector('#slide-picker').value === '7');
    await page.locator('.deck>.slide.is-active [data-evidence]').focus();
    await page.keyboard.press('Enter');
    await page.locator('#evidence-dialog[open]').waitFor();
    assert.equal(await page.locator('#evidence-dialog tbody tr').count(), 27);
    const downloadPending = page.waitForEvent('download');
    await page.getByRole('button', {name:'导出图中聚合数据'}).click();
    const exported = JSON.parse(await readFile(await (await downloadPending).path(), 'utf8'));
    const time = JSON.parse(await readFile('public/data/snapshot/time.json', 'utf8'));
    assert.deepEqual(exported.chart, time.charts.find(chart => chart.slice_id === 'B-retracted'));
    await capture('desktop-evidence');
    await page.keyboard.press('Escape');
    assert.equal(await page.locator('#evidence-dialog[open]').count(), 0);
    await page.locator('.deck>.slide.is-active a').click();
    await page.locator('figure').first().waitFor();
    assert(page.url().includes('slice=T1%2FB-retracted'));
  });
  await check('Taxonomy summaries, Concepts trends, offline map and citation explanation', async () => {
    await page.goto(`${base}presentation-v2/index.html#/8`);
    const summary = await page.locator('.deck>.slide.is-active').innerText();
    for (const label of ['RW Subject', 'OpenAlex Topic', 'OpenAlex Concepts']) assert(summary.includes(label));
    assert.equal(await page.locator('.deck>.slide.is-active .taxonomy-panels>section').count(), 3);
    await page.selectOption('#slide-picker', '10');
    await page.waitForFunction(() => document.querySelectorAll('.deck>.slide.is-active .trend-panels svg').length === 3);
    assert.equal(await page.locator('.deck>.slide.is-active .partial-line').count(), 3);
    const trendButtons = page.locator('.deck>.slide.is-active [data-evidence]');
    for (let index = 0; index < 3; index++) {
      await trendButtons.nth(index).click();
      await page.locator('#evidence-dialog[open]').waitFor();
      assert.equal(await page.locator('#evidence-dialog tbody tr').count(), 27);
      await page.keyboard.press('Escape');
    }
    await page.selectOption('#slide-picker', '11');
    const distributionText = await page.locator('.deck>.slide.is-active').innerText();
    assert(distributionText.includes('%'));
    await page.locator('.deck>.slide.is-active [data-evidence]').click();
    await page.locator('#evidence-dialog[open]').waitFor();
    const distributionDownload = page.waitForEvent('download');
    await page.getByRole('button', {name:'导出图中聚合数据'}).click();
    const distribution = JSON.parse(await readFile(await (await distributionDownload).path(), 'utf8'));
    assert.equal(distribution.chart.scope.metric, 'proportion');
    assert.equal(distribution.chart.scope.taxonomy, 'concepts');
    assert(distribution.chart.rows.length > 6);
    for (const row of distribution.chart.rows) {
      assert.equal(row.denominator, row.publication_denominator);
      assert.equal(row.value, row.denominator ? row.numerator / row.denominator * 100 : null);
    }
    await capture('desktop-proportion-evidence');
    await page.keyboard.press('Escape');
    assert((await page.locator('.deck>.slide.is-active .evidence-actions a').getAttribute('href')).includes('metric=proportion'));
    await page.selectOption('#slide-picker', '12');
    await page.waitForFunction(() => document.querySelectorAll('.deck>.slide.is-active .trend-panels svg').length === 3);
    const proportionButtons = page.locator('.deck>.slide.is-active [data-evidence]');
    assert.equal(await proportionButtons.count(), 3);
    for (let index = 0; index < 3; index++) {
      await proportionButtons.nth(index).click();
      await page.locator('#evidence-dialog[open]').waitFor();
      assert.equal(await page.locator('#evidence-dialog tbody tr').count(), 27);
      const trendDownload = page.waitForEvent('download');
      await page.getByRole('button', {name:'导出图中聚合数据'}).click();
      const trend = JSON.parse(await readFile(await (await trendDownload).path(), 'utf8'));
      assert.equal(trend.chart.scope.metric, 'proportion');
      assert.equal(trend.chart.scope.date_basis, 'publication_year');
      assert.equal(trend.chart.rows.at(-1).partial, true);
      for (const row of trend.chart.rows) {
        assert.equal(row.denominator, row.publication_denominator);
        assert.equal(row.value, row.denominator ? row.numerator / row.denominator * 100 : null);
      }
      await page.keyboard.press('Escape');
    }
    for (const href of await page.locator('.deck>.slide.is-active .evidence-actions a').evaluateAll(anchors => anchors.map(anchor => anchor.href))) assert(href.includes('metric=proportion'));
    await page.selectOption('#slide-picker', '13');
    await page.locator('.deck>.slide.is-active .ppt-world-map').waitFor();
    assert.equal(await page.locator('.deck>.slide.is-active .ppt-world-map path').count(), 177);
    assert((await page.locator('.deck>.slide.is-active').innerText()).includes('无对应数值'));
    await page.selectOption('#slide-picker', '14');
    await page.locator('.deck>.slide.is-active .ppt-world-map').waitFor();
    assert.equal(await page.locator('.deck>.slide.is-active .ppt-world-map path').count(), 177);
    await page.locator('.deck>.slide.is-active [data-evidence]').click();
    await page.locator('#evidence-dialog[open]').waitFor();
    const countryDownload = page.waitForEvent('download');
    await page.getByRole('button', {name:'导出图中聚合数据'}).click();
    const country = JSON.parse(await readFile(await (await countryDownload).path(), 'utf8'));
    assert.equal(country.chart.metric_id, 'proportion');
    for (const row of country.chart.rows) assert.equal(row.value, row.denominator ? row.numerator / row.denominator * 100 : null);
    await capture('desktop-country-proportion-evidence');
    await page.keyboard.press('Escape');
    assert((await page.locator('.deck>.slide.is-active .evidence-actions a').getAttribute('href')).includes('metric=proportion'));
    await page.selectOption('#slide-picker', '15');
    await page.locator('.deck>.slide.is-active .citation-explainer').waitFor();
    const citation = await page.locator('.deck>.slide.is-active').innerText();
    for (const label of ['中位数', '至少观察到一次引用', '累计窗口', '不是“第 5 年新增 9 次”']) assert(citation.includes(label), label);
    await page.locator('.deck>.slide.is-active [data-evidence]').click();
    await page.locator('#evidence-dialog[open]').waitFor();
    assert.equal(await page.locator('#evidence-dialog tbody tr').count(), 3);
    assert((await page.locator('#evidence-dialog').innerText()).includes('中位数'));
    try {await capture('desktop-citation-evidence');}
    finally {await page.keyboard.press('Escape');}
  });
  await check('Presenter popup and local-only presentation requests', async () => {
    const remote = [];
    page.on('request', request => {if (!request.url().startsWith(base) && /^https?:/.test(request.url())) remote.push(request.url());});
    await page.goto(`${base}presentation-v2/index.html#/1`);
    const popupPending = page.waitForEvent('popup');
    await page.getByRole('button', {name:'演讲者', exact:true}).click();
    const popup = await popupPending;
    await popup.waitForLoadState();
    assert((await popup.locator('iframe').count()) >= 2);
    await popup.screenshot({path:`${output}/presenter.png`});
    await popup.close();
    assert.deepEqual(remote, []);
  });
  await check('Every figure links to its published report topic', async () => {
    await page.goto(`${base}presentation-v2/index.html`);
    const links = await page.locator('.deck .evidence-actions a').evaluateAll(anchors => anchors.map(anchor => anchor.href));
    assert(links.length >= 10);
    for (const href of new Set(links)) {
      await page.goto(href);
      await page.locator('figure').first().waitFor();
      assert.equal(await page.locator('[role=alert]').count(), 0, href);
    }
  });
  assert.deepEqual(errors, []);
} finally {
  await browser.close();
  await writeFile(`${output}/checks.json`, JSON.stringify({base, checks, errors}, null, 2));
  console.log(JSON.stringify({checks, errors}, null, 2));
}
assert(checks.every(check => check.status === 'passed'));
