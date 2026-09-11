import React, {useEffect, useRef, useState} from 'react';
import {validateManifest, validateChunk} from './schema.js';
import ReportGuide from './ReportGuide.jsx';
import {number, UNITS, POPULATIONS, WORK_TYPES, chartName, variantName, rowLabel, selectChart, chartMethod, insightText} from './reader.js';
import './snapshot.css';

const PAGES = {overview: '研究概览', time: '时间与观察期', fields: '学科与主题', reasons: '撤稿原因', geography: '地理与合作', entities: '机构与作者', publishing: '期刊与出版', citations: '引用与持续传播', quality: '数据与方法'};

function readRoute() {
  const [route, query = ''] = window.location.hash.slice(1).split('?');
  const page = route.split('/')[2] || 'overview';
  const params = new URLSearchParams(query);
  const rejected = [...params.keys()].filter(key => key !== 'slice');
  return {page: PAGES[page] ? page : 'overview', slice: params.get('slice') || '',
    error: !PAGES[page] ? `未支持的章节：${page}` : rejected.length ? `未支持的参数：${rejected.join(', ')}` : null};
}

async function checkedJSON(url, signal, expected) {
  const response = await fetch(url, {signal, cache: 'no-cache'});
  if (!response.ok) throw new Error(`无法读取报告 (${response.status})`);
  const bytes = await response.arrayBuffer();
  if (expected) {
    if (bytes.byteLength !== expected.bytes) throw new Error('报告文件大小不匹配，请重新加载');
    const hash = [...new Uint8Array(await crypto.subtle.digest('SHA-256', bytes))].map(value => value.toString(16).padStart(2, '0')).join('');
    if (hash !== expected.sha256) throw new Error('报告文件校验失败，请重新加载');
  }
  return JSON.parse(new TextDecoder().decode(bytes));
}

function Export({chart}) {
  function save() {
    const metadata = {release_id: chart.release_id, chart_id: chart.chart_id, slice_id: chart.slice_id,
      population: chart.population_key, metric: chart.metric_id, scope: JSON.stringify(chart.scope),
      oa_date: chart.oa_snapshot_date, rw_date: chart.rw_snapshot_date, cutoff: chart.metric_observation_cutoff, methods: chart.methods_version,
      citation_ratio: chart.post_retraction_citation_ratio ? JSON.stringify(chart.post_retraction_citation_ratio) : '',
      reason_mapping: chart.reason_mapping_version || chart.scope.attribution};
    const rows = chart.rows.map(row => ({...metadata, ...row}));
    const keys = [...new Set(rows.flatMap(row => Object.keys(row)))];
    const quote = value => `"${String(value ?? '').replace(/^[=+@\-\t\r]/, "'$&").replaceAll('"', '""')}"`;
    const body = [keys, ...rows.map(row => keys.map(key => row[key]))].map(row => row.map(quote).join(',')).join('\r\n');
    const url = URL.createObjectURL(new Blob(['\ufeff' + body], {type: 'text/csv;charset=utf-8'}));
    const link = document.createElement('a'); link.href = url; link.download = `${chart.chart_id}-${chart.slice_id}.csv`; link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  return <button type="button" onClick={save} disabled={!chart.rows.length}>导出本切片聚合 CSV</button>;
}

function Plot({chart}) {
  const valid = chart.rows.filter(row => row.value !== null);
  if (!valid.length) return <p>该切片没有可绘制的数值；请查看缺失说明。</p>;
  if (chart.chart_id === 'population-accounting') return <div className="snapshot-populations">{valid.map(row => <div key={row.id}><span>{row.label}</span><strong>{number(row.value)}</strong><small>独立口径 · 不与其他卡片相加</small></div>)}</div>;
  if (chart.chart_id === 'screening') return <div className="snapshot-table" tabIndex={0}><table><caption>每条标记记录只进入一个分组；数量之和等于筛选前总数。</caption><thead><tr><th scope="col">筛选结果</th><th scope="col">记录数</th><th scope="col">占筛选前比例</th></tr></thead><tbody>{chart.rows.map(row => <tr key={row.id}><th scope="row">{row.label}</th><td>{number(row.numerator)}</td><td>{number(row.value)}%</td></tr>)}</tbody></table></div>;
  if (chart.chart_id === 'work-types') return <div className="snapshot-table" tabIndex={0}><table><caption>文献类型与来源类型交叉核对。“来自期刊”不是“已经通过原论文身份筛选”。</caption><thead><tr>{['文献类型', '带标记记录', '占全部标记', '其中主来源为期刊', '默认样本保留'].map(label => <th scope="col" key={label}>{label}</th>)}</tr></thead><tbody>{chart.rows.map(row => <tr key={row.id}><th scope="row">{row.label}<small className="snapshot-code-note">{row.work_type}</small></th><td>{number(row.numerator)}</td><td>{number(row.pct_of_flagged)}%</td><td>{number(row.journal_source_records)}</td><td>{number(row.default_included_records)}</td></tr>)}</tbody></table></div>;
  if (chart.chart_id === 'author-top') return <div className="snapshot-table" tabIndex={0}><table><caption>按不同关联论文数降序，同数按作者 ID 排序；这是署名关联，不是责任排名。</caption><thead><tr><th scope="col">顺序</th><th scope="col">OpenAlex 作者身份</th><th scope="col">关联论文数</th></tr></thead><tbody>{chart.rows.map(row => <tr key={row.id}><td>{row.rank}</td><th scope="row">{row.label}<small className="snapshot-code-note">{/^https:\/\/openalex.org\/A[1-9][0-9]*$/.test(row.author_id) ? <a href={row.author_id} target="_blank" rel="noreferrer" aria-label={`查看 ${row.label} 的 OpenAlex 身份 ${row.author_id.split('/').at(-1)}`}>{row.author_id.split('/').at(-1)} ↗</a> : '身份链接不可用'}</small></th><td>{number(row.numerator)}</td></tr>)}</tbody></table></div>;
  if (chart.chart_id === 'annual-growth') return <div className="snapshot-table" tabIndex={0}><table><thead><tr>{['年份', '当前数量', '前期基数', '同比 %', '解释状态'].map(label => <th scope="col" key={label}>{label}</th>)}</tr></thead><tbody>{chart.rows.map(row => <tr key={row.id}><th scope="row">{row.label}</th><td>{number(row.numerator)}</td><td>{number(row.denominator)}</td><td>{number(row.value)}</td><td>{row.partial ? '年度未完整' : row.small_base ? '小基数 / 未定义' : '完整年度记录'}</td></tr>)}</tbody></table></div>;
  if (chart.control_policy) {
    const maximum = Math.max(...chart.rows.flatMap(row => [row.value, row.threshold]), 1);
    const horizontal = index => 60 + 700 * index / Math.max(chart.rows.length - 1, 1);
    const vertical = value => 235 - 190 * value / maximum;
    return <div className="snapshot-plot" tabIndex={0}><svg viewBox="0 0 800 290" role="img" aria-label="月度记录数与描述性复核阈值；虚线为阈值，橙色标记超过阈值，空心为未完整月份。"><line x1="60" y1="235" x2="760" y2="235" stroke="#8495a5"/><text x="5" y="30">{number(maximum)} 篇</text><polyline points={chart.rows.map((row, index) => `${horizontal(index)},${vertical(row.value)}`).join(' ')} fill="none" stroke="#197a86" strokeWidth="2"/><polyline points={chart.rows.map((row, index) => `${horizontal(index)},${vertical(row.threshold)}`).join(' ')} fill="none" stroke="#965321" strokeDasharray="5 4"/>{chart.rows.map((row, index) => <circle key={row.id} cx={horizontal(index)} cy={vertical(row.value)} r={row.review_flag ? 4 : 2} stroke={row.review_flag ? '#965321' : '#197a86'} fill={row.partial ? 'white' : row.review_flag ? '#965321' : '#197a86'}><title>{row.label}: {row.value}；阈值 {number(row.threshold)}；{row.partial ? '月份未完整' : row.review_flag ? '需复核' : '未超过阈值'}</title></circle>)}<text x="60" y="260">{chart.rows[0]?.label}</text><text x="690" y="260">{chart.rows.at(-1)?.label}</text></svg><p className="snapshot-caption">虚线为固定规则阈值；橙色点需人工复核，空心点为未完整月份，不执行标记。</p></div>;
  }
  if (chart.chart_id === 'C4') return <div className="snapshot-table" tabIndex={0}><table><caption>日历窗口；均值和分位数均包含已观察零引用目标，不是置信区间。</caption><thead><tr>{['窗口', '合格目标 N', '引用边总数', '均值', '中位数', 'P25–P75', '至少一次引用', '排除目标'].map(label => <th scope="col" key={label}>{label}</th>)}</tr></thead><tbody>{chart.rows.map(row => <tr key={row.id}><th scope="row">{row.label}</th><td>{number(row.denominator)}</td><td>{number(row.numerator)}</td><td>{number(row.value)}</td><td>{number(row.median)}</td><td>{number(row.p25)}–{number(row.p75)}</td><td>{number(row.targets_with_edges)} / {number(row.denominator)}（{number(row.targets_with_edges_pct)}%）</td><td>{number(row.excluded_targets)}</td></tr>)}</tbody></table></div>;
  if (chart.chart_id === 'R3') {
    const groups = valid.filter(row => row.reason_labels?.length), labels = [...new Set(groups.flatMap(row => row.reason_labels))];
    const maximum = Math.max(...groups.map(row => row.value), 1), width = Math.max(700, 270 + groups.length * 48);
    return <div className="snapshot-plot" tabIndex={0}><svg viewBox={`0 0 ${width} ${250 + labels.length * 24}`} role="img" aria-label="完整原因标签组合 UpSet：每列是一个互斥组合，柱高为作品数，圆点标记该组合包含的原始标签。">
      {groups.map((row, index) => <g key={row.id}><rect x={260 + index * 48} y={185 - 140 * row.value / maximum} width="28" height={140 * row.value / maximum} fill="#197a86"><title>{row.label}: {row.value} 篇</title></rect><text x={255 + index * 48} y={175 - 140 * row.value / maximum}>{row.value}</text><text x={267 + index * 48} y="207">{index + 1}</text>{labels.map((label, labelIndex) => <circle key={label} cx={274 + index * 48} cy={232 + labelIndex * 24} r="4" fill={row.reason_labels.includes(label) ? '#173d4d' : '#e1e8ed'}><title>{label}: {row.reason_labels.includes(label) ? '包含' : '不包含'}</title></circle>)}</g>)}
      {labels.map((label, index) => <text key={label} x="0" y={236 + index * 24}>{label.length > 34 ? label.slice(0, 33) + '…' : label}<title>{label}</title></text>)}
    </svg><p className="snapshot-caption">Other 与 Unknown 分开保留：{valid.filter(row => !row.reason_labels?.length).map(row => `${row.label} ${number(row.value)} 篇`).join('；')}。每篇仅属于一个完整组合。</p></div>;
  }
  if (chart.chart_id === 'F4') return <div className="snapshot-table" tabIndex={0}><table><caption>同一完整可排名集合中的顺序；并列数值按稳定 ID 排序。</caption><thead><tr><th>学科</th><th>数量顺序</th><th>比例顺序</th><th>n / N</th></tr></thead><tbody>{valid.map(row => <tr key={row.id}><th scope="row">{row.label}</th><td>{row.count_rank}</td><td>{row.proportion_rank}</td><td>{number(row.numerator)} / {number(row.denominator)}</td></tr>)}</tbody></table></div>;
  if (['R4', 'P3'].includes(chart.chart_id)) {
    const maximum = Math.max(...valid.map(row => row.p75), 1);
    return <div className="snapshot-plot" tabIndex={0}><svg viewBox={`0 0 800 ${valid.length * 40 + 45}`} role="img" aria-label={`${chart.title}，点为中位数，线段为P25–P75；不是置信区间。`}>{valid.map((row, index) => <g key={row.id}><text x="0" y={index * 40 + 24}>{row.label.length > 30 ? row.label.slice(0, 29) + '…' : row.label}<title>{row.label}</title></text><line x1={280 + 420 * row.p25 / maximum} x2={280 + 420 * row.p75 / maximum} y1={index * 40 + 20} y2={index * 40 + 20} stroke="#197a86" strokeWidth="4"/><circle cx={280 + 420 * row.value / maximum} cy={index * 40 + 20} r="5" fill="#173d4d"><title>{row.label}: P25={row.p25}, median={row.value}, P75={row.p75}; n={row.numerator}</title></circle><text x="720" y={index * 40 + 24}>n={row.numerator}</text></g>)}<text x="280" y={valid.length * 40 + 25}>0 年</text><text x="640" y={valid.length * 40 + 25}>{number(maximum)} 年</text></svg></div>;
  }
  if (['F3', 'P1'].includes(chart.chart_id)) {
    const maximum = Math.max(...valid.map(row => row.value), 1), maxSize = Math.max(...valid.map(row => Math.log10(row.denominator)), 1);
    return <div className="snapshot-plot" tabIndex={0}><svg viewBox="0 0 800 300" role="img" aria-label={`${chart.title}：横轴为发表分母N（log10），纵轴为每万篇比例；空心点不满足排名门槛。`}><line x1="60" y1="240" x2="760" y2="240" stroke="#8495a5"/><line x1="60" y1="30" x2="60" y2="240" stroke="#8495a5"/>{valid.map(row => <circle key={row.id} cx={60 + 680 * Math.log10(row.denominator) / maxSize} cy={240 - 190 * row.value / maximum} r="5" stroke="#197a86" fill={row.ranking_eligible ? '#197a86' : 'white'}><title>{row.label}: {number(row.value)} 每万篇; n={row.numerator}, N={row.denominator}; {row.ranking_eligible ? '满足排名门槛' : '不参与排名'}</title></circle>)}<text x="4" y="25">每万篇</text><text x="5" y="50">{number(maximum)}</text><text x="270" y="285">发表分母 N（log10 标度）</text><text x="60" y="260">1</text><text x="690" y="260">{number(10 ** maxSize)}</text></svg></div>;
  }
  const isLine = ['T1', 'T3', 'T4', 'E3', 'C1', 'C2'].includes(chart.chart_id);
  if (isLine) {
    const horizontal = row => row.relative_year ?? row.year ?? row.lag_days ?? row.entity_pct ?? (row.cited_by_count == null ? null : Math.log1p(row.cited_by_count));
    const points = valid.filter(row => horizontal(row) != null && (row.year == null || row.year >= 2000));
    if (!points.length) return <p>2000 年后的展示范围内无可绘制数据；完整聚合表仍可查看。</p>;
    const lower = Math.min(...points.map(horizontal)), upper = Math.max(...points.map(horizontal));
    const maximum = Math.max(...points.map(row => row.value), 1);
    const x = row => 60 + 700 * (horizontal(row) - lower) / Math.max(upper - lower, 1);
    const y = row => 235 - 190 * row.value / maximum;
    const axis = chart.chart_id === 'C2' ? '相对撤稿年度（每个年度分母不同）' : chart.chart_id === 'T4' ? '发表至撤稿（天）' : chart.chart_id === 'E3' ? '正关联实体累计比例（%）' : chart.chart_id === 'C1' ? 'log1p(快照引用次数)' : '年份（展示自 2000 年起）';
    return <div className="snapshot-plot" tabIndex={0}><svg viewBox="0 0 800 290" role="img" aria-label={`${chart.title}；${axis}；单位 ${UNITS[points[0].unit] || points[0].unit}；完整数值见下方表格。`}>
      <line x1="60" y1="235" x2="765" y2="235" stroke="#8495a5"/><line x1="60" y1="35" x2="60" y2="235" stroke="#8495a5"/>
      <text x="5" y="28">{UNITS[points[0].unit] || points[0].unit}</text><text x="8" y="50">{number(maximum)}</text><text x="30" y="238">0</text>
      <polyline points={points.map(row => `${x(row)},${y(row)}`).join(' ')} fill="none" stroke="#197a86" strokeWidth="2"/>
      {chart.chart_id === 'E3' && <line x1="60" y1="235" x2="760" y2="45" stroke="#9da9b1" strokeDasharray="5 5"><title>均等关联份额参考线</title></line>}
      {chart.chart_id === 'C2' && lower <= 0 && upper >= 0 && <line x1={60 + 700 * (0 - lower) / Math.max(upper - lower, 1)} y1="35" x2={60 + 700 * (0 - lower) / Math.max(upper - lower, 1)} y2="235" stroke="#965321" strokeDasharray="5 4"><title>撤稿事件边界；同日引用不硬分前后</title></line>}
      {points.map(row => <g key={row.id}><circle cx={x(row)} cy={y(row)} r={row.partial ? 5 : 2.5} fill={row.partial ? 'white' : '#197a86'} stroke="#197a86"><title>{row.label}: {number(row.value)} {UNITS[row.unit] || row.unit}; n={row.numerator}, N={row.denominator ?? '未定义'}{row.partial ? '；未完整年度' : ''}</title></circle></g>)}
      <text x="60" y="255">{lower}</text><text x="710" y="255">{upper}</text><text x="275" y="280">{axis}</text>
    </svg><p className="snapshot-caption">空心点表示未完整年度。连线只描述已发布的聚合单元，不代表因果关系或未来风险。</p></div>;
  }
  if (['T2', 'F2', 'G3', 'R2', 'P2'].includes(chart.chart_id)) {
    const rowName = row => chart.chart_id === 'T2' ? row.event_year : chart.chart_id === 'G3' ? row.country_left : chart.chart_id === 'P2' ? row.source : row.field;
    const column = row => chart.chart_id === 'T2' ? row.publication_year : chart.chart_id === 'G3' ? row.country_right : chart.chart_id === 'R2' ? row.reason : chart.chart_id === 'P2' ? row.month : row.year;
    const years = [...new Set(valid.map(column).filter(value => typeof value !== 'number' || value >= 2000))].sort((first, second) => String(first).localeCompare(String(second)));
    const totals = new Map(); valid.forEach(row => totals.set(rowName(row), (totals.get(rowName(row)) || 0) + row.value));
    const labels = [...totals.keys()].sort((first, second) => chart.chart_id === 'T2' ? second - first : totals.get(second) - totals.get(first)).filter(label => chart.chart_id !== 'T2' || label >= 2000).slice(0, 20);
    const cells = new Map(valid.map(row => [`${rowName(row)}|${column(row)}`, row]));
    const max = Math.max(...valid.map(row => row.value), 1);
    return <div className="snapshot-table" tabIndex={0}><table className="snapshot-heatmap"><caption>{UNITS[valid[0].unit] || valid[0].unit} · log1p 色阶：浅→深。最多 20 行；完整单元见聚合表。— 表示未发布或不适用。</caption><thead><tr><th scope="col">{chart.chart_id === 'T2' ? '撤稿年 / 发表年' : chart.chart_id === 'G3' ? '国家 / 国家' : chart.chart_id === 'R2' ? '学科 / 原因' : chart.chart_id === 'P2' ? '来源 / 撤稿月' : '学科 / 发表年'}</th>{years.map(year => <th scope="col" key={year}>{year}</th>)}</tr></thead><tbody>{labels.map(label => <tr key={label}><th scope="row">{label}</th>{years.map(year => {const cell = cells.get(`${label}|${year}`); return <td key={year} style={cell ? {background: `rgba(25,122,134,${.08 + .6 * Math.log1p(cell.value) / Math.log1p(max)})`} : {}} title={cell ? `${cell.label}: ${cell.value} ${UNITS[cell.unit] || cell.unit}; n=${cell.numerator}, N=${cell.denominator ?? '未定义'}` : '该单元未发布或不适用'}>{cell ? number(cell.value) : '—'}</td>;})}</tr>)}</tbody></table></div>;
  }
  const rows = valid.slice(0, 15), maximum = Math.max(...rows.map(row => row.value), 1);
  return <div className="snapshot-bars" role="img" aria-label={`${chart.title}；展示前 ${rows.length} 个已发布单元，完整数据在下方表格。`}>{rows.map(row => <div className="snapshot-bar-row" key={row.id}><span title={row.label}>{row.label}</span><div><i style={{width: `${100 * row.value / maximum}%`}}/></div><b>{number(row.value)} <small>{UNITS[row.unit] || row.unit}</small></b></div>)}</div>;
}

function ChartCard({chart}) {
  const [metric, setMetric] = useState('linked_work_count');
  const transformed = chart.chart_id === 'G1' && chart.association_summary && metric !== 'linked_work_count' ? {...chart,
    metric_id: metric, title: `${chart.title} · ${metric}`,
    rows: chart.rows.map(row => ({...row, value: row[metric],
      unit: metric === 'fractional_work_count' ? 'work_equivalents' : 'percent',
      numerator: metric.startsWith('fractional') ? row.fractional_work_count : row.numerator,
      denominator: metric === 'association_share_pct' ? chart.association_summary.association_total : metric.startsWith('fractional') ? chart.association_summary.known_works : row.denominator})),
    insights: []} : chart;
  const active = {...transformed, rows: transformed.rows.map(row => ({...row, label: rowLabel(row, chart)}))};
  const method = chartMethod(active);
  const columns = [...new Set(active.rows.flatMap(row => Object.keys(row)))];
  return <article className="snapshot-card" id={`${chart.chart_id}-${chart.slice_id}`}>
    <p className="snapshot-question">{chart.question}</p><h2>{chartName(active)}</h2><p className="snapshot-variant-name">{variantName(active)}</p>
    <div className="snapshot-scope"><span>{POPULATIONS[chart.population_key] || '本图研究范围'}</span><span>{chart.scope.corpus === 'core' ? 'OpenAlex 主体库' : chart.scope.corpus === 'rw' ? 'Retraction Watch 记录' : '范围分别说明'} · {chart.scope.work_types.map(type => WORK_TYPES[type] || type).join(' + ')}</span><span>观察截止 {chart.metric_observation_cutoff}</span></div>
    <div className="snapshot-method-brief"><h3>这张图怎样计算</h3><p>{method[0]}</p><details><summary>原理、选择与限制</summary>{method.slice(1).map(text => <p key={text}>{text}</p>)}</details></div>
    {chart.status !== 'ready' ? <p className="snapshot-unavailable" role="status">尚未计算：{chart.unavailable_reason}</p> : <>
      {chart.chart_id === 'G1' && chart.association_summary && <label>本图计数方式 <select value={metric} onChange={event => setMetric(event.target.value)}>{[['linked_work_count', '关联作品数'], ['paper_coverage_pct', '论文覆盖比例'], ['association_share_pct', '关联份额'], ['fractional_work_count', '已知成员分数计数'], ['fractional_share_pct', '已知成员分数份额']].map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></label>}
      <div className="snapshot-insight"><h3>从数据中读到什么</h3>{active.insights.length ? active.insights.map(insight => <p key={insight.insight_id}>{insightText(insight, active)}</p>) : transformed !== chart && active.rows.length ? <p>当前计数口径下，{active.rows[0]?.label} 为 {number(active.rows[0]?.value)} {UNITS[active.rows[0]?.unit] || active.rows[0]?.unit}。这仍是同一批论文；改变的是如何分配关联和选择基数，不是新增论文。</p> : <p>该分析没有达到展示条件的数值。请查看缺失、比较基数和有效样本量；这不等于观测到零。</p>}</div>
      <Plot chart={active}/>
      {chart.post_retraction_citation_ratio && <p className="snapshot-caption">时间可判定的观测引用边中，撤稿后比例：{number(chart.post_retraction_citation_ratio.value == null ? null : 100 * chart.post_retraction_citation_ratio.value)}%；after={number(chart.post_retraction_citation_ratio.numerator)} / (before+after)={number(chart.post_retraction_citation_ratio.denominator)}。</p>}
      {chart.chart_id === 'C2' && <p className="snapshot-caption">每个相对年度的合格目标 N：{chart.rows.map(row => `${row.label}: ${number(row.denominator)}`).join('；')}。</p>}
      {(chart.citation_quality || chart.static_count_audit || chart.raw_to_family_mapping) && <details><summary>查看来源覆盖与映射审计</summary><pre>{JSON.stringify(chart.citation_quality || chart.static_count_audit || chart.raw_to_family_mapping, null, 2)}</pre></details>}
      <p className="snapshot-caption">{chart.quality.eligible_works == null ? '各项统计范围分别说明。' : `本图研究范围：${number(chart.quality.eligible_works)}；其中相关信息缺失：${number(chart.quality.missing_works)}。`}只展示前若干项时，比较基数不会随之缩小。</p>
      {chart.concept_coverage && <p className="snapshot-caption">有该层旧标签的论文 {number(chart.concept_coverage.known_works)} 篇；缺少该层标签 {number(chart.concept_coverage.missing_works)} 篇。共涉及 {number(chart.concept_coverage.distinct_concepts)} 个概念，聚合表保留前 {number(chart.concept_coverage.displayed_concepts)} 个；图中显示其中前 15 个。</p>}
      {chart.outside_display_range_works != null && <p className="snapshot-caption">另有 {number(chart.outside_display_range_works)} 篇位于展示年份之前，保留在总体核算中。</p>}
      {chart.quantiles && <p className="snapshot-caption">分位数：{Object.entries(chart.quantiles).map(([key, value]) => `${key}=${number(value)}`).join(' · ')}（分布统计，不是置信区间）</p>}
      {chart.gini != null && <p className="snapshot-caption">Gini：{number(chart.gini)}；HHI：{number(chart.hhi)}。虚线为均等关联份额参考线。</p>}
      {chart.zero_citation_works != null && <p className="snapshot-caption">其中零引用 {number(chart.zero_citation_works)} 篇；这是观测零，不是引用字段缺失。</p>}
      <details><summary>查看完整聚合数据与计算方法</summary><p>方法：{chart.methods_version}；OA {chart.oa_snapshot_date} / RW {chart.rw_snapshot_date}。比例由行内 n/N 复算；每万篇比例为 10,000 × n/N。分数权重按筛选前的已知成员集合计算。</p><div className="snapshot-table" tabIndex={0}><table><thead><tr>{columns.map(column => <th scope="col" key={column}>{column}</th>)}</tr></thead><tbody>{active.rows.map(row => <tr key={row.id}>{columns.map(column => <td key={column}>{row[column] == null ? '—' : typeof row[column] === 'number' ? number(row[column]) : String(row[column])}</td>)}</tr>)}</tbody></table></div><Export chart={active}/></details>
      <details><summary>技术标识与精确统计范围（供复核）</summary><pre>{JSON.stringify({chart_id: chart.chart_id, slice_id: chart.slice_id, population_key: chart.population_key, metric_id: active.metric_id, scope: chart.scope, release_id: chart.release_id}, null, 2)}</pre></details>
    </>}
    <div className="snapshot-boundary"><h3>解释边界</h3>{chart.limitations.map(text => <p key={text}>{text}</p>)}</div>
  </article>;
}

export default function SnapshotReport() {
  const [route, setRoute] = useState(readRoute), [manifest, setManifest] = useState(null), [state, setState] = useState({key: '', charts: null, error: null});
  const [manifestError, setManifestError] = useState(null);
  const [shareStatus, setShareStatus] = useState('');
  const headingRef = useRef(null), analysisRef = useRef(null);
  useEffect(() => {const change = () => setRoute(readRoute()); window.addEventListener('hashchange', change); return () => window.removeEventListener('hashchange', change);}, []);
  useEffect(() => {const controller = new AbortController(); checkedJSON(`${import.meta.env.BASE_URL}data/snapshot/manifest.json`, controller.signal).then(validateManifest).then(setManifest).catch(error => {if (error.name !== 'AbortError') setManifestError(error.message);}); return () => controller.abort();}, []);
  useEffect(() => {
    if (!manifest) return;
    const controller = new AbortController(), page = route.page;
    setState({key: page, charts: null, error: null});
    const file = manifest.files.find(item => item.path.endsWith(`/${page}.json`));
    checkedJSON(`${import.meta.env.BASE_URL}${file.path}`, controller.signal, file).then(chunk => validateChunk(chunk, manifest, page))
      .then(chunk => {if (!controller.signal.aborted) setState({key: page, charts: chunk.charts, error: null});})
      .catch(error => {if (error.name !== 'AbortError') setState({key: page, charts: null, error: error.message});});
    return () => controller.abort();
  }, [manifest, route.page]);
  const current = state.key === route.page ? state : {charts: null, error: null};
  const selected = selectChart(current.charts || [], route.slice);
  const position = current.charts?.indexOf(selected) ?? -1;
  const groups = new Map();
  for (const chart of current.charts || []) {
    if (!groups.has(chart.chart_id)) groups.set(chart.chart_id, []);
    groups.get(chart.chart_id).push(chart);
  }
  const changeSlice = value => {window.location.hash = `/snapshot/${route.page}${value ? '?slice=' + encodeURIComponent(value) : ''}`;};
  const choose = chart => {if (chart) changeSlice(`${chart.chart_id}/${chart.slice_id}`);};
  useEffect(() => {
    if (!current.charts) return;
    setShareStatus('');
    if (route.slice) {
      analysisRef.current?.focus({preventScroll: true});
      analysisRef.current?.scrollIntoView({block: 'start', behavior: 'instant'});
    } else {
      headingRef.current?.focus({preventScroll: true});
      window.scrollTo({top: 0, behavior: 'instant'});
    }
  }, [route.page, route.slice, current.charts]);
  return <div className="snapshot-app"><header className="snapshot-header"><a href="#">← 当前 RW 报告</a><span>Scholarly Retraction Observatory</span><a href="#/snapshot/quality">数据与方法</a></header><div className="snapshot-layout"><nav aria-label="快照报告章节"><h2>快照联合研究报告</h2>{Object.entries(PAGES).map(([key, label]) => <a key={key} href={`#/snapshot/${key}`} aria-current={route.page === key ? 'page' : undefined}>{label}</a>)}</nav><main>
    <p className="snapshot-eyebrow">OPENALEX × RETRACTION WATCH</p><h1 ref={headingRef} tabIndex={-1}>{PAGES[route.page]}</h1>
    {manifest && <><p className="snapshot-caption">OpenAlex 文献快照：{manifest.oa_snapshot_date} · Retraction Watch 记录截至：{manifest.rw_snapshot_date}</p><details className="snapshot-source-audit"><summary>数据版本与来源审计</summary><p>报告版本：{manifest.release_id}。{manifest.source_acceptance_policy === 'retrospective-v1' ? '本地清单、文件和身份检查通过；项目接受回溯验证，但下载前清单及传输时间日志没有保存，不能补造这些历史证据。' : '来源检查结果保存在报告的可复核清单中。'}</p><a href="#/snapshot/quality">查看数据质量与方法</a></details></>}
    {route.error && <p role="alert" className="snapshot-unavailable">{route.error}；已显示明确的默认章节。</p>}
    {manifestError || current.error ? <p role="alert">{manifestError || current.error}。未显示旧版数据；请重新加载。</p> : !current.charts ? <p role="status">正在验证并加载本章聚合数据…</p> : <>
      <ReportGuide page={route.page} charts={current.charts}/>
      {route.page === 'overview' && <nav className="snapshot-entry-tabs" aria-label="概览阅读入口">{['population-accounting', 'screening', 'work-types'].map(identifier => <button key={identifier} onClick={() => choose(current.charts.find(chart => chart.chart_id === identifier))}>{chartName({chart_id: identifier})}</button>)}</nav>}
      {route.page === 'fields' && <nav className="snapshot-entry-tabs" aria-label="选择学科分类体系"><button onClick={() => choose(current.charts.find(chart => chart.chart_id === 'F1'))}>Topics：现行主题分类</button><button onClick={() => choose(current.charts.find(chart => chart.chart_id === 'concepts' && chart.population_key === 'C') || current.charts.find(chart => chart.chart_id === 'concepts'))}>Concepts：旧学科分类</button><button onClick={() => choose(current.charts.find(chart => chart.chart_id === 'concepts-coverage' && chart.population_key === 'C'))}>旧分类覆盖率</button></nav>}
      {route.page === 'entities' && <nav className="snapshot-entry-tabs" aria-label="机构与作者入口"><button onClick={() => choose(current.charts.find(chart => chart.chart_id === 'E1'))}>机构关联</button><button onClick={() => choose(current.charts.find(chart => chart.chart_id === 'author-top' && chart.population_key === 'C'))}>作者 Top 20 表</button><button onClick={() => choose(current.charts.find(chart => chart.chart_id === 'E2'))}>作者重复关联分布</button></nav>}
      <div className="snapshot-controls"><label>选择本章分析 <select value={route.slice || (selected ? `${selected.chart_id}/${selected.slice_id}` : '')} onChange={event => changeSlice(event.target.value)}>{current.charts.map(chart => <option key={`${chart.chart_id}/${chart.slice_id}`} value={`${chart.chart_id}/${chart.slice_id}`}>{chartName(chart)} — {variantName(chart)}</option>)}{route.slice && !selected && <option value={route.slice}>未支持的分析</option>}</select></label><button onClick={() => changeSlice('')}>重置</button><button onClick={async () => {try {await navigator.clipboard.writeText(window.location.href); setShareStatus('链接已复制，包含当前分析选择。');} catch {setShareStatus('无法自动复制，请复制浏览器地址栏中的链接。');}}}>复制当前分析链接</button><span role="status">{shareStatus}</span></div>
      <div className="snapshot-analysis-layout"><nav className="snapshot-analysis-index" aria-label="本章分析目录"><h2>本章目录</h2><p>选择一个问题阅读，不必向下寻找长图表。</p>{[...groups].map(([identifier, charts]) => <details key={identifier} open={selected?.chart_id === identifier}><summary>{chartName(charts[0])}</summary>{charts.map(chart => <a key={chart.slice_id} href={`#/snapshot/${route.page}?slice=${encodeURIComponent(`${chart.chart_id}/${chart.slice_id}`)}`} aria-current={selected === chart ? 'true' : undefined}>{variantName(chart)}</a>)}</details>)}</nav><section className="snapshot-analysis-panel" ref={analysisRef} tabIndex={-1} aria-label="当前分析">
      {selected && <div className="snapshot-pagination"><button disabled={position <= 0} onClick={() => choose(current.charts[position - 1])}>← 上一项分析</button><span>{position + 1} / {current.charts.length}</span><button disabled={position >= current.charts.length - 1} onClick={() => choose(current.charts[position + 1])}>下一项分析 →</button></div>}
      {!selected ? <p role="status" className="snapshot-unavailable">该组合未预计算；这不表示没有撤稿。请选择列表中的切片。</p> : <ChartCard key={`${selected.chart_id}/${selected.slice_id}`} chart={selected}/>}
      </section></div>
      {route.page === 'quality' && <details><summary>完整来源与质量门槛</summary><pre>{JSON.stringify(manifest, null, 2)}</pre></details>}
    </>}
    <footer>仅导出已发布的聚合单元；国家、机构、作者或来源关联均不等于不端责任。</footer>
  </main></div></div>;
}
