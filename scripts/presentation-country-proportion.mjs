import {countryStudy} from '../src/report/country.js';
import {mapColor, mapScale, mapStatus, MAP_COLORS, mapCountryCode, mapRowsByCode, COUNTRY_MAP_GROUPING_NOTE} from '../src/report/countryMap.js';
import {escape, number} from './presentation-figures.mjs';

const percent = value => Number(value).toLocaleString('zh-CN', {minimumFractionDigits: 4, maximumFractionDigits: 4});

export function countryProportionEvidence(explorer) {
  const study = countryStudy(explorer, ['oa'], {population: 'A1', metric: 'proportion'});
  if (study.error) throw new Error(study.error);
  return {
    chart_id: 'country-distribution', slice_id: 'A1/all/proportion', metric_id: 'proportion',
    title: '国家内撤稿比例（%）', population_key: 'A1', status: 'ready',
    release_id: explorer.release_id, metric_observation_cutoff: explorer.oa_cutoff,
    scope: {population: 'A1', metric: 'proportion', work_types: explorer.work_types || ['article'], publication_year_range: [explorer.year_start, explorer.year_end], attribution: explorer.attribution},
    rows: study.ranked,
    limitations: [explorer.method, ...explorer.limitations,
      'n 为该国机构关联的筛选后撤稿标记论文数，N 为同国、同发表年份范围内全部合格发表论文数；比例为 n/N × 100%，不是该国占全球撤稿记录的份额。',
      '仅 n≥20 且 N≥1,000 的国家参与比例着色和排名；小基数保留真实数值，不置零。分母为零时比例不可计算。']
  };
}

export function countryProportionPlot(world, chart) {
  const byCode = mapRowsByCode(chart.rows);
  const {maximum, thresholds} = mapScale(chart.rows, 'proportion');
  const names = new Intl.DisplayNames(['zh-CN'], {type: 'region'});
  const represented = new Set(world.regions.map(region => mapCountryCode(region.code)));
  const unmapped = chart.rows.filter(row => !represented.has(row.id));
  const leaders = chart.rows.filter(row => mapStatus(row, 'proportion') === 'value').sort((first, second) => second.value - first.value || first.id.localeCompare(second.id)).slice(0, 3);
  const pattern = 'ppt-country-proportion-small';
  const smallBackground = 'repeating-linear-gradient(45deg,var(--map-missing),var(--map-missing) 3px,var(--text-2) 3px,var(--text-2) 4px)';
  function description(row) {
    const value = Number.isFinite(row.value) ? `${percent(row.value)}%` : '比例不可计算';
    return `${names.of(row.id)}：${value}；n=${number(row.numerator)} / N=${number(row.denominator)}${mapStatus(row, 'proportion') === 'small' ? '；小基数，不参与比例着色和排名' : ''}`;
  }
  return `<div class="map-layout"><svg class="ppt-world-map" viewBox="${world.viewBox}" role="img" aria-label="各国机构关联撤稿标记论文占该国合格发表论文的比例；仅 n≥20 且 N≥1,000 的国家着色"><title>OpenAlex 国家内已观测撤稿比例</title><defs><pattern id="${pattern}" width="6" height="6" patternUnits="userSpaceOnUse"><rect width="6" height="6" fill="var(--map-missing)"/><line x1="0" y1="0" x2="6" y2="6" stroke="var(--text-2)" stroke-width="1"/></pattern></defs>${world.regions.map(region => {
    const row = byCode.get(mapCountryCode(region.code)), status = mapStatus(row, 'proportion');
    const fill = status === 'value' ? mapColor(row.value, maximum) : status === 'small' ? `url(#${pattern})` : 'var(--map-missing)';
    return `<path d="${region.path}" data-country="${escape(region.code || '')}" data-status="${status}" fill="${fill}"><title>${escape(row ? description(row) : `${region.name}：无对应数值，不代表零`)}</title></path>`;
  }).join('')}</svg><div class="map-ranking"><h3>符合基数门槛的前三</h3>${leaders.map(row => `<p data-ranked-country="${escape(row.id)}">${escape(names.of(row.id))}<strong>${percent(row.value)}<small>%</small></strong><small>n=${number(row.numerator)}<br/>N=${number(row.denominator)}</small></p>`).join('')}<p class="small-print">按国家内比例排序<br/>不是全球撤稿份额</p></div></div><div class="map-legend"><span><i style="background:${MAP_COLORS[0]}"></i>0%</span>${maximum > 0 ? thresholds.map((upper, index) => `<span><i style="background:${MAP_COLORS[index + 1]}"></i>(${index ? percent(thresholds[index - 1]) : '0'}, ${percent(upper)}]%</span>`).join('') : ''}<span><i style="background:${smallBackground}"></i>小基数（含已观测 0）</span><span><i style="background:var(--map-missing)"></i>无数据或比例不可计算</span></div><p class="map-credit">${COUNTRY_MAP_GROUPING_NOTE}Natural Earth 本地底图；${unmapped.length} 个国家/地区未匹配到底图，仍保留在数据表。跨国论文各国计一次，不可跨国相加；国界仅作定位，不代表主权立场。</p>`;
}
