import assert from 'node:assert/strict';
import test from 'node:test';
import {SECTIONS, validateManifest, validateChunk} from '../src/report/schema.js';

function fixture() {
  const manifest = {schema_version: 3, status: 'ready', release_id: 'test-release', oa_snapshot_date: '2026-06-26',
    oa_source_prefix: 's3://openalex/data/parquet/', oa_manifest_sha256: 'a'.repeat(64), rw_snapshot_date: '2026-09-10',
    rw_source_commit: 'b'.repeat(40), rw_csv_sha256: 'c'.repeat(64), pipeline_commit: 'd'.repeat(40), config_sha256: 'e'.repeat(64),
    schema_adapter_version: 'test', role_policy_version: 'test', reason_mapping_version: 'test', metric_observation_cutoff: '2026-06-26',
    generated_at: '2026-09-11T00:00:00Z', source_acceptance_policy: 'retrospective-v1', transfer_provenance_status: 'missing',
    quality_gates: {source_validation: true}, files: SECTIONS.map(section => ({path: `data/snapshot/${section}.json`, bytes: 1, sha256: 'f'.repeat(64)})),
    supported_slices: [{chart_id: 'T3', slice_id: 'core-article', section: 'time', status: 'ready'}]};
  const chunk = {schema_version: 3, release_id: 'test-release', section: 'time', charts: [{schema_version: 3, release_id: 'test-release',
    chart_id: 'T3', slice_id: 'core-article', status: 'ready', population_key: 'A1_over_D', metric_id: 'oa_flagged_cohort_per_10k',
    scope: {corpus: 'core', attribution: 'unique_work', work_types: ['article']}, methods_version: 'test',
    oa_snapshot_date: '2026-06-26', rw_snapshot_date: '2026-09-10', limitations: ['Test only'],
    rows: [{id: '2020', label: '2020', numerator: 0, denominator: 1000, value: 0, ranking_eligible: false, unit: 'per_10k'}],
    insights: [{release_id: 'test-release', chart_id: 'T3', slice_id: 'core-article', evidence_cells: ['2020']}]}]};
  return {manifest, chunk};
}

test('valid zero has a denominator and remains distinct from unavailable', () => {
  const {manifest, chunk} = fixture();
  validateManifest(manifest); validateChunk(chunk, manifest, 'time');
  chunk.charts[0].rows[0].denominator = 0;
  assert.throws(() => validateChunk(chunk, manifest, 'time'), /reproduced/);
  chunk.charts[0].rows[0].value = null;
  validateChunk(chunk, manifest, 'time');
});
test('a mixed release is rejected', () => {
  const {manifest, chunk} = fixture(); chunk.release_id = 'stale';
  assert.throws(() => validateChunk(chunk, manifest, 'time'), /release/);
});
test('stale observations cannot accompany new slices', () => {
  const {manifest, chunk} = fixture(); chunk.charts[0].insights[0].slice_id = 'old-slice';
  assert.throws(() => validateChunk(chunk, manifest, 'time'), /Stale observation/);
});
test('raw nested records cannot be published', () => {
  const {manifest, chunk} = fixture(); chunk.charts[0].authorships = [];
  assert.throws(() => validateChunk(chunk, manifest, 'time'), /Raw field/);
});
test('n must be contained in N and ranking thresholds are enforced', () => {
  const {manifest, chunk} = fixture(); const row = chunk.charts[0].rows[0];
  row.numerator = 1001;
  assert.throws(() => validateChunk(chunk, manifest, 'time'), /numerator/);
  row.numerator = 0; row.ranking_eligible = true;
  assert.throws(() => validateChunk(chunk, manifest, 'time'), /threshold/);
});
test('unavailable charts cannot contain computed-looking cells', () => {
  const {manifest, chunk} = fixture(); const chart = chunk.charts[0];
  chart.status = 'not_computed'; manifest.supported_slices[0].status = 'not_computed'; chart.unavailable_reason = 'Not scanned';
  assert.throws(() => validateChunk(chunk, manifest, 'time'), /Unavailable/);
  chart.rows = []; chart.insights = [];
  validateChunk(chunk, manifest, 'time');
});
test('unexpected paths and missing provenance fail validation', () => {
  const {manifest} = fixture(); manifest.files[0].path = 'data/snapshot/raw.json';
  assert.throws(() => validateManifest(manifest), /path/);
  const next = fixture().manifest; next.oa_manifest_sha256 = null;
  assert.throws(() => validateManifest(next), /provenance/);
});

test('incoming ratio requires before plus after, not static citation count', () => {
  const {manifest, chunk} = fixture();
  const chart = chunk.charts[0];
  chart.chart_id = 'C3'; chart.metric_id = 'incoming_edge_count';
  manifest.supported_slices[0].chart_id = 'C3'; chart.insights[0].chart_id = 'C3';
  chart.rows = [{id: 'before', label: 'before', numerator: 2, denominator: 4, value: 2},
    {id: 'after', label: 'after', numerator: 1, denominator: 4, value: 1},
    {id: 'ambiguous', label: 'ambiguous', numerator: 1, denominator: 4, value: 1}];
  chart.insights[0].evidence_cells = ['after'];
  chart.post_retraction_citation_ratio = {numerator: 1, denominator: 3, value: 1 / 3};
  validateChunk(chunk, manifest, 'time');
  chart.post_retraction_citation_ratio.denominator = 4;
  assert.throws(() => validateChunk(chunk, manifest, 'time'), /wrong denominator/);
});

test('common persistence windows cannot silently change target denominators', () => {
  const {manifest, chunk} = fixture(); const chart = chunk.charts[0];
  chart.chart_id = 'C4'; chart.metric_id = 'mean_incoming_edges';
  Object.assign(chart.scope, {citing_corpus: 'all', date_precision: 'reported', cohort_mode: 'common_5y'});
  manifest.supported_slices[0].chart_id = 'C4'; chart.insights[0].chart_id = 'C4';
  chart.rows = [1, 3].map(years => ({id: String(years), label: String(years), numerator: 0, denominator: 2, value: 0,
    excluded_targets: 1, targets_with_edges: 0, targets_with_edges_pct: 0}));
  chart.insights[0].evidence_cells = ['1']; validateChunk(chunk, manifest, 'time');
  chart.rows[1].denominator = 3;
  assert.throws(() => validateChunk(chunk, manifest, 'time'), /Common followup/);
});
