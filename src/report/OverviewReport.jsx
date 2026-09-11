import React, {useRef, useState} from 'react';
import ReportGuide from './ReportGuide.jsx';
import ScreeningFigure from './ReportFigure.jsx';
import {chartName, chartMethod} from './reader.js';
import {SOURCE_NAMES, SOURCE_ORDER, filterCharts, reportHref} from './sources.js';
import {overviewNarrative, overviewScope, overviewSelection} from './overview.js';
import './overview.css';

export default function OverviewReport({route, manifest, charts, error, pages, navigate, changeSources, headingRef, analysisRef, ChartCard, Export}) {
  const explorerRef = useRef(null), [shareStatus, setShareStatus] = useState({url: '', text: ''});
  const available = filterCharts(charts || [], route.sources);
  const chart = !error && !route.error && charts ? overviewSelection(charts, route.sources, route.slice) : null;
  const narrative = overviewNarrative(chart);
  const isScreening = chart?.chart_id === 'screening' && chart.status === 'ready';
  const currentHref = reportHref('overview', route.sources, route.slice);
  const question = chart?.chart_id === 'work-types' ? '文献类型与发表来源，是一回事吗？' : chart?.chart_id === 'population-accounting' ? '两份数据库，各自记录了什么？' : route.sources.length === 1 && route.sources[0] === 'rw' ? 'Retraction Watch 记录了哪些撤稿论文？' : '一条撤稿标记，等于一篇撤稿论文吗？';
  function openExplorer() {
    explorerRef.current.open = true;
    explorerRef.current.scrollIntoView({block: 'start', behavior: 'instant'});
    explorerRef.current.querySelector('summary').focus({preventScroll: true});
  }
  async function copyLink() {
    const url = window.location.href;
    try {await navigator.clipboard.writeText(url); setShareStatus({url, text: '链接已复制，包含当前数据集与分析。'});}
    catch {setShareStatus({url, text: '无法自动复制，请复制浏览器地址栏中的完整链接。'});}
  }
  return <div className="snapshot-app report-overview">
    <a className="report-skip" href={currentHref} onClick={event => {event.preventDefault(); headingRef.current?.focus();}}>跳到报告正文</a>
    <header className="report-masthead"><a href={reportHref('overview', route.sources)} className="report-identity">Scholarly Retraction Observatory<span>学术撤稿观察 · 研究报告</span></a><details className="report-chapters"><summary>报告目录</summary><nav aria-label="快照报告章节">{Object.entries(pages).map(([key, label]) => <a key={key} href={reportHref(key, route.sources)} aria-current={key === 'overview' ? 'page' : undefined}>{label}</a>)}<a href="#">当前 RW 报告（原版）</a></nav></details></header>
    <main className="report-reading">
      <header className="report-opening"><p className="report-kicker">01 / 研究概览</p><h1 ref={headingRef} tabIndex={-1}>{question}</h1><p className="report-introduction">撤稿是已发表论文的撤回，不是投稿被拒。{route.sources.includes('oa') ? 'OpenAlex 是学术文献目录，一条文献记录（Work）可能是原论文，也可能是通知。先分清记录的对象，才能读懂数量。' : 'Retraction Watch（RW）记录原论文、通知、日期与原因；报告按原论文标识去重，不把同文的多条通知算作多篇论文。'}</p>
        <div className="report-scope-summary" aria-label="当前报告范围"><p><strong>当前报告：{route.sources.map(source => SOURCE_NAMES[source]).join(' + ') || '数据集选择无效'}</strong>{route.sources.length === 2 && <span> · 联合阅读，不是两库并集。</span>}</p>{manifest && <p>{route.sources.includes('oa') && <span>OpenAlex 快照 {manifest.oa_snapshot_date}</span>}{route.sources.includes('rw') && <span>RW 记录截至 {manifest.rw_snapshot_date}</span>}</p>}<button className="report-text-button" onClick={openExplorer}>更改数据集或分析 ↓</button></div>
      </header>
      {error || route.error ? <p className="report-unavailable" role="alert">{error || route.error}。未显示替代结果，请核对链接或重新加载。</p> : !charts ? <p role="status">正在验证并加载概览聚合数据…</p> : chart ? <section ref={analysisRef} tabIndex={-1} className="report-evidence" aria-label="当前研究发现" data-chart-id={chart.chart_id} data-slice-id={chart.slice_id} data-population={chart.population_key} data-metric={chart.metric_id}>
        <div className="report-finding"><p className="report-kicker">本项证据 · {overviewScope(chart)}</p><h2>{narrative.title}</h2><p className="report-finding-text">{narrative.finding}</p></div>
        {isScreening ? <><ScreeningFigure key={`${chart.release_id}/${chart.slice_id}`} chart={chart} Export={Export}/><p className="report-key-boundary"><strong>如何理解这个差别</strong>{narrative.boundary}</p><details className="report-methods"><summary>筛选如何完成？查看方法与限制</summary>{chartMethod(chart).map(text => <p key={text}>{text}</p>)}{chart.limitations.map(text => <p key={text}>{text}</p>)}<p>OpenAlex 的撤稿标记与原论文/通知身份筛选存在 RW 来源依赖，因此这不是两个独立来源的验证。观察截至 {chart.metric_observation_cutoff}；方法版本 {chart.methods_version}。</p><p>有效范围：{chart.quality.eligible_works?.toLocaleString('zh-CN') ?? '分别说明'} 条；本图相关信息缺失：{chart.quality.missing_works?.toLocaleString('zh-CN') ?? '未提供'} 条。</p></details></> : <ChartCard key={`${chart.chart_id}/${chart.slice_id}`} chart={chart}/>}
      </section> : <section className="report-unavailable" ref={analysisRef} tabIndex={-1}><h2>当前选择没有可用的概览图</h2><p role="status">{route.slice ? '这个深链接的分析不属于当前数据集，或尚未发布；不会自动改成另一个切片。' : '本章尚未发布只使用 RW 的概览图。这不等于没有撤稿，也不会用 OpenAlex 图表替代。'}</p><a href={reportHref('time', route.sources)}>阅读所选数据集的时间分析 →</a></section>}
      <details ref={explorerRef} className="report-explorer"><summary>探索数据 · 数据集与本章其他分析</summary><p>选择只切换已发布视图，不重算分母；当前可用 {available.length} 项。单选时隐藏依赖另一库的分析。</p><fieldset><legend>分析数据集（可多选，至少保留一个）</legend>{SOURCE_ORDER.map(source => <label key={source}><input type="checkbox" checked={route.sources.includes(source)} disabled={route.sources.length === 1 && route.sources.includes(source)} onChange={() => changeSources(source)}/>{SOURCE_NAMES[source]}</label>)}</fieldset><label className="report-analysis-select">选择本章分析<select aria-label="选择本章分析" disabled={!available.length} value={route.slice || (chart ? `${chart.chart_id}/${chart.slice_id}` : '')} onChange={event => navigate(reportHref('overview', route.sources, event.target.value))}>{available.map(item => <option key={`${item.chart_id}/${item.slice_id}`} value={`${item.chart_id}/${item.slice_id}`}>{chartName(item)}</option>)}{route.slice && !chart && <option value={route.slice}>当前数据集不可用的分析</option>}</select></label><div className="report-explorer-actions"><button onClick={() => navigate(reportHref('overview', route.sources))}>返回概览主图</button><button onClick={copyLink}>复制当前分析链接</button></div><p role="status">{shareStatus.url === window.location.href ? shareStatus.text : ''}</p></details>
      {manifest && <details className="report-methods"><summary>来源、术语与版本说明</summary><ReportGuide page="overview" charts={available}/><p>报告版本：{manifest.release_id}。OpenAlex {manifest.oa_snapshot_date} / RW {manifest.rw_snapshot_date}。</p><p>{manifest.source_acceptance_policy === 'retrospective-v1' ? '本地清单、文件和身份检查通过；项目接受回溯验证，但未保存下载前清单及传输时间日志，不能补造这些历史证据。' : '来源检查结果保存在报告的可复核清单中。'}</p><p>联合分析包含匹配子集与跨库核对，不是去重并集；不能将两个来源的总量相加。</p><a href={reportHref('quality', route.sources)}>查看完整数据与方法 →</a></details>}
      <section className="report-next"><h2>继续阅读</h2><div><a href={reportHref('time', route.sources)}><span>02 / 时间与观察期</span><strong>论文何时发表，何时被撤稿？</strong></a><a href={reportHref('fields', route.sources)}><span>03 / 学科与主题</span><strong>沿分类树比较主学科与子学科</strong></a><a href={reportHref('quality', route.sources)}><span>09 / 数据与方法</span><strong>哪些覆盖与匹配限制需要保留？</strong></a></div></section>
      <footer>本报告提供描述性统计，不判定研究不端或个人责任。仅导出已发布的聚合单元。</footer>
    </main>
  </div>;
}
