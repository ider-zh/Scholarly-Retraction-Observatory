"""Two-level subject explorer: exact counts, coverage shares and cohort rates."""

from collections import Counter
import json
from pathlib import Path

import duckdb
import pyarrow.parquet as pq

from .concept_analysis import concept_members
from .taxonomy import PREFIXES, SOURCE, subject_parts
from .validate_snapshot import digest


REFERENCE = Path(__file__).resolve().parents[1]/'data/reference/openalex-concept-tree-v3.json'


def series(counter, years):
    return [sum(counter.values()), *[counter[year] for year in years]]


def subject_nodes(papers, years):
    nodes, counters = {}, {}
    for paper in papers:
        members = set()
        for subject in paper.get('subjects') or ['未提供 Subject']:
            prefix, label = subject_parts(subject)
            parent, child = 'rw-'+prefix, 'subject-'+digest(subject.encode())[:16]
            nodes[parent] = {'id': parent, 'label': PREFIXES[prefix][0], 'level': 0, 'parents': [], 'missing': prefix == 'UNKNOWN'}
            nodes[child] = {'id': child, 'label': label, 'level': 1, 'parents': [parent], 'missing': prefix == 'UNKNOWN'}
            members.update((parent, child))
        year = int(paper['published'][:4]) if paper.get('published') else 0
        for identifier in members:
            counters.setdefault(identifier, Counter())[year] += 1
    for identifier, node in nodes.items():
        node['counts'] = {'B': series(counters[identifier], years)}
        node['denominator'] = None
    totals = Counter(int(paper['published'][:4]) if paper.get('published') else 0 for paper in papers)
    return {'id': 'subjects', 'label': 'RW Subject', 'levels': ['主类', 'Subject 子学科'], 'populations': ['B'],
        'method': 'RW 官方 Subject 前缀为主类，完整标签为子学科。每篇在每个节点只计一次；同一主类多个标签先去重。以原论文发表年看队列，不把标签占比称为撤稿率。',
        'rate_policy': 'RW 没有全体发表论文分母，不能计算学科撤稿率；可查看该学科占 RW 撤稿论文的覆盖比例。',
        'reference': SOURCE, 'counts': {'B': series(totals, years)}, 'denominator': None,
        'nodes': sorted(nodes.values(), key=lambda node: (node['level'], node['id']))}


def build_explorer(release_dir, provenance, validation, entries, papers, works, cd, denominators, flagged):
    release_dir = Path(release_dir)
    marker_path = release_dir/'taxonomy-complete.json'
    if not marker_path.exists():
        return None
    marker = json.loads(marker_path.read_text())
    if marker['scan_config_sha256'] != provenance['config_sha256'] or marker['files'] != len(entries):
        raise ValueError('Taxonomy scan identity mismatch')
    paths = []
    for entry in entries:
        path = Path(marker['directory'])/(digest(entry['key'].encode())+'.parquet')
        checkpoint = json.loads(path.with_suffix('.json').read_text())
        if checkpoint['source_fingerprint'] != digest(json.dumps(entry, sort_keys=True).encode()) or checkpoint['sha256'] != digest(path.read_bytes()):
            raise ValueError('Taxonomy shard integrity failed')
        paths.append(str(path))
    with duckdb.connect(config={'threads': 16, 'memory_limit': '32GB'}) as connection:
        connection.read_parquet(paths).create_view('taxonomy_counts')
        rows = connection.execute('SELECT dimension, group_id, year, sum(denominator)::BIGINT, sum(flagged)::BIGINT FROM taxonomy_counts GROUP BY ALL').fetchall()
    counts, bases = {}, {}
    for dimension, identifier, year, base, numerator in rows:
        counts.setdefault((dimension, identifier), Counter())[year] = numerator
        bases.setdefault((dimension, identifier), Counter())[year] = base
    expected_base, expected_flag = Counter(), Counter()
    for (kind, year), count in denominators.items():
        if kind == 'article':
            expected_base[year if year >= 2000 else 0] += count
    for (kind, year), count in flagged.items():
        if kind == 'article':
            expected_flag[year if year >= 2000 else 0] += count
    if bases.get(('scope', 'all'), Counter()) != expected_base or counts.get(('scope', 'all'), Counter()) != expected_flag:
        raise ValueError('Taxonomy cohorts differ from validated article denominator or A1')
    for dimension in ('field', 'subfield'):
        partition = Counter()
        for (category, identifier), values in bases.items():
            if category == dimension:
                partition.update(values)
        if partition != expected_base:
            raise ValueError('Topic partition does not reproduce D')
    reference = json.loads(REFERENCE.read_text())
    metadata = {'field': {}, 'subfield': {}, 'concept0': {}, 'concept1': {}}
    validation_path = Path(provenance['validation_report'])
    catalog_entries = json.loads((validation_path.parent/'files.json').read_text())
    for entry in catalog_entries:
        if entry['entity'] not in ('fields', 'subfields', 'concepts'):
            continue
        path = Path(validation['snapshot_dir'])/entry['key']
        stat = path.stat()
        if stat.st_size != entry['actual_bytes'] or stat.st_mtime_ns != entry['mtime_ns']:
            raise ValueError('Taxonomy catalog changed after validation')
        columns = ['id', 'display_name', 'level'] if entry['entity'] == 'concepts' else ['id', 'display_name', 'field'] if entry['entity'] == 'subfields' else ['id', 'display_name']
        for node in pq.ParquetFile(path).read(columns=columns).to_pylist():
            dimension = 'concept'+str(node['level']) if entry['entity'] == 'concepts' else entry['entity'][:-1]
            if dimension not in metadata:
                continue
            parents = reference['parents'].get(node['id'], []) if dimension == 'concept1' else [(node.get('field') or {}).get('id')] if dimension == 'subfield' else []
            metadata[dimension][node['id']] = {'id': node['id'], 'label': node.get('display_name') or node['id'],
                'level': int(dimension in ('subfield', 'concept1')), 'parents': [parent for parent in parents if parent]}
    matched = {}
    for identifier in cd:
        work = works[identifier]
        year = work['publication_year'] if work['publication_year'] >= 2000 else 0
        for dimension in ('field', 'subfield'):
            node = work['topic'].get(dimension) or {}
            member = node.get('id') or 'unknown'
            matched.setdefault((dimension, member), Counter())[year] += 1
            if member != 'unknown' and member not in metadata[dimension]:
                parent = (work['topic'].get('field') or {}).get('id')
                metadata[dimension][member] = {'id': member, 'label': node.get('display_name') or member,
                    'level': int(dimension == 'subfield'), 'parents': [parent] if dimension == 'subfield' and parent else []}
    concept_marker = json.loads((release_dir/'concepts-complete.json').read_text())
    seen = set()
    for entry in entries:
        path = Path(concept_marker['directory'])/(digest(entry['key'].encode())+'.parquet')
        checkpoint = json.loads(path.with_suffix('.json').read_text())
        if checkpoint['sha256'] != digest(path.read_bytes()) or checkpoint['source_fingerprint'] != digest(json.dumps(entry, sort_keys=True).encode()):
            raise ValueError('Concept extraction integrity failed')
        for batch in pq.ParquetFile(path).iter_batches():
            for record in batch.to_pylist():
                if record['id'] not in cd:
                    continue
                if record['id'] in seen:
                    raise ValueError('Duplicate Concept identity')
                seen.add(record['id'])
                year = works[record['id']]['publication_year']
                year = year if year >= 2000 else 0
                for level in (0, 1):
                    members = concept_members(record['concepts'], level)
                    for member in members or {'unknown': '标签缺失'}:
                        matched.setdefault(('concept'+str(level), member), Counter())[year] += 1
                        if member != 'unknown' and member not in metadata['concept'+str(level)]:
                            metadata['concept'+str(level)][member] = {'id': member, 'label': members[member], 'level': level, 'parents': reference['parents'].get(member, [])}
    if seen != set(cd):
        raise ValueError('Concept extraction missing matched candidates')
    year_end = int(validation['oa_snapshot_date'][:4])
    years = list(range(2000, year_end+1))
    totals = {'A1': series(expected_flag, years), 'C_D': series(Counter(works[identifier]['publication_year'] for identifier in cd), years)}
    denominator = series(expected_base, years)
    taxonomies = [subject_nodes(papers, years)]
    for taxonomy, dimensions in [('topics', ('field', 'subfield')), ('concepts', ('concept0', 'concept1'))]:
        nodes = []
        for dimension in dimensions:
            level = dimensions.index(dimension)
            keys = sorted(set(metadata[dimension]) | {identifier for category, identifier in bases if category == dimension} | {'unknown'})
            for identifier in keys:
                node = dict(metadata[dimension].get(identifier, {'id': dimension+':unknown' if identifier == 'unknown' else identifier,
                    'label': ('主学科' if level == 0 else '子学科')+'标签缺失' if identifier == 'unknown' else identifier,
                    'level': level, 'parents': [], 'missing': identifier == 'unknown'}))
                node['counts'] = {'A1': series(counts.get((dimension, identifier), Counter()), years),
                                  'C_D': series(matched.get((dimension, identifier), Counter()), years)}
                node['denominator'] = series(bases.get((dimension, identifier), Counter()), years)
                if any(numerator > base for values in node['counts'].values() for numerator, base in zip(values, node['denominator'])):
                    raise ValueError('Taxonomy numerator outside matching publication denominator: '+identifier)
                nodes.append(node)
        orphan_id = taxonomy+'-unknown-parent'
        roots = {node['id'] for node in nodes if node['level'] == 0}
        for node in nodes:
            if node['level'] == 1:
                node['parents'] = [parent for parent in node['parents'] if parent in roots] or [orphan_id]
        if any(orphan_id in node['parents'] for node in nodes):
            nodes.append({'id': orphan_id, 'label': '父级未提供 / 标签缺失', 'level': 0, 'parents': [], 'navigation_only': True,
                'counts': {population: [0]*len(denominator) for population in totals}, 'denominator': [0]*len(denominator)})
        taxonomies.append({'id': taxonomy, 'label': 'OpenAlex Topics' if taxonomy == 'topics' else 'OpenAlex Concepts（旧体系）',
            'levels': ['主学科 Field', '子学科 Subfield'] if taxonomy == 'topics' else ['主学科 Level 0', '子学科 Level 1'],
            'populations': ['A1', 'C_D'], 'counts': totals, 'denominator': denominator, 'nodes': nodes,
            'method': '按主主题的 Field → Subfield，每篇每层只计一次；含无标签论文的分层总数核对全体发文基数。' if taxonomy == 'topics' else '按快照已有第 0/1 级概念 ID 在篇内去重，含已附带的低分/零分标签。不重新打标签。历史官方 V3 祖先链仅用于树导航；多父级不重复存储同一概念统计，不能用子节点加总推算父节点。',
            'rate_policy': '每万篇比例 = 本节点记录论文数 / 同范围、同分类、同发表年份的全部合格 article × 10,000。Concepts 仅代表已有旧标签的可比记录，不是当前分类下的总体风险。' if taxonomy == 'concepts' else '每万篇比例的分子分母使用相同 article、主体库、原论文身份、分类及发表年份口径。不是不端发生率或因果风险。',
            'reference': 'https://help.openalex.org/data/topics/' if taxonomy == 'topics' else reference['documentation']})
    return {'version': 'discipline-explorer-v1', 'year_start': 2000, 'year_end': year_end,
        'oa_cutoff': validation['oa_snapshot_date'], 'rw_cutoff': provenance['rw']['rw_snapshot_date'],
        'series_layout': 'total_then_publication_years_inclusive', 'taxonomies': taxonomies,
        'provenance': {'taxonomy_scan_sha256': marker['config_sha256'], 'taxonomy_scan_files': marker['files'],
            'concept_tree_version': reference['version'], 'concept_tree_sha256': digest(REFERENCE.read_bytes()),
            'concept_tree_artifacts': reference['sources'], 'concept_parent_source': 'official_historical_classifier_not_current_snapshot'}}
