"""Explicit broad candidate policy, separate from the historical article policy."""

import json
from pathlib import Path


VERSION = 'original-first-independent-notices-v2'
METHOD = '宽口径候选：不限 OpenAlex 文献类型；标题前缀和身份冲突仅作核查标记。仅排除有不同原文标识符关联、且自身未命中原文标识符的独立通知。保留无法判定的记录，不宣称均为已确认原论文。'


def is_broad(provenance):
    return provenance['config']['role_policy'] == VERSION


def broad_run(release_dir):
    return is_broad(json.loads((Path(release_dir) / 'provenance.json').read_text()))


def type_selected(kind, broad=False):
    return broad or kind == 'article'


def notice_links(notices):
    links = {}
    for notice in notices:
        for namespace in ('doi', 'pmid'):
            identifier = notice.get(namespace)
            if identifier:
                links.setdefault((namespace, identifier), set()).update(notice['original_ids'])
    return links


def classify(work, links):
    originals = set()
    for namespace in ('doi', 'pmid'):
        originals.update(links.get((namespace, work.get(namespace)), ()))
    distinct = sorted(identifier for identifier in originals
                      if identifier.startswith('doi:') and work.get('doi') and identifier[4:] != work['doi']
                      or identifier.startswith('pmid:') and work.get('pmid') and identifier[5:] != work['pmid'])
    independent = bool(distinct) and not work['original_evidence']
    role = 'known_notice' if independent else 'original_supported' if work['original_evidence'] else 'unresolved'
    uncertain = not independent and (not work['original_evidence'] or work['notice_evidence'] or work['title_suspected'] or work['type'] != 'article')
    return role, uncertain, distinct
