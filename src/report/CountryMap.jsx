import React, {useId, useState} from 'react';
import world from './assets/world-map.json';
import {MAP_COLORS, mapStatus, mapScale, mapColor, mapCountryCode, mapRowsByCode, COUNTRY_MAP_GROUPING_NOTE} from './countryMap.js';
import {number, UNITS} from './reader.js';
import './country-map.css';

export default function CountryMap({rows, metric, selected, onSelect}) {
  const pattern = useId().replaceAll(':', ''), [hovered, setHovered] = useState(null);
  const byCode = mapRowsByCode(rows);
  const represented = new Set(world.regions.map(region => mapCountryCode(region.code)));
  const unmapped = rows.filter(row => !represented.has(row.id));
  const active = byCode.get(hovered) || byCode.get(mapCountryCode(selected));
  const {maximum, thresholds} = mapScale(rows, metric);
  const unit = UNITS[rows[0]?.unit] || '';
  function description(row) {return `${row.label}：${number(row.value)} ${UNITS[row.unit]}；n=${number(row.numerator)}，N=${number(row.denominator)}${mapStatus(row, metric) === 'small' ? '；小基数，不参与比例着色' : ''}`;}
  return <div className="country-map">
    <p className="snapshot-caption">悬停或聚焦查看 n/N；点击或按 Enter 选择国家，联动下方年度趋势。小国也可通过上方国家选择器访问。{COUNTRY_MAP_GROUPING_NOTE}</p>
    <svg viewBox={world.viewBox} role="group" aria-label="国家分布离线地图">
      <defs><pattern id={pattern} width="6" height="6" patternUnits="userSpaceOnUse"><rect width="6" height="6" fill="#f1eee6"/><path d="M0,0L6,6" stroke="#9a927d" strokeWidth="1"/></pattern></defs>
      {world.regions.map(region => {
        const row = byCode.get(mapCountryCode(region.code)), status = mapStatus(row, metric);
        return <path key={region.id} d={region.path} data-country={region.code || ''} data-status={status} role={row ? 'button' : undefined} tabIndex={row ? 0 : undefined} aria-label={row ? description(row) : undefined} aria-pressed={row ? mapCountryCode(selected) === row.id : undefined} fill={status === 'value' ? mapColor(row.value, maximum) : status === 'small' ? `url(#${pattern})` : '#e3e5e7'} onMouseEnter={() => setHovered(mapCountryCode(region.code))} onMouseLeave={() => setHovered(null)} onFocus={() => setHovered(mapCountryCode(region.code))} onBlur={() => setHovered(null)} onClick={() => row && onSelect(row.id)} onKeyDown={event => {if (row && ['Enter', ' '].includes(event.key)) {event.preventDefault(); onSelect(row.id);}}}><title>{row ? description(row) : `${region.name}：没有可对应的已发布数值，不代表零`}</title></path>;
      })}
    </svg>
    <div className="country-map-legend" aria-label="地图色阶"><span><i style={{background: MAP_COLORS[0]}}/>0 {unit}</span>{maximum > 0 && thresholds.map((value, index) => <span key={index}><i style={{background: MAP_COLORS[index+1]}}/>{index ? number(thresholds[index-1]) : '0'}–{number(value)} {unit}</span>)}{metric !== 'count' && <span><i className="country-map-small"/>小基数，不参与比例着色</span>}<span><i style={{background: '#e3e5e7'}}/>无数据或无法对应</span></div>
    <p className="country-map-detail" role="status">{active ? description(active) : '选择国家查看其统计值。'}</p>
    <p className="snapshot-caption">线性色阶按当前总体与指标更新，跨图颜色不可直接比较；面积不表示论文数量。比例仅对 n≥20 且 N≥1,000 的国家着色，小基数的真实数值仍在详情与表中保留。地图不受条形图搜索或前 N 项影响。</p>
    <details><summary>底图来源与未显示地区（{unmapped.length}）</summary><p>Natural Earth v5.1.2，1:110m 简化国界，Natural Earth 1 投影。本地矢量资源，无在线地图、瓦片或 API 请求。边界仅作定位示意，不用于判定署名国家，也不代表主权立场。</p><p>底图 TW 与 CN 均对应已去重合并的中国统计行；其余按 ISO_A2_EH 与已发布国家代码对应。未被该比例尺覆盖的国家/地区仍保留在选择器和完整表中：{unmapped.map(row => row.label).join('、') || '无'}。</p><a href="https://www.naturalearthdata.com/about/terms-of-use/" target="_blank" rel="noreferrer">Natural Earth 公共领域条款</a></details>
  </div>;
}
