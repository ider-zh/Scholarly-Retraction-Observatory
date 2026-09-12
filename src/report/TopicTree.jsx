import React, {useEffect, useMemo, useState} from 'react';
import {number} from './reader.js';
import {studyAncestors} from './discipline.js';
import './topic-tree.css';

function Branch({node, childrenByParent, study, path, href}) {
  const children = childrenByParent.get(node.id) || [];
  const active = path.has(node.id);
  const [open, setOpen] = useState(active);
  useEffect(() => {if (active) setOpen(true);}, [active]);
  const link = <a href={href(node, node.parents[0] || '')} aria-current={study.node.id === node.id ? 'true' : undefined}>{node.label}<small>{number(node.counts[study.population][0])} 篇 · {study.taxonomy.levels[node.level]}</small></a>;
  if (!children.length) return link;
  return <details data-topic-node={node.id} open={open} onToggle={event => setOpen(event.currentTarget.open)}><summary>{node.label} <small>{children.length} 个下级节点 · {study.taxonomy.levels[node.level]}</small></summary>{open && <>{!node.navigation_only && <a href={href(node, node.parents[0] || '')} aria-current={study.node.id === node.id ? 'true' : undefined}>查看本层统计 · {number(node.counts[study.population][0])} 篇</a>}{children.map(child => <Branch key={child.id} node={child} childrenByParent={childrenByParent} study={study} path={path} href={href}/>)}</>}</details>;
}

export default function TopicTree({study, href, allHref}) {
  const [search, setSearch] = useState(''), [limit, setLimit] = useState(50);
  const {taxonomy, node, population} = study;
  const childrenByParent = useMemo(() => {
    const mapping = new Map();
    for (const candidate of taxonomy.nodes) for (const parent of candidate.parents) mapping.set(parent, [...(mapping.get(parent) || []), candidate]);
    return mapping;
  }, [taxonomy]);
  const roots = taxonomy.nodes.filter(candidate => candidate.level === 0);
  const path = new Set([...studyAncestors(study).map(ancestor => ancestor.id), node.id]);
  const query = search.trim().toLocaleLowerCase();
  const results = query ? taxonomy.nodes.filter(candidate => !candidate.navigation_only && `${candidate.label} ${candidate.id}`.toLocaleLowerCase().includes(query)) : [];
  return <nav className="discipline-tree topic-tree" aria-label="Topics 四层分类索引"><h3>从大领域进入具体研究主题</h3><p>Domain 大领域 → Field 学科 → Subfield 子学科 → Topic 研究主题。四个大领域不是四个 Topic；每篇按主主题归入一条分类路径。</p><label>搜索学科或研究主题 <input type="search" value={search} onChange={event => {setSearch(event.target.value); setLimit(50);}} placeholder="输入名称或 OpenAlex ID"/></label><a href={allHref} aria-current={node.id === 'all' ? 'true' : undefined}>全部大领域 · {number(taxonomy.counts[population][0])} 篇</a>
    {query ? <><p role="status">匹配 {results.length} 个节点，显示 {Math.min(limit, results.length)} 个。</p>{results.slice(0, limit).map(candidate => <a key={candidate.id} href={href(candidate, candidate.parents[0] || '')}>{candidate.label}<small>{taxonomy.levels[candidate.level]} · {number(candidate.counts[population][0])} 篇</small></a>)}{results.length > limit && <button onClick={() => setLimit(current => current+100)}>显示更多搜索结果</button>}</> : roots.map(root => <Branch key={root.id} node={root} childrenByParent={childrenByParent} study={study} path={path} href={href}/>)}
    <p className="snapshot-caption">按需展开全部层级，不按 Top N 截断索引；标签缺失单列，不是额外的大领域。</p>
  </nav>;
}
