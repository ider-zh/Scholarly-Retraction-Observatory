import React, {lazy, Suspense, useEffect, useState} from 'react';
import {createRoot} from 'react-dom/client';
import App from './App.jsx';
import './styles.css';
import './report/entry.css';
import ReportIndex from './ReportIndex.jsx';
const SnapshotReport = lazy(() => import('./report/SnapshotReport.jsx'));
function ReportApp() {
  const [hash, setHash] = useState(() => window.location.hash);
  useEffect(() => {const update = () => setHash(window.location.hash); window.addEventListener('hashchange', update); return () => window.removeEventListener('hashchange', update);}, []);
  if (!hash || hash === '#' || hash === '#/') return <ReportIndex/>;
  return hash.startsWith('#/snapshot') ? <Suspense fallback={<p role="status">正在加载快照报告…</p>}><SnapshotReport/></Suspense> : <><a className="snapshot-report-link" href="#/">报告首页</a><App/></>;
}
createRoot(document.getElementById('root')).render(<React.StrictMode><ReportApp/></React.StrictMode>);
