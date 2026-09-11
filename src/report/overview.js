import {filterCharts, sourceProfile} from './sources.js';
import {chartName, insightText, number, selectChart} from './reader.js';

export function overviewEvidence(chart, rows = chart.rows) {
  return {aggregate: 'data/snapshot/overview.json', release_id: chart.release_id,
    chart_id: chart.chart_id, slice_id: chart.slice_id, population: chart.population_key,
    metric: chart.metric_id, scope: chart.scope, oa_date: chart.oa_snapshot_date,
    rw_date: chart.rw_snapshot_date, cutoff: chart.metric_observation_cutoff,
    cells: rows.map(row => ({id: row.id, n: row.numerator, N: row.denominator, value: row.value, unit: row.unit}))};
}

export function overviewSelection(charts, sources, slice) {
  const available = filterCharts(charts, sources);
  if (slice) return selectChart(available, slice);
  return available.find(chart => chart.chart_id === 'screening' && chart.slice_id === 'A0-screening') || selectChart(available, '');
}

export function overviewNarrative(chart) {
  if (!chart) return null;
  const evidence = overviewEvidence(chart);
  if (chart.status !== 'ready') return {title: chartName(chart), finding: '这项分析尚未达到发布条件。', boundary: chart.unavailable_reason, evidence};
  const retained = chart.rows.find(row => row.id === 'retained_A1');
  if (chart.chart_id === 'screening' && retained?.value != null && retained.denominator > 0) {
    return {title: '撤稿标记，不能直接当作原论文数量',
      finding: `${number(retained.denominator)} 条标记记录中，${number(retained.numerator)} 篇研究论文候选进入默认分析，占 ${retained.value.toLocaleString('zh-CN', {maximumFractionDigits: 2})}%。`,
      boundary: '筛选缩小的是研究范围，不代表被排除的记录都无效；这个比例也不是全部发表论文的撤稿率。', evidence};
  }
  return {title: chartName(chart), finding: chart.insights.map(insight => insightText(insight, chart)).join(' ') || '该分析没有已发布的数值发现；请查看有效样本与缺失说明。',
    boundary: chart.limitations[0], evidence};
}

export const SCREENING_NOTES = {
  retained_A1: '保留符合文献类型、原论文身份和日期规则的 article 候选；尚未独立确认身份的记录不因此变成已确认原论文。',
  excluded_work_type: '主分析限定 article。综述、通知等其他类型不进入默认研究论文样本；不意味着它们不会撤稿。',
  excluded_known_notice: '原论文与通知分别核对身份。撤稿或更正通知不能再当作另一篇被撤稿的原论文。',
  excluded_suspected_notice: '标题规则提示可能是通知，默认暂不纳入；并非逐篇裁定，敏感性计数另行保留。',
  excluded_conflict: '同一标识同时出现原论文与通知身份线索；冲突没有通过自动选择一方来消除。',
};

export function screeningRows(chart) {
  return [...chart.rows].sort((first, second) => Number(second.id === 'retained_A1') - Number(first.id === 'retained_A1') || (second.value ?? -1) - (first.value ?? -1) || first.id.localeCompare(second.id));
}

export function overviewScope(chart) {
  return chart ? sourceProfile(chart).label : '当前选择尚无概览图';
}
