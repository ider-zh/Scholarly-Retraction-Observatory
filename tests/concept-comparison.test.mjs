import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {decodeExplorer} from '../src/report/explorerCodec.js';
import {resolveStudy} from '../src/report/discipline.js';
import {conceptComparison, comparisonSegments} from '../src/report/conceptComparison.js';

const data = decodeExplorer(JSON.parse(readFileSync('public/data/snapshot/fields.json')).discipline_explorer);

test('All 19 Concepts roots and every linked child retain exact published annual counts', () => {
  const before = JSON.stringify(data);
  for (const population of ['A1', 'C_D']) {
    const study = resolveStudy(data, ['rw', 'oa'], {taxonomy: 'concepts', population});
    const roots = conceptComparison(data, study);
    assert.equal(roots.length, 19);
    for (const root of roots) {
      const children = conceptComparison(data, study, root.id);
      assert.equal(children.length, study.taxonomy.nodes.filter(node => node.level === 1 && !node.navigation_only && !node.missing && node.parents.includes(root.id)).length);
      for (const item of [root, ...children]) {
        const published = study.taxonomy.nodes.find(node => node.id === item.id);
        assert.deepEqual(item.rows.map(row => row.count), published.counts[population].slice(1));
        assert.equal(item.rows[0].year, data.year_start);
        assert.equal(item.rows.at(-1).partial, true);
      }
    }
  }
  assert.equal(JSON.stringify(data), before);
});

test('Missing points break lines without turning into zero; other classifications are not substituted', () => {
  const rows = [{year: 2000, count: 0}, {year: 2001, count: null}, {year: 2002, count: 3}];
  assert.deepEqual(comparisonSegments(rows), [[rows[0]], [rows[2]]]);
  assert.deepEqual(conceptComparison(data, resolveStudy(data, ['rw'], {taxonomy: 'subjects'})), []);
  assert(resolveStudy(data, ['rw'], {taxonomy: 'concepts'}).error);
});

test('Every root and child proportion uses its own same-year publication denominator', () => {
  const before = JSON.stringify(data);
  for (const population of ['A1', 'C_D']) {
    const study = resolveStudy(data, ['rw', 'oa'], {taxonomy: 'concepts', population, metric: 'proportion'});
    const roots = conceptComparison(data, study);
    assert.equal(roots.length, 19);
    for (const root of roots) {
      for (const item of [root, ...conceptComparison(data, study, root.id)]) {
        const node = study.taxonomy.nodes.find(node => node.id === item.id);
        for (const [offset, row] of item.rows.entries()) {
          const numerator = node.counts[population][offset + 1], denominator = node.denominator[offset + 1];
          assert.equal(row.numerator, numerator);
          assert.equal(row.denominator, denominator);
          assert.equal(row.publication_denominator, denominator);
          assert.equal(row.value, denominator ? numerator / denominator * 100 : null);
          assert.equal(row.unit, 'percent');
          assert.equal(row.ranking_eligible, numerator >= 20 && denominator >= 1000);
        }
      }
    }
  }
  assert.equal(JSON.stringify(data), before);
});

test('Proportion paths break at missing denominators and small bases without discarding table values', () => {
  const rows = [
    {year: 2000, count: 20, value: 2, ranking_eligible: true},
    {year: 2001, count: 0, value: 0, ranking_eligible: false},
    {year: 2002, count: 5, value: 0.5, ranking_eligible: false},
    {year: 2003, count: 0, value: null, ranking_eligible: false},
    {year: 2004, count: 30, value: 3, ranking_eligible: true, partial: true}
  ];
  assert.deepEqual(comparisonSegments(rows, 'proportion'), [[rows[0]], [rows[4]]]);
  assert.deepEqual(comparisonSegments(rows), [rows]);
  assert.equal(rows[1].value, 0);
  assert.equal(rows[2].value, 0.5);
  assert.equal(rows[3].value, null);
});
