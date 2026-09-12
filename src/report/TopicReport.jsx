import React, {useEffect, useRef} from 'react';
import {ReportHeader} from './ReportChrome.jsx';
import {TopicAnalysis} from './TopicAnalysis.jsx';
import {topicCatalog, topicHref} from './topics.js';
import {SOURCE_NAMES, SOURCE_ORDER, reportHref} from './sources.js';
import './overview.css';
import './chapters.css';
import './topics.css';

export default function TopicReport({route, manifest, current, error, pages, navigate, ChartCard, Export}) {
  const heading = useRef(null);
  useEffect(() => {heading.current?.focus({preventScroll: true}); window.scrollTo({top: 0});}, [route.page, route.topic]);
  const topic = topicCatalog(current.charts || [], route.sources, current.explorer, current.countryExplorer).find(item => item.id === route.topic);
  function changeSources(source) {const sources = route.sources.includes(source) ? route.sources.filter(item => item !== source) : SOURCE_ORDER.filter(item => route.sources.includes(item) || item === source); navigate(topicHref(route.page, route.topic, sources, route.slice, route.explorerSelection));}
  return <div className="snapshot-app report-publication report-chapter report-topic"><a className="report-skip" href="#topic-heading" onClick={event => {event.preventDefault(); heading.current?.focus();}}>跳到专题正文</a><ReportHeader page={route.page} pages={pages} sources={route.sources}/><main className="report-reading"><nav className="topic-breadcrumb" aria-label="数据专题路径"><a href={reportHref(route.page, route.sources)}>{pages[route.page]}</a> / 数据专题 / {topic?.title || route.topic}</nav><header className="report-opening"><p className="report-kicker">独立数据专题 · 不替换原章节</p><h1 id="topic-heading" ref={heading} tabIndex={-1}>{topic?.title || '数据专题'}</h1><p className="report-introduction">{topic?.question}</p><p className="snapshot-caption">可用来源：{route.sources.map(source => SOURCE_NAMES[source]).join(' + ')}；联合选择不是两库并集。{manifest && `OpenAlex ${manifest.oa_snapshot_date} / RW ${manifest.rw_snapshot_date} · 版本 ${manifest.release_id}`}</p></header>
      <details className="report-methods"><summary>调整专题可用来源</summary><fieldset><legend>允许使用的数据集</legend>{SOURCE_ORDER.map(source => <label key={source}><input type="checkbox" checked={route.sources.includes(source)} disabled={route.sources.length === 1 && route.sources.includes(source)} onChange={() => changeSources(source)}/>{SOURCE_NAMES[source]}</label>)}</fieldset><p>移除当前分析所需的来源后，不自动替换为另一份数据；请重新选择可用研究总体。</p></details>
      <TopicAnalysis route={route} current={current} error={error} navigate={navigate} ChartCard={ChartCard} Export={Export}/>
      <footer><a href={reportHref(route.page, route.sources)}>返回{pages[route.page]}章节</a> · 仅使用已发布聚合；原章节标签页保持原位。</footer>
    </main></div>;
}
