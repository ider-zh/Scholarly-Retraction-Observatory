import argparse
import hashlib
import importlib.util
import json
from pathlib import Path


MODULE_PATH = Path(__file__).with_name('disruption_analysis.py')
SPECIFICATION = importlib.util.spec_from_file_location('disruption_analysis', MODULE_PATH)
ANALYSIS = importlib.util.module_from_spec(SPECIFICATION)
SPECIFICATION.loader.exec_module(ANALYSIS)


def digest(path):
    checksum = hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b''):
            checksum.update(block)
    return checksum.hexdigest()


def query_sql():
    expression = ANALYSIS.variant_expression(ANALYSIS.VARIANTS[0])
    return f'''WITH scored AS (SELECT in_oa,in_rw,is_retracted,try_cast(end_ex_5y AS DATE)<retraction_date AND publication_after_retraction IS NOT TRUE AS pre_eligible,{expression} AS score FROM metrics), grouped AS (SELECT score,'oa_all' population FROM scored WHERE in_oa UNION ALL SELECT score,'oa_retracted' FROM scored WHERE in_oa AND is_retracted UNION ALL SELECT score,'oa_not_marked' FROM scored WHERE in_oa AND NOT is_retracted UNION ALL SELECT score,'rw' FROM scored WHERE in_rw UNION ALL SELECT score,'rw_pre_retraction' FROM scored WHERE in_rw AND pre_eligible) SELECT population,count(score) qualified_count,avg(score) mean_cd,quantile_cont(score,.5) median_cd,quantile_cont(score,.25) q25_cd,quantile_cont(score,.75) q75_cd,count(*) FILTER(WHERE score>0)::DOUBLE/nullif(count(score),0) positive_fraction FROM grouped GROUP BY population'''


def export(output):
    source = output / 'cohort_metrics.parquet'
    destination = output / 'global_main_metrics.json'
    source_hash = digest(source)
    source_bytes = source.stat().st_size
    variant = list(ANALYSIS.VARIANTS[0])
    query = query_sql()
    if destination.exists():
        current = json.loads(destination.read_text())
        expected = {'source': str(source), 'source_sha256': source_hash,
                    'source_bytes': source_bytes, 'variant': variant,
                    'sql': query, 'code_sha256': ANALYSIS.CODE_SHA256}
        for name, value in expected.items():
            if current.get(name) != value:
                raise ValueError(f'Existing global metrics differ in {name}; preserve them and use a new version')
        assert {row['population'] for row in current['metrics']} == {'oa_all', 'oa_retracted', 'oa_not_marked', 'rw', 'rw_pre_retraction'}
        print('Existing global metrics verified; no files rewritten', flush=True)
        return current
    database = ANALYSIS.connection(4, '16GB')
    database.read_parquet(str(source)).create_view('metrics')
    cursor = database.execute(query)
    columns = [column[0] for column in cursor.description]
    metrics = [dict(zip(columns, row)) for row in cursor.fetchall()]
    result = {'source': str(source), 'source_sha256': source_hash, 'source_bytes': source_bytes,
              'variant': variant, 'sql': query, 'metrics': metrics, 'code_sha256': ANALYSIS.CODE_SHA256,
              'exporter_sha256': digest(Path(__file__))}
    ANALYSIS.write_json(destination, result)
    database.close()
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=ANALYSIS.OUTPUT)
    arguments = parser.parse_args()
    export(arguments.output)


if __name__ == '__main__':
    main()
