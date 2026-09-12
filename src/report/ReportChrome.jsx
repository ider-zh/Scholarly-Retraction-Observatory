import React, {useEffect, useId, useRef, useState} from 'react';
import {SOURCE_NAMES, reportHref} from './sources.js';
import {BROAD_WORK_POLICY, BROAD_WORK_METHOD} from './workPolicy.js';
import './navigation.css';

export function ReportHeader({page, pages, sources}) {
  const dialog = useRef(null), navigationId = useId();
  const [compact, setCompact] = useState(() => typeof window !== 'undefined' && window.matchMedia('(max-width: 1023px)').matches);
  const [open, setOpen] = useState(false);
  useEffect(() => {
    const media = window.matchMedia('(max-width: 1023px)');
    const change = () => {dialog.current?.close(); setOpen(false); setCompact(media.matches);};
    media.addEventListener('change', change);
    return () => media.removeEventListener('change', change);
  }, []);
  useEffect(() => {dialog.current?.close(); setOpen(false);}, [page, sources.join(',')]);
  function close() {dialog.current?.close(); setOpen(false);}
  function show() {dialog.current?.showModal(); setOpen(true);}
  function keepFocus(event) {
    if (event.key !== 'Tab') return;
    const controls = [...dialog.current.querySelectorAll('a[href], button:not(:disabled)')];
    const target = event.shiftKey ? controls.at(-1) : controls[0];
    if (document.activeElement === (event.shiftKey ? controls[0] : controls.at(-1))) {event.preventDefault(); target?.focus();}
  }
  const directory = <aside className="report-sidebar" aria-label="报告导航"><a href={reportHref('overview', sources)} className="report-sidebar-identity" onClick={close}>Scholarly Retraction Observatory<span>学术撤稿观察</span></a><div className="report-sidebar-heading"><h2>报告目录</h2>{compact && <button type="button" onClick={close} aria-label="关闭报告目录">关闭 <span aria-hidden="true">×</span></button>}</div><nav id={navigationId} aria-label="快照报告章节" onClick={event => {if (event.target.closest('a')) close();}}>{Object.entries(pages).filter(([key]) => key !== 'fields').map(([key, label]) => <a key={key} href={reportHref(key, sources)} aria-current={key === page ? 'page' : undefined}>{label}</a>)}<a className="report-legacy-link" href="#/report-v1">Report v1 · 原版 RW 报告</a><a className="report-legacy-link" href="#/">报告首页</a></nav><p className="report-sidebar-note">研究报告与数据专题</p></aside>;
  return compact ? <><header className="report-mobile-header"><a href={reportHref('overview', sources)}>学术撤稿观察</a><button type="button" aria-haspopup="dialog" aria-expanded={open} aria-controls={navigationId} onClick={show}><svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true"><path d="M2 4h14M2 9h14M2 14h14" fill="none" stroke="currentColor" strokeWidth="1.5"/></svg>报告目录</button></header><dialog ref={dialog} className="report-nav-dialog" aria-label="报告目录" onClose={() => setOpen(false)} onKeyDown={keepFocus} onClick={event => {if (event.target === dialog.current) close();}}>{directory}</dialog></> : directory;
}

export function ReportScope({sources, manifest, openExplorer}) {
return <div className="report-scope-summary" aria-label="当前报告范围"><p><strong>当前报告：{sources.map(source => SOURCE_NAMES[source]).join(' + ') || '数据集选择无效'}</strong>{sources.length === 2 && <span> · 联合阅读，不是两库并集。</span>}</p>{manifest && <p>{sources.includes('oa') && <span>OpenAlex 快照 {manifest.oa_snapshot_date}</span>}{sources.includes('rw') && <span>RW 记录截至 {manifest.rw_snapshot_date}</span>}</p>}{sources.includes('oa') && manifest?.role_policy_version === BROAD_WORK_POLICY && <details><summary>OA 使用宽口径候选记录，而非仅 article</summary><p>{BROAD_WORK_METHOD}发文分母采用相同口径。</p></details>}<button className="report-text-button" onClick={openExplorer}>查找数据专题 ↓</button></div>;
}
