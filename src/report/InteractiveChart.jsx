import React, {useEffect, useId, useRef, useState} from 'react';
import {chartName, number, UNITS} from './reader.js';
import {plotKind, plotRows, lineSegments} from './chartGeometry.js';

function axisLabel(chart, kind) {
  if (kind === 'scatter') return '全部发表论文数 N（对数刻度）';
  if (kind === 'control') return '撤稿记录月份';
  return {T4: '发表至撤稿的间隔（天）', E3: '正关联实体累计比例（%）', C1: '快照累计被引次数（log1p 刻度）', C2: '相对撤稿年度'}[chart.chart_id] || '年份（2000 年起）';
}

export default function InteractiveChart({chart}) {
  const kind = plotKind(chart), rows = plotRows(chart), descriptionId = useId();
  const canvasRef = useRef(null);
  const [containerWidth, setContainerWidth] = useState(800);
  const [hovered, setHovered] = useState(null), [pinned, setPinned] = useState(null);
  const [start, setStart] = useState(0), [end, setEnd] = useState(Math.max(0, rows.length - 1));
  useEffect(() => {
    if (!canvasRef.current) return;
    const observer = new ResizeObserver(entries => setContainerWidth(Math.max(300, Math.min(800, Math.round(entries[0].contentRect.width)))));
    observer.observe(canvasRef.current);
    return () => observer.disconnect();
  }, []);
  if (!rows.length) return <p>当前展示范围没有可绘制数据；完整聚合表仍可核对。</p>;
  const visible = rows.slice(start, end + 1), selected = visible.find(row => row.id === (pinned ?? hovered));
  const height = kind === 'interval' ? Math.max(320, visible.length * 42 + 100) : 350;
  const width = kind === 'interval' ? 800 : containerWidth;
  const left = kind === 'interval' ? 245 : width < 450 ? 64 : 76, right = width - 28, top = 30, bottom = height - 65;
  const minimumX = Math.min(...visible.map(row => row.position)), maximumX = Math.max(...visible.map(row => row.position));
  const maximumY = Math.max(1, ...visible.flatMap(row => [row.value, row.threshold || 0, row.p75 || 0]));
  const minimumY = Math.min(0, ...visible.map(row => row.value));
  const horizontal = row => kind === 'interval' ? left + (right - left) * row.value / maximumY : left + (right - left) * (row.position - minimumX) / (maximumX - minimumX || 1);
  const vertical = row => kind === 'interval' ? top + 24 + visible.indexOf(row) * 42 : bottom - (bottom - top) * (row.value - minimumY) / (maximumY - minimumY);
  const scaleY = value => bottom - (bottom - top) * (value - minimumY) / (maximumY - minimumY);
  const tickLabel = value => kind === 'scatter' ? number(Math.round(10 ** value)) : chart.chart_id === 'C1' ? number(Math.round(Math.expm1(value))) : kind === 'control' ? rows[Math.round(value)]?.label : ['T1', 'T3'].includes(chart.chart_id) ? String(value) : number(value);
  const unit = UNITS[visible[0].unit] || visible[0].unit;
  const selectPoint = row => {setHovered(row.id); setPinned(current => current === row.id ? null : row.id);};
  function move(event) {
    if (pinned) return;
    const bounds = event.currentTarget.getBoundingClientRect();
    const pointerX = (event.clientX - bounds.left) * width / bounds.width;
    const pointerY = (event.clientY - bounds.top) * height / bounds.height;
    const distance = row => kind === 'line' || kind === 'control' ? Math.abs(horizontal(row) - pointerX) : kind === 'interval' ? Math.abs(vertical(row) - pointerY) : Math.hypot(horizontal(row) - pointerX, vertical(row) - pointerY);
    const nearest = visible.reduce((best, row) => distance(row) < distance(best) ? row : best);
    setHovered(kind === 'scatter' && distance(nearest) > 45 ? null : nearest.id);
  }
  function keyPoint(event, row) {
    if (event.key === 'Enter' || event.key === ' ') {event.preventDefault(); selectPoint(row);}
    if (event.key === 'Escape') {setPinned(null); setHovered(null);}
    if (['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown'].includes(event.key)) {
      event.preventDefault();
      const direction = ['ArrowLeft', 'ArrowUp'].includes(event.key) ? -1 : 1;
      const next = Math.max(0, Math.min(visible.length - 1, visible.indexOf(row) + direction));
      event.currentTarget.ownerSVGElement.querySelectorAll('[data-chart-point]')[next]?.focus();
    }
  }
  function reset() {setStart(0); setEnd(rows.length - 1); setPinned(null); setHovered(null);}
  return <section className="snapshot-interactive-chart" aria-label={`${chartName(chart)}交互图表`}>
    <p id={descriptionId} className="snapshot-caption">悬停查看数值，点击或轻触锁定；键盘方向键切换数据点，Enter 锁定，Esc 取消。{kind === 'interval' ? '点是中位数，线段是中间一半样本（P25–P75），不是置信区间。' : '空心点表示未完整时期或不满足排名条件。'}</p>
    <div className={`snapshot-chart-canvas${kind === 'interval' ? ' snapshot-chart-wide' : ''}`} ref={canvasRef}><svg viewBox={`0 0 ${width} ${height}`} role="group" aria-label={chartName(chart)} aria-describedby={descriptionId} onPointerMove={move} onPointerLeave={() => setHovered(null)}>
      {Array.from({length: 5}, (_, index) => {
        const fraction = index / 4, value = minimumY + (maximumY - minimumY) * fraction;
        return kind === 'interval' ? <g key={index}><line x1={left + (right - left) * fraction} x2={left + (right - left) * fraction} y1={top} y2={bottom} className="snapshot-chart-grid"/><text x={left + (right - left) * fraction} y={bottom + 24} textAnchor="middle">{number(maximumY * fraction)}</text></g> : <g key={index}><line x1={left} x2={right} y1={scaleY(value)} y2={scaleY(value)} className="snapshot-chart-grid"/><text x={left - 12} y={scaleY(value) + 4} textAnchor="end">{number(value)}</text></g>;
      })}
      {kind !== 'interval' && [...new Set(Array.from({length: width < 500 ? 3 : 5}, (_, index) => kind === 'scatter' ? minimumX + (maximumX - minimumX) * index / (width < 500 ? 2 : 4) : visible[Math.round((visible.length - 1) * index / (width < 500 ? 2 : 4))].position))].map(position => <text key={position} x={horizontal({position})} y={bottom + 26} textAnchor={position === minimumX ? 'start' : position === maximumX ? 'end' : 'middle'}>{tickLabel(position)}</text>)}
      <text x={left} y={16}>{kind === 'interval' ? '中位数与四分位区间' : unit}</text>
      <text x={(left + right) / 2} y={height - 12} textAnchor="middle">{kind === 'interval' ? '发表至撤稿（年）' : axisLabel(chart, kind)}</text>
      {['line', 'control'].includes(kind) && lineSegments(visible).map(segment => <polyline key={segment[0].id} className="snapshot-chart-line" points={segment.map(row => `${horizontal(row)},${vertical(row)}`).join(' ')} fill="none" stroke="#197a86" strokeWidth="2.5"/>)}
      {kind === 'control' && <polyline points={visible.map(row => `${horizontal(row)},${scaleY(row.threshold)}`).join(' ')} fill="none" stroke="#965321" strokeDasharray="6 5"/>}
      {chart.chart_id === 'E3' && <line x1={left} y1={scaleY(minimumX)} x2={right} y2={scaleY(maximumX)} stroke="#697d88" strokeDasharray="6 5"/>}
      {chart.chart_id === 'C2' && minimumX <= 0 && maximumX >= 0 && <line x1={horizontal({position: 0})} x2={horizontal({position: 0})} y1={top} y2={bottom} stroke="#965321" strokeDasharray="6 5"/>}
      {selected && kind !== 'interval' && <line x1={horizontal(selected)} x2={horizontal(selected)} y1={top} y2={bottom} stroke="#799ba6" strokeDasharray="3 3" pointerEvents="none"/>}
      {visible.map(row => <g key={row.id}>
        {kind === 'interval' && <><text x={8} y={vertical(row) + 4}>{row.label.length > 28 ? row.label.slice(0, 27) + '…' : row.label}</text><line x1={left + (right - left) * row.p25 / maximumY} x2={left + (right - left) * row.p75 / maximumY} y1={vertical(row)} y2={vertical(row)} stroke="#197a86" strokeWidth={selected?.id === row.id ? 7 : 4}/></>}
        <circle data-chart-point={row.id} className="snapshot-chart-point" role="button" tabIndex={0} aria-pressed={pinned === row.id} aria-label={`${row.label}：${number(row.value)} ${unit}`} cx={horizontal(row)} cy={vertical(row)} r={selected?.id === row.id ? 8 : kind === 'scatter' ? 5 : 4} fill={row.partial || row.ranking_eligible === false ? '#fff' : row.review_flag ? '#965321' : '#197a86'} stroke={selected?.id === row.id ? '#142e40' : '#197a86'} strokeWidth={selected?.id === row.id ? 3 : 1.5} onFocus={() => {setPinned(null); setHovered(row.id);}} onBlur={() => setHovered(null)} onClick={() => selectPoint(row)} onKeyDown={event => keyPoint(event, row)}/>
      </g>)}
    </svg></div>
    <div className="snapshot-point-detail" role="status" aria-live="polite" aria-atomic="true">
      {selected ? <><strong>{pinned ? '已锁定 · ' : ''}{selected.label}</strong><span>{number(selected.value)} {unit}</span><span>计数 n：{number(selected.numerator)} · 比较基数 N：{number(selected.denominator)}</span>{kind === 'interval' && <span>P25：{number(selected.p25)} 年 · P75：{number(selected.p75)} 年</span>}{selected.threshold != null && <span>描述性阈值：{number(selected.threshold)} · {selected.partial ? '时期未完整，不执行标记' : selected.review_flag ? '超过阈值，需人工复核' : '未超过阈值'}</span>}{selected.partial && <span>未完整时期，不能直接与完整时期比较</span>}{selected.ranking_eligible === false && <span>未满足排名门槛，不参与排序结论</span>}</> : <span>将指针移到图上，或用 Tab 聚焦数据点，查看完整标签和统计基数。</span>}
      {pinned && <button onClick={() => {setPinned(null); setHovered(null);}}>取消锁定</button>}
    </div>
    {['line', 'control'].includes(kind) && rows.length > 2 && <div className="snapshot-chart-range"><label>显示起点 <input type="range" min="0" max={end} value={start} onChange={event => {setStart(Number(event.target.value)); setPinned(null); setHovered(null);}}/><output>{rows[start].label}</output></label><label>显示终点 <input type="range" min={start} max={rows.length - 1} value={end} onChange={event => {setEnd(Number(event.target.value)); setPinned(null); setHovered(null);}}/><output>{rows[end].label}</output></label><button onClick={reset}>重置图表范围</button><p className="snapshot-caption">仅缩放已发布的数据点；每点的分子、分母及完整数据导出不变。</p></div>}
    {kind === 'control' && <p className="snapshot-caption">棕色虚线是描述性复核阈值，不是因果判断或统计显著性界限。</p>}
    {chart.chart_id === 'E3' && <p className="snapshot-caption">虚线表示均等关联份额，不是拟合趋势。</p>}
    {chart.chart_id === 'C2' && <p className="snapshot-caption">竖虚线为撤稿事件年；各相对年度的合格论文基数不同，同日引用不硬分前后。</p>}
  </section>;
}
