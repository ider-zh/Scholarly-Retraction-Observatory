import React, {useEffect, useRef, useState} from 'react';
import {Figure} from './ReportFigure.jsx';
import {annualSeries} from './topics.js';
import {plotRows, lineSegments} from './chartGeometry.js';
import {chapterFinding, chapterEvidence} from './chapter.js';
import {number, chartMethod} from './reader.js';

export default function AnnualComparison({charts, Export}) {
  const series = annualSeries(charts), canvas = useRef(null);
  const [width, setWidth] = useState(800), [visible, setVisible] = useState(['published', 'retracted']);
  const [hovered, setHovered] = useState(null), [pinned, setPinned] = useState(null);
  useEffect(() => {if (!canvas.current) return; const observer = new ResizeObserver(entries => setWidth(Math.max(300, Math.min(900, entries[0].contentRect.width)))); observer.observe(canvas.current); return () => observer.disconnect();}, []);
  const prepared = series.map(chart => ({chart, basis: chart.scope.date_basis, label: chart.scope.date_basis === 'published' ? '按发表年' : '按撤稿年', color: chart.scope.date_basis === 'published' ? '#176b73' : '#a45125', rows: plotRows(chart)}));
  const active = prepared.filter(item => visible.includes(item.basis));
  const years = [...new Set(prepared.flatMap(item => item.rows.map(row => row.year)))].sort((first, second) => first - second);
  if (!years.length) return <p role="status">这组年度分析没有可绘制的已发布数值；未填补为零。</p>;
  const left = 66, right = width - 20, top = 32, bottom = 290, height = 350;
  const maximum = Math.ceil(Math.max(1, ...prepared.flatMap(item => item.rows.map(row => row.value))) / 4) * 4;
  const horizontal = year => left + (right - left) * (year - years[0]) / (years.at(-1) - years[0] || 1);
  const vertical = value => bottom - (bottom - top) * value / maximum;
  const selected = pinned ?? hovered;
  function toggle(basis) {setVisible(current => current.includes(basis) ? current.filter(item => item !== basis) : [...current, basis]); setPinned(null); setHovered(null);}
  function keyPoint(event, year) {
    if (event.key === 'Enter' || event.key === ' ') {event.preventDefault(); setPinned(current => current === year ? null : year);}
    if (event.key === 'Escape') {setPinned(null); setHovered(null);}
    if (['ArrowLeft', 'ArrowRight'].includes(event.key)) {event.preventDefault(); const points = [...event.currentTarget.ownerSVGElement.querySelectorAll('[data-annual-point]')]; const next = points[points.indexOf(event.currentTarget) + (event.key === 'ArrowLeft' ? -1 : 1)]; next?.focus();}
  }
  return <article className="topic-annual-comparison" data-topic-analysis="annual-counts">
    <div className="report-finding"><h2>两种年份，同一批 RW 原论文</h2>{active.map(item => <p className="report-finding-text" key={item.basis}><strong>{item.label}：</strong>{chapterFinding(item.chart)}</p>)}</div>
    <Figure kicker="对比图 · RW 撤稿原论文" title="发表年与撤稿年的年度数量" subtitle="同一横轴、同一计数单位；实线是发表年，虚线是撤稿年，不相加。" caption={<figcaption className="report-caption">计数单位：篇；观察截至 {series[0].metric_observation_cutoff}。两条线分别按原论文发表年与首次有效撤稿年分组；同一横坐标不代表同一批论文，也不是“当年发表、当年撤稿”的比率。空心点为未完整年度；缺失年份不补零，缺口不连线。隐藏序列只影响展示，不改纵轴、原始表或导出。</figcaption>} dataTools={<details className="report-data-table"><summary>查看两条序列的完整数据与导出</summary>{prepared.map(item => <section key={item.basis} aria-label={`${item.label}原始数据`}><h3>{item.label}</h3><div className="snapshot-table" tabIndex={0} role="region" aria-label={`${item.label}完整年度表`}><table><caption>{item.chart.chart_id}/{item.chart.slice_id} · {item.chart.metric_id} · {item.chart.metric_observation_cutoff}</caption><thead><tr><th>年份</th><th>论文数 n</th><th>原切片比较基数 N</th><th>年度状态</th></tr></thead><tbody>{item.chart.rows.map(row => <tr key={row.id}><th scope="row">{row.year}</th><td>{number(row.numerator)}</td><td>{number(row.denominator)}</td><td>{row.partial ? '未完整' : '已发布'}</td></tr>)}</tbody></table></div><Export chart={item.chart}/></section>)}</details>}>
      <fieldset className="topic-series-legend"><legend>显示的时间序列（至少保留一条）</legend>{prepared.map(item => <label key={item.basis}><input type="checkbox" checked={visible.includes(item.basis)} disabled={visible.length === 1 && visible.includes(item.basis)} onChange={() => toggle(item.basis)}/><span className={`topic-series-line ${item.basis}`} aria-hidden="true"/>{item.label}</label>)}</fieldset>
      <p className="snapshot-caption">悬停、聚焦或轻触数据点查看同年两种计数；Enter 锁定，Esc 取消，左右方向键切换点。</p>
      <div ref={canvas} className="topic-annual-canvas"><svg viewBox={`0 0 ${width} ${height}`} role="group" aria-label="RW 发表年与撤稿年双序列图" onPointerMove={event => {if (pinned != null) return; const bounds = event.currentTarget.getBoundingClientRect(); const position = (event.clientX - bounds.left) * width / bounds.width; setHovered(years.reduce((best, year) => Math.abs(horizontal(year) - position) < Math.abs(horizontal(best) - position) ? year : best));}} onPointerLeave={() => setHovered(null)}>
        {[0, 1, 2, 3, 4].map(index => <g key={index}><line x1={left} x2={right} y1={vertical(maximum * index / 4)} y2={vertical(maximum * index / 4)} stroke="#dce5e7" strokeDasharray="3 4"/><text x={left - 8} y={vertical(maximum * index / 4) + 4} textAnchor="end">{number(maximum * index / 4)}</text></g>)}
        {[...new Set([years[0], years[Math.floor(years.length / 2)], years.at(-1)])].map(year => <text key={year} x={horizontal(year)} y={bottom + 25} textAnchor={year === years[0] ? 'start' : year === years.at(-1) ? 'end' : 'middle'}>{year}</text>)}<text x={left} y={18}>篇</text><text x={(left + right) / 2} y={height - 12} textAnchor="middle">日历年份（两种不同分组依据）</text>
        {selected != null && <line x1={horizontal(selected)} x2={horizontal(selected)} y1={top} y2={bottom} stroke="#8d9da5" strokeDasharray="3 4"/>}
        {active.map(item => <g key={item.basis}>{lineSegments(item.rows).map(segment => <polyline key={segment[0].id} points={segment.map(row => `${horizontal(row.year)},${vertical(row.value)}`).join(' ')} fill="none" stroke={item.color} strokeWidth="2.5" strokeDasharray={item.basis === 'retracted' ? '7 4' : undefined}/>)}{item.rows.map(row => <circle key={row.id} data-annual-point={`${item.basis}/${row.id}`} role="button" tabIndex={0} aria-label={`${item.label} ${row.year}：${number(row.value)} 篇`} aria-pressed={pinned === row.year} cx={horizontal(row.year)} cy={vertical(row.value)} r={selected === row.year ? 6 : 4} fill={row.partial ? '#fff' : item.color} stroke={item.color} strokeWidth="2" onFocus={() => {setPinned(null); setHovered(row.year);}} onClick={() => setPinned(current => current === row.year ? null : row.year)} onKeyDown={event => keyPoint(event, row.year)}/>)}</g>)}
      </svg></div>
      <div className="topic-comparison-detail" role="status" aria-live="polite">{selected == null ? '选择一个年份，查看两条序列各自的计数和比较基数。' : <><strong>{pinned != null ? '已锁定 · ' : ''}{selected} 年</strong>{active.map(item => {const row = item.chart.rows.find(row => row.year === selected); return <p key={item.basis}>{item.label}：{row?.value == null ? '未发布 / 缺失，不当作零' : `${number(row.value)} 篇 · n=${number(row.numerator)} / N=${number(row.denominator)}${row.partial ? ' · 年度未完整' : ''}`}</p>;})}{pinned != null && <button onClick={() => {setPinned(null); setHovered(null);}}>取消锁定</button>}</>}</div>
    </Figure>
    <details className="report-methods"><summary>两条序列的范围、方法与证据</summary>{prepared.map(item => <section key={item.basis}><h3>{item.label}</h3>{chartMethod(item.chart).map(text => <p key={text}>{text}</p>)}{item.chart.limitations.map(text => <p key={text}>{text}</p>)}{item.chart.outside_display_range_works != null && <p>另有 {number(item.chart.outside_display_range_works)} 篇早于展示年份，仍保留在总体内。</p>}<pre>{JSON.stringify(chapterEvidence(item.chart, 'time'), null, 2)}</pre></section>)}</details>
  </article>;
}
