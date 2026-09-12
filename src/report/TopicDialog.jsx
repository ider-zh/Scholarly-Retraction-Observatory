import React, {useEffect, useId, useRef, useState} from 'react';
import {TopicAnalysis} from './TopicAnalysis.jsx';
import {parseReportRoute} from './routes.js';
import {topicCatalog, topicHref} from './topics.js';

export default function TopicDialog({initialRoute, current, ChartCard, Export, onDismiss}) {
  const dialogRef = useRef(null), titleId = useId();
  const [route, setRoute] = useState(initialRoute);
  const topic = topicCatalog(current.charts, route.sources, current.explorer, current.countryExplorer).find(candidate => candidate.id === route.topic);
  useEffect(() => {
    const dialog = dialogRef.current, trigger = document.activeElement;
    dialog.showModal();
    return () => {dialog.close(); if (trigger?.isConnected) trigger.focus({preventScroll: true});};
  }, []);
  function trapFocus(event) {
    if (event.key !== 'Tab') return;
    const controls = [...dialogRef.current.querySelectorAll('a[href],button:not(:disabled),input:not(:disabled),select:not(:disabled),summary,[tabindex="0"]')].filter(element => element.getClientRects().length);
    const first = controls[0], last = controls[controls.length - 1];
    if (event.shiftKey && document.activeElement === first) {event.preventDefault(); last?.focus();}
    else if (!event.shiftKey && document.activeElement === last) {event.preventDefault(); first?.focus();}
  }
  return <dialog className="topic-dialog" ref={dialogRef} aria-labelledby={titleId} onCancel={event => {event.preventDefault(); onDismiss();}} onKeyDown={trapFocus} onClick={event => {if (event.target === event.currentTarget) {const bounds = event.currentTarget.getBoundingClientRect(); if (event.clientX < bounds.left || event.clientX > bounds.right || event.clientY < bounds.top || event.clientY > bounds.bottom) onDismiss();}}}>
    <header className="topic-dialog-header"><h2 id={titleId}>{topic?.title || '数据专题'}</h2><button onClick={onDismiss} autoFocus>关闭专题</button></header>
    <div className="topic-dialog-content"><TopicAnalysis route={route} current={current} navigate={href => setRoute(parseReportRoute(href, {[route.page]: route.page}))} ChartCard={ChartCard} Export={Export}/><p className="topic-dialog-link"><a href={topicHref(route.page, route.topic, route.sources, route.slice, route.explorerSelection)} target="_blank" rel="noopener noreferrer">在独立页面打开当前分析（新标签页）</a></p></div>
  </dialog>;
}
