import test from 'node:test';
import assert from 'node:assert/strict';
import {number, selectChart, chartName, variantName, rowLabel, chartMethod, insightText} from '../src/report/reader.js';

test('physical counts display without forced decimals; fractions retain precision', () => {
  assert.equal(number(50331), '50,331');
  assert.equal(number(0), '0');
  assert.equal(number(.5), '0.5');
  assert.equal(number(null), '未计算 / 缺失');
});

test('one analysis selected by default or exact shareable identifier', () => {
  const charts = [{chart_id: 'screening', slice_id: 'A0'}, {chart_id: 'population-accounting', slice_id: 'all'}];
  assert.equal(selectChart(charts), charts[1]);
  assert.equal(selectChart(charts, 'screening/A0'), charts[0]);
  assert.equal(selectChart(charts, 'screening/unknown'), null);
  assert.equal(selectChart([]), null);
});

test('reader labels explain separate classification and geography methods', () => {
  const chart = {chart_id: 'concepts', population_key: 'C', scope: {taxonomy: 'oa_concepts_legacy', level: 0}, slice_id: 'C-concepts-level-0'};
  assert.match(chartName(chart), /旧学科分类/);
  assert.match(variantName(chart), /旧分类第 0 级/);
  assert.match(chartMethod(chart).join(''), /停止更新/);
  assert.equal(rowLabel({id: 'CN'}, {chart_id: 'G1'}), '中国（CN）');
  assert.match(chartMethod({chart_id: 'G1'}).join(''), /不推测国籍/);
  assert.equal(insightText({text: '“CN”为 3 篇'}, {chart_id: 'G1', rows: [{id: 'CN'}]}), '“中国（CN）”为 3 篇');
});
