export const SOURCE_NAMES = {rw: 'Retraction Watch（RW）', oa: 'OpenAlex'};
export const SOURCE_ORDER = ['rw', 'oa'];

export function sourceProfile(chart) {
  const population = chart.population_key;
  if (['Q1', 'Q2', 'population-accounting'].includes(chart.chart_id)) return {key: 'comparison', required: ['rw', 'oa'], label: 'RW + OpenAlex · 跨库核对', description: '分别核对两份来源的记录与匹配结果，不是将两库数量相加，也不是去重并集。'};
  if (population === 'B') return {key: 'rw', required: ['rw'], label: 'RW · 撤稿原论文', description: '研究对象和本图字段来自 RW，按原论文标识去重；不要求该论文能在 OpenAlex 中匹配。'};
  if (['A0', 'A1', 'D', 'A1_over_D'].includes(population)) return {key: 'oa', required: ['oa'], label: 'OpenAlex · 快照记录口径', description: '以 OpenAlex 的记录、标记和元数据定义研究范围；不是 OpenAlex 全库都被撤稿。标记及原论文/通知筛选存在 RW 来源依赖，不是独立验证。'};
  if (['C', 'C_D', 'C_D_over_D'].includes(population)) return {key: 'matched', required: ['rw', 'oa'], label: 'RW × OpenAlex · 匹配子集', description: '先从 RW 原论文中取与 OpenAlex 匹配且通过本图筛选的记录，再使用 OpenAlex 元数据。它不是两者的并集，也不要求 OpenAlex 同时带撤稿标记。'};
  return {key: 'unclassified', required: ['rw', 'oa'], label: '跨来源 · 需核对技术范围', description: '尚无单一来源归类，不能在只选一个数据集时将它当作该库独立分析。'};
}

export function filterCharts(charts, sources) {
  return charts.filter(chart => sourceProfile(chart).required.every(source => sources.includes(source)));
}

export function parseSources(value) {
  if (value == null) return {sources: [...SOURCE_ORDER], error: null};
  const selected = value.split(',');
  if (!selected.length || selected.some(source => !SOURCE_ORDER.includes(source)) || new Set(selected).size !== selected.length) return {sources: [], error: '数据集参数无效，请重新选择数据集。'};
  return {sources: SOURCE_ORDER.filter(source => selected.includes(source)), error: null};
}

export function reportHref(page, sources, slice = '') {
  const params = new URLSearchParams({sources: SOURCE_ORDER.filter(source => sources.includes(source)).join(',')});
  if (slice) params.set('slice', slice);
  return `#/snapshot/${page}?${params}`;
}
