import React from 'react';
import {number} from './reader.js';

const INTRO = {
  overview: ['先认识数据，再读数字', '这份报告把“撤稿记录”与“论文的学术信息”连接起来。我们先说明统计了什么，再比较时间、学科、署名和引用；不是把数据库里所有带标记的条目都叫作撤稿论文。'],
  time: ['发表时间与撤稿时间不是同一条时间线', '按发表年看的是哪些年份的论文后来被记录撤稿；按撤稿年看的是记录何时出现。阅读数量变化时，也要考虑发文增长、资料覆盖和观察时间长短。'],
  fields: ['先选择分类体系', 'Topics 是现行的四级主题体系；Concepts 是已冻结的旧标签体系。它们是两套不同分类，不应混成一棵树。下面可分别进入分类数量、同口径比例与旧标签覆盖分析。'],
  reasons: ['“记录了什么原因”不等于“裁定了谁的责任”', '一篇论文可能有多个原因。图中既有错误或可靠性问题，也有调查和通知程序描述；原因族只是便于阅读的项目归组，原始标签仍可核对。'],
  geography: ['这里的“国家”来自论文署名，而不是作者国籍', '我们查看论文当时记录的作者署名和机构位置。一篇论文可以关联多个国家；信息不完整时，只能说观察到了哪些国家，不能把未观察到的国家当作不存在。'],
  entities: ['先看署名关联，再理解排名', '机构和作者通过 OpenAlex ID 识别。关联论文数是某个身份在本研究样本中署名的不同论文数，不是其全部发文数，更不是对个人或机构的不端行为排名。'],
  publishing: ['把论文、期刊和出版商分开看', '研究论文是文献，期刊是发表它的来源，出版商是来源的宿主。一篇期刊中的撤稿通知仍是通知。我们分别比较关联数量、相同发文基数下的比例和记录时滞。'],
  citations: ['撤稿以后，论文是否还被引用？', '引用可以是在支持原文，也可以是在批评、复核或介绍撤稿。这里只统计指向论文的观测引用及其时间，不把“仍被引用”解释成“错误仍被认同”。'],
  quality: ['知道哪些信息不完整，是解释结果的一部分', '匹配失败不等于论文不存在，标记缺失不等于未撤稿。这里保留两份来源的匹配、筛选和字段覆盖核对，帮助判断哪些比较值得相信、哪些需要谨慎。'],
};

export default function ReportGuide({page, charts}) {
  const [title, summary] = INTRO[page];
  const population = charts?.find(chart => chart.chart_id === 'population-accounting');
  const counts = Object.fromEntries((population?.rows || []).map(row => [row.id, row.numerator]));
  return <section className="snapshot-reader-guide" aria-label="阅读指南"><h2>{title}</h2><p>{summary}</p>
    {page === 'overview' && <>
      <div className="snapshot-source-intro"><div><h3>OpenAlex：学术文献目录</h3><p>提供文献、作者、机构、主题、发表来源与引用关系。一个 <strong>Work</strong> 指一条独立文献记录；研究论文、书籍、数据集、撤稿通知都可能各有自己的记录，并不总是一篇原始研究论文。</p></div><div><h3>Retraction Watch（RW）：撤稿记录来源</h3><p>记录被撤稿的原论文、通知、日期和原因。我们用 DOI 等标识找出它们对应的 OpenAlex 文献，再补充学科和署名信息。OpenAlex 的撤稿标记也依赖 RW，因此二者不是独立的两次验证。</p></div></div>
      <details><summary>主体库、扩展库和 A0/A1 等代码是什么意思？</summary><p><strong>主体库（core）</strong>是 OpenAlex 区别于扩展库（expansion）的语料部分，由快照中的 is_xpac 字段区分。这里默认使用主体库以保持统计范围一致；“主体”不是质量认证，也不保证每条记录经过同行评审。</p><dl><dt>A0：带撤稿标记的记录</dt><dd>还未区分原论文和通知的数据库标记数量。</dd><dt>A1：筛选后的标记论文</dt><dd>从 A0 中保留符合文献类型、身份和日期规则的研究论文候选。</dd><dt>B：RW 撤稿原论文</dt><dd>按原论文标识去重后的 RW 记录；不同通知不自动算作多篇原论文。</dd><dt>C：匹配成功的记录</dt><dd>能与 OpenAlex 高置信对接的 RW 原论文对应记录；不要求 OpenAlex 已经标记撤稿。具体图表还会限定文献类型。</dd><dt>D：比较基数</dt><dd>同一范围内的全部合格发表论文，用来计算“每万篇中有多少篇”的比例。</dd></dl></details>
      {counts.A0 > 0 && <p className="snapshot-reader-finding">从主体库的 <strong>{number(counts.A0)} 条</strong>撤稿标记记录出发，默认分析保留 <strong>{number(counts.A1)} 篇</strong>研究论文候选（{number(100*counts.A1/counts.A0)}%）。其余记录没有从来源数据中删除；下方“筛选前后”会解释每一种排除及其比例。</p>}
      <details><summary>为什么选 article？journal 类型的论文被排除了吗？</summary><p><strong>没有因为发表在 journal 而排除论文。</strong>article（研究论文）描述文献本身；journal（期刊）描述其发表来源。它们可以同时成立：一篇研究论文可以发表在某一期刊中。综述、社论、通知也可以发表在期刊中。</p><p>主分析选研究论文，是为了让撤稿记录与全部发表论文的比较基数尽量具有相近的文献形态，而不是宣称其他类型不重要。综述已有独立比例视图。身份核对还要排除通知或冲突，因为通知有时也会被分成 article。单纯限定 journal 无法解决这个问题。</p><p>可核对 <a href="https://help.openalex.org/data/work-types/" target="_blank" rel="noreferrer">OpenAlex 文献类型说明</a>与<a href="https://help.openalex.org/data/source-types/" target="_blank" rel="noreferrer">来源类型说明</a>；本报告实际计数以固定快照为准。</p></details>
    </>}
    {page === 'geography' && <details><summary>用一个例子理解国家计数</summary><ol><li>一篇论文有三处作者署名机构：中国、中国、美国。</li><li>先在论文内去重，得到中国、美国两个国家。关联论文计数各加 1，所以各国计数相加可能超过论文总数。</li><li>“论文覆盖比例”除以全部样本论文数；“关联份额”除以所有国家—论文关联次数，两者分母不同。</li><li>若选择分数计数，两个已知国家各分到 0.5 篇等价值。只选择一个国家查看，不会重分另一半权重。</li><li>若另一名作者的机构缺失，已知国家的分数可能被高估；只见一个国家时，也不能断言是完整的单国合作。</li></ol><p>默认从已识别机构的所在国计算；“署名国家”模式还允许 OpenAlex 从地址识别、但尚未匹配机构的国家。两种口径单独展示，不偷偷合并。<a href="https://help.openalex.org/data/authorships/" target="_blank" rel="noreferrer">署名字段说明</a></p></details>}
    {page === 'fields' && <details><summary>Topics 和 Concepts 各适合回答什么问题？</summary><p>Topics 由领域（Domain）、学科（Field）、子学科（Subfield）和具体主题（Topic）组成；主主题模式每篇只选一条分类路径。Concepts 是旧版六级标签，第 0 级最宽泛，一篇可带多个标签。</p><p>Concepts 已停止更新，用它查看历史标签分布时应先看覆盖率，不能把近年缺标签解释成某学科没有研究。<a href="https://help.openalex.org/data/concepts/" target="_blank" rel="noreferrer">OpenAlex 的旧分类说明</a></p></details>}
  </section>;
}
