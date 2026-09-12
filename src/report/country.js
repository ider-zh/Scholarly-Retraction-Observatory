export const COUNTRY_METRICS = {count: '关联撤稿论文数', proportion: '国家内撤稿比例（%）', rate: '每万篇发表论文中的记录数'};
const COUNTRY_GROUPING = 'country-grouping-cn-includes-tw-v1';

export function countryCell(node, population, metric, index = 0) {
  const numerator = node.counts[population][index], denominator = node.denominator[index];
  return {id: node.id, label: node.id, numerator, denominator,
    value: metric === 'count' ? numerator : denominator ? numerator / denominator * (metric === 'rate' ? 10000 : 100) : null,
    unit: metric === 'count' ? 'works' : metric === 'rate' ? 'per_10k' : 'percent',
    ranking_eligible: numerator >= 20 && denominator >= 1000};
}

export function countryStudy(data, sources, selection) {
  if (!data) return {error: '国家年度聚合尚未发布。'};
  if (!sources.includes('oa')) return {error: '国家内比例需要 OpenAlex 的同口径发表论文分母；RW 单库不能代替。'};
  const population = selection.population || 'A1', metric = selection.metric || 'proportion';
  if (!['A1', 'C_D'].includes(population) || (population === 'C_D' && !sources.includes('rw'))) return {error: '当前数据集不支持所选研究总体。'};
  if (!Object.hasOwn(COUNTRY_METRICS, metric) || selection.taxonomy || selection.parent) return {error: '国家年度分析不接受此指标或学科路径。'};
  const ranked = data.nodes.map(node => countryCell(node, population, metric)).sort((first, second) => {
    if (metric !== 'count' && (!first.ranking_eligible || !second.ranking_eligible)) return Number(second.ranking_eligible) - Number(first.ranking_eligible) || first.id.localeCompare(second.id);
    return (second.value ?? -1) - (first.value ?? -1) || first.id.localeCompare(second.id);
  });
  const selectedCode = data.country_grouping_version === COUNTRY_GROUPING && selection.node === 'TW' ? 'CN' : selection.node;
  const node = data.nodes.find(node => node.id === (selectedCode || ranked[0]?.id));
  if (!node) return {error: '国家代码不存在，没有回退到其他国家。'};
  return {population, metric, node, ranked};
}

export function countryTimeChart(data, study) {
  const {node, population, metric} = study;
  return {chart_id: 'country-time', metric_id: metric, slice_id: `${population}/${node.id}/${metric}`, population_key: population,
    title: `${node.id}：${COUNTRY_METRICS[metric]}随发表年变化`, rows: Array.from({length: data.year_end - data.year_start + 1}, (_, offset) => ({...countryCell(node, population, metric, offset + 1), id: String(data.year_start + offset), label: String(data.year_start + offset), year: data.year_start + offset, partial: data.year_start + offset === data.year_end}))};
}

export function validateCountryExplorer(data, manifest) {
  const check = (condition, message) => {if (!condition) throw new Error(message);};
  check(data?.version === 'country-cohorts-v1' && data.release_id === manifest.release_id, 'Invalid country explorer release');
  check(data.oa_cutoff === manifest.oa_snapshot_date && data.rw_cutoff === manifest.rw_snapshot_date && data.attribution === 'institution_country', 'Country scope mismatch');
  check(data.year_start === 2000 && data.year_end === Number(manifest.oa_snapshot_date.slice(0, 4)), 'Invalid country years');
  check(JSON.stringify(data.populations) === '["A1","C_D"]' && data.method && Array.isArray(data.limitations) && data.limitations.length > 0, 'Missing country methods');
  check(data.dimension_source_sha256 === manifest.dimension_builder_source_sha256 && data.scan_config_sha256 === manifest.scan_config_sha256, 'Country provenance mismatch');
  check(data.country_grouping_version === manifest.country_grouping_version, 'Country grouping provenance mismatch');
  if (manifest.role_policy_version === BROAD_WORK_POLICY) check(JSON.stringify(data.work_types) === '["all"]', 'Country type scope mismatch');
  if (data.country_grouping_version) {
    check(data.country_grouping_version === COUNTRY_GROUPING, 'Unsupported country grouping');
    check(!data.nodes?.some(node => node.id === 'TW'), 'Unmerged Taiwan country row');
  }
  const length = data.year_end - data.year_start + 2;
  const series = values => check(Array.isArray(values) && values.length === length && values.every(value => Number.isSafeInteger(value) && value >= 0) && values[0] === values.slice(1).reduce((sum, value) => sum + value, 0), 'Invalid country count series');
  check(Array.isArray(data.nodes) && data.nodes.length > 0 && data.nodes.length <= 300 && new Set(data.nodes.map(node => node.id)).size === data.nodes.length, 'Invalid country nodes');
  for (const population of data.populations) series(data.missing_country?.[population]);
  for (const node of data.nodes) {
    check(/^[A-Z]{2}$/.test(node.id), 'Invalid country code'); series(node.denominator);
    for (const population of data.populations) {series(node.counts?.[population]); check(node.counts[population].every((value, index) => value <= node.denominator[index]), 'Country numerator exceeds annual denominator');}
  }
  return data;
}
import {BROAD_WORK_POLICY} from './workPolicy.js';
