import React, {useState} from 'react';
import InteractiveChart from './InteractiveChart.jsx';
import {number} from './reader.js';
import './lag.css';

const years = days => (days / 365.25).toLocaleString('zh-CN', {minimumFractionDigits: 2, maximumFractionDigits: 2});

export default function LagSummaryPlot({chart}) {
  const [selected, setSelected] = useState('p50_days');
  const milestones = [['p25_days', '四分之一', 25], ['p50_days', '一半', 50], ['p75_days', '四分之三', 75], ['p90_days', '九成', 90]].map(([key, label, percentile]) => ({key, label, percentile, days: chart.quantiles[key]}));
  if (milestones.some(item => !Number.isFinite(item.days) || item.days < 0)) return <p role="status">分位时间未完整发布，请查看原始累计数据。</p>;
  const maximum = Math.max(...milestones.map(item => item.days), 1);
  const active = milestones.find(item => item.key === selected);
  function move(event) {
    if (!['ArrowDown', 'ArrowUp'].includes(event.key)) return;
    event.preventDefault();
    const buttons = [...event.currentTarget.parentElement.querySelectorAll('[data-lag-quantile]')];
    buttons[(buttons.indexOf(event.currentTarget) + (event.key === 'ArrowDown' ? 1 : buttons.length - 1)) % buttons.length]?.focus();
  }
  return <section className="lag-summary" aria-label="四个时间点读懂撤稿时滞">
    <p>把已记录撤稿的论文按等待时间从短到长排列。先看“一半”这一行：它标出中位时间，不是平均时间。<strong>条越长，等待越久，不是论文越多。</strong></p>
    <div className="lag-heading" aria-hidden="true"><span>排到样本中的哪个位置</span><span>从发表到撤稿的时间 →</span><span>已发布分位时间</span></div>
    <div className="lag-milestones">{milestones.map(item => <button type="button" key={item.key} data-lag-quantile={item.key} aria-pressed={selected === item.key} onClick={() => setSelected(item.key)} onFocus={() => setSelected(item.key)} onKeyDown={move} className={item.key === 'p50_days' ? 'lag-median' : ''}>
      <span className="lag-label"><strong>{item.label}</strong><small>{item.percentile}% 位置{item.key === 'p50_days' ? ' · 中位数' : ''}</small></span>
      <span className="lag-track" aria-hidden="true"><span style={{width: `${100 * item.days / maximum}%`}}/></span>
      <span className="lag-value"><strong>约 {years(item.days)} 年</strong><small>{number(item.days)} 天</small></span>
    </button>)}</div>
    <p className="lag-explanation" role="status">{active.label}对应的分位时间是 {number(active.days)} 天（约 {years(active.days)} 年）。条越长，表示等到撤稿的时间越久；四行来自同一批论文，不能相加。</p>
    <p className="snapshot-caption">每条都从发表时点（0）起算，共用线性时间刻度。年数按 365.25 天折算并四舍五入；天数保持已发布精度。90% 位置不是最长时间，仍有更长时滞；这不是“所有论文在几年内会被撤稿”的概率。</p>
    <details className="lag-advanced"><summary>查看完整累计曲线与更长时滞（进阶）</summary><p>横轴是发表后经过的天数，纵轴是这批已撤稿论文中、不晚于该时点被记录撤稿的累计比例。长尾会压缩左侧；可调整显示范围，但不改变统计基数。曲线连接已发布采样点，不据连线推算未发布时点。</p><InteractiveChart chart={chart}/></details>
  </section>;
}
