import React from 'react';
import {number} from './reader.js';

export default function AuthorRanking({chart}) {
  const rawNames = chart.chart_id === 'rw-author-names';
  const coverage = chart.association_summary;
  return <section aria-label={rawNames ? 'RW 原始署名字符串排行' : 'OpenAlex 作者身份关联排行'}>
    <p className="report-key-boundary">{rawNames ? '按姓名字符串统计，不代表同名记录属于同一人。此表覆盖 RW 撤稿原论文，不要求 OpenAlex 匹配。' : '按 OpenAlex 作者 ID 统计，不同 ID 即使同名也分别计数；作者消歧仍可能出错。RW 匹配视图也使用 OA 身份，不是 RW 全库姓名排行。'}两种排行的聚合对象和论文范围不同，不能直接比较名次或相加。</p>
    <div className="snapshot-table" tabIndex={0}><table>
      <caption>按不同关联论文数降序；同数按{rawNames ? '原始姓名字符串' : '作者 ID'}排序。Top 20 不改变统计范围；这是署名关联，不是责任排名。</caption>
      <thead><tr><th scope="col">顺序</th><th scope="col">{rawNames ? 'RW 原始署名字符串（未消歧）' : 'OpenAlex 作者身份'}</th><th scope="col">关联论文数</th></tr></thead>
      <tbody>{chart.rows.map(row => <tr key={row.id}><td>{row.rank}</td><th scope="row">{row.label}{!rawNames && <small className="snapshot-code-note">{/^https:\/\/openalex.org\/A[1-9][0-9]*$/.test(row.author_id) ? <a href={row.author_id} target="_blank" rel="noreferrer" aria-label={`查看 ${row.label} 的 OpenAlex 身份 ${row.author_id.split('/').at(-1)}`}>{row.author_id.split('/').at(-1)} ↗</a> : '身份链接不可用'}</small>}</th><td>{number(row.numerator)}</td></tr>)}</tbody>
    </table></div>
    {rawNames && coverage && <p className="report-caption">全部 RW 原论文 {number(chart.quality.eligible_works)} 篇；有非占位署名 {number(coverage.known_works)} 篇，无非占位署名 {number(coverage.unknown_works)} 篇；另有 {number(coverage.partially_missing_works)} 篇同时含已知署名与缺失记录。共 {number(coverage.distinct_name_strings)} 个不同姓名字符串，不等于独立作者人数。Unknown 等缺失占位值单列，不参加排行。</p>}
  </section>;
}
