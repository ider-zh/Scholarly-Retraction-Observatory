export const BROAD_WORK_POLICY = 'original-first-independent-notices-v2';
export const isBroadChart = chart => chart?.scope?.work_policy === BROAD_WORK_POLICY;
export const BROAD_WORK_METHOD = '不限 OpenAlex 文献类型；标题前缀和身份冲突不单独导致排除。仅排除有不同原文标识符关联、且自身没有原文标识符支持的独立通知；其余身份不确定记录保留为候选，不当作已逐篇确认的原论文。';
