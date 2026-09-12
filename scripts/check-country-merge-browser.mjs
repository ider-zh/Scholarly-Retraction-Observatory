import assert from 'node:assert/strict';
import {mkdir, readFile, writeFile} from 'node:fs/promises';

const {chromium} = await import(process.env.PLAYWRIGHT_MODULE || 'playwright');
const base = process.env.REPORT_QA_URL || 'http://127.0.0.1:5186/';
const output = process.env.REPORT_QA_OUT || '/tmp/sro-country-merge-review';
await mkdir(output, {recursive: true});
const browser = await chromium.launch({executablePath: process.env.CHROMIUM_PATH || undefined, args: ['--no-sandbox']});
const page = await browser.newPage({reducedMotion: 'reduce'});
const errors = [], checks = [];
page.on('pageerror', error => errors.push(error.message));
async function comparePaths(selector, description, titleAttribute) {
  const china = page.locator(`${selector} [data-country="CN"]`);
  const taiwan = page.locator(`${selector} [data-country="TW"]`);
  await china.waitFor({state: 'visible'});
  assert.equal(await china.getAttribute('fill'), await taiwan.getAttribute('fill'), `${description}: fills`);
  const chinaTitle = titleAttribute ? await china.getAttribute(titleAttribute) : await china.locator('title').textContent();
  const taiwanTitle = titleAttribute ? await taiwan.getAttribute(titleAttribute) : await taiwan.locator('title').textContent();
  assert.equal(chinaTitle, taiwanTitle, `${description}: values and label`);
  assert.match(chinaTitle, /中国/);
  checks.push({description, fill: await china.getAttribute('fill'), label: chinaTitle});
}
try {
  for (const [device, width, height] of [['desktop',1440,900], ['tablet',768,1024], ['mobile',390,844]]) {
    await page.setViewportSize({width, height});
    for (const slide of [13,14]) {
      await page.goto(`${base}presentation-v2/index.html#/${slide}`);
      await page.waitForFunction(() => document.querySelectorAll('.deck>.slide.is-active').length === 1);
      await comparePaths('.deck>.slide.is-active .ppt-world-map', `${device} slide ${slide}`);
      await page.screenshot({path: `${output}/${device}-slide-${slide}.png`});
      assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
      if (device === 'desktop') {
        await page.locator('.deck>.slide.is-active [data-evidence]').click();
        const downloading = page.waitForEvent('download');
        await page.getByRole('button', {name: '导出图中聚合数据'}).click();
        const exported = JSON.parse(await readFile(await (await downloading).path(), 'utf8'));
        assert(exported.chart.rows.some(row => row.id === 'CN'));
        assert(!exported.chart.rows.some(row => row.id === 'TW'));
        await writeFile(`${output}/slide-${slide}-export.json`, JSON.stringify(exported, null, 2));
        await page.keyboard.press('Escape');
      }
    }
    for (const metric of ['count','proportion']) {
      await page.goto(`${base}#/snapshot/geography/topic/countries?sources=oa&population=A1&metric=${metric}&node=TW`);
      await comparePaths('.country-map', `${device} website ${metric}`, 'aria-label');
      assert.equal(await page.locator('option[value="TW"]').count(), 0);
      const taiwan = page.locator('.country-map [data-country="TW"]');
      await taiwan.focus();
      await taiwan.press('Enter');
      await page.waitForURL(/node=CN/);
      assert.equal(await taiwan.getAttribute('aria-pressed'), 'true');
      await page.screenshot({path: `${output}/${device}-website-${metric}.png`, fullPage: true});
      assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1));
      if (device === 'desktop') {
        const distributionDetails = page.locator('details').filter({has: page.getByText('查看国家分布数据与导出', {exact: true})});
        if (!(await distributionDetails.getAttribute('open'))) {
          await distributionDetails.evaluate(element => {element.open = true;});
        }
        const downloading = page.waitForEvent('download');
        await page.getByRole('button', {name: '导出国家分布聚合 CSV', exact: true}).click();
        const csv = await readFile(await (await downloading).path(), 'utf8');
        assert(csv.includes('"country_grouping_version"'));
        assert(csv.includes('"method"'));
        assert(csv.includes('"country-grouping-cn-includes-tw-v1"'));
        assert(csv.includes('"CN"'));
        assert(!csv.includes('"TW"'));
        await writeFile(`${output}/website-${metric}.csv`, csv);
      }
    }
  }
  assert.deepEqual(errors, []);
  await writeFile(`${output}/checks.json`, JSON.stringify({base, checks, errors}, null, 2));
  console.log(`PASS: ${checks.length} map states, matching CN/TW values and fills, selection canonicalization, no page errors`);
} finally {
  await browser.close();
}
