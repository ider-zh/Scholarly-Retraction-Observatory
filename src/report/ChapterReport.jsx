import React, {useEffect, useRef, useState} from 'react';
import {ReportHeader, ReportScope} from './ReportChrome.jsx';
import ReportGuide from './ReportGuide.jsx';
import CountryExplorer from './CountryExplorer.jsx';
import DisciplineExplorer from './DisciplineExplorer.jsx';
import TopicIndex from './TopicIndex.jsx';
import {EmbeddedAnalysis} from './TopicAnalysis.jsx';
import {CHAPTERS} from './chapter.js';
import {DISCIPLINE_SECTIONS, disciplineTaxonomy, sectionDisciplineHref} from './sections.js';
import {SOURCE_ORDER, SOURCE_NAMES, filterCharts, reportHref} from './sources.js';
import {selectChart, chartName, variantName} from './reader.js';
import './overview.css';
import './chapters.css';

export default function ChapterReport({route, manifest, current, error, pages, navigate, changeSources, headingRef, analysisRef, ChartCard, Export}) {
  const controlsRef = useRef(null), [share, setShare] = useState({url: '', text: ''});
  useEffect(() => {if (controlsRef.current) controlsRef.current.open = true;}, [route.page]);
  const [chapterNumber, question, introduction] = CHAPTERS[route.page];
  const available = filterCharts(current.charts || [], route.sources);
  const selected = selectChart(available, route.slice);
  const taxonomy = disciplineTaxonomy(route.page);
  const country = route.page === 'geography' && current.countryExplorer && !route.slice;
  const tree = (route.page === 'fields' || taxonomy) && current.explorer && !route.slice && route.view !== 'charts';
  const requiredSource = taxonomy && DISCIPLINE_SECTIONS[taxonomy].source;
  const sourceAvailable = !requiredSource || route.sources.includes(requiredSource);
  function openExplorer() {controlsRef.current.open = true; controlsRef.current.scrollIntoView({block: 'start', behavior: 'instant'}); controlsRef.current.querySelector('summary').focus({preventScroll: true});}
  async function copyLink() {const url = window.location.href; try {await navigator.clipboard.writeText(url); setShare({url, text: '已复制当前数据集、分析与学科路径链接。'});} catch {setShare({url, text: '无法自动复制，请复制地址栏中的完整链接。'});}}
  return <div className="snapshot-app report-publication report-chapter">
    <a className="report-skip" href={reportHref(route.page, route.sources)} onClick={event => {event.preventDefault(); headingRef.current?.focus();}}>跳到报告正文</a>
    <ReportHeader page={route.page} pages={pages} sources={route.sources}/>
    <main className="report-reading"><header className="report-opening"><p className="report-kicker">{chapterNumber} / {pages[route.page]}</p><h1 ref={headingRef} tabIndex={-1}>{question}</h1><p className="report-introduction">{introduction}</p><ReportScope sources={route.sources} manifest={manifest} openExplorer={openExplorer}/></header>
      {error || route.error ? <p role="alert" className="report-unavailable">{error || route.error}。未显示替代结果，请核对链接或重新加载。</p> : !current.charts ? <p role="status">正在验证并加载本章聚合数据…</p> : <section className="report-evidence" ref={analysisRef} tabIndex={-1} aria-label="当前分析">{!sourceAvailable ? <div className="report-unavailable" role="status"><h2>本章需要 {requiredSource === 'rw' ? 'Retraction Watch' : 'OpenAlex'} 数据</h2><p>当前来源选择不支持这套分类，没有展示其他体系的替代结果。</p><a href={sectionDisciplineHref(route.page, SOURCE_ORDER.filter(source => route.sources.includes(source) || source === requiredSource), route.explorerSelection)}>启用本章所需数据集</a></div> : country ? <CountryExplorer data={current.countryExplorer} sources={route.sources} selection={route.explorerSelection} navigate={navigate} hrefForStudy={(sources, selection) => sectionDisciplineHref('geography', sources, selection)}/> : tree ? <DisciplineExplorer data={current.explorer} sources={route.sources} selection={route.explorerSelection} navigate={navigate} fixedTaxonomy={taxonomy} hrefForStudy={(sources, selection) => sectionDisciplineHref(route.page, sources, selection)} editorial/> : selected ? <EmbeddedAnalysis key={`${route.page}/${route.sources.join(',')}/${route.slice}`} route={route} navigate={navigate} current={current} chart={selected} ChartCard={ChartCard} Export={Export}/> : <div className="report-unavailable"><h2>当前选择没有可用的分析</h2><p role="status">本章没有符合此数据集或深链接的已发布分析；不等于观测为零，也不会换成另一个来源的结果。</p><button onClick={openExplorer}>查看可用数据集与分析</button></div>}</section>}
      {manifest && <details className="report-methods"><summary>本章阅读方法、来源与版本</summary><ReportGuide page={route.page} charts={available}/><p>报告 {manifest.release_id}；OpenAlex {manifest.oa_snapshot_date} / RW {manifest.rw_snapshot_date}。</p><p>{manifest.source_acceptance_policy === 'retrospective-v1' ? '已接受回溯验证，但下载前清单与传输时间日志未保存；不补造这些历史证据。' : '来源核验记录见数据与方法。'}</p><p>联合选择不是两库并集；OpenAlex 标记与身份筛选存在 RW 来源依赖，不是独立验证。</p>{route.page === 'quality' ? <details><summary>完整来源与质量门槛</summary><pre>{JSON.stringify(manifest, null, 2)}</pre></details> : <a href={reportHref('quality', route.sources)}>查看数据与方法 →</a>}</details>}
      <details ref={controlsRef} className="report-explorer" open><summary>探索数据 · 本章数据专题</summary><TopicIndex section={route.page} charts={current.charts || []} sources={route.sources} explorer={current.explorer} countryExplorer={current.countryExplorer} ChartCard={ChartCard} Export={Export}/><div className="report-explorer-actions"><button onClick={copyLink}>复制当前章节链接</button></div><p role="status">{share.url === window.location.href ? share.text : ''}</p></details>
      <section className="report-next"><h2>继续阅读</h2><div>{Object.entries(pages).filter(([key]) => key !== route.page).filter(([key]) => ['overview', 'time', 'concepts', 'quality'].includes(key)).slice(0, 3).map(([key, label]) => <a key={key} href={reportHref(key, route.sources)}><strong>{label} →</strong></a>)}</div></section><footer>仅导出已发布的聚合单元。署名、机构、国家或来源关联不等于不端责任。</footer>
    </main>
  </div>;
}
