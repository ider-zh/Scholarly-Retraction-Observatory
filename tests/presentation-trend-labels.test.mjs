import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {conceptTrendPlot} from '../scripts/presentation-figures.mjs';

test('Trend annotations bind to eligible complete-year peaks and a shared comparison year', async () => {
  const html = await readFile('public/presentation-v2/index.html', 'utf8');
  const evidence = JSON.parse(html.match(/id="presentation-evidence">([\s\S]*?)<\/script>/)[1]);
  for (const metric of ['count', 'proportion']) {
    const charts = evidence.filter(entry => entry.chart.chart_id === 'discipline-time' && entry.chart.metric_id === metric).map(entry => entry.chart);
    const original = structuredClone(charts);
    const rendered = conceptTrendPlot(charts);
    for (const chart of charts) {
      const peak = chart.rows.filter(row => !row.partial && Number.isFinite(row.value) && (metric === 'count' || row.ranking_eligible)).sort((left, right) => right.value-left.value)[0];
      assert(rendered.includes(`data-year="${peak.year}" data-value="${peak.value}"`));
    }
    assert.equal((rendered.match(/2025 年发表队列/g) || []).length, 3);
    assert.equal((rendered.match(/n \/ N =/g) || []).length, metric === 'proportion' ? 3 : 0);
    assert.deepEqual(charts, original);
  }
});

test('Missing values, partial peaks and small bases cannot become trend key values', () => {
  const chart = {metric_id:'proportion', scope:{node_label:'Medicine'}, rows:[
    {year:2023,value:null,ranking_eligible:true},
    {year:2024,value:2,ranking_eligible:false},
    {year:2025,value:1,ranking_eligible:true,numerator:20,denominator:2000},
    {year:2026,value:9,ranking_eligible:true,partial:true},
  ]};
  const rendered = conceptTrendPlot([chart]);
  assert(rendered.includes('data-year="2025" data-value="1"'));
  assert(!rendered.includes('data-value="9"'));
  assert(!rendered.includes('data-value="2"'));
  assert(!/NaN|Infinity/.test(rendered));
  const unavailable = conceptTrendPlot([{...chart, rows:chart.rows.slice(0,2)}]);
  assert(unavailable.includes('无共同可比较的完整发表年份'));
  assert(!unavailable.includes('class="trend-annotation"'));
});
