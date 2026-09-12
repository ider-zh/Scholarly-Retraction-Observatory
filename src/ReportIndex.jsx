import React from 'react';
import {publicationBuilds} from './publication-builds.js';
import './report-index.css';

const buildTime = new Intl.DateTimeFormat('zh-CN', {timeZone: 'Asia/Shanghai', year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit', hourCycle: 'h23'});

function BuildStamp({publication}) {
  const metadata = publicationBuilds[publication];
  return <div className="publication-build">
    <span className="publication-build-label">{metadata.label}</span>
    <time dateTime={metadata.builtAt}>{buildTime.format(new Date(metadata.builtAt)).replaceAll('/', '-')} <small>UTC+8</small></time>
    <span className="publication-cutoff">数据截止：{metadata.sourceDates.map(({source, date}) => `${source} ${date}`).join('；')}</span>
  </div>;
}

export default function ReportIndex() {
  return <main className="publication-index">
    <header><p className="publication-name">Scholarly Retraction Observatory</p><h1>学术撤稿观察</h1><p className="publication-intro">理解撤稿记录，也理解记录的边界。<br/>选择完整报告，或从演示稿开始阅读。</p></header>
    <nav aria-label="报告版本" className="publication-list">
      <a href="#/report-v1"><div><span className="publication-format">原版研究报告 · RW</span><h2>Report v1</h2><BuildStamp publication="v1"/><p>基于 Retraction Watch 的时间、学科与作者署名分析。保留原版统计口径与交互。</p></div><span className="publication-action">阅读原版报告</span></a>
      <a href="#/snapshot/overview?sources=rw%2Coa"><div><span className="publication-format">快照研究报告 · RW / OpenAlex</span><h2>Report v2</h2><BuildStamp publication="v2"/><p>从来源核对到时间、学科、地理和引用分析。可选择数据集，核对方法并导出聚合数据。</p></div><span className="publication-action">阅读快照报告</span></a>
      <a href={`${import.meta.env.BASE_URL}presentation-v2/index.html`}><div><span className="publication-format">研究摘要 · HTML 演示稿</span><h2>HTML-PPT (v2)</h2><BuildStamp publication="ppt"/><p>以 v2 已发布证据串联研究问题、代表图与解释边界。支持翻页、目录和演讲者视图。</p></div><span className="publication-action">打开演示稿</span></a>
    </nav>
    <footer>不同版本的快照日期与总体可能不同，请以各报告标注为准。RW 与 OpenAlex 联合阅读不等于两库相加或去重并集。</footer>
  </main>;
}
