import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {decodeExplorer} from '../src/report/explorerCodec.js';
import {validateExplorer} from '../src/report/explorerSchema.js';
import {resolveStudy, distributionRows, studyAncestors, disciplineTimeChart} from '../src/report/discipline.js';

const manifest = JSON.parse(readFileSync('public/data/snapshot/manifest.json'));
const data = decodeExplorer(JSON.parse(readFileSync('public/data/snapshot/fields.json')).discipline_explorer);
const taxonomy = data.taxonomies.find(taxonomy => taxonomy.id === 'topics');

test('Topics has four Domain roots and complete Field/Subfield/Topic catalog', () => {
  assert.equal(taxonomy.levels.length, 4);
  assert.deepEqual(taxonomy.levels.map((_, level) => taxonomy.nodes.filter(node => node.level === level && !node.missing && !node.navigation_only).length), [4, 26, 252, 4516]);
  validateExplorer(data, manifest);
  const root = resolveStudy(data, ['oa'], {taxonomy: 'topics'});
  assert.equal(root.node.label, '全部大领域');
  assert(distributionRows(root).every(row => taxonomy.nodes.find(node => node.id === row.id).level === 0));
});

test('every Topic retains a full breadcrumb, sibling distribution and same-year publication denominator', () => {
  for (const node of taxonomy.nodes.filter(node => node.level === 3 && !node.missing)) {
    for (const population of ['A1', 'C_D']) {
      const study = resolveStudy(data, ['rw', 'oa'], {taxonomy: 'topics', node: node.id, population, metric: 'proportion'});
      assert(!study.error);
      assert.deepEqual(studyAncestors(study).map(node => node.level), [0, 1, 2]);
      for (const row of disciplineTimeChart(data, study).rows) {
        const index = row.year-data.year_start+1;
        assert.equal(row.denominator, node.denominator[index]);
        assert.equal(row.value, row.denominator ? node.counts[population][index]/row.denominator*100 : null);
      }
    }
  }
  const field = taxonomy.nodes.find(node => node.label === 'Medicine');
  const study = resolveStudy(data, ['oa'], {taxonomy: 'topics', node: field.id});
  assert(distributionRows(study).every(row => taxonomy.nodes.find(node => node.id === row.id).parents.includes(field.id)));
  const leaf = taxonomy.nodes.find(node => node.level === 3 && !node.missing);
  const leafStudy = resolveStudy(data, ['oa'], {taxonomy: 'topics', node: leaf.id});
  assert(distributionRows(leafStudy).every(row => taxonomy.nodes.find(node => node.id === row.id).parents.includes(leafStudy.parent)));
});

test('legacy Field/Subfield links stay valid and parent or partition corruption is rejected', () => {
  for (const node of taxonomy.nodes.filter(node => [1, 2].includes(node.level) && !node.navigation_only)) assert(!resolveStudy(data, ['oa'], {taxonomy: 'topics', node: node.id}).error);
  assert(!resolveStudy(data, ['oa'], {taxonomy: 'topics', node: 'subfield:unknown', parent: 'topics-unknown-parent'}).error);
  const changed = structuredClone(data), tree = changed.taxonomies.find(taxonomy => taxonomy.id === 'topics');
  const node = tree.nodes.find(node => node.level === 3 && node.counts.A1[0] > 0);
  node.counts.A1[0]--;
  const index = node.counts.A1.findIndex((value, index) => index > 0 && value > 0); node.counts.A1[index]--;
  assert.throws(() => validateExplorer(changed, manifest), /partition|parent/);
});
