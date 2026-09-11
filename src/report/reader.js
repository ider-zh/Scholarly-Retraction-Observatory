export const POPULATIONS = {
  A0: '带撤稿标记的数据库记录', A1: '筛选后的撤稿标记论文', B: 'RW 记录的撤稿原论文',
  C: '与 OpenAlex 匹配的 RW 论文', D: '同口径发表论文',
  A1_over_D: '撤稿标记论文与全部发表论文比较', C_D_over_D: 'RW 记录论文与全部发表论文比较',
  mixed_diagnostic: '两份数据的研究范围', source_quality: '数据质量核对', unavailable: '尚未计算的分析',
};
export const WORK_TYPES = {article: '研究论文', review: '综述论文', retraction: '撤稿通知', erratum: '更正通知', all: '全部文献类型', mixed: '不同文献类型'};
export const UNITS = {works: '篇', records: '条记录', authors: '位作者', percent: '%', per_10k: '篇 / 每万篇', years: '年', work_equivalents: '篇等价值', edges: '条引用', edges_per_target: '条 / 合格论文'};
const NAMES = {
  'population-accounting': '研究范围：两份数据分别告诉我们什么', screening: '筛选前后：保留与排除', 'work-types': '文献类型与期刊来源的区别',
  T1: '发表与撤稿的年度数量', T2: '发表年与撤稿年的关系', T3: '考虑发文基数后的比例', T4: '从发表到撤稿经过多久',
  F1: '研究领域分布', F2: '不同年份的学科分布', F3: '学科发文规模与撤稿记录比例', F4: '数量与比例的排序对照',
  R1: '撤稿记录中提到了哪些原因', R2: '不同学科记录了哪些原因', R3: '哪些原因一同出现', R4: '不同原因对应的撤稿时滞',
  G1: '论文署名关联的国家', G2: '跨国署名与信息完整性', G3: '哪些国家在同一篇论文上出现',
  E1: '机构署名关联数量', E2: '作者关联一篇还是多篇论文', E3: '署名关联是否集中', E4: '头部实体覆盖多少不同论文',
  'author-top': '作者关联论文数 Top 20', 'source-counts': '主要发表来源', 'publisher-counts': '当前出版商关联数量',
  P1: '期刊或出版商的发文规模与比例', P2: '撤稿记录的月度分布', P3: '不同发表来源的撤稿时滞',
  C1: '这些论文收到了多少引用', C2: '撤稿前后何时仍有引用', C3: '能否判断引用发生在撤稿之后', C4: '撤稿后 1、3、5 年的引用',
  Q1: '两份数据匹配得怎样', Q2: '匹配与字段缺失', Q3: '筛选排除了哪些记录',
  concepts: 'Concepts：旧学科分类', 'concepts-coverage': '旧学科标签覆盖了多少论文',
  'annual-growth': '年度记录数量的同比变化', 'cohort-oa_status': '开放获取状态与记录比例',
  'cohort-language': '元数据语言与记录比例', 'cohort-observed_team_band': '观察到的团队规模与记录比例',
  'cohort-authorship_audit': '作者列表是否完整',
};
const LABELS = {
  multi_country_observed: '观察到多个国家', single_country_incomplete: '单一已知国家，署名不完整',
  single_country_complete_observed: '单一国家且有完整性证据', completeness_unknown: '单一已知国家，完整性未知', country_unknown: '国家未知',
  no_detected_truncation_not_proven_complete: '未发现截断，但不能证明完整', detected_truncation: '作者总数大于已存署名数',
  count_conflict: '作者总数与署名列表冲突', unknown: '信息缺失', Unknown: '未识别 / 缺失',
};

export function number(value) {
  if (value == null) return '未计算 / 缺失';
  return value !== 0 && Math.abs(value) < .001 ? value.toPrecision(2) : value.toLocaleString('zh-CN', {maximumFractionDigits: 3});
}

export function chartName(chart) {
  return NAMES[chart.chart_id] || chart.title;
}

export function variantName(chart) {
  const parts = [POPULATIONS[chart.population_key] || '本图研究范围'];
  const scope = chart.scope;
  if (scope.work_types?.includes('review')) parts.push('综述论文');
  if (chart.chart_id === 'T1') parts.push(chart.slice_id.endsWith('published') ? '按发表年' : '按撤稿年');
  if (chart.chart_id === 'T3' && scope.followup_years) parts.push(`发表后 ${scope.followup_years} 年`);
  if (scope.level != null) parts.push(scope.taxonomy === 'oa_concepts_legacy' ? `旧分类第 ${scope.level} 级` : ({domain: '领域', field: '学科', subfield: '子学科', topic: '主题'}[scope.level] || scope.level));
  if (scope.attribution?.includes('authorship_country')) parts.push('署名国家（含地址识别）');
  else if (scope.attribution?.includes('institution_country')) parts.push('署名机构所在国');
  if (scope.attribution?.includes('authors')) parts.push('作者');
  if (scope.attribution?.includes('institutions')) parts.push('机构');
  if (scope.attribution === 'immediate_publisher') parts.push('直接出版商');
  if (scope.attribution === 'root_publisher') parts.push('出版集团');
  if (scope.attribution === 'journal') parts.push('期刊');
  if (scope.attribution?.includes('any_topic')) parts.push('所有主题，多标签');
  if (chart.chart_id.startsWith('R')) parts.push(scope.attribution?.includes('families') ? '项目原因族' : '原始原因标签');
  if (scope.cohort_mode) parts.push(scope.cohort_mode === 'common_5y' ? '共同五年随访队列' : '各窗口独立队列');
  if (chart.slice_id.includes('year_interval')) parts.push('日期扩大到整年');
  if (chart.slice_id.includes('reported_day')) parts.push('按报告日期');
  if (chart.slice_id.includes('citing_article_review')) parts.push('引用方限论文与综述');
  if (chart.slice_id === 'C-incoming-field') parts.push('按学科比较');
  if (chart.control_policy) parts.push('含月度复核阈值');
  if (scope.publication_year_range?.[0]) parts.push(`${scope.publication_year_range[0]} 年起发表`);
  return parts.join(' · ');
}

const countryNames = new Intl.DisplayNames(['zh-Hans'], {type: 'region'});
export function rowLabel(row, chart) {
  if (chart.chart_id === 'G1' && /^[A-Z]{2}$/.test(row.id)) return `${countryNames.of(row.id)}（${row.id}）`;
  return LABELS[row.label] || row.label;
}

export function insightText(insight, chart) {
  if (chart.chart_id !== 'G1') return insight.text;
  return chart.rows.reduce((text, row) => text.replaceAll(`“${row.id}”`, `“${rowLabel(row, chart)}”`), insight.text);
}

export function selectChart(charts, requested) {
  if (requested) return charts.find(chart => `${chart.chart_id}/${chart.slice_id}` === requested) || null;
  return charts.find(chart => chart.chart_id === 'population-accounting') || charts[0] || null;
}

export function chartMethod(chart) {
  if (chart.chart_id === 'population-accounting') return ['每条 OpenAlex 文献记录有一个 Work ID。原论文、撤稿通知和更正通知可能分别占一条记录，所以“带标记的记录数”不能直接当作“撤稿原论文数”。', '研究先选定可比的文献范围，再用同一范围内的全部发表论文作基数。Retraction Watch 的原论文通过 DOI 等标识与 OpenAlex 对接，而不是靠标题相似就认定同一篇。'];
  if (['screening', 'work-types', 'Q3'].includes(chart.chart_id)) return ['先分文献类型，再检查原论文与通知身份，最后检查日期。通知 DOI、原论文 DOI 和文献类型共同提供证据；身份冲突不自动选边。', '主分析采用 article（研究论文），让分子与全部发表论文的文献形态更接近。综述另算；期刊 journal 是来源类型，不是与 article 并列的文献类型。标题疑似通知的默认排除并不等于最终认定，纳入它们的敏感性计数另有保留。'];
  if (chart.chart_id.startsWith('concepts')) return ['逐篇读取这份快照已有的 Concepts 标签，按概念 ID 去重，然后在所选层级累计关联论文数。没有把 Topics 换个名字当作 Concepts，也没有用概念实体的总发文数代替本研究统计。', '这些旧标签已经停止更新，覆盖情况需以本批数据的覆盖率表为准；缺失不能当作零学科，也不能据此判断近年某学科研究或撤稿减少。'];
  if (chart.chart_id.startsWith('G')) return ['默认顺序是：论文 → 该论文上每位作者的署名机构 → 机构所在国 → 在同一篇论文内去重。它不使用作者今天任职的机构，也不推测国籍。', '例如一篇论文出现中国、中国、美国三处署名，关联计数是中国 1 篇、美国 1 篇。分数计数则各分到 0.5 篇等价值；切换成只看中国时不会改分为 1。', '“署名国家”另读 authorships.countries，可包含未能匹配机构、但从地址识别出的国家。只观察到一个国家但署名缺失时，不能直接称为国内合作。'];
  if (chart.chart_id === 'E3') return ['先按关联论文数从少到多排列全部有记录的作者或机构，再看“前多少比例的实体，累计占多少关联”。曲线越偏离均等分配的对角线，关联越集中；不是只用榜单前几名计算。', 'Gini 是这种不均等程度的汇总，越接近 0 越均等；HHI 把各实体关联份额平方后相加，数值越大越集中。本图不包括零关联实体；两项指标都不是不端责任评分。'];
  if (chart.chart_id === 'E4') return ['先选出关联数最多的一组作者或机构，再把他们关联的论文 ID 合并去重。“唯一论文覆盖”不会把几位合作者共同署名的一篇重复相加。', '“关联份额”则以全部实体—论文关联次数为分母，回答的是另一个问题。头部数量固定，展示或隐藏其他成员不会改变基数。'];
  if (chart.chart_id === 'author-top' || chart.chart_id.startsWith('E')) return ['以论文中的 OpenAlex 作者或机构 ID 建立关联，同一实体在同一篇上只计一次。同名不自动合并；两位合作者同时上榜时，他们共同署名的一篇会分别计入各自数量。', '表中是本研究范围内的署名关联，不是一个人的全部发文数，也不是责任认定。作者消歧、机构匹配和不完整署名都会影响结果。'];
  if (chart.chart_id === 'C1') return ['这里读取 OpenAlex 为每篇论文记录的累计被引次数，再看这批论文的分布；它不是原论文参考文献的条数。零引用与引用字段缺失分别保留。', '累计次数包含撤稿前后，不能直接得出撤稿后仍被引用多少。需要时间判断时，请转到本章的撤稿前后和固定观察窗分析。'];
  if (chart.chart_id === 'C2' || chart.chart_id === 'C3' || chart.chart_id === 'C4') return ['从全库其他文献的参考文献列表寻找指向这些目标论文的引用，并按“引用方 ID—目标 ID”去重。目标论文本身引用了谁不是这里统计的入边。', '用引用方的发表日期近似引用时间。同日或日期区间相交不能硬分前后；固定年限分析只纳入已经走完相应日历观察窗的论文，并把观测到零引用的论文留在基数内。'];
  if (chart.metric_id.endsWith('_cohort_per_10k')) return ['先在同一文献类型、发表年份和分类范围内数出全部合格发表论文，再数出其中带撤稿标记或被 RW 记录的论文。每万篇比例 = 记录论文数 ÷ 同口径发表论文数 × 10,000。', '这不是某年所有学者发生不端的概率。近期发表的论文可观察时间更短；不同学科、时期和资料覆盖也会改变比例。'];
  if (chart.chart_id.startsWith('R')) return ['一篇原论文可能对应多条撤稿记录；本报告合并这篇论文被记录的原因标签，再按所选原因或原因族计数。多标签论文会出现在多个原因组，所以比例之和可以超过 100%。', '错误、疑虑、调查、程序描述和来源使用的不端标签保持区分。这不是独立事实裁定，也不能认为所有原因在首次撤稿日就已明确。'];
  if (chart.chart_id.startsWith('F')) return ['Topics 是 OpenAlex 的现行分类。主主题模式每篇只选一个主题，并读取它所属的领域、学科和子学科；“所有主题”模式则按每篇出现的不同分类 ID 分别计数。', '看数量时要同时考虑各学科的发文规模。某学科关联论文更多，不等于其每篇论文的记录比例更高。'];
  if (chart.chart_id.startsWith('P') || chart.chart_id.includes('publisher') || chart.chart_id === 'source-counts') return ['以主发表来源识别期刊，而不是把所有存储论文副本的网站各算一家期刊。出版商表只使用能对上 publisher 实体的期刊宿主，直接出版商和母集团分别计算。', '归属表示这份快照记录的当前关系，不保证是论文发表或撤稿当时的所有权。数量、比例和时滞也不能直接解释为出版方责任或编辑效率。'];
  if (chart.chart_id === 'T4') return ['从 RW 的原论文日期到首次有效撤稿日期计算间隔；日期无效或间隔为负的记录不进入时滞分布。', '中位数表示有效样本一半不超过这个时长；四分位区间描述中间一半样本，不是置信区间。这只是已有撤稿记录的分布。'];
  if (chart.chart_id.startsWith('T') || chart.chart_id === 'annual-growth') return ['发表年与撤稿年回答不同问题：前者看这些论文何时问世，后者看数据库在何时记录了撤稿。通知更新日期和快照下载日期不拿来充当撤稿日期。', '本图只使用标明的数据范围；未完整年度、小基数、缺失日期和零值分别保留，不把近期较少记录解释为情况改善。'];
  return ['先核对本图的研究范围、观察截止日和计数基数，再比较数值。缺失、未计算和观测零值不是同一种状态。', '完整数值、导出字段和可复核的处理版本可在下方数据与技术信息中查看。'];
}
