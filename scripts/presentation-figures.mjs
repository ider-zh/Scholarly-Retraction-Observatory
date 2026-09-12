import {disciplineTimeChart, distributionRows, resolveStudy} from '../src/report/discipline.js';
import {mapColor, mapScale, MAP_COLORS, mapCountryCode, mapRowsByCode, COUNTRY_MAP_GROUPING_NOTE} from '../src/report/countryMap.js';

export const escape = value => String(value).replace(/[&<>"']/g, character => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[character]));
export const number = value => value == null ? '不适用' : Number(value).toLocaleString('zh-CN', {maximumFractionDigits: 2});
export const conceptLabels = {'Medicine': '医学', 'Biology': '生物学', 'Computer science': '计算机科学', 'Chemistry': '化学', 'Engineering': '工程学', 'Mathematics': '数学'};

export function disciplineEvidence(explorer, taxonomy, population, node = 'all', metric = 'count') {
  const study = resolveStudy(explorer, ['rw', 'oa'], {taxonomy, population, node, metric});
  if (study.error) throw new Error(study.error);
  const annual = node !== 'all';
  const chart = annual ? disciplineTimeChart(explorer, study) : {chart_id: 'discipline-distribution', slice_id: `${taxonomy}/${population}/all/${metric}`, metric_id: metric, title: `${study.taxonomy.label} ${metric === 'proportion' ? '学科内撤稿比例（%）' : '主类关联论文数'}`, population_key: population, rows: distributionRows(study)};
  return {...chart, status: 'ready', release_id: explorer.release_id, metric_observation_cutoff: taxonomy === 'subjects' ? explorer.rw_cutoff : explorer.oa_cutoff,
    scope: {taxonomy, population, node, node_label: study.node.label, metric, date_basis: 'publication_year', publication_year_range: annual ? [explorer.year_start, explorer.year_end] : null, attribution: study.taxonomy.method},
    limitations: [study.taxonomy.method, study.taxonomy.rate_policy, annual ? '横轴是原论文发表年，不是撤稿年。近期论文随访较短；最后一年尚未结束。' : '总体计数不局限于年度图展示的年份。标签关联不代表责任。']};
}

export function conceptTrendPlot(series) {
  const proportion = series[0]?.metric_id === 'proportion';
  const eligible = row => Number.isFinite(row.value) && (!proportion || row.ranking_eligible);
  const values = series.flatMap(chart => chart.rows.filter(eligible).map(row => row.value));
  const step = proportion ? 0.05 : 1000;
  const maximum = Math.max(step, Math.ceil(Math.max(0, ...values) / step) * step);
  const format = value => proportion ? Number(value).toLocaleString('zh-CN', {maximumFractionDigits: 3}) : number(value);
  const unit = proportion ? '%' : ' 篇';
  const completeYears = series[0]?.rows.filter(row => !row.partial && eligible(row) && series.every(chart => chart.rows.some(candidate => candidate.year === row.year && !candidate.partial && eligible(candidate)))).map(row => row.year) || [];
  const comparisonYear = completeYears.length ? Math.max(...completeYears) : null;
  return `<p class="figure-scope">实心点标注完整发表年份中的峰值；空心点与下方数值对比${comparisonYear ?? '共同完整发表'} 年队列。完整发表年份不代表随访已经结束。</p><div class="trend-panels" data-metric="${proportion ? 'proportion' : 'count'}">${series.map(chart => {
    const horizontal = year => 50 + (year-2000)/26*260;
    const vertical = value => 200-value/maximum*160;
    const name = conceptLabels[chart.scope.node_label] || chart.scope.node_label;
    const peak = chart.rows.filter(row => !row.partial && eligible(row)).reduce((best, row) => !best || row.value > best.value ? row : best, null);
    const latest = chart.rows.find(row => row.year === comparisonYear);
    const annotations = peak ? `<g class="trend-annotation" data-year="${peak.year}" data-value="${peak.value}"><circle cx="${horizontal(peak.year)}" cy="${vertical(peak.value)}" r="4"/><text x="305" y="${vertical(peak.value)-14}" text-anchor="end">${peak.year} · ${format(peak.value)}${unit}</text></g>` : '';
    const comparison = latest ? `<p class="trend-comparison"><span>${comparisonYear} 年发表队列</span><strong>${format(latest.value)}${unit}</strong>${proportion ? `<small>n / N = ${number(latest.numerator)} / ${number(latest.denominator)}</small>` : ''}</p>` : '<p class="trend-comparison">无共同可比较的完整发表年份</p>';
    const segments = chart.rows.slice(1).map((row,index) => {
      const previous = chart.rows[index];
      if (!eligible(previous) || !eligible(row)) return '';
      return `<path d="M${horizontal(previous.year)},${vertical(previous.value)}L${horizontal(row.year)},${vertical(row.value)}" class="trend-line${row.partial ? ' partial-line' : ''}"/>`;
    }).join('');
    const small = proportion ? chart.rows.filter(row => Number.isFinite(row.value) && !row.ranking_eligible).map(row => `<path d="M${horizontal(row.year)-3},197l6,6m-6,0l6,-6" class="small-base-mark"><title>${row.year}：小基数；n=${row.numerator}，N=${row.denominator}；真实比例见数据表。符号位置不表示数值。</title></path>`).join('') : '';
    return `<section><h3>${escape(name)}</h3><svg viewBox="0 0 330 240" role="img" aria-label="${escape(name)}，2000 至 2026 年发表队列的${proportion ? '学科内撤稿比例' : '撤稿标记论文数量'}；各面板共用纵轴${peak ? `；完整发表年份峰值 ${peak.year} 年 ${format(peak.value)}${unit}` : ''}"><text x="50" y="20">${proportion ? '%' : '篇'}</text>${[0, maximum/2, maximum].map(value => `<line x1="50" x2="310" y1="${vertical(value)}" y2="${vertical(value)}" class="gridline"/><text x="44" y="${vertical(value)+5}" text-anchor="end">${format(value)}</text>`).join('')}${segments}${small}${annotations}${latest ? `<circle class="trend-latest" cx="${horizontal(latest.year)}" cy="${vertical(latest.value)}" r="4"><title>${latest.year}：${format(latest.value)}${unit}</title></circle>` : ''}${[2000,2010,2020,2026].map(year => `<text x="${horizontal(year)}" y="225" text-anchor="middle">${year}</text>`).join('')}</svg>${comparison}</section>`;
  }).join('')}</div>`;
}

export function conceptProportionPlot(chart, selectedIds) {
  const rows = chart.rows.filter(row => selectedIds.includes(row.id) && row.ranking_eligible && Number.isFinite(row.value)).sort((first,second) => second.value-first.value);
  const maximum = Math.max(0.01, ...rows.map(row => row.value));
  return `<div class="proportion-bars"><div class="proportion-heading"><span>学科（数量前六中比较）</span><span>学科内撤稿比例</span><span>n / N（篇）</span></div>${rows.map(row => `<div class="proportion-row"><span>${escape(conceptLabels[row.label] || row.label)}</span><div><div class="bar-track"><span style="width:${row.value/maximum*100}%"></span></div><strong>${row.value.toFixed(4)}%</strong></div><span>${number(row.numerator)} / ${number(row.denominator)}</span></div>`).join('')}</div>`;
}

export function countryMapPlot(world, chart) {
  const byCode = mapRowsByCode(chart.rows);
  const {maximum, thresholds} = mapScale(chart.rows, 'count');
  const names = new Intl.DisplayNames(['zh-CN'], {type: 'region'});
  const represented = new Set(world.regions.map(region => mapCountryCode(region.code)));
  const unmapped = chart.rows.filter(row => !represented.has(row.id));
  return `<div class="map-layout"><svg class="ppt-world-map" viewBox="${world.viewBox}" role="img" aria-label="各国机构关联撤稿标记论文数；颜色越深数量越多，灰色为无对应数值"><title>OpenAlex 机构国家关联分布</title>${world.regions.map(region => {const candidate = byCode.get(mapCountryCode(region.code));const row = Number.isFinite(candidate?.value) ? candidate : null;return `<path d="${region.path}" data-country="${escape(region.code || '')}" fill="${row ? mapColor(row.value, maximum) : 'var(--map-missing)'}"><title>${escape(row ? names.of(row.id) : region.name)}：${row ? `${number(row.value)} 篇，n=${row.numerator} / N=${row.denominator}` : '无对应数值，不代表零'}</title></path>`;}).join('')}</svg><div class="map-ranking"><h3>关联数量前三</h3>${[...chart.rows].sort((first, second) => second.value-first.value).slice(0,3).map(row => `<p>${escape(names.of(row.id))}<strong>${number(row.value)} <small>篇</small></strong></p>`).join('')}<p class="small-print">不是国家内撤稿率<br/>同一论文可关联多个国家</p></div></div><div class="map-legend"><span><i style="background:${MAP_COLORS[0]}"></i>0 篇</span>${thresholds.map((upper,index) => `<span><i style="background:${MAP_COLORS[index+1]}"></i>${number(index ? thresholds[index-1] : 0)}–${number(upper)}</span>`).join('')}<span><i style="background:var(--map-missing)"></i>无对应数值</span></div><p class="map-credit">${COUNTRY_MAP_GROUPING_NOTE}Natural Earth 1:110m 本地底图；${unmapped.length} 个有数值的国家/地区未匹配到本比例尺底图，仍保留在数据表。边界仅作定位，不代表主权立场。</p>`;
}

export function citationPlot(chart) {
  const last = chart.rows.at(-1);
  return `<div class="citation-explainer"><div><h3>哪些论文在撤稿后被引用？</h3><p>同一批可完整观察五年的 ${number(last.denominator)} 篇论文</p><div class="citation-coverage" role="img" aria-label="${number(last.targets_with_edges)} / ${number(last.denominator)} 篇在撤稿后五年内至少被引用一次"><span style="width:${last.targets_with_edges_pct}%"></span></div><p><strong>${number(last.targets_with_edges)} 篇（${number(last.targets_with_edges_pct)}%）</strong><br/>撤稿后五年内至少观察到一次引用</p><p class="small-print">其余 ${number(last.denominator-last.targets_with_edges)} 篇：在已扫描引用图中未观察到，不保证现实中没有引用。</p></div><div><h3>累计被引用多少次？</h3><div class="citation-windows">${chart.rows.map(row => `<div><h4>撤稿后 ${row.window_years} 年内</h4><strong>${number(row.value)}</strong><span>平均条数 / 篇</span><p>中位数 ${number(row.median)} 条<br/>${number(row.targets_with_edges_pct)}% 至少被引一次</p></div>`).join('')}</div><p class="small-print">1 → 3 → 5 年为从撤稿日开始的累计窗口，共用同一批论文。不是“第 5 年新增 9 次”，也不是每篇都被引 9 次。</p></div></div>`;
}
