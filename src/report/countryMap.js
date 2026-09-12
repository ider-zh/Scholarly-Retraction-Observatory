export const MAP_COLORS = ['#e1f0ed', '#aed4cd', '#68aaa1', '#28776f', '#124e48'];

export const COUNTRY_MAP_GROUPING_NOTE = '中国包含台湾；同一论文在两地均有关联时，合并后仅计一次。两地底图使用同一中国统计值着色。';

export function mapCountryCode(code) {
  return code === 'TW' ? 'CN' : code;
}

export function mapRowsByCode(rows) {
  if (rows.some(row => row.id === 'TW')) throw new Error('国家数据尚未完成中国与台湾的逐论文去重合并，不能显示合并地图。请重新加载最新报告数据。');
  return new Map(rows.map(row => [row.id, row]));
}

export function countryRateRows(chart, rows) {
  if (chart.chart_id !== 'G1' || !chart.metric_id.endsWith('_cohort_per_10k')) return rows;
  return [...rows].sort((first, second) => Number(second.ranking_eligible) - Number(first.ranking_eligible) || (first.ranking_eligible ? second.value - first.value : 0) || first.id.localeCompare(second.id));
}

export function mapStatus(row, metric) {
  if (!row || !Number.isFinite(row.value)) return 'missing';
  if (metric !== 'count' && !row.ranking_eligible) return 'small';
  return 'value';
}

export function mapScale(rows, metric) {
  const maximum = Math.max(0, ...rows.filter(row => mapStatus(row, metric) === 'value').map(row => row.value));
  return {maximum, thresholds: [1, 2, 3, 4].map(index => maximum * index / 4)};
}

export function mapColor(value, maximum) {
  if (value === 0 || maximum === 0) return MAP_COLORS[0];
  return MAP_COLORS[Math.min(4, Math.max(1, Math.ceil(value / maximum * 4)))];
}
