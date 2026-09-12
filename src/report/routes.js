import {parseSources} from './sources.js';
import {disciplineTaxonomy} from './sections.js';

export function parseReportRoute(hash, pages) {
  const [path, query = ''] = hash.replace(/^#/, '').split('?');
  const segments = path.split('/');
  const page = segments[2] || 'overview';
  const params = new URLSearchParams(query);
  const selection = parseSources(params.get('sources'));
  const explorerSelection = Object.fromEntries(['taxonomy', 'population', 'node', 'parent', 'metric'].map(key => [key, params.get(key) || '']));
  const rejected = [...params.keys()].filter(key => !['slice', 'sources', 'view', ...Object.keys(explorerSelection)].includes(key));
  let topic = '', pathError = null;
  if (segments.length > 3) {
    if (segments.length !== 5 || segments[3] !== 'topic' || !segments[4]) pathError = '未支持的专题路径';
    else try {topic = decodeURIComponent(segments[4]);} catch {pathError = '专题路径编码无效';}
  }
  const error = !Object.hasOwn(pages, page) ? `未支持的章节：${page}` : pathError || (rejected.length ? `未支持的参数：${rejected.join(', ')}` : selection.error) || (params.has('view') && !['tree', 'charts'].includes(params.get('view')) ? '未支持的学科视图' : null) || (topic && !['discipline', 'countries'].includes(topic) && Object.values(explorerSelection).some(Boolean) ? '此专题不接受学科树参数' : null);
  const taxonomy = disciplineTaxonomy(page);
  const taxonomyError = taxonomy && explorerSelection.taxonomy && taxonomy !== explorerSelection.taxonomy ? '分类体系与当前章节不一致，请进入对应分类章节；未替换结果。' : null;
  if (taxonomy && !explorerSelection.taxonomy) explorerSelection.taxonomy = taxonomy;
  return {page: Object.hasOwn(pages, page) ? page : 'overview', topic, slice: params.get('slice') || '', sources: selection.sources, view: params.get('view'), explorerSelection, error: error || taxonomyError};
}
