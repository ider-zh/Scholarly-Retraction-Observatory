export const EXCLUSION_GROUPS = {
  excluded_known_notice: {title: '有通知身份证据：不把通知再算成原论文', explanation: '这些 article 记录命中了 RW 通知标识符。通知记录与被撤回的原论文不是同一个计数对象；标题没有“撤稿”字样也可能是通知。'},
  excluded_work_type_other: {title: '其他文献类型：先按研究范围排除', explanation: '筛选先检查 OpenAlex 的文献类型。retraction 表示撤稿通知类型，不应再当作额外的原论文；其他非 article 类型则需按具体字段理解，不能一概视为无效记录。'},
  excluded_work_type_review: {title: '综述类型：范围排除，不等于不是撤稿论文', explanation: '默认总体只纳入 article，因而排除了 OpenAlex 标为 review 的记录。综述本身也可以被撤稿；这只能说明它不在当前类型范围内，不能证明它无效。元数据类型也不能替代对正文的判断。'},
  excluded_suspected_notice: {title: '标题疑似通知：需要保留误排的可能', explanation: '这些记录没有命中已知原论文或通知标识符，只因标题前缀触发规则。尤其是“Retracted:”也可能用于标记已撤稿的原论文，不能仅凭此前缀认定它是通知。'},
  excluded_conflict: {title: '原论文与通知证据冲突：暂缓纳入', explanation: '同一 Work 同时命中原论文与通知标识符。暂缓纳入是避免身份混淆的保守处理，不是确认它一定不是原论文。'},
  excluded_date: {title: '日期不符合当前观察范围', explanation: '记录的发表年或发表日期不符合当前快照截止范围；这是时间范围排除，不是撤稿真实性判断。'},
};

export const EXAMPLE_REVIEWS = {
  W3128835701: {text: 'PubMed 将此 DOI 列为 Retraction Notice，并链接到另一个原论文 DOI（10.1073/pnas.86.20.7928）。这一例支持区分通知与原文，而不能只看标题。', url: 'https://pubmed.ncbi.nlm.nih.gov/1502206/', label: 'PubMed：通知与原论文关系'},
  W4295766134: {text: 'PubMed 列出的是已撤稿原文，并另列撤稿通知 DOI（10.1155/2023/9854393）；其类型同时含 Journal Article 与 Review。这一例说明：按 review 排除是范围规则，并不等于它不是被撤稿的原论文。', url: 'https://pubmed.ncbi.nlm.nih.gov/36158123/', label: 'PubMed：原论文及撤稿通知'},
};

export function validateScreeningExamples(data, manifest, chart) {
  const check = (condition, message) => {if (!condition) throw new Error(message);};
  const reassessed = data?.schema_version === 2;
  check((data?.schema_version === 1 && data.sampling_version === 'screening-examples-v1') || (reassessed && data.sampling_version === 'legacy-screening-reassessment-v2'), '排除案例格式不匹配');
  for (const key of ['oa_snapshot_date', 'rw_snapshot_date', 'oa_manifest_sha256', 'scan_config_sha256', 'role_policy_version']) check(data[key] === manifest[key], '排除案例与当前来源或筛选版本不匹配');
  check(chart.chart_id === 'screening' && chart.slice_id === 'A0-screening', '排除案例不属于当前切片');
  const counts = Object.fromEntries(chart.rows.map(row => [row.id, row.numerator]));
  check(Object.keys(counts).length === Object.keys(data.screening_counts || {}).length && Object.entries(counts).every(([key, value]) => data.screening_counts[key] === value), '排除案例与当前筛选数量不一致');
  check(Array.isArray(data.items) && data.items.length > 0 && data.items.length <= 12 && data.sample_count === data.items.length, '排除案例数量超出约定');
  check(new Set(data.items.map(row => row.id)).size === data.items.length, '排除案例 Work 重复');
  const allowed = ['id', 'doi', 'pmid', 'publication_year', 'publication_date', 'type', 'is_retracted', 'is_xpac', 'original_evidence', 'notice_evidence', 'title_suspected', 'document_role', 'exclusion', 'stratum', 'title'];
  if (reassessed) allowed.push('linked_distinct_originals', 'current_outcome');
  for (const row of data.items) {
    check(Object.keys(row).every(key => allowed.includes(key)), '排除案例包含非许可字段');
    check(/^https:\/\/openalex\.org\/W[1-9][0-9]*$/.test(row.id) && row.is_retracted === true && row.is_xpac === false, '案例不是主体库撤稿标记 Work');
    check(row.title === null || (typeof row.title === 'string' && row.title.length <= 4000), '案例标题格式错误');
    check(row.doi === null || /^10\.\d{4,9}\/\S+$/i.test(row.doi), '案例 DOI 格式错误');
    check(Object.hasOwn(EXCLUSION_GROUPS, row.stratum) && Number.isSafeInteger(data.stratum_counts?.[row.stratum]) && data.stratum_counts[row.stratum] > 0, '案例分层不匹配');
    check(['original_evidence', 'notice_evidence', 'title_suspected'].every(key => typeof row[key] === 'boolean'), '案例身份字段格式错误');
    const role = row.original_evidence && row.notice_evidence ? 'conflict' : row.notice_evidence ? 'known_notice' : row.original_evidence ? 'original_supported' : row.title_suspected ? 'suspected_notice' : 'unresolved';
    check(row.document_role === role, '案例身份与证据不一致');
    const cutoff = data.oa_snapshot_date;
    const reason = row.type !== 'article' ? 'excluded_work_type' : !['original_supported', 'unresolved'].includes(row.document_role) ? `excluded_${row.document_role}` : !row.publication_year || row.publication_year < 1 || row.publication_year > Number(cutoff.slice(0, 4)) || (row.publication_date && row.publication_date > cutoff) ? 'excluded_date' : 'retained_A1';
    check(reason === row.exclusion && reason !== 'retained_A1', '案例不满足记录的排除规则');
    check(row.stratum === (reason === 'excluded_work_type' ? `${reason}_${row.type === 'review' ? 'review' : 'other'}` : reason), '案例排除与分层不一致');
    if (reassessed) {
      check(data.role_policy_version === 'original-first-independent-notices-v2', '案例宽口径版本不匹配');
      check(Array.isArray(row.linked_distinct_originals) && row.linked_distinct_originals.every(identifier => (identifier.startsWith('doi:') && row.doi && identifier.slice(4) !== row.doi) || (identifier.startsWith('pmid:') && row.pmid && identifier.slice(5) !== row.pmid)), '缺少不同原文的关联证据');
      const independent = row.linked_distinct_originals.length > 0 && !row.original_evidence;
      const validDate = row.publication_year > 0 && row.publication_year <= Number(cutoff.slice(0, 4)) && (!row.publication_date || row.publication_date <= cutoff);
      check(row.current_outcome === (independent ? 'excluded_known_notice' : validDate ? 'retained_A1' : 'excluded_date'), '新筛选结果不一致');
    }
  }
  return data;
}
