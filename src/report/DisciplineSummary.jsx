import React from 'react';
import {disciplineCell, DISCIPLINE_METRICS} from './discipline.js';
import {number} from './reader.js';

export default function DisciplineSummary({study, populationLabel, cutoff}) {
  const {taxonomy, node, population, metric} = study;
  const share = disciplineCell(taxonomy, node, population, 'share', 0);
  const rate = disciplineCell(taxonomy, node, population, 'rate', 0);
  const percent = rate.value == null ? null : rate.value / 100;
  const formattedPercent = percent == null ? '未定义' : percent > 0 && percent < 0.000001 ? '<0.000001%' : `${new Intl.NumberFormat('zh-CN', {maximumFractionDigits: 6}).format(percent)}%`;
  return <section aria-label="当前节点统计" data-metric={metric}>
    <p className="snapshot-caption">全历史背景统计 · {populationLabel} · 观察截止 {cutoff}。以下三项固定并列展示；当前分布与年度图指标：{DISCIPLINE_METRICS[metric]}。年度图使用各年的分母，不使用这里的全历史分母。</p>
    <div className="discipline-totals">
      <div><span>当前节点关联的撤稿记录论文 n</span><strong>{number(share.numerator)} 篇</strong><span>同一论文在本节点只计一次；不是两库相加。</span></div>
      <div><span>占全部所选撤稿样本的比例</span><strong>{share.value == null ? '未定义' : `${number(share.value)}%`}</strong><span>{number(share.numerator)} ÷ {number(share.denominator)} × 100%</span><span>分母：全部学科的所选撤稿样本，含标签缺失组。不是该学科的发表论文数。</span></div>
      <div><span>占本节点同口径发表论文的比例</span><strong>{formattedPercent}</strong>{rate.denominator == null ? <span>RW 未提供同口径发表论文分母；不能用样本占比代替。</span> : <><span>{number(rate.numerator)} ÷ {number(rate.denominator)} × 100%</span><span>分母：本节点同口径发表论文 {number(rate.denominator)} 篇。</span><span>{rate.value == null ? '分母为零，比率未定义。' : `相当于每万篇 ${number(rate.value)} 篇；不是不端发生率。`}</span></>}</div>
    </div>
    {taxonomy.id === 'concepts' && <p className="snapshot-caption">Concepts 统计附带该旧概念标签的论文，包含低分/零分标签，不等于以该学科为主要研究方向。多标签可重叠，不能跨节点相加；也不能与 Topics 的同名学科直接对比。</p>}
  </section>;
}
