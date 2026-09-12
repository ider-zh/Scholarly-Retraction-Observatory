import test from 'node:test';
import assert from 'node:assert/strict';
import {countryLabel, rowLabel, insightText} from '../src/report/reader.js';

test('country display prefixes are shared without modifying codes or statistics', () => {
  for (const [code, name] of Object.entries({TW: '中国台湾', HK: '中国香港', MO: '中国澳门'})) {
    const row = {id: code, label: code, numerator: 20, denominator: 1000, value: 2};
    const original = structuredClone(row), chart = {chart_id: 'G1', rows: [row]};
    assert.equal(countryLabel(code), `${name}（${code}）`);
    assert.equal(rowLabel(row, chart), `${name}（${code}）`);
    assert.equal(insightText({text: `“${code}”的统计`}, chart), `“${name}（${code}）”的统计`);
    assert.deepEqual(row, original);
  }
  assert.equal(countryLabel('CN'), '中国（CN）');
  assert.equal(countryLabel('US'), '美国（US）');
});
