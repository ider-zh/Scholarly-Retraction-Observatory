import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {countryStudy, validateCountryExplorer} from '../src/report/country.js';

test('Grouped country release preserves Taiwan deep links as China and rejects mixed provenance', async () => {
  const manifest = JSON.parse(await readFile('public/data/snapshot/manifest.json', 'utf8'));
  const {country_explorer: explorer} = JSON.parse(await readFile('public/data/snapshot/geography.json', 'utf8'));
  assert.equal(explorer.country_grouping_version, 'country-grouping-cn-includes-tw-v1');
  assert.equal(validateCountryExplorer(explorer, manifest), explorer);
  const selected = countryStudy(explorer, ['oa'], {node: 'TW', metric: 'proportion'});
  assert.equal(selected.node.id, 'CN');
  assert(!selected.ranked.some(row => row.id === 'TW'));
  assert.throws(() => validateCountryExplorer({...explorer, country_grouping_version: undefined}, manifest), /grouping provenance/);
  assert.throws(() => validateCountryExplorer({...explorer, nodes: [...explorer.nodes, {...explorer.nodes[0], id: 'TW'}]}, manifest), /Unmerged Taiwan/);
});
