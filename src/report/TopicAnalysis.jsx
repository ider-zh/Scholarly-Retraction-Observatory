import React, {useId} from 'react';
import CountryExplorer from './CountryExplorer.jsx';
import DisciplineExplorer from './DisciplineExplorer.jsx';
import AnnualComparison from './AnnualComparison.jsx';
import {topicCatalog, topicHref, topicId, selectTopicChart, variantKey, topicDatasetLabel, topicVariantLabel, annualSeries} from './topics.js';
import {filterCharts, reportHref} from './sources.js';
import {parseReportRoute} from './routes.js';
import {disciplineTaxonomy} from './sections.js';
import './topics.css';

export function TopicAnalysis({route, current, error, navigate, ChartCard, Export}) {
  const controlId = useId();
  const topic = topicCatalog(current.charts || [], route.sources, current.explorer, current.countryExplorer).find(item => item.id === route.topic);
  const selected = topic && selectTopicChart(topic, route.sources, route.slice);
  const populations = topic ? [...new Map(topic.charts.map(chart => [chart.population_key, chart])).values()] : [];
  const active = selected || topic?.charts.find(chart => `${chart.chart_id}/${chart.slice_id}` === route.slice);
  const variants = topic?.charts.filter(chart => chart.population_key === active?.population_key) || [];
  const href = chart => topicHref(route.page, route.topic, route.sources, `${chart.chart_id}/${chart.slice_id}`);
  const annual = selected && topic.id === 'annual-counts' && annualSeries(topic.allowed).length === 2;
  const countryPopulation = selected?.population_key === 'C_D_over_D' ? 'C_D' : 'A1';

  return <div className="topic-analysis" onClick={event => {const link = event.target.closest('a[href^="#/snapshot/"]'); if (link && !event.ctrlKey && !event.metaKey && !event.shiftKey && !event.altKey) {event.preventDefault(); navigate(link.getAttribute('href'));}}}>
      {topic?.supersededBy && <p className="report-key-boundary">此旧版汇总入口已合并到<a href={topicHref('geography', 'countries', route.sources, '', {population: countryPopulation, metric: 'rate'})}>国家内撤稿比例与年度趋势</a>，可查看同口径地图和年度变化。这里保留原切片及导出以兼容旧链接；比例图按可排名国家的指标值降序显示。</p>}
      {error || route.error ? <p role="alert" className="report-unavailable">{error || route.error}。未展示替代结果。</p> : !current.charts ? <p role="status">正在校验专题聚合数据…</p> : !topic ? <p role="alert" className="report-unavailable">这个专题不存在；没有回退到其他分析。</p> : topic.countries ? route.slice ? <p role="alert">国家年度专题不接受 slice；请选择国家与指标。</p> : <CountryExplorer data={current.countryExplorer} sources={route.sources} selection={route.explorerSelection} navigate={navigate} hrefForStudy={(sources, selection) => topicHref('geography', 'countries', sources, '', selection)}/> : topic.tree ? route.slice ? <p role="alert">学科树专题不接受 slice；请使用 taxonomy、population、node、parent、metric。</p> : <DisciplineExplorer fixedTaxonomy={disciplineTaxonomy(route.page)} data={current.explorer} sources={route.sources} selection={route.explorerSelection} navigate={navigate} hrefForStudy={(sources, selection) => topicHref(route.page, 'discipline', sources, '', selection)} editorial/> : <>
        {!annual && (populations.length > 1 || variants.length > 1) && <section className="topic-controls" aria-label="图表数据口径"><fieldset><legend>本图研究总体（单选，不相加）</legend>{populations.map(candidate => {const target = topic.charts.find(chart => chart.population_key === candidate.population_key && (!active || variantKey(chart) === variantKey(active))); const enabled = target && filterCharts([target], route.sources).length > 0; return <label key={candidate.population_key}><input type="radio" name={`${controlId}-population`} value={candidate.population_key} checked={selected?.population_key === candidate.population_key} disabled={!enabled} onChange={() => navigate(href(target))}/>{topicDatasetLabel(candidate)}{!enabled && '（当前来源或统计范围不可用）'}</label>;})}</fieldset>{variants.length > 1 && <fieldset><legend>统计范围与方法（单选）</legend>{variants.map(chart => <label key={chart.slice_id}><input type="radio" name={`${controlId}-variant`} value={`${chart.chart_id}/${chart.slice_id}`} checked={selected?.slice_id === chart.slice_id} disabled={!filterCharts([chart], route.sources).length} onChange={() => navigate(href(chart))}/>{topicVariantLabel(chart)}</label>)}</fieldset>}</section>}
        {selected ? annual ? <AnnualComparison key={`${topic.id}/${route.sources.join(',')}`} charts={topic.allowed} Export={Export}/> : <ChartCard key={`${selected.chart_id}/${selected.slice_id}`} chart={selected} editorial section={route.page}/> : <p role="alert" className="report-unavailable">当前切片不属于此专题或所选来源。没有可用数值不等于零；请选择可用研究总体。</p>}
      </>}
  </div>;
}

export function EmbeddedAnalysis({route, current, chart, navigate, ChartCard, Export}) {
  const analysisRoute = {...route, topic: topicId(chart), slice: `${chart.chart_id}/${chart.slice_id}`};
  return <TopicAnalysis route={analysisRoute} current={current} navigate={href => {const next = parseReportRoute(href, {[route.page]: route.page}); navigate(reportHref(next.page, next.sources, next.slice));}} ChartCard={ChartCard} Export={Export}/>;
}
