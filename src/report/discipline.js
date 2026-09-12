import {reportHref, sourceProfile} from './sources.js';

export const DISCIPLINE_METRICS = {count: '撤稿记录论文数', proportion: '学科内撤稿比例（%）', share: '样本内论文覆盖比例（%）', rate: '每万篇发表论文中的记录数'};

export const publicationMetric = metric => ['rate', 'proportion'].includes(metric);

export function availableStudies(data, sources) {
  return data.taxonomies.map(taxonomy => ({taxonomy, populations: taxonomy.populations.filter(population => sourceProfile({chart_id: 'discipline', population_key: population}).required.every(source => sources.includes(source)))})).filter(study => study.populations.length);
}

export function resolveStudy(data, sources, selection) {
  const studies = availableStudies(data, sources);
  const preferred = studies.find(study => study.taxonomy.id === 'topics') || studies[0];
  const study = selection.taxonomy ? studies.find(study => study.taxonomy.id === selection.taxonomy) : preferred;
  if (!study) return {error: '当前数据集选择不支持这个分类体系。Subject 需要 RW；Topics / Concepts 需要 OpenAlex。'};
  const taxonomy = study.taxonomy, population = selection.population || study.populations[0], metric = selection.metric || 'count';
  if (!study.populations.includes(population)) return {error: '所选研究总体不属于当前数据集和分类体系。'};
  if (!Object.hasOwn(DISCIPLINE_METRICS, metric) || (publicationMetric(metric) && taxonomy.denominator === null)) return {error: '该比率没有可用的同口径全体发文分母；不能用样本占比替代撤稿率。'};
  const root = {id: 'all', label: taxonomy.levels.length === 4 ? '全部大领域' : '全部主学科', level: -1, parents: [], counts: taxonomy.counts, denominator: taxonomy.denominator};
  const node = !selection.node || selection.node === 'all' ? root : taxonomy.nodes.find(node => node.id === selection.node && !node.navigation_only);
  if (!node) return {error: '该学科节点不存在或仅是导航分组，请重新选择。'};
  const legacyMissingParent = taxonomy.id === 'topics' && taxonomy.levels.length === 4 && node.id === 'subfield:unknown' && selection.parent === 'topics-unknown-parent';
  const parent = legacyMissingParent ? node.parents[0] : selection.parent || node.parents[0] || '';
  if (parent && !node.parents.includes(parent)) return {error: '这个子学科不属于所选父级；没有自动改换分类路径。'};
  return {taxonomy, population, metric, node, parent, studies};
}

export function disciplineHref(sources, selection) {
  const href = reportHref('fields', sources), params = new URLSearchParams(href.split('?')[1]);
  for (const key of ['taxonomy', 'population', 'node', 'parent', 'metric']) if (selection[key]) params.set(key, selection[key]);
  return href.split('?')[0]+'?'+params;
}

export function disciplineCell(taxonomy, node, population, metric, index) {
  const numerator = node.counts[population][index], scope = taxonomy.counts[population][index];
  const publicationDenominator = node.denominator?.[index] ?? null;
  const denominator = publicationMetric(metric) ? publicationDenominator : scope;
  const value = metric === 'count' ? numerator : denominator ? numerator / denominator * (metric === 'rate' ? 10000 : 100) : null;
  return {id: node.id, label: node.label, numerator, denominator, value,
    unit: metric === 'count' ? 'works' : metric === 'rate' ? 'per_10k' : 'percent',
    sample_denominator: scope, publication_denominator: publicationDenominator,
    ranking_eligible: !publicationMetric(metric) || (numerator >= 20 && publicationDenominator >= 1000)};
}

export function distributionRows(study) {
  const {taxonomy, node, parent, population, metric} = study;
  const hasChildren = taxonomy.nodes.some(candidate => candidate.parents.includes(node.id));
  const candidates = taxonomy.nodes.filter(candidate => !candidate.navigation_only && (node.level === -1 ? candidate.level === 0 : candidate.parents.includes(hasChildren ? node.id : parent)));
  return candidates.map(candidate => disciplineCell(taxonomy, candidate, population, metric, 0)).sort((first, second) => {
    if (publicationMetric(metric) && (!first.ranking_eligible || !second.ranking_eligible)) return Number(second.ranking_eligible) - Number(first.ranking_eligible) || first.label.localeCompare(second.label);
    return (second.value ?? -1) - (first.value ?? -1) || first.id.localeCompare(second.id);
  });
}

export function studyAncestors(study) {
  const nodes = new Map(study.taxonomy.nodes.map(node => [node.id, node]));
  const ancestors = [], seen = new Set([study.node.id]);
  let identifier = study.parent;
  while (identifier && !seen.has(identifier)) {
    seen.add(identifier);
    const ancestor = nodes.get(identifier);
    if (!ancestor) break;
    ancestors.unshift(ancestor);
    identifier = ancestor.parents[0];
  }
  return ancestors;
}

export function disciplineTimeChart(data, study) {
  const {taxonomy, node, population, metric} = study;
  return {chart_id: 'discipline-time', metric_id: metric, slice_id: `${taxonomy.id}/${population}/${node.id}/${metric}`,
    title: `${node.label}：按发表年观察${DISCIPLINE_METRICS[metric]}`, population_key: population,
    rows: Array.from({length: data.year_end-data.year_start+1}, (_, offset) => ({...disciplineCell(taxonomy, node, population, metric, offset+1),
      id: String(data.year_start+offset), label: String(data.year_start+offset), year: data.year_start+offset, partial: data.year_start+offset === data.year_end}))};
}
