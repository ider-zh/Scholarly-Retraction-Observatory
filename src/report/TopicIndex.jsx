import React, {useEffect, useState} from 'react';
import {SOURCE_NAMES, SOURCE_ORDER} from './sources.js';
import {topicCatalog, topicHref} from './topics.js';
import {variantName} from './reader.js';
import TopicDialog from './TopicDialog.jsx';
import './topics.css';

export default function TopicIndex({section, charts, sources, explorer, countryExplorer, ChartCard, Export}) {
  const [dialogRoute, setDialogRoute] = useState(null);
  const [selected, setSelected] = useState(sources), [query, setQuery] = useState('');
  useEffect(() => {setSelected(sources); setQuery(''); setDialogRoute(null);}, [section, sources.join(',')]);
  const topics = topicCatalog(charts, selected, explorer, countryExplorer).filter(topic => !topic.supersededBy);
  const search = query.trim().toLocaleLowerCase();
  const visible = topics.filter(topic => [topic.title, topic.question, topic.id, ...topic.charts.map(chart => `${chart.chart_id} ${chart.slice_id} ${chart.title} ${variantName(chart)}`)].join(' ').toLocaleLowerCase().includes(search));
  function toggle(source) {setSelected(current => current.includes(source) ? current.filter(item => item !== source) : SOURCE_ORDER.filter(item => current.includes(item) || item === source));}
  return <section className="topic-index" aria-label="本章数据专题目录">
    <p>点击专题，在弹层中查看图表与分析，关闭后继续原处阅读。这里的筛选只控制专题入口，不替换正文；联合选择不是两库并集。</p>
    <div className="topic-index-filters"><fieldset><legend>专题目录的数据集</legend>{SOURCE_ORDER.map(source => <label key={source}><input type="checkbox" checked={selected.includes(source)} disabled={selected.length === 1 && selected.includes(source)} onChange={() => toggle(source)}/>{SOURCE_NAMES[source]}</label>)}</fieldset><label>搜索数据专题<input type="search" value={query} onChange={event => setQuery(event.target.value)} placeholder="研究问题、主题或分析 ID"/></label></div>
    <p className="snapshot-caption" role="status">{topics.filter(topic => topic.enabled).length} / {topics.length} 个专题可用；搜索显示 {visible.length} 个。不可用入口保留在后方。</p>
    <div className="topic-card-grid">{visible.map(topic => <article key={topic.id} className={`topic-card${topic.enabled ? '' : ' topic-card-disabled'}`} data-topic-id={topic.id} data-enabled={topic.enabled}>
      <h3>{topic.enabled ? <a href={topicHref(section, topic.id, selected)} aria-haspopup="dialog" onClick={event => {if (event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return; event.preventDefault(); setDialogRoute({page: section, topic: topic.id, sources: selected, slice: '', explorerSelection: {}});}}>{topic.title}<span className="topic-new-tab">查看图表与分析</span></a> : <span role="link" aria-disabled="true">{topic.title}</span>}</h3><p>{topic.question}</p><p className="topic-card-sources">{topic.countries ? 'OpenAlex / RW × OpenAlex 同截止日匹配子集' : topic.tree ? explorer.taxonomies.map(taxonomy => taxonomy.label).join(' / ') : topic.profiles.map(profile => profile.label).join(' / ')}</p><small>{topic.enabled ? topic.countries ? '国家分布 · 逐年分子与发表分母' : topic.tree ? '完整分类索引 · 分布与年度图' : `${topic.allowed.length} / ${topic.charts.length} 个已发布视图可用` : '当前来源不足；请启用上方对应数据集。'}</small>
      </article>)}</div>{!visible.length && <p>未找到匹配专题，请调整搜索词；章节正文没有改变。</p>}
    {dialogRoute && <TopicDialog initialRoute={dialogRoute} current={{charts, explorer, countryExplorer}} ChartCard={ChartCard} Export={Export} onDismiss={() => setDialogRoute(null)}/>}
  </section>;
}
