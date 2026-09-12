import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {countryStudy} from '../src/report/country.js';
import {countryProportionEvidence, countryProportionPlot} from '../scripts/presentation-country-proportion.mjs';
import {countryMapPlot} from '../scripts/presentation-figures.mjs';

const geography = JSON.parse(await readFile('public/data/snapshot/geography.json', 'utf8'));

test('Country presentation proportion preserves the published country cohort projection and scope', () => {
  const explorer = geography.country_explorer;
  const chart = countryProportionEvidence(explorer);
  assert.deepEqual(chart.rows, countryStudy(explorer, ['oa'], {population: 'A1', metric: 'proportion'}).ranked);
  assert.deepEqual(chart.scope, {population: 'A1', metric: 'proportion', work_types: explorer.work_types || ['article'], publication_year_range: [2000, 2026], attribution: 'institution_country'});
  assert.equal(chart.release_id, explorer.release_id);
  assert.equal(chart.metric_observation_cutoff, explorer.oa_cutoff);
  assert(chart.limitations.includes(explorer.method));
  assert(chart.limitations.some(text => text.includes('n≥20') && text.includes('N≥1,000')));
  assert(chart.rows.some(row => row.value === 0 && !row.ranking_eligible));
});

test('Country proportion map separates small bases and missing rates and ranks eligible countries only', () => {
  const rows = [
    {id: 'CN', value: 0.1, numerator: 100, denominator: 100000, ranking_eligible: true},
    {id: 'GB', value: 2, numerator: 20, denominator: 1000, ranking_eligible: true},
    {id: 'US', value: 50, numerator: 1, denominator: 2, ranking_eligible: false},
    {id: 'FR', value: 0, numerator: 0, denominator: 10000, ranking_eligible: false},
    {id: 'DE', value: null, numerator: 0, denominator: 0, ranking_eligible: false}
  ];
  const world = {viewBox: '0 0 100 100', regions: [...rows.map(row => row.id), 'ZZ'].map(code => ({code, name: code, path: 'M0,0L1,1Z'}))};
  const html = countryProportionPlot(world, {rows});
  assert.equal((html.match(/<path /g) || []).length, world.regions.length);
  assert.match(html, /data-country="US" data-status="small" fill="url\(#ppt-country-proportion-small\)"/);
  assert.match(html, /data-country="FR" data-status="small"/);
  assert.match(html, /法国：0\.0000%；n=0 \/ N=10,000/);
  assert.match(html, /data-country="DE" data-status="missing"/);
  assert.match(html, /data-country="ZZ" data-status="missing"/);
  assert.deepEqual([...html.matchAll(/data-ranked-country="([^"]+)"/g)].map(match => match[1]), ['GB', 'CN']);
  assert.match(html, /\(0, 0\.5000\]%/);
  assert.match(html, /\(1\.5000, 2\.0000\]%/);
  assert.match(html, /n=20<br\/>N=1,000/);
  assert.doesNotMatch(countryProportionPlot(world, {rows: rows.slice(2)}), /\(0, 0\.0000\]%/);
});

test('Country evidence keeps an undefined denominator result null rather than writing zero', () => {
  const explorer = {...geography.country_explorer, nodes: [{id: 'US', counts: {A1: [0]}, denominator: [0]}]};
  assert.equal(countryProportionEvidence(explorer).rows[0].value, null);
  assert.throws(() => countryProportionEvidence(null), /尚未发布/);
});

test('both presentation maps color Taiwan geometry with the same deduplicated China row', () => {
  const world = {viewBox: '0 0 10 10', regions: ['CN', 'TW', 'US'].map(code => ({code, name: code, path: 'M0,0L1,1Z'}))};
  const chart = {rows: [{id: 'CN', value: 2, numerator: 20, denominator: 1000, ranking_eligible: true}]};
  const original = structuredClone(chart);
  for (const plot of [countryMapPlot, countryProportionPlot]) {
    const html = plot(world, chart);
    const china = html.match(/data-country="CN"[^>]*fill="([^"]+)"[^>]*><title>([^<]+)<\/title>/);
    const taiwan = html.match(/data-country="TW"[^>]*fill="([^"]+)"[^>]*><title>([^<]+)<\/title>/);
    assert(china && taiwan);
    assert.equal(taiwan[1], china[1]);
    assert.equal(taiwan[2], china[2]);
    assert.match(taiwan[2], /中国/);
    assert.match(html, /同一论文在两地均有关联时，合并后仅计一次/);
    assert.equal((html.match(/<path /g) || []).length, 3);
  }
  assert.deepEqual(chart, original);
});

test('both presentation maps reject separate Taiwan rows from stale aggregates', () => {
  const world = {viewBox: '0 0 10 10', regions: []};
  const chart = {rows: [{id: 'CN', value: 20}, {id: 'TW', value: 5}]};
  for (const plot of [countryMapPlot, countryProportionPlot]) {
    assert.throws(() => plot(world, chart), /逐论文去重合并/);
  }
});
