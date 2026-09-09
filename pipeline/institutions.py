"""Conservative, exact placeholder matching; preserve actual affiliation strings."""
import re
import unicodedata
UNKNOWN_ID = '__unknown_institution__'
UNKNOWN_NAME = '机构未知（缺失值合并）'
MISSING = {'', 'unknown', 'unavailable', 'not available', 'not applicable',
           'not reported', 'not provided', 'not specified', 'none', 'null', 'n/a', 'na',
           'affiliation unknown', 'affiliations unknown', 'affliation unknown',
           'affiliation not provided to ssrn', 'no affiliation available',
           'no affiliations available', 'no affiliation given', 'no affiliation found'}
def is_missing(value):
    value = unicodedata.normalize('NFKC', value or '').casefold()
    value = re.sub(r'\s+', ' ', value).strip().strip(' .,:;!?-–—')
    return value in MISSING

def institution_members(paper):
    return {UNKNOWN_ID if is_missing(v) else v: UNKNOWN_NAME if is_missing(v) else v
            for v in (paper.get('institutions') or [''])}
