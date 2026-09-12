import {chartName, variantName, populationName} from './reader.js';
import {filterCharts, sourceProfile, SOURCE_ORDER} from './sources.js';
import {availableStudies} from './discipline.js';

export function topicId(chart) {
  if (chart.chart_id === 'T1') return 'annual-counts';
  if (chart.chart_id === 'G1' && chart.metric_id.endsWith('_cohort_per_10k')) return 'country-rates';
  if (chart.chart_id === 'P2' && chart.control_policy) return 'monthly-control';
  return chart.chart_id.toLowerCase();
}

export function topicHref(section, topic, sources, slice = '', selection = {}) {
  const params = new URLSearchParams({sources: SOURCE_ORDER.filter(source => sources.includes(source)).join(',')});
  if (slice) params.set('slice', slice);
  for (const key of ['taxonomy', 'population', 'node', 'parent', 'metric']) if (selection[key]) params.set(key, selection[key]);
  return `#/snapshot/${section}/topic/${encodeURIComponent(topic)}?${params}`;
}

export function topicCatalog(charts, sources, explorer, countryExplorer) {
  const groups = new Map();
  for (const chart of charts) {
    const id = topicId(chart);
    if (!groups.has(id)) groups.set(id, {id, title: chartName(chart), question: chart.question, charts: []});
    groups.get(id).charts.push(chart);
  }
  if (groups.has('annual-counts')) Object.assign(groups.get('annual-counts'), {title: '发表年与撤稿年：同图对比', question: '同一批 RW 原论文，按发表年和撤稿年观察有什么不同？'});
  if (groups.has('country-rates')) Object.assign(groups.get('country-rates'), {title: '国家比例：旧版聚合视图', supersededBy: countryExplorer ? 'countries' : null});
  if (explorer) groups.set('discipline', {id: 'discipline', title: explorer.taxonomies.length === 1 ? `${explorer.taxonomies[0].label}：分布和时间` : '主学科与子学科：分布和时间', question: explorer.taxonomies.length === 1 ? `${explorer.taxonomies[0].label} 的各级分类如何分布，随发表年怎样变化？数量、样本覆盖与分类内比例分开查看。` : '分别沿 Subject、四层 Topics、Concepts 分类树查看数量、覆盖与同口径比例。', charts: [], tree: true});
  if (countryExplorer) groups.set('countries', {id: 'countries', title: '国家内撤稿比例与年度趋势', question: '在各国同口径发表论文中，已有多少被记录撤稿？这个比例随发表年如何变化？', charts: [], countries: true});
  return [...groups.values()].map(group => {
    const allowed = filterCharts(group.charts, sources);
    return {...group, allowed, enabled: group.countries ? sources.includes('oa') : group.tree ? availableStudies(explorer, sources).length > 0 : allowed.length > 0,
      profiles: [...new Map(group.charts.map(chart => [sourceProfile(chart).key, sourceProfile(chart)])).values()]};
  }).sort((first, second) => Number(second.enabled) - Number(first.enabled));
}

export function variantKey(chart) {
  return chart.slice_id.replace(/^(A1_over_D|C_D_over_D|A0|A1|B|C_D|C|D)-/, '');
}

export function topicDatasetLabel(chart) {
  if (chart.chart_id === 'author-top') return chart.population_key === 'C' ? 'OpenAlex 作者 ID · RW 匹配且筛选后的论文' : 'OpenAlex 作者 ID · OA 标记且筛选后的论文';
  return `${sourceProfile(chart).label} · ${populationName(chart)}`;
}

export function topicVariantLabel(chart) {
  if (variantKey(chart) === 'any-topic-field') return '按学科汇总（所有主题，多标签）';
  if (variantKey(chart) === 'any-topic-topic') return '按主题汇总（所有主题，多标签）';
  return variantName(chart).split(' · ').slice(1).join(' · ') || chart.question;
}

export function selectTopicChart(topic, sources, slice) {
  const available = filterCharts(topic.charts, sources);
  return slice ? available.find(chart => `${chart.chart_id}/${chart.slice_id}` === slice) || null : available[0] || null;
}

export function annualSeries(charts) {
  const series = ['published', 'retracted'].map(basis => charts.find(chart => chart.chart_id === 'T1' && chart.population_key === 'B' && chart.scope.date_basis === basis));
  if (series.some(chart => !chart || chart.status !== 'ready' || chart.metric_id !== 'work_count' || chart.rows.some(row => row.unit !== 'works'))) return [];
  return series.every(chart => chart.release_id === series[0].release_id && chart.metric_observation_cutoff === series[0].metric_observation_cutoff) ? series : [];
}
