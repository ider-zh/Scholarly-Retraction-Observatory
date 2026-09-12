import {disciplineCell} from './discipline.js';

export function conceptComparison(data, study, parentId = '') {
  if (study.taxonomy.id !== 'concepts') return [];
  const metric = study.metric === 'proportion' ? 'proportion' : 'count';
  return study.taxonomy.nodes.filter(node => !node.navigation_only && !node.missing && (parentId ? node.level === 1 && node.parents.includes(parentId) : node.level === 0))
    .sort((first, second) => first.label.localeCompare(second.label))
    .map(node => ({id: node.id, label: node.label, rows: Array.from({length: data.year_end - data.year_start + 1}, (_, offset) => {
      const cell = disciplineCell(study.taxonomy, node, study.population, metric, offset + 1);
      const count = cell.numerator ?? null;
      return {...cell, year: data.year_start + offset, count, numerator: count, value: count === null ? null : cell.value, partial: data.year_start + offset === data.year_end};
    })}));
}

export function comparisonSegments(rows, metric = 'count') {
  const segments = [];
  for (const row of rows) {
    if (metric === 'proportion' ? !Number.isFinite(row.value) || !row.ranking_eligible : row.count == null) {segments.push([]); continue;}
    if (!segments.length) segments.push([]);
    segments.at(-1).push(row);
  }
  return segments.filter(segment => segment.length);
}
