import React, {useEffect, useRef, useState} from 'react';
import {Figure} from './ReportFigure.jsx';
import MetricChoices from './MetricChoices.jsx';
import {number} from './reader.js';
import {conceptComparison, comparisonSegments} from './conceptComparison.js';
import './concept-comparison.css';

const COLORS = ['#176b73', '#a45125', '#53679a', '#76633b', '#8e4b77', '#3f7652', '#7d5555', '#415d73'];

function ComparisonFigure({data, study, series, parent, selected, onSelect, sourceLabel}) {
  const [hovered, setHovered] = useState(''), [year, setYear] = useState(data.year_end - 1);
  const canvas = useRef(null);
  const [width, setWidth] = useState(1000);
  useEffect(() => {
    if (!canvas.current) return;
    const observer = new ResizeObserver(entries => setWidth(Math.max(280, Math.min(1000, entries[0].contentRect.width))));
    observer.observe(canvas.current);
    return () => observer.disconnect();
  }, []);
  const active = hovered || selected;
  const metric = study.metric === 'proportion' ? 'proportion' : 'count';
  const proportion = metric === 'proportion';
  const valueOf = row => proportion ? row?.value : row?.count;
  const eligible = row => Number.isFinite(valueOf(row)) && (!proportion || row.ranking_eligible);
  const format = value => Number.isFinite(value) ? proportion ? `${value.toFixed(4)}%` : `${number(value)} 篇` : '缺失';
  const highest = Math.max(0, ...series.flatMap(item => item.rows.filter(eligible).map(valueOf)));
  const hasEligible = series.some(item => item.rows.some(eligible));
  const maximum = proportion ? Math.max(.0001, Math.ceil(highest / .0001) * .0001) : Math.max(4, Math.ceil(highest / 4) * 4);
  const horizontal = value => 65 + (width - 90) * (value - data.year_start) / (data.year_end - data.year_start || 1);
  const vertical = value => 320 - 275 * value / maximum;
  const title = `${parent ? `${parent.label}：全部二级学科` : '全部主学科'}：${proportion ? '学科内撤稿比例' : '撤稿记录论文数'}随发表年变化`;
  const color = index => COLORS[index % COLORS.length];
  const dash = index => ['', '7 4', '2 3'][Math.floor(index / COLORS.length) % 3];
  function download() {
    const rows = series.flatMap(item => item.rows.map(row => ({release_id: data.release_id, taxonomy: 'concepts', population: study.population, source: sourceLabel, metric, date_basis: 'original_publication_year', navigation_parent: parent?.id || '', concept_id: item.id, concept_label: item.label, ...row, unit: proportion ? 'percent' : 'works', oa_cutoff: data.oa_cutoff, rw_cutoff: data.rw_cutoff, taxonomy_scan_sha256: data.provenance.taxonomy_scan_sha256, concept_tree_sha256: data.provenance.concept_tree_sha256})));
    if (!rows.length) return;
    const columns = Object.keys(rows[0]);
    const quote = value => '"' + String(value ?? '').replace(/^[=+@\-\t\r]/, "'$&").replaceAll('"', '""') + '"';
    const csv = [columns, ...rows.map(row => columns.map(column => row[column]))].map(row => row.map(quote).join(',')).join('\r\n');
    const url = URL.createObjectURL(new Blob(['\ufeff' + csv], {type: 'text/csv;charset=utf-8'}));
    const link = document.createElement('a'); link.href = url; link.download = `concept-comparison-${study.population}-${metric}-${parent ? parent.id.split('/').at(-1) : 'roots'}.csv`; link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  return <section className="concept-comparison" data-comparison-level={parent ? 'children' : 'roots'} data-parent={parent?.id || ''} data-population={study.population} data-metric={metric}>
    <Figure kicker={`年度${proportion ? '学科内比例' : '数量'}对比 · ${sourceLabel}`} title={title} subtitle={`同一坐标轴比较全部 ${series.length} 个${parent ? '二级学科' : '主学科'}，不按 Top N 截取。${proportion ? '比例 = 该学科同发表年撤稿记录论文数 n / 合格发表论文数 N × 100%。' : '按原论文发表年统计记录论文数。'}`} caption={<figcaption className="report-caption">Concepts 旧标签 · {sourceLabel} · {study.population}；横轴为原论文发表年，不是撤稿年，纵轴为{proportion ? '学科内撤稿比例（%），不是学科占撤稿样本的份额。n < 20 或 N < 1,000 的小基数点不绘制、不跨越连线，原值与 n/N 保留在数据表和导出中。近期发表队列随访更短' : '记录论文数（篇）'}。截至 {data.oa_cutoff}；末年空心点表示未完整年度，缺失不补零、不跨缺口连线。多标签可能重叠，不堆叠、不相加。{parent && '父子关系仅用于历史分类导航；子学科数值为该子概念的全部记录，不是与所选主学科的交集。'}标签缺失组不作为真实学科画线，仍保留在原有统计中。高亮不改变坐标轴、数据表或导出。</figcaption>}>
      {!series.length ? <p role="status">此分支没有已发布的二级学科序列。</p> : <>
        <p className="snapshot-caption">{parent ? '点击图例突出一条曲线，再次点击取消。' : '点击曲线或图例选择主学科，下方比较其二级学科。'}悬停或聚焦图例可辨认曲线；调节年份查看同年各学科数值。</p>
        {!hasEligible && <p role="status">当前分支没有符合绘图条件的年度数据；缺失、无分母或小基数记录仍可在下方数据表中核对。</p>}
        <div ref={canvas} hidden={!hasEligible} className="concept-comparison-canvas" role="region" aria-label={title} tabIndex={0}>
          <svg viewBox={`0 0 ${width} 380`} role="img" aria-label={title} onPointerMove={event => {const bounds = event.currentTarget.getBoundingClientRect(); const position = (event.clientX - bounds.left) * width / bounds.width; setYear(Math.max(data.year_start, Math.min(data.year_end, Math.round(data.year_start + (position - 65) / (width - 90) * (data.year_end - data.year_start)))));}}>
            {[0, 1, 2, 3, 4].map(index => {const value = maximum * index / 4; return <g key={index}><line x1="65" x2={width - 25} y1={vertical(value)} y2={vertical(value)} stroke="#dce5e7"/><text x="55" y={vertical(value) + 5} textAnchor="end">{proportion ? value.toFixed(4) : number(value)}</text></g>;})}
            <text x="65" y="25">{proportion ? '%' : '篇'}</text>{[data.year_start, Math.round((data.year_start + data.year_end) / 2), data.year_end].map(value => <text key={value} x={horizontal(value)} y="345" textAnchor={value === data.year_start ? 'start' : value === data.year_end ? 'end' : 'middle'}>{value}</text>)}<text x={(width + 40) / 2} y="374" textAnchor="middle">原论文发表年</text>
            {series.map((item, index) => <g key={item.id} data-concept-series={item.id} opacity={active && active !== item.id ? .16 : 1} onPointerEnter={() => setHovered(item.id)} onPointerLeave={() => setHovered('')} onClick={() => onSelect(item.id)}>
              <title>{item.label}；点击图例也可选择</title>
              {comparisonSegments(item.rows, metric).map(segment => <polyline key={segment[0].year} points={segment.map(row => `${horizontal(row.year)},${vertical(valueOf(row))}`).join(' ')} fill="none" stroke={color(index)} strokeWidth={active === item.id ? 3.5 : 1.7} strokeDasharray={dash(index)}/>) }
              {item.rows.filter((row, index) => eligible(row) && (row.year === year || row.partial || (!eligible(item.rows[index - 1]) && !eligible(item.rows[index + 1])))).map(row => <circle key={row.year} data-year={row.year} cx={horizontal(row.year)} cy={vertical(valueOf(row))} r={active === item.id ? 4.5 : 2.5} fill={row.partial ? '#fff' : color(index)} stroke={color(index)}/>) }
            </g>)}
          </svg>
        </div>
        <label className="concept-comparison-year">查看年份：{year}{year === data.year_end ? '（未完整）' : ''}<input aria-label={parent ? '二级学科对比年份' : '主学科对比年份'} type="range" min={data.year_start} max={data.year_end} value={year} onChange={event => setYear(Number(event.target.value))}/></label>
        <div className="concept-comparison-legend" aria-label={parent ? '二级学科曲线图例' : '选择主学科以比较二级学科'}>{series.map((item, index) => {const row = item.rows.find(row => row.year === year); return <button type="button" key={item.id} data-concept-choice={item.id} aria-pressed={selected === item.id} onClick={() => onSelect(item.id)} onPointerEnter={() => setHovered(item.id)} onPointerLeave={() => setHovered('')} onFocus={() => setHovered(item.id)} onBlur={() => setHovered('')}><svg viewBox="0 0 28 8" aria-hidden="true"><line x1="0" x2="28" y1="4" y2="4" stroke={color(index)} strokeWidth="3" strokeDasharray={dash(index)}/></svg><span>{item.label}</span><strong>{format(valueOf(row))}{proportion && <small>n/N：{number(row?.numerator)}/{number(row?.denominator)}{Number.isFinite(valueOf(row)) && !eligible(row) && ' · 小基数，不绘制'}</small>}</strong></button>;})}</div>
        <details className="report-data-table"><summary>查看全部对比数据与导出</summary><button type="button" onClick={download}>导出全部对比序列 CSV</button><div className="snapshot-table" role="region" tabIndex={0} aria-label="各学科完整年度数据"><table><caption>{title}；单位：{proportion ? '%' : '篇'}；空值显示为缺失。</caption><thead><tr><th scope="col">学科</th><th scope="col">发表年</th><th scope="col">{proportion ? '学科内撤稿比例' : '记录论文数'}</th>{proportion && <><th scope="col">撤稿记录论文数 n</th><th scope="col">合格发表论文数 N</th><th scope="col">绘图状态</th></>}<th scope="col">年度状态</th></tr></thead><tbody>{series.flatMap(item => item.rows.map(row => <tr key={`${item.id}/${row.year}`}><th scope="row">{item.label}</th><td>{row.year}</td><td>{format(valueOf(row))}</td>{proportion && <><td>{number(row.numerator)}</td><td>{number(row.denominator)}</td><td>{eligible(row) ? '绘制' : Number.isFinite(valueOf(row)) ? '小基数，不绘制' : '缺失或无分母，不绘制'}</td></>}<td>{row.partial ? '未完整' : '完整年度'}</td></tr>))}</tbody></table></div></details>
      </>}
    </Figure>
  </section>;
}

export default function ConceptComparison({data, study, onSelectRoot, onMetricChange, sourceLabel}) {
  const roots = conceptComparison(data, study);
  const parent = study.taxonomy.nodes.find(node => node.level === 0 && !node.navigation_only && (node.id === study.node.id || node.id === study.parent));
  const children = parent ? conceptComparison(data, study, parent.id) : [];
  const [highlighted, setHighlighted] = useState('');
  const childRef = useRef(null), pendingRoot = useRef(false);
  useEffect(() => {
    if (!pendingRoot.current || !parent) return;
    pendingRoot.current = false;
    const frame = requestAnimationFrame(() => childRef.current?.scrollIntoView({block: 'start', behavior: 'instant'}));
    return () => cancelAnimationFrame(frame);
  }, [parent?.id]);
  function chooseRoot(identifier) {
    if (identifier === parent?.id) childRef.current?.scrollIntoView({block: 'start', behavior: 'instant'});
    else pendingRoot.current = true;
    onSelectRoot(identifier);
  }
  return <div className="concept-comparisons">
    <MetricChoices value={study.metric === 'proportion' ? 'proportion' : 'count'} options={{count: '撤稿记录论文数', proportion: '学科内撤稿比例'}} onChange={onMetricChange} legend="全部学科年度对比指标"/>
    {!['count', 'proportion'].includes(study.metric) && <p className="snapshot-caption">此处的跨学科年度对比支持数量和学科内比例；当前显示数量，不沿用上方的样本份额或每万篇指标。</p>}
    <ComparisonFigure key={`${data.release_id}/${study.population}`} data={data} study={study} series={roots} selected={parent?.id || ''} onSelect={chooseRoot} sourceLabel={sourceLabel}/>
    <div ref={childRef} className="concept-comparison-child">{parent ? <ComparisonFigure key={`${data.release_id}/${study.population}/${parent.id}`} data={data} study={study} parent={parent} series={children} selected={children.some(child => child.id === highlighted) ? highlighted : ''} onSelect={identifier => setHighlighted(current => current === identifier ? '' : identifier)} sourceLabel={sourceLabel}/> : <p className="report-key-boundary">选择上图任一主学科，即可在这里比较它的全部二级学科年度曲线。</p>}</div>
  </div>;
}
