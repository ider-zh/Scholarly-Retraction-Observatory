export function plotKind(chart) {
  if (chart.control_policy) return 'control';
  if (['R4', 'P3'].includes(chart.chart_id)) return 'interval';
  if (['F3', 'P1'].includes(chart.chart_id)) return 'scatter';
  if (['T1', 'T3', 'T4', 'E3', 'C1', 'C2'].includes(chart.chart_id)) return 'line';
  return null;
}

export function plotRows(chart) {
  const kind = plotKind(chart);
  return chart.rows.flatMap((row, index) => {
    if (!Number.isFinite(row.value)) return [];
    const position = kind === 'control' || kind === 'interval' ? index : kind === 'scatter' ? row.denominator > 0 ? Math.log10(row.denominator) : null : row.relative_year ?? row.year ?? row.lag_days ?? row.entity_pct ?? (row.cited_by_count == null ? null : Math.log1p(row.cited_by_count));
    if (!Number.isFinite(position) || (kind === 'line' && row.year != null && row.year < 2000)) return [];
    return [{...row, position}];
  }).sort((first, second) => first.position - second.position);
}

export function lineSegments(rows) {
  const segments = [];
  for (const row of rows) {
    const previous = segments.at(-1)?.at(-1);
    if (!previous || (row.year != null && previous.year != null && row.year > previous.year + 1)) segments.push([]);
    segments.at(-1).push(row);
  }
  return segments;
}
