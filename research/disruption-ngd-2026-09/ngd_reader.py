import copy
import math
import statistics


def average_ranks(values):
    positions = {}
    for position, value in enumerate(sorted(values), 1):
        positions.setdefault(value, []).append(position)
    return [statistics.mean(positions[value]) for value in values]


def annotate_panorama(slide, correlations):
    revised = copy.deepcopy(slide)
    results = {}
    for taxonomy in ['concepts', 'topics']:
        rows = [row for row in correlations if row['taxonomy'] == taxonomy
                and row['reference'] == 'Mathematics' and row['scope'] == 'all_unique_children']
        if len(rows) != 1:
            raise ValueError('Expected one frozen mathematics correlation per taxonomy')
        row = rows[0]
        points = [point for series in slide['chart']['series']
                  if series['name'].split(' · ')[0] == taxonomy for point in series['points']]
        if len(points) != row['children']:
            raise ValueError('Panorama subject count differs from correlation cohort')
        observed = statistics.correlation(average_ranks([point['x'] for point in points]),
                                          average_ranks([point['y'] for point in points]))
        if not math.isclose(observed, row['spearman_crude'], abs_tol=1e-12):
            raise ValueError('Panorama correlation differs from frozen evidence')
        results[taxonomy] = row
    concepts, topics = results['concepts'], results['topics']
    revised['subtitle'] = (f"数学NGD × 撤稿标记占比：Concepts ρ={concepts['spearman_crude']:+.3f}（{concepts['children']}个）；"
                           f"Topics ρ={topics['spearman_crude']:+.3f}（{topics['children']}个）")
    if not (-0.15 < concepts['spearman_crude'] < 0 < topics['spearman_crude'] < 0.15):
        raise ValueError('Observed coefficients no longer support weak opposite-direction wording')
    revised['takeaway'] = '两组ρ均接近0：Concepts弱负向、Topics弱正向；不能据此概括“近数学、低占比”。'
    revised['source'] += ' ρ分别用各体系全部图中子学科计算（含n<20），不是按颜色分组计算；未做年份调整。下一页为调整对照。'
    return revised
