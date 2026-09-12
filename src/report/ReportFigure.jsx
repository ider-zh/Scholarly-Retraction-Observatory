import React, {useId, useState} from 'react';
import {number} from './reader.js';
import {overviewEvidence, screeningNote, screeningRows} from './overview.js';
import {isBroadChart} from './workPolicy.js';
import {chapterCaption} from './chapter.js';

export function FigureCaption({chart, children}) {
  return <figcaption className="report-caption"><p>{children}</p><p>{chart.chart_id === 'screening' ? `来源：OpenAlex 主体库 · 观察截至 ${chart.metric_observation_cutoff}。计数单位为独立文献记录；保留组对应${isBroadChart(chart) ? '宽口径文献候选' : '研究论文候选'}。图中比例为筛选构成，不是撤稿率。` : chapterCaption(chart)}</p></figcaption>;
}

export function Figure({title, subtitle, children, caption, dataTools, kicker = '图 1 · OpenAlex 筛选范围'}) {
  const titleId = useId();
  return <figure className="report-figure" aria-labelledby={titleId}><header><p className="report-figure-number">{kicker}</p><h2 id={titleId}>{title}</h2><p className="report-figure-subtitle">{subtitle}</p></header>{children}{caption}{dataTools}</figure>;
}

export default function ScreeningFigure({chart, Export}) {
  const [hovered, setHovered] = useState(null), [pinned, setPinned] = useState(null);
  const rows = screeningRows(chart), current = rows.find(row => row.id === (pinned || hovered));
  const descriptionId = useId();
  function keyRow(event, index) {
    if (event.key === 'Escape') {setPinned(null); setHovered(null);}
    if (['ArrowDown', 'ArrowUp', 'Home', 'End'].includes(event.key)) {
      event.preventDefault();
      const next = event.key === 'Home' ? 0 : event.key === 'End' ? rows.length - 1 : Math.max(0, Math.min(rows.length - 1, index + (event.key === 'ArrowDown' ? 1 : -1)));
      event.currentTarget.parentElement.querySelectorAll('[data-screening-row]')[next]?.focus();
    }
  }
  const dataTools = <details className="report-data-table"><summary>查看本图数据表与导出</summary><div className="snapshot-table" role="region" aria-label="筛选聚合数据表，可横向滚动" tabIndex={0}><table><caption>全部已发布筛选组；n 为本组记录数，N 为筛选前记录数。</caption><thead><tr><th scope="col">筛选结果</th><th scope="col">记录数 n</th><th scope="col">筛选前 N</th><th scope="col">占比（%）</th></tr></thead><tbody>{rows.map(row => <tr key={row.id}><th scope="row">{row.label}</th><td>{number(row.numerator)}</td><td>{number(row.denominator)}</td><td>{number(row.value)}</td></tr>)}</tbody></table></div><Export chart={chart}/><details><summary>本图精确范围与证据标识</summary><pre>{JSON.stringify(overviewEvidence(chart), null, 2)}</pre></details></details>;
  return <Figure title="哪些标记记录进入论文分析？" subtitle="各筛选结果占筛选前记录的比例（%）；每条记录只归入一组。" dataTools={dataTools} caption={<FigureCaption chart={chart}>分母 N = {number(chart.quality.eligible_works)} 条标记记录；比例 = 本组 n / N × 100%。深色为保留组，其余按比例降序。所有组别互斥，共同覆盖筛选前总体。</FigureCaption>}>
    <div className="report-screening-plot" aria-label="筛选构成条形图" aria-describedby={descriptionId}>
      <div className="report-bar-heading" aria-hidden="true"><span>筛选结果</span><span>占筛选前比例</span><span>记录数 · 比例</span></div>
      <div onPointerLeave={() => setHovered(null)}>{rows.map((row, index) => <button type="button" key={row.id} className={`report-screening-row${row.id === 'retained_A1' ? ' is-retained' : ''}`} data-screening-row={row.id} aria-pressed={pinned === row.id} aria-label={`${row.label}：${number(row.numerator)} 条，占 ${number(row.value)}%；分母 ${number(row.denominator)} 条`} onPointerEnter={() => setHovered(row.id)} onFocus={() => setHovered(row.id)} onBlur={() => setHovered(null)} onClick={() => setPinned(pinned === row.id ? null : row.id)} onKeyDown={event => keyRow(event, index)}>
        <span className="report-bar-label">{row.label}</span><span className="report-bar-track" aria-hidden="true"><span style={{width: row.value == null ? 0 : `${row.value}%`}}/></span><span className="report-bar-value">{number(row.numerator)}<small>{row.value == null ? '比例未定义' : number(row.value)+'%'}</small></span>
      </button>)}</div>
      <div className="report-bar-axis" aria-hidden="true"><span/><div>{[0, 25, 50, 75, 100].map(value => <span key={value}>{value}%</span>)}</div><span/></div>
    </div>
    <p id={descriptionId} className="report-chart-help">悬停、轻触或键盘聚焦查看分组说明；点击 / Enter 锁定，Esc 取消，方向键切换。数值始终直接标注。</p>
    <div className="report-bar-detail" role="status" aria-live="polite" aria-atomic="true">{current ? <><strong>{pinned ? '已锁定 · ' : ''}{current.label}</strong><span>n = {number(current.numerator)} / N = {number(current.denominator)}；{screeningNote(chart, current)}</span>{pinned && <button onClick={() => {setPinned(null); setHovered(null);}}>取消锁定</button>}</> : <span>{isBroadChart(chart) ? '深色组进入宽口径分析；标题、类型和身份冲突不单独导致排除。候选不等于已逐篇确认的原论文。' : '深色组进入默认论文分析，其余组留在来源核算中。标题疑似通知是规则筛查，不是逐篇裁定。'}</span>}</div>
  </Figure>;
}
