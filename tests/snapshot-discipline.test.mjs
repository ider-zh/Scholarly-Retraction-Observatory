import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {validateChunk, decodeChartRows} from '../src/report/schema.js';
import {validateExplorer} from '../src/report/explorerSchema.js';
import {resolveStudy, availableStudies, disciplineCell, distributionRows, disciplineTimeChart, disciplineHref} from '../src/report/discipline.js';

const manifest = JSON.parse(readFileSync('public/data/snapshot/manifest.json'));
const fields = JSON.parse(readFileSync('public/data/snapshot/fields.json'));
const data = validateChunk(fields, manifest, 'fields').discipline_explorer;

test('all three classification systems have complete indexes without Top N truncation', () => {
  for (const [identifier, roots, children] of [['subjects', 7, 130], ['topics', data.taxonomies[1].levels.length === 4 ? 4 : 26, data.taxonomies[1].levels.length === 4 ? 26 : 252], ['concepts', 19, 284]]) {
    const taxonomy = data.taxonomies.find(taxonomy => taxonomy.id === identifier);
    assert.equal(taxonomy.nodes.filter(node => node.level === 0 && !node.missing && !node.navigation_only).length, roots);
    assert.equal(taxonomy.nodes.filter(node => node.level === 1 && !node.missing).length, children);
  }
});

test('all nodes and populations reproduce count, share and rate series with original denominators', () => {
  for (const taxonomy of data.taxonomies) for (const population of taxonomy.populations) for (const node of taxonomy.nodes.filter(node => !node.navigation_only)) {
    const metrics = taxonomy.denominator ? ['count', 'share', 'rate'] : ['count', 'share'];
    for (const metric of metrics) {
      const study = resolveStudy(data, ['rw', 'oa'], {taxonomy: taxonomy.id, population, node: node.id, metric});
      assert(!study.error);
      for (let index = 0; index < node.counts[population].length; index++) {
        const cell = disciplineCell(taxonomy, node, population, metric, index);
        assert.equal(cell.numerator, node.counts[population][index]);
        assert.equal(cell.value, metric === 'count' ? cell.numerator : cell.denominator ? cell.numerator / cell.denominator * (metric === 'rate' ? 10000 : 100) : null);
      }
      const time = disciplineTimeChart(data, study);
      assert.equal(time.rows.length, data.year_end-data.year_start+1);
      assert(time.rows.at(-1).partial);
      assert(time.rows.reduce((total, row) => total+row.numerator, 0) <= node.counts[population][0]);
    }
  }
});

test('source, classification, parent and metric deep links fail closed', () => {
  assert.deepEqual(availableStudies(data, ['rw']).map(study => study.taxonomy.id), ['subjects']);
  assert.equal(availableStudies(data, ['oa']).length, 2);
  for (const selection of [{taxonomy: 'subjects', metric: 'rate'}, {taxonomy: 'topics', population: 'B'}, {taxonomy: 'concepts', node: 'missing'}, {taxonomy: 'topics', metric: 'toString'}]) assert(resolveStudy(data, ['rw', 'oa'], selection).error);
  assert(resolveStudy(data, ['rw'], {taxonomy: 'concepts'}).error);
  const child = data.taxonomies[2].nodes.find(node => node.parents.length > 1);
  const first = resolveStudy(data, ['rw', 'oa'], {taxonomy: 'concepts', node: child.id, parent: child.parents[0]});
  const second = resolveStudy(data, ['rw', 'oa'], {taxonomy: 'concepts', node: child.id, parent: child.parents[1]});
  assert.equal(first.node, second.node);
  assert.equal(new URLSearchParams(disciplineHref(['oa'], {taxonomy: 'concepts', node: child.id, parent: child.parents[1], metric: 'rate'}).split('?')[1]).get('parent'), child.parents[1]);
  assert(resolveStudy(data, ['oa'], {taxonomy: 'concepts', node: child.id, parent: 'bad-parent'}).error);
});

test('filtering distribution does not rebase rate or sample coverage', () => {
  const study = resolveStudy(data, ['oa'], {taxonomy: 'topics', metric: 'rate'});
  for (const row of distributionRows(study).slice(0, 5)) {
    const node = study.taxonomy.nodes.find(node => node.id === row.id);
    assert.equal(row.denominator, node.denominator[0]);
  }
});

test('invalid graph, numerator, time vector and mixed release cannot be published', () => {
  for (const mutate of [value => {value.release_id = 'stale';}, value => {value.taxonomies[1].nodes[0].counts.A1[0] = Number.MAX_SAFE_INTEGER;}, value => {value.taxonomies[1].nodes.find(node => node.level === 1).parents = ['missing'];}, value => {value.taxonomies[0].counts.B.pop();}, value => {value.taxonomies[0].denominator = [1];}]) {
    const changed = structuredClone(data); mutate(changed); assert.throws(() => validateExplorer(changed, manifest));
  }
});

test('columnar aggregate rows decode losslessly and cannot hide raw/prototype fields', () => {
  assert.deepEqual(decodeChartRows({row_columns: ['id', 'value'], row_values: [['zero', 0], ['missing', null]]}).rows, [{id: 'zero', value: 0}, {id: 'missing', value: null}]);
  for (const column of ['papers', 'authorships', '__proto__', 'constructor']) assert.throws(() => decodeChartRows({row_columns: [column], row_values: [[1]]}));
  assert.throws(() => decodeChartRows({row_columns: ['id', 'id'], row_values: [['a', 'a']]}));
  assert.throws(() => decodeChartRows({row_columns: ['id'], row_values: [[]]}));
  assert.throws(() => decodeChartRows({rows: [], row_columns: ['id'], row_values: [['a']]}));
});
