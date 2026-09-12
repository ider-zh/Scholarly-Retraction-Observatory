import React from 'react';

export default function AuthorIdentityNote() {
  return <aside className="report-key-boundary" aria-label="同名署名与作者身份说明">
    <h3>同名署名，不一定是同一位作者</h3>
    <p>在 RW 与 OpenAlex 的对照中，观察到了同一姓名字符串在 RW 中汇总、在 OpenAlex 中按不同作者 ID 区分的现象。RW 原始署名排行统计的是姓名字符串关联的论文；OpenAlex 作者排行统计的是各作者 ID 关联的论文。因此，RW 同名字符串的合计不能直接归给某一位个人，也不能与某个 OpenAlex 作者 ID 的数量直接等同。</p>
    <p>这项观察不等于已经逐篇核实这些署名分别属于哪些真实作者。OpenAlex 的作者消歧仍可能误合并或误拆分，两份排行的样本范围与匹配覆盖也不同，不能把数量或名次差异全部归因于同名问题。</p>
    <p>这里只补充阅读说明：保留现有 RW 姓名字符串与 OpenAlex 作者 ID，不据此清洗、合并、拆分或重新计算数据；署名关联不代表不端责任。</p>
  </aside>;
}
