import React, {lazy, Suspense, useEffect, useState} from 'react';
import {createRoot} from 'react-dom/client';
import App from './App.jsx';
import './styles.css';
import './report/entry.css';
const SnapshotReport = lazy(() => import('./report/SnapshotReport.jsx'));
function ReportApp() {
  const [snapshot, setSnapshot] = useState(() => window.location.hash.startsWith('#/snapshot'));
  useEffect(() => {const update = () => setSnapshot(window.location.hash.startsWith('#/snapshot')); window.addEventListener('hashchange', update); return () => window.removeEventListener('hashchange', update);}, []);
  return snapshot ? <Suspense fallback={<p role="status">正在加载快照报告…</p>}><SnapshotReport/></Suspense> : <><a className="snapshot-report-link" href="#/snapshot/overview">查看 OpenAlex 快照联合研究报告 →</a><App/></>;
}
createRoot(document.getElementById('root')).render(<React.StrictMode><ReportApp/></React.StrictMode>);
