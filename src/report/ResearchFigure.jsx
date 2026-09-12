import React from 'react';
import AuthorIdentityNote from './AuthorIdentityNote.jsx';
import {Figure, FigureCaption} from './ReportFigure.jsx';
import {chartName, chartMethod, number, variantName} from './reader.js';
import {sourceProfile} from './sources.js';
import {chapterFinding, chapterEvidence, chapterMetricNote} from './chapter.js';

export default function ResearchFigure({chart, section, plot, controls, Export}) {
  const columns = [...new Set(chart.rows.flatMap(row => Object.keys(row)))];
  const method = chartMethod(chart);
  return <article className="report-research-figure" data-chart-id={chart.chart_id} data-slice-id={chart.slice_id} data-population={chart.population_key} data-metric={chart.metric_id}>
    <div className="report-finding"><p className="report-kicker">本项证据 · {sourceProfile(chart).label}</p><h2>{chart.question}</h2><p className="report-finding-text">{chapterFinding(chart)}</p></div>
    {chart.status === 'ready' ? <Figure kicker={`图 · ${sourceProfile(chart).label}`} title={chartName(chart)} subtitle={variantName(chart)} caption={<FigureCaption chart={chart}><span>{chapterMetricNote(chart)}</span><br/>{chart.quality.eligible_works == null ? '各项总体分别说明。' : `本图有效范围 ${number(chart.quality.eligible_works)}；相关信息缺失 ${number(chart.quality.missing_works)}。`}</FigureCaption>} dataTools={<details className="report-data-table"><summary>查看完整聚合数据与导出</summary><div className="snapshot-table" role="region" aria-label="完整聚合数据，可横向滚动" tabIndex={0}><table><caption>{chartName(chart)} · {chart.metric_id}；null 保留为未定义，不当作零。</caption><thead><tr>{columns.map(column => <th scope="col" key={column}>{column}</th>)}</tr></thead><tbody>{chart.rows.map(row => <tr key={row.id}>{columns.map(column => <td key={column}>{row[column] == null ? '未定义 / 不适用' : typeof row[column] === 'number' ? number(row[column]) : String(row[column])}</td>)}</tr>)}</tbody></table></div><Export chart={chart}/><details><summary>本图精确范围与证据标识</summary><pre>{JSON.stringify(chapterEvidence(chart, section), null, 2)}</pre></details></details>}>
      {['rw-author-names', 'author-top'].includes(chart.chart_id) && <AuthorIdentityNote/>}
      {controls && <details className="report-metric-controls"><summary>切换本图计数方式</summary>{controls}</details>}{plot}
      {chart.post_retraction_citation_ratio && <p className="report-caption">可判定引用边的撤稿后比例：{number(chart.post_retraction_citation_ratio.value == null ? null : 100*chart.post_retraction_citation_ratio.value)}%；n={number(chart.post_retraction_citation_ratio.numerator)} / N={number(chart.post_retraction_citation_ratio.denominator)}（明确之前 + 明确之后）。</p>}
      {chart.chart_id === 'C2' && <details><summary>每个相对年度的合格目标 N</summary><p>{chart.rows.map(row => `${row.label}: ${number(row.denominator)}`).join('；')}</p></details>}
      {chart.concept_coverage && <p className="report-caption">有该层旧标签 {number(chart.concept_coverage.known_works)} 篇，缺少标签 {number(chart.concept_coverage.missing_works)} 篇；涉及 {number(chart.concept_coverage.distinct_concepts)} 个概念，发布前 {number(chart.concept_coverage.displayed_concepts)} 个，图中显示前 15 个。</p>}
      {chart.outside_display_range_works != null && <p className="report-caption">另有 {number(chart.outside_display_range_works)} 篇早于展示年份，仍保留在总体中。</p>}
      {chart.quantiles && chart.chart_id !== 'T4' && <p className="report-caption">分位数：{Object.entries(chart.quantiles).map(([key, value]) => `${key}=${number(value)}`).join(' · ')}；分布统计，不是置信区间。</p>}
      {chart.gini != null && <p className="report-caption">Gini {number(chart.gini)}；HHI {number(chart.hhi)}。虚线表示均等关联份额，不是拟合趋势。</p>}
      {chart.zero_citation_works != null && <p className="report-caption">其中零引用 {number(chart.zero_citation_works)} 篇；这是观测零，不是引用字段缺失。</p>}
    </Figure> : <p role="status" className="report-unavailable">未发布有效图形：{chart.unavailable_reason}</p>}
    <p className="report-key-boundary"><strong>解释这张图时，需要保留的边界</strong>{chart.limitations[0] || sourceProfile(chart).description}</p>
    <details className="report-methods"><summary>计算方法、来源与完整限制</summary>{method.map(text => <p key={text}>{text}</p>)}<p>{sourceProfile(chart).description}</p>{chart.limitations.map(text => <p key={text}>{text}</p>)}<p>方法 {chart.methods_version}；报告版本 {chart.release_id}。OA {chart.oa_snapshot_date} / RW {chart.rw_snapshot_date}；本指标观察截止 {chart.metric_observation_cutoff}。</p>{chart.insights.length > 1 && <details><summary>其余已发布数据观察</summary>{chart.insights.slice(1).map(insight => <p key={insight.insight_id}>{insight.text}</p>)}</details>}{['citation_quality', 'static_count_audit', 'raw_to_family_mapping', 'association_summary'].filter(key => chart[key]).map(key => <details key={key}><summary>覆盖或映射审计：{key}</summary><pre>{JSON.stringify(chart[key], null, 2)}</pre></details>)}</details>
  </article>;
}
