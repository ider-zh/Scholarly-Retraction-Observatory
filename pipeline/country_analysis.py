"""Country publication cohorts using the existing role-screened dimension scan."""

from collections import Counter
from .country_grouping import VERSION as COUNTRY_GROUPING, METHOD as COUNTRY_METHOD, country_code
from .work_policy import type_selected, METHOD as BROAD_METHOD


def build_explorer(dimension_rows, works, flagged_ids, recorded_ids, oa_date, rw_date, broad=False):
    if not dimension_rows:
        return None
    years = range(2000, int(oa_date[:4]) + 1)
    denominators = Counter()
    for dimension, country, kind, year, count, weight in dimension_rows:
        if dimension in ('institution_country', 'authorship_country') and country == 'TW':
            raise ValueError('Unmerged country denominators require a new dimension scan; do not sum CN and TW aggregates')
        if dimension == 'institution_country' and country and type_selected(kind, broad) and year in years:
            denominators[(country, year)] += count
    counts = {population: Counter() for population in ('A1', 'C_D')}
    missing = {population: Counter() for population in counts}
    for population, identifiers in [('A1', flagged_ids), ('C_D', recorded_ids)]:
        for identifier in identifiers:
            work = works[identifier]
            year = work['publication_year']
            if year not in years:
                continue
            countries = {country_code(country) for country in work['countries']['institution_country']['countries']}
            if not countries:
                missing[population][year] += 1
            for country in countries:
                counts[population][(country, year)] += 1
    countries = sorted({country for country, year in denominators} | {country for counter in counts.values() for country, year in counter})
    if not countries:
        return None
    nodes = []
    for country in countries:
        denominator = [denominators[(country, year)] for year in years]
        numerators = {population: [counter[(country, year)] for year in years] for population, counter in counts.items()}
        if any(value > denominator[index] for values in numerators.values() for index, value in enumerate(values)):
            raise ValueError('Country annual numerator exceeds compatible publication denominator: ' + country)
        nodes.append({'id': country, 'denominator': [sum(denominator), *denominator],
                      'counts': {population: [sum(values), *values] for population, values in numerators.items()}})
    return {'version': 'country-cohorts-v1', 'year_start': years.start, 'year_end': years.stop - 1,
            'work_types': ['all'] if broad else ['article'],
            'oa_cutoff': oa_date, 'rw_cutoff': rw_date, 'attribution': 'institution_country',
            'populations': ['A1', 'C_D'], 'nodes': nodes, 'country_grouping_version': COUNTRY_GROUPING,
            'missing_country': {population: [sum(counter.values()), *[counter[year] for year in years]] for population, counter in missing.items()},
            'method': ('主体库宽口径 Work；' + BROAD_METHOD if broad else '主体库 article；') + '原论文身份、日期筛选与 D 一致。国家来自论文署名机构；同篇同国去重，多国各计一次。按原论文发表年分组，分母为该国同年全部合格发表论文。' + COUNTRY_METHOD,
            'limitations': ['国家表示署名机构所在地，不是作者国籍或不端责任。跨国论文会进入多个国家，不可跨国相加。',
                            'A1 是截至 OA 快照的筛选后撤稿标记论文；C_D 是同截止日前被 RW 记录撤稿并匹配、通过筛选的原论文，不是全部 RW。',
                            '近期发表队列随访较短；这是截至快照的已观测比例，不是最终撤稿概率。无机构国家的记录单列缺失，不用已知国家代填。',
                            '只为机构所在国提供同口径年度分母；不将署名地址国家或国家合作对的计数除以此分母。']}
