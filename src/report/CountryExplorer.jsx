import React, {useState} from 'react';
import MetricChoices from './MetricChoices.jsx';
import InteractiveChart from './InteractiveChart.jsx';
import CountryMap from './CountryMap.jsx';
import {Figure} from './ReportFigure.jsx';
import {COUNTRY_METRICS, countryCell, countryStudy, countryTimeChart} from './country.js';
import {number, UNITS, countryLabel as label} from './reader.js';
import './discipline.css';
import './country.css';

const populations = {A1: 'OpenAlex 筛选后的撤稿标记论文', C_D: 'RW × OpenAlex 匹配原论文（截至 OA 快照）'};

function CountryData({data, study, rows, view}) {
  function download() {
    const records = rows.map(row => ({release_id: data.release_id, population: study.population, metric: study.metric, attribution: data.attribution, country_grouping_version: data.country_grouping_version, method: data.method, country: view === 'time' ? study.node.id : row.id, view, date_basis: 'original_publication_year', year_start: data.year_start, year_end: data.year_end, cutoff: data.oa_cutoff, oa_date: data.oa_cutoff, rw_date: data.rw_cutoff, dimension_source_sha256: data.dimension_source_sha256, scan_config_sha256: data.scan_config_sha256, ...row}));
    const columns = [...new Set(records.flatMap(row => Object.keys(row)))];
    const quote = value => '"' + String(value ?? '').replace(/^[=+@\-\t\r]/, "'$&").replaceAll('"', '""') + '"';
    const csv = [columns, ...records.map(row => columns.map(key => row[key]))].map(row => row.map(quote).join(',')).join('\r\n');
    const url = URL.createObjectURL(new Blob(['\ufeff' + csv], {type: 'text/csv;charset=utf-8'}));
    const link = document.createElement('a'); link.href = url; link.download = `country-${study.population}-${study.node.id}-${study.metric}-${view}.csv`; link.click(); setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  return <details className="report-data-table"><summary>查看{view === 'time' ? '年度' : '国家分布'}数据与导出</summary><div className="snapshot-table" tabIndex={0} role="region" aria-label={`${view}完整数据`}><table><caption>{COUNTRY_METRICS[study.metric]}；分母为相同国家、相同发表范围的全部合格论文。</caption><thead><tr><th scope="col">{view === 'time' ? '发表年' : '国家/地区'}</th><th scope="col">撤稿论文 n</th><th scope="col">发表论文 N</th><th scope="col">{COUNTRY_METRICS[study.metric]}</th></tr></thead><tbody>{rows.map(row => <tr key={row.id}><th scope="row">{row.label}</th><td>{number(row.numerator)}</td><td>{number(row.denominator)}</td><td>{number(row.value)} {UNITS[row.unit]}</td></tr>)}</tbody></table></div><button onClick={download}>导出{view === 'time' ? '国家年度' : '国家分布'}聚合 CSV</button></details>;
}

export default function CountryExplorer({data, sources, selection, navigate, hrefForStudy}) {
  const [search, setSearch] = useState(''), [limit, setLimit] = useState(20), [view, setView] = useState('map');
  const study = countryStudy(data, sources, selection);
  if (study.error) return <div className="report-unavailable" role="status">{study.error}</div>;
  const {node, population, metric} = study;
  function change(values) {navigate(hrefForStudy(sources, {node: node.id, population, metric, ...values}));}
  const rows = study.ranked.map(row => ({...row, label: label(row.id)}));
  const shown = rows.filter(row => row.label.toLocaleLowerCase().includes(search.toLocaleLowerCase())).slice(0, limit);
  const maximum = Math.max(...shown.map(row => row.value ?? 0), 1e-12);
  const time = countryTimeChart(data, study), total = countryCell(node, population, 'proportion');
  return <section className="country-explorer" aria-label="国家内撤稿比例与年度分析">
    <h2>国家内有多少发表论文被记录撤稿？</h2><p>国家内比例 = 与该国机构关联、已被记录撤稿的论文 n ÷ 同国同发表范围的全部合格论文 N。它不是该国在全部撤稿论文中的占比。</p>
    <p className="snapshot-caption">本图研究总体：{populations[population]}；OpenAlex 主体库{data.work_types?.includes('all') ? '宽口径文献候选（不限类型）' : ' article'}；按机构所在国计数。发表范围 {data.year_start}–{data.year_end}，观察截止 {data.oa_cutoff}。</p>
    <MetricChoices value={metric} options={COUNTRY_METRICS} onChange={metric => change({metric})}/>
    <div className="topic-controls"><label>研究总体 <select aria-label="国家分析研究总体" value={population} onChange={event => change({population: event.target.value})}>{Object.entries(populations).map(([key, title]) => <option key={key} value={key} disabled={key === 'C_D' && !sources.includes('rw')}>{title}</option>)}</select></label><label>趋势国家/地区 <select aria-label="趋势国家/地区" value={node.id} onChange={event => change({node: event.target.value})}>{data.nodes.map(candidate => <option key={candidate.id} value={candidate.id}>{label(candidate.id)}</option>)}</select></label></div>
    <p className="report-key-boundary"><strong>{label(node.id)}：{number(total.numerator)} / {number(total.denominator)} 篇，国家内比例 {number(total.value)}%</strong>分母始终是该国的同口径发表论文。多国署名论文会关联多个国家，不能相加。年度图按发表年，不是撤稿事件年；近期发表队列观察时间更短。</p>
    <Figure kicker={`国家比较 · ${populations[population]}`} title={COUNTRY_METRICS[metric]} subtitle="点击地图或条形中的国家，查看下方该国的年度趋势。" caption={<figcaption className="report-caption">计数范围 {data.year_start}–{data.year_end}；机构所在国。{metric !== 'count' && 'n≥20 且 N≥1,000 才进入比例排名，其余保留并标记小基数。'}搜索和前 N 项只改变显示，不改变任何分母。</figcaption>} dataTools={<CountryData data={data} study={study} rows={rows} view="distribution"/>}>
      <div className="country-view-choice" role="group" aria-label="国家分布展示方式"><button aria-pressed={view === 'map'} onClick={() => setView('map')}>离线地图</button><button aria-pressed={view === 'bars'} onClick={() => setView('bars')}>排序条形图</button></div>
      {view === 'map' ? <CountryMap rows={rows} metric={metric} selected={node.id} onSelect={node => change({node})}/> : <><p className="snapshot-caption">按当前指标从高到低显示；比例图先列可排名国家，小基数组随后按代码排列，不参与排名。</p><label>搜索国家/地区 <input type="search" value={search} onChange={event => setSearch(event.target.value)} placeholder="中国 / CN"/></label><label>显示国家数 <select value={limit} onChange={event => setLimit(Number(event.target.value))}><option value={20}>前 20 项</option><option value={300}>全部国家</option></select></label>
      <div className="discipline-bars">{shown.map(row => <button className="discipline-bar" key={row.id} aria-current={row.id === node.id ? 'true' : undefined} onClick={() => change({node: row.id})}><span>{row.label}</span><span className="discipline-track"><span style={{width: `${100 * (row.value ?? 0) / maximum}%`}}/></span><strong>{number(row.value)} {UNITS[row.unit]}{metric !== 'count' && !row.ranking_eligible && ' · 小基数'}</strong></button>)}</div>{!shown.length && <p role="status">没有匹配国家，年度趋势仍保留当前选择。</p>}
      </>}
    </Figure>
    <Figure kicker={`发表队列年度趋势 · ${populations[population]}`} title={`${label(node.id)}：${COUNTRY_METRICS[metric]}随发表年变化`} subtitle={metric === 'count' ? '每年发表、截至快照已被记录撤稿的论文数。' : `每个点使用该国同年发表论文 N，比例 = n / N × ${metric === 'rate' ? '10,000' : '100%'}。`} caption={<figcaption className="report-caption">发表年 {data.year_start}–{data.year_end}；观察截止 {data.oa_cutoff}。末年未完整，N=0 时比例未定义，不补零。</figcaption>} dataTools={<CountryData data={data} study={study} rows={time.rows} view="time"/>}><InteractiveChart key={time.slice_id} chart={time}/></Figure>
    <p className="snapshot-caption">所选总体中另有 {number(data.missing_country[population][0])} 篇缺少机构国家，未分配给任何国家；不按已知国家重新分配这些记录。</p>
    <details className="report-methods"><summary>国家判断、分母与时间范围</summary><p>{data.method}</p>{data.limitations.map(text => <p key={text}>{text}</p>)}<p>OA {data.oa_cutoff}；RW {data.rw_cutoff}；报告 {data.release_id}。仅引用既有维度扫描与已验证身份/匹配数据。</p></details>
  </section>;
}
