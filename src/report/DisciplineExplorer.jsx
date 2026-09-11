import React, {useEffect, useRef, useState} from 'react';
import InteractiveChart from './InteractiveChart.jsx';
import {number, UNITS} from './reader.js';
import {sourceProfile} from './sources.js';
import {availableStudies, resolveStudy, disciplineHref, disciplineCell, distributionRows, disciplineTimeChart, DISCIPLINE_METRICS} from './discipline.js';
import './discipline.css';

const POPULATION_LABELS = {B: 'RW 撤稿原论文', A1: 'OpenAlex 撤稿标记论文', C_D: 'RW × OpenAlex 匹配论文（截至 OA 快照）'};

function Download({data, study, rows, view}) {
  function download() {
    const scope = sourceProfile({chart_id: 'discipline', population_key: study.population});
    const records = rows.map(row => ({release_id: data.release_id, dataset: scope.label, population: study.population,
      taxonomy: study.taxonomy.id, selected_node: study.node.id, navigation_parent: study.parent, metric: study.metric,
      view, date_basis: 'original_publication_year', oa_cutoff: data.oa_cutoff, rw_cutoff: data.rw_cutoff,
      taxonomy_scan_sha256: data.provenance.taxonomy_scan_sha256, concept_tree_sha256: data.provenance.concept_tree_sha256, ...row}));
    const columns = [...new Set(records.flatMap(row => Object.keys(row)))];
    const quote = value => '"'+String(value ?? '').replace(/^[=+@\-\t\r]/, "'$&").replaceAll('"', '""')+'"';
    const text = [columns, ...records.map(row => columns.map(column => row[column]))].map(row => row.map(quote).join(',')).join('\r\n');
    const url = URL.createObjectURL(new Blob(['\ufeff'+text], {type: 'text/csv;charset=utf-8'}));
    const link = document.createElement('a'); link.href = url; link.download = `discipline-${study.taxonomy.id}-${study.population}-${study.node.id.replace(/[^a-zA-Z0-9-]/g, '-').slice(-30)}-${study.metric}-${view}.csv`; link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  return <button onClick={download} disabled={!rows.length}>导出{view === 'distribution' ? '分布' : '时间'}聚合 CSV</button>;
}

export default function DisciplineExplorer({data, sources, selection, navigate}) {
  const [search, setSearch] = useState(''), [limit, setLimit] = useState(20);
  const resultsRef = useRef(null);
  const study = resolveStudy(data, sources, selection), studies = availableStudies(data, sources);
  useEffect(() => {
    if (study.node?.id && study.node.id !== 'all' && window.matchMedia('(max-width: 1150px)').matches) resultsRef.current?.scrollIntoView({block: 'start', behavior: 'instant'});
  }, [study.node?.id]);
  function change(values) {
    const current = study.error ? {} : {taxonomy: study.taxonomy.id, population: study.population, metric: study.metric, node: study.node.id, parent: study.parent};
    navigate(disciplineHref(sources, {...current, ...values}));
  }
  if (study.error) return <section className="snapshot-card"><p role="alert">{study.error}</p><button onClick={() => navigate(disciplineHref(sources, {}))}>返回可用学科树</button></section>;
  const {taxonomy, node, population, parent, metric} = study;
  const profile = sourceProfile({chart_id: 'discipline', population_key: population});
  const roots = taxonomy.nodes.filter(candidate => candidate.level === 0);
  const activeParent = taxonomy.nodes.find(candidate => candidate.id === parent);
  const filter = search.trim().toLocaleLowerCase();
  const matches = candidate => !filter || candidate.label.toLocaleLowerCase().includes(filter) || candidate.id.toLowerCase().includes(filter);
  const rows = distributionRows(study), shown = rows.slice(0, limit), maximum = Math.max(...shown.map(row => row.value ?? 0), 1);
  const time = disciplineTimeChart(data, study), total = disciplineCell(taxonomy, node, population, metric, 0);
  const href = (candidate, parentId = '') => disciplineHref(sources, {taxonomy: taxonomy.id, population, metric, node: candidate.id, parent: parentId});
  return <section className="discipline-explorer" aria-label="两层学科分析">
    <div className="discipline-intro"><h2>按数据集与分类体系，逐层探索学科</h2><p>这里的“撤稿”指已发表论文的撤回记录，不是投稿被期刊拒收。先选研究总体，再从主学科进入子学科；分布与年度图随同一节点联动，不堆叠成数百张图。</p></div>
    <div className="discipline-selectors"><label>分类方法论 <select aria-label="分类方法论" value={taxonomy.id} onChange={event => {const next = studies.find(study => study.taxonomy.id === event.target.value); setSearch(''); change({taxonomy: next.taxonomy.id, population: next.populations.includes(population) ? population : next.populations[0], node: 'all', parent: '', metric: next.taxonomy.denominator === null && metric === 'rate' ? 'count' : metric});}}>{studies.map(study => <option key={study.taxonomy.id} value={study.taxonomy.id}>{study.taxonomy.label}</option>)}</select></label><label>研究总体 <select aria-label="研究总体" value={population} onChange={event => change({population: event.target.value})}>{studies.find(study => study.taxonomy.id === taxonomy.id).populations.map(population => <option key={population} value={population}>{POPULATION_LABELS[population]}</option>)}</select></label><label>查看指标 <select aria-label="查看指标" value={metric} onChange={event => change({metric: event.target.value})}>{Object.entries(DISCIPLINE_METRICS).map(([key, label]) => <option key={key} value={key} disabled={key === 'rate' && taxonomy.denominator === null}>{label}{key === 'rate' && taxonomy.denominator === null ? '（RW 无发文分母）' : ''}</option>)}</select></label></div>
    <div className={`snapshot-dataset-badge dataset-${profile.key}`}><strong>本组数据集：{profile.label}</strong><p>{POPULATION_LABELS[population]} · {taxonomy.label} · {taxonomy.levels.join(' → ')}</p><p>{profile.description}</p>{population === 'C_D' && <p>只纳入在 {data.oa_cutoff} 之前已被 RW 记录撤稿且通过匹配与原论文筛选的论文，以保持发表分母的观察截止一致；不是两库并集。</p>}</div>
    <details className="discipline-method" open><summary>如何计数、计算比率与理解层级</summary><p>{taxonomy.method}</p><p>{taxonomy.rate_policy}</p><p>“样本内覆盖比例” = 节点论文数 ÷ 所选总体论文数；年度图用同发表年的总体。多标签可重叠，不能把覆盖比例相加当作 100%。近期论文随访更短，低计数的比例不宜排名。</p>{taxonomy.id === 'concepts' && <p>快照的父级字段为空。本树使用官方 2023-11-06 V3 分类器的历史祖先链，19 个主学科与 284 个子学科可有多个父级。同一子学科在不同分支下是同一组统计，不是父学科条件下的交集；不推断缺失标签，也不把旧分类当作当前分类。</p>}<a href={taxonomy.reference} target="_blank" rel="noreferrer">查看分类方法来源</a></details>
    <div className="discipline-layout"><nav className="discipline-tree" aria-label="主学科与子学科索引"><h3>学科树</h3><label>搜索学科或 ID <input type="search" value={search} onChange={event => setSearch(event.target.value)} placeholder="例如 Medicine / Biology"/></label><a href={disciplineHref(sources, {taxonomy: taxonomy.id, population, metric, node: 'all'})} aria-current={node.id === 'all' ? 'true' : undefined}>全部主学科 · {number(taxonomy.counts[population][0])} 篇</a>{roots.filter(root => matches(root) || taxonomy.nodes.some(child => child.parents.includes(root.id) && matches(child))).map(root => {
      const children = taxonomy.nodes.filter(child => child.parents.includes(root.id));
      return <details key={root.id} open={Boolean(filter) || node.id === root.id || parent === root.id}><summary>{root.label} <small>{children.length} 个子学科</small></summary>{!root.navigation_only && <a href={href(root)} aria-current={node.id === root.id ? 'true' : undefined}>查看主学科 · {number(root.counts[population][0])} 篇</a>}{children.filter(child => matches(root) || matches(child)).map(child => <a key={child.id} href={href(child, root.id)} aria-current={node.id === child.id && parent === root.id ? 'true' : undefined}>{child.label} <small>{number(child.counts[population][0])} 篇{child.parents.length > 1 ? ' · 多父级' : ''}</small></a>)}</details>;
    })}{filter && !taxonomy.nodes.some(matches) && <p role="status">未找到学科；没有改变右侧分析。</p>}<p className="snapshot-caption">显示全部 {taxonomy.nodes.filter(candidate => candidate.level === 0 && !candidate.navigation_only).length} 个主层节点、{taxonomy.nodes.filter(candidate => candidate.level === 1).length} 个子层节点（含缺失组），不按 Top N 裁剪索引。</p></nav>
    <div className="discipline-results" ref={resultsRef}><nav className="discipline-breadcrumb" aria-label="当前学科路径"><a href={disciplineHref(sources, {taxonomy: taxonomy.id, population, metric, node: 'all'})}>{taxonomy.label}</a>{activeParent && <><span> / </span>{activeParent.navigation_only ? <span>{activeParent.label}</span> : <a href={href(activeParent)}>{activeParent.label}</a>}</>}<span> / {node.label}</span></nav><h2>{node.label}</h2>{node.missing && <p className="snapshot-unavailable">这是标签缺失组，不是一个真实学科；保留它以便核对资料覆盖。</p>}
      <div className="discipline-totals"><div><span>关联撤稿记录论文</span><strong>{number(node.counts[population][0])} 篇</strong></div><div><span>样本内论文覆盖</span><strong>{number(disciplineCell(taxonomy, node, population, 'share', 0).value)}%</strong></div><div><span>同口径发表论文</span><strong>{node.denominator ? number(node.denominator[0])+' 篇' : 'RW 无此分母'}</strong></div></div>
      <section className="snapshot-card discipline-chart"><h3>{node.level === -1 ? '主学科分布' : node.level === 0 ? '本主学科的子学科分布' : '同一父级下的子学科对照'} · {DISCIPLINE_METRICS[metric]}</h3><p className="snapshot-caption">全历史合格记录；每个节点按自身已发布计数计算，不把子节点相加推算父节点。{metric === 'rate' ? '只有 n≥20 且 N≥1,000 的节点按比例排序；其余按名称列出，不参与比例排名。' : '可点击条形进入该学科；基数始终为所选总体，不随前 N 项缩小。'}</p><label>图中展示 <select value={limit} onChange={event => setLimit(Number(event.target.value))}><option value={20}>前 20 项</option><option value={50}>前 50 项</option><option value={2000}>全部节点</option></select></label><div className="discipline-bars">{shown.map(row => {const candidate = taxonomy.nodes.find(node => node.id === row.id); return <button className="discipline-bar" key={row.id} aria-current={row.id === node.id ? 'true' : undefined} onClick={() => change({node: row.id, parent: candidate.level === 0 ? '' : node.level === 0 ? node.id : parent})}><span>{row.label}</span><span className="discipline-track"><span style={{width: `${100*(row.value ?? 0)/maximum}%`}}/></span><strong>{number(row.value)} {UNITS[row.unit]}{metric === 'rate' && !row.ranking_eligible ? ' · 小基数' : ''}</strong></button>;})}</div>{!rows.length && <p>没有可用子节点；本节点的年度统计仍可查看。</p>}<p className="snapshot-caption">显示 {shown.length} / {rows.length} 个节点。</p><Download data={data} study={study} rows={rows} view="distribution"/><details><summary>查看全部分布数据与分子/分母</summary><div className="snapshot-table" tabIndex={0}><table><thead><tr><th>学科</th><th>记录论文 n</th><th>本指标分母 N</th><th>{DISCIPLINE_METRICS[metric]}</th></tr></thead><tbody>{rows.map(row => <tr key={row.id}><th scope="row">{row.label}</th><td>{number(row.numerator)}</td><td>{number(row.denominator)}</td><td>{number(row.value)}</td></tr>)}</tbody></table></div></details></section>
      <section className="snapshot-card discipline-chart"><h3>{node.label} · {DISCIPLINE_METRICS[metric]}随发表年变化</h3><p>横轴是原论文发表年，不是撤稿事件年。每个点对应这一年发表、截至来源日期已被记录撤稿的论文。{metric === 'rate' ? '分母是该学科同年全部合格发表论文，而不是全学科或撤稿论文总数。' : '计数与覆盖比例不是论文被撤稿的发生概率。'}</p><InteractiveChart key={time.slice_id} chart={time}/><p className="snapshot-caption">年度展示 {data.year_start}–{data.year_end}；另有 {number(node.counts[population][0]-time.rows.reduce((sum, row) => sum+row.numerator, 0))} 篇在展示年份外或缺少发表年。末年尚未完整，观察截至 {population === 'B' ? data.rw_cutoff : data.oa_cutoff}。</p><Download data={data} study={study} rows={time.rows} view="time"/><details><summary>查看完整年度数据</summary><div className="snapshot-table" tabIndex={0}><table><thead><tr><th>发表年</th><th>记录论文 n</th><th>本指标分母 N</th><th>{DISCIPLINE_METRICS[metric]}</th></tr></thead><tbody>{time.rows.map(row => <tr key={row.id}><th scope="row">{row.year}{row.partial ? '（未完整）' : ''}</th><td>{number(row.numerator)}</td><td>{number(row.denominator)}</td><td>{number(row.value)}</td></tr>)}</tbody></table></div></details></section>
      <details><summary>本学科的可复核标识</summary><pre>{JSON.stringify({release_id: data.release_id, taxonomy: taxonomy.id, population, node: node.id, parents: node.parents, navigation_parent: parent, metric, count: total.numerator, denominator: total.denominator, provenance: data.provenance}, null, 2)}</pre></details>
    </div></div>
  </section>;
}
