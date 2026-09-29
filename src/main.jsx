import React, {lazy, Suspense, useEffect, useState} from 'react';
import {createRoot} from 'react-dom/client';
import App from './App.jsx';
import './styles.css';
import './report/entry.css';
import ReportIndex from './ReportIndex.jsx';
import ShareLink from './ShareLink.jsx';
import {publicationRedirect, canonicalReportHash, siteHref} from './siteRoutes.js';
const redirect = publicationRedirect(window.location);
if (redirect && redirect !== `${location.pathname}${location.search}${location.hash}`) window.location.replace(redirect);
const version = /\/reports\/(v[12])(?:\/index\.html|\/)?$/.exec(location.pathname)?.[1];
function normalizeHash() {
  if (version === 'v2') {
    const hash = canonicalReportHash(location.hash);
    if (hash !== location.hash) history.replaceState(null, '', `${location.pathname}${location.search}${hash}`);
  }
}
normalizeHash();
window.addEventListener('hashchange', normalizeHash);
const SnapshotReport = lazy(() => import('./report/SnapshotReport.jsx'));
function ReportApp() {
  const [hash, setHash] = useState(() => window.location.hash);
  useEffect(() => {const update = () => setHash(window.location.hash); window.addEventListener('hashchange', update); return () => window.removeEventListener('hashchange', update);}, []);
  if (!version && (!hash || hash === '#' || hash === '#/')) return <ReportIndex/>;
  return version === 'v2' || hash.startsWith('#/snapshot') ? <Suspense fallback={<p role="status">正在加载快照报告…</p>}><SnapshotReport/></Suspense> : <><div className="publication-home-actions"><a href={siteHref()}>报告首页</a><ShareLink/></div><App/></>;
}
createRoot(document.getElementById('root')).render(<React.StrictMode><ReportApp/></React.StrictMode>);
