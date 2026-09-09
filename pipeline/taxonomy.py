"""RW's published subject prefixes; two display levels, no inferred reassignment."""
import re
PREFIXES = {
    'B/T': ('商业与技术', 'Business and Technology'),
    'BLS': ('基础生命科学', 'Basic Life Sciences'),
    'ENV': ('环境科学', 'Environmental Sciences'),
    'HSC': ('健康科学', 'Health Sciences'),
    'HUM': ('人文学科', 'Humanities'),
    'PHY': ('物理科学', 'Physical Sciences'),
    'SOC': ('社会科学', 'Social Sciences'),
    'UNKNOWN': ('未分类', 'Unclassified'),
}
SOURCE = 'https://retractionwatch.com/retraction-watch-database-user-guide/retraction-watch-database-user-guide-appendix-a-fields/'

def subject_parts(value):
    match = re.match(r'^\(([^)]+)\)\s*(.+)$', value.strip())
    if match and match[1] in PREFIXES and match[1] != 'UNKNOWN':
        return match[1], match[2]
    return 'UNKNOWN', value.strip() or '未提供 Subject'

def labels(paper, level):
    subjects = paper.get('subjects') or ['未提供 Subject']
    if level == 1:
        return {prefix: PREFIXES[prefix][0] for prefix,_ in map(subject_parts, subjects)}
    return {s:s for s in subjects}
