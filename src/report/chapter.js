import {chartName, insightText, number, UNITS, populationName, WORK_TYPES, variantName} from './reader.js';
import {sourceProfile} from './sources.js';
import {aggregateSection} from './sections.js';

export const CHAPTERS = {
  time: ['02', '论文何时发表，何时被撤稿？', '发表年描述原论文的年代，撤稿年描述记录出现的时间。两条时间线不能互换；近期论文可观察的时间也更短。'],
  fields: ['03', '哪些学科关联更多撤稿记录？', 'Subject、Topics 与 Concepts 是不同分类。分别查看主学科、子学科的数量与比例，不把样本覆盖比例当作全部论文的撤稿率。'],
  subjects: ['03', 'RW 记录的撤稿论文涉及哪些学科？', '本章只使用 Retraction Watch 的 Subject 学科标签。沿主学科与子学科查看论文数量、样本内覆盖和发表年变化；多标签可能重叠。RW 不提供全部发表论文的学科基数，因此不计算总体撤稿率。'],
  topics: ['04', '按 OpenAlex Topics，撤稿记录集中在哪些研究主题？', '从四个 Domain 大领域进入 Field 学科、Subfield 子学科，最后到具体 Topic 研究主题。每层均可查看数量、同口径发表论文中的比例和年度趋势。这里按论文的主主题分类，不与 RW Subject 或 Concepts 混合；RW 匹配视图仅代表匹配子集。'],
  concepts: ['05', '按旧 Concepts 标签，撤稿记录如何分布？', '本章只使用 OpenAlex Concepts（旧体系），沿主学科和子学科查看数量、覆盖和年度变化。旧标签与现行 Topics 不混合；历史父级仅用于导航，多父级关联不能加总为父学科数量。'],
  reasons: ['06', '撤稿记录提到了哪些原因？', '同一篇论文可以有多个原因标签。错误、疑虑与调查程序保持区分；标签描述来源记录，不是独立的责任裁定。'],
  geography: ['07', '论文署名关联哪些国家与合作？', '国家来自论文当时的机构或署名地址，不是作者国籍。一篇论文可关联多个国家；缺失署名会限制合作判断。'],
  entities: ['08', '机构与作者的署名关联如何分布？', 'RW 原始署名字符串与 OpenAlex 作者身份分开排行：前者未做同名消歧，后者按作者 ID 关联论文。两者的论文范围也不同，不能直接比较名次；署名关联不是责任排名。'],
  publishing: ['09', '论文、期刊与出版商如何区分？', '期刊是发表来源，出版商是来源的宿主。分别比较记录数量、发文基数与时滞；当前归属不能代替历史出版归属。'],
  citations: ['10', '撤稿论文如何被引用与继续传播？', '累计引用和撤稿后的引用不是同一指标。引用可能支持、质疑或介绍原文；持续引用不等于持续认同。'],
  quality: ['11', '哪些数据边界影响这些结论？', '匹配失败不等于论文不存在，标记缺失不等于没有撤稿。核对筛选、日期与字段覆盖，才能知道比较的适用范围。'],
};

export function chapterFinding(chart) {
  if (chart.status !== 'ready') return chart.unavailable_reason || '这项分析尚未达到发布条件，不能解释为零。';
  if (chart.insights.length) return insightText(chart.insights[0], chart).replace('这些数值描述数据库中的记录；如何计数和哪些记录未纳入，见本图方法。', '').trim();
  const row = chart.rows.find(row => row.value != null);
  return row ? `当前计数方式下，${row.label} 为 ${number(row.value)} ${UNITS[row.unit] || row.unit}（n=${number(row.numerator)}，N=${number(row.denominator)}）。` : '没有已发布的有效数值；这不等于观测为零。';
}

export function chapterEvidence(chart, section) {
  return {aggregate: `data/snapshot/${aggregateSection(section)}.json`, release_id: chart.release_id, chart_id: chart.chart_id,
    slice_id: chart.slice_id, population: chart.population_key, metric: chart.metric_id,
    scope: chart.scope, oa_date: chart.oa_snapshot_date, rw_date: chart.rw_snapshot_date,
    cutoff: chart.metric_observation_cutoff, methods: chart.methods_version,
    cells: chart.rows.map(row => ({id: row.id, n: row.numerator, N: row.denominator, value: row.value, unit: row.unit}))};
}

export function chapterCaption(chart) {
  const units = [...new Set(chart.rows.map(row => UNITS[row.unit] || row.unit))].join(' / ') || '尚无有效单位';
  const type = chart.scope.work_types.map(type => WORK_TYPES[type] || type).join(' + ');
  return `${sourceProfile(chart).label}；${populationName(chart)}；${type}。单位：${units}。${variantName(chart)}。观察截止 ${chart.metric_observation_cutoff}。`;
}

export function chapterMetricNote(chart) {
  if (chart.metric_id.endsWith('_cohort_per_10k')) return '每万篇比例 = n / 同口径发表论文 N × 10,000；按发表队列比较，不用撤稿年除以同年发文数。';
  if (chart.metric_id === 'annual_count_yoy_pct') return '同比 =（当前数量 − 前期数量）/ 前期数量 × 100%；前期零或观察不足保持未定义。';
  if (chart.metric_id === 'paper_coverage_pct') return '覆盖比例 = 关联论文 n / 当前总体 N × 100%；多标签可以重叠，显示前 N 项不改变比较基数。';
  if (chart.metric_id === 'association_share_pct') return '关联份额的分母是全部已知成员—论文关联次数，不是论文总数。';
  if (chart.metric_id.startsWith('fractional')) return '按论文原有的已知成员集合分配权重；选择或隐藏成员不重新分配，篇等价值不是物理论文数。';
  return '完整数据表保留每个单元的 n/N、单位与缺失状态；没有分母的计数不解释为发生率。';
}
