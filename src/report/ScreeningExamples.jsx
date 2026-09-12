import React, {useEffect, useState} from 'react';
import {verifyReportBytes} from './integrity.js';
import {screeningExamplesAsset} from './screeningExamplesAsset.js';
import {EXCLUSION_GROUPS, EXAMPLE_REVIEWS, validateScreeningExamples} from './screeningExamples.js';
import './screening-examples.css';
import {BROAD_WORK_POLICY} from './workPolicy.js';

export default function ScreeningExamples({manifest, chart}) {
  const [result, setResult] = useState(null);
  const identity = `${manifest.release_id}/${chart.slice_id}`;
  useEffect(() => {
    const controller = new AbortController();
    async function load() {
      try {
        const response = await fetch(`${import.meta.env.BASE_URL}data/screening-examples.json`, {signal: controller.signal});
        if (!response.ok) throw new Error('排除案例暂时无法加载');
        const bytes = await response.arrayBuffer();
        await verifyReportBytes(bytes, screeningExamplesAsset);
        const data = validateScreeningExamples(JSON.parse(new TextDecoder().decode(bytes)), manifest, chart);
        if (!controller.signal.aborted) setResult({identity, data});
      } catch (error) {if (!controller.signal.aborted) setResult({identity, error: error.message});}
    }
    load();
    return () => controller.abort();
  }, [identity, manifest, chart]);
  const current = result?.identity === identity ? result : null;
  const reassessed = manifest.role_policy_version === BROAD_WORK_POLICY;
  return <section className="screening-examples" aria-label="排除案例核查">
    <h2>{reassessed ? '原来被排除的记录，现在如何处理？' : '被排除的记录，究竟是什么？'}</h2>
    <p>{reassessed ? '继续核对原先抽取的 10 条记录，不重新挑选有利案例。下面保留旧规则分组和旧排除依据，并逐条标明宽口径的现行处理。' : '看具体记录，才能区分“撤稿通知”“不在当前范围的原论文”和“仍需核查的身份”。以下样本解释规则如何生效，不把排除等同于记录无效。'}</p>
    {!current ? <p role="status">正在校验排除案例…</p> : current.error ? <p role="status">{current.error}。未显示旧版或替代案例；主图不受影响。</p> : <>
      <p className="screening-example-boundary"><strong>样本不能证明全部排除都正确。</strong>{reassessed ? '新口径不再因标题、类型或身份冲突自动排除。仅有明确不同原文关联的独立通知仍排除；缺少这种证据的记录保留为候选，并非宣称其身份已被确认。' : '已核对的案例支持把通知与原文分开计数；但综述类型排除只是范围选择，标题疑似通知与身份冲突仍可能排除真正的原论文。本次不改变统计或筛选结果。'}</p>
      <p className="snapshot-caption">OpenAlex 主体库撤稿标记记录；快照 {current.data.oa_snapshot_date}。按{reassessed ? '旧规则的' : ''}排除原因分层，文献类型另分综述与其他类型，每层固定抽取 2 条，共 {current.data.sample_count} 条；不是按总体比例抽样。</p>
      {Object.entries(EXCLUSION_GROUPS).map(([group, description]) => {
        const rows = current.data.items.filter(row => row.stratum === group);
        return rows.length ? <details className="screening-example-group" key={group} open={group === 'excluded_known_notice'}>
          <summary>{reassessed && '旧规则：'}{description.title}<span>样本 {rows.length} / {reassessed ? '旧规则本层' : '本层'} {current.data.stratum_counts[group].toLocaleString('zh-CN')} 条</span></summary>
          <p>{reassessed && '以下是旧规则的解释，现行决定以每条案例的“现行处理”为准：'}{description.explanation}</p>
          <ol>{rows.map(row => {
            const review = EXAMPLE_REVIEWS[row.id.split('/').at(-1)];
            return <li key={row.id}><h3><a href={row.id} target="_blank" rel="noreferrer">{row.title || '来源未提供标题'}</a></h3>
              {reassessed && <p className="screening-example-boundary"><strong>现行处理：{row.current_outcome === 'retained_A1' ? '保留为宽口径候选' : row.current_outcome === 'excluded_known_notice' ? '仍排除：有独立通知证据' : '日期不符合范围'}</strong>{row.current_outcome === 'excluded_known_notice' ? `。关联到不同原文：${row.linked_distinct_originals.join('；')}；自身无原文标识符支持。` : '。不再单凭标题、类型或冲突排除；仍保留身份核查标记。'}</p>}
              <p className="snapshot-caption">{row.id.split('/').at(-1)} · 类型 {row.type || '未提供'} · 发表年 {row.publication_year ?? '未提供'}{row.doi && <> · <a href={`https://doi.org/${row.doi}`} target="_blank" rel="noreferrer">DOI：{row.doi}</a></>}</p>
              <dl><div><dt>{reassessed ? '旧规则排除依据' : '本次排除依据'}</dt><dd>{row.exclusion === 'excluded_work_type' ? `文献类型为 ${row.type}，不满足默认 article 条件；在身份规则之前排除。` : row.exclusion === 'excluded_known_notice' ? '类型虽为 article，但命中通知标识符证据，未命中原论文标识符。' : row.exclusion === 'excluded_conflict' ? '同时命中原论文与通知标识符，身份冲突。' : row.exclusion === 'excluded_suspected_notice' ? '没有原论文或通知标识符证据，仅标题前缀命中疑似通知规则。' : '发表日期或年份不符合当前快照范围。'}</dd></div><div><dt>来源证据字段</dt><dd>原论文标识符命中：{row.original_evidence ? '是' : '否'}；通知标识符/类型命中：{row.notice_evidence ? '是' : '否'}；标题规则命中：{row.title_suspected ? '是' : '否'}。</dd></div></dl>
              {review && <p className="screening-example-review">{review.text} <a href={review.url} target="_blank" rel="noreferrer">{review.label}</a>（外部关系核查，不修改快照。）</p>}
            </li>;
          })}</ol>
        </details> : null;
      })}
      <details className="report-methods"><summary>如何抽样、如何复核？</summary><p>案例来自冻结扫描；抽样沿用下载文件中记录的旧筛选规则，现行全体筛选计数另与上图校验。层内按 SHA-256("screening-examples-v1/" + Work ID) 升序选择前 2 条，不按标题是否“像通知”挑选。综述单列是为展示研究范围的边界；各层样本数不能用于估计误排率。</p><p>标题来自同一份已验证快照；身份字段来自已有扫描。外部链接用于进一步复核，不代表所有案例都已逐篇核查。标题前缀、类型标注、标识符关联都可能有局限；判断误排率需要更大的分层随机样本与独立人工复核。</p><p>抽样版本 {current.data.sampling_version}；角色规则 {current.data.role_policy_version}。沿用旧样本中已有分组，不为新增日期排除分组补造案例。</p><a href={`${import.meta.env.BASE_URL}data/screening-examples.json`} download="screening-examples.json">下载这 {current.data.sample_count} 条案例及抽样来源</a></details>
    </>}
  </section>;
}
