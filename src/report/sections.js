export const DISCIPLINE_SECTIONS = {
  subjects: {label: 'RW · Subject 学科', source: 'rw'},
  topics: {label: 'OpenAlex · Topics 主题', source: 'oa'},
  concepts: {label: 'OpenAlex · Concepts 旧体系', source: 'oa'},
};

export const REPORT_PAGES = {overview: '研究概览', time: '时间与观察期', ...Object.fromEntries(Object.entries(DISCIPLINE_SECTIONS).map(([key, section]) => [key, section.label])), reasons: '撤稿原因', geography: '地理与合作', entities: '机构与作者', publishing: '期刊与出版', citations: '引用与持续传播', quality: '数据与方法', fields: '学科与主题（旧链接）'};

export function disciplineTaxonomy(page) {
  return Object.hasOwn(DISCIPLINE_SECTIONS, page) ? page : '';
}

export function aggregateSection(page) {
  return disciplineTaxonomy(page) ? 'fields' : page;
}

export function sectionData(current, page) {
  if (!disciplineTaxonomy(page) || !current.charts) return current;
  return {...current, charts: current.charts.filter(chart => page === 'subjects' ? false : page === 'concepts' ? chart.chart_id.startsWith('concepts') : !chart.chart_id.startsWith('concepts')),
    explorer: current.explorer && {...current.explorer, taxonomies: current.explorer.taxonomies.filter(taxonomy => taxonomy.id === page)}};
}

export function sectionDisciplineHref(page, sources, selection) {
  const params = new URLSearchParams({sources: sources.join(',')});
  for (const key of ['taxonomy', 'population', 'node', 'parent', 'metric']) if (selection[key]) params.set(key, selection[key]);
  return `#/snapshot/${page}?${params}`;
}
