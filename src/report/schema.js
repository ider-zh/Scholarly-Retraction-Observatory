export const SECTIONS = ['overview', 'time', 'fields', 'reasons', 'geography', 'entities', 'publishing', 'citations', 'quality'];
export const SNAPSHOT_PATHS = ['data/snapshot/manifest.json', ...SECTIONS.map(section => `data/snapshot/${section}.json`)];
const STATES = new Set(['ready', 'not_computed', 'missing_data', 'missing_denominator', 'insufficient_followup', 'small_base']);
const forbidden = new Set(['papers', 'authorships', 'referenced_works', 'abstract_inverted_index', 'rw_ids', 'raw_dates', 'citation_edges']);
function requireValue(condition, message) { if (!condition) throw new Error(message); }
function inspect(value) {
  if (typeof value === 'number') requireValue(Number.isFinite(value), 'Nonfinite aggregate value');
  if (value && typeof value === 'object') for (const [key, child] of Object.entries(value)) {
    requireValue(!forbidden.has(key), `Raw field prohibited: ${key}`);
    inspect(child);
  }
}
export function validateManifest(manifest) {
  requireValue(manifest?.schema_version === 3 && manifest.status === 'ready', 'Snapshot manifest is not ready v3');
  for (const key of ['release_id', 'oa_snapshot_date', 'oa_source_prefix', 'oa_manifest_sha256', 'rw_snapshot_date', 'rw_source_commit', 'rw_csv_sha256', 'pipeline_commit', 'config_sha256', 'schema_adapter_version', 'role_policy_version', 'reason_mapping_version', 'metric_observation_cutoff', 'generated_at', 'source_acceptance_policy']) {
    requireValue(typeof manifest[key] === 'string' && manifest[key].length > 0, `Missing provenance: ${key}`);
  }
  requireValue(manifest.metric_observation_cutoff <= manifest.oa_snapshot_date, 'Cohort cutoff exceeds OA snapshot');
  requireValue(manifest.source_acceptance_policy !== 'retrospective-v1' || manifest.transfer_provenance_status === 'missing', 'Retrospective provenance must remain visible');
  requireValue(manifest.quality_gates && Object.values(manifest.quality_gates).every(value => value === true), 'Failed publication gate');
  requireValue(Array.isArray(manifest.files) && manifest.files.length === SECTIONS.length, 'Incomplete snapshot section list');
  requireValue(new Set(manifest.files.map(file => file.path)).size === SECTIONS.length, 'Duplicate snapshot path');
  for (const file of manifest.files) {
    requireValue(SNAPSHOT_PATHS.slice(1).includes(file.path), 'Unexpected snapshot path');
    requireValue(Number.isInteger(file.bytes) && file.bytes > 0 && /^[a-f0-9]{64}$/.test(file.sha256), 'Invalid chunk integrity metadata');
  }
  requireValue(Array.isArray(manifest.supported_slices), 'Missing supported slices');
  inspect(manifest);
  return manifest;
}
export function validateChunk(chunk, manifest, section) {
  requireValue(chunk?.schema_version === 3 && chunk.release_id === manifest.release_id && chunk.section === section, 'Mixed or invalid snapshot release');
  requireValue(Array.isArray(chunk.charts), 'Missing chart collection');
  const seen = new Set();
  for (const chart of chunk.charts) {
    const key = `${chart.chart_id}/${chart.slice_id}`;
    requireValue(!seen.has(key), 'Duplicate chart slice'); seen.add(key);
    requireValue(chart.release_id === manifest.release_id && chart.schema_version === 3, 'Mixed chart release');
    requireValue(STATES.has(chart.status), 'Unknown chart state');
    requireValue(typeof chart.population_key === 'string' && typeof chart.metric_id === 'string', 'Missing chart semantics');
    requireValue(chart.scope?.corpus && chart.scope?.attribution && Array.isArray(chart.scope.work_types), 'Missing scope');
    requireValue(chart.methods_version && chart.oa_snapshot_date === manifest.oa_snapshot_date && chart.rw_snapshot_date === manifest.rw_snapshot_date, 'Missing or inconsistent chart provenance');
    requireValue(manifest.supported_slices.some(slice => slice.section === section && slice.chart_id === chart.chart_id && slice.slice_id === chart.slice_id && slice.status === chart.status), 'Undeclared chart slice');
    requireValue(Array.isArray(chart.rows) && Array.isArray(chart.insights) && Array.isArray(chart.limitations), 'Incomplete chart contract');
    requireValue(chart.status === 'ready' || (chart.rows.length === 0 && chart.insights.length === 0 && chart.unavailable_reason), 'Unavailable chart contains computed-looking data');
    const rowIds = new Set();
    if (chart.chart_id === 'C3' && chart.post_retraction_citation_ratio) {
      const ratio = chart.post_retraction_citation_ratio;
      const before = chart.rows.find(row => row.id === 'before')?.numerator;
      const after = chart.rows.find(row => row.id === 'after')?.numerator;
      requireValue(Number.isFinite(before) && Number.isFinite(after) && ratio.numerator === after && ratio.denominator === before + after, 'Citation ratio uses wrong denominator');
      requireValue(ratio.denominator ? Math.abs(ratio.value - after / ratio.denominator) < 1e-6 : ratio.value === null, 'Citation ratio cannot be reproduced');
    }
    for (const row of chart.rows) {
      requireValue(typeof row.id === 'string' && !rowIds.has(row.id), 'Duplicate/missing aggregate cell ID'); rowIds.add(row.id);
      requireValue(typeof row.label === 'string' && Number.isFinite(row.numerator) && row.numerator >= 0, 'Invalid cell numerator');
      requireValue(row.denominator === null || (Number.isFinite(row.denominator) && row.denominator >= 0), 'Invalid cell denominator');
      requireValue(row.value === null || Number.isFinite(row.value), 'Invalid cell value');
      if (chart.metric_id.endsWith('_cohort_per_10k')) {
        requireValue(row.numerator <= row.denominator, 'Rate numerator not contained in denominator');
        requireValue(row.denominator ? Math.abs(row.value - 10000 * row.numerator / row.denominator) < 1e-6 : row.value === null, 'Rate cannot be reproduced');
        requireValue(row.ranking_eligible === (row.denominator >= 1000 && row.numerator >= 20), 'Invalid ranking threshold');
      }
      if (chart.status === 'ready' && ['C2', 'C4'].includes(chart.chart_id)) {
        requireValue(chart.scope.citing_corpus && chart.scope.date_precision, 'Missing citation scope');
        requireValue(row.denominator ? Math.abs(row.value - row.numerator / row.denominator) < 1e-6 : row.value === null, 'Citation mean cannot be reproduced');
        requireValue(Number.isInteger(row.excluded_targets) && row.excluded_targets >= 0, 'Missing followup exclusions');
        if (chart.chart_id === 'C4') requireValue(row.targets_with_edges <= row.denominator &&
          (row.denominator ? Math.abs(row.targets_with_edges_pct - 100 * row.targets_with_edges / row.denominator) < 1e-6 : row.targets_with_edges_pct === null), 'Invalid persistence coverage');
      }
    }
    if (chart.chart_id === 'C4' && chart.scope.cohort_mode === 'common_5y') requireValue(new Set(chart.rows.map(row => row.denominator)).size <= 1, 'Common followup cohort changed across windows');
    if (chart.status === 'ready' && chart.rows.some(row => row.value !== null)) requireValue(chart.insights.length > 0, 'Ready chart has no numerical observation');
    for (const insight of chart.insights) {
      requireValue(insight.release_id === manifest.release_id && insight.chart_id === chart.chart_id && insight.slice_id === chart.slice_id, 'Stale observation');
      requireValue(insight.evidence_cells.length > 0 && insight.evidence_cells.every(id => rowIds.has(id) ||
        (id.startsWith('quantiles:') && Number.isFinite(chart.quantiles?.[id.slice(10)]))), 'Observation has no supporting cell');
    }
  }
  inspect(chunk);
  return chunk;
}
