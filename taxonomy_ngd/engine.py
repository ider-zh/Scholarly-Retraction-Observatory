"""Columnar membership projection and equivalent native/SQL counting routes."""

import array
import io
import json
from pathlib import Path
import struct
import subprocess

import duckdb
import pyarrow as pa

from taxonomy_ngd.core import GROUPS


def literal(value):
    return "'" + str(value).replace("'", "''") + "'"


def connect(entities, memory='6GiB'):
    connection = duckdb.connect(config={'threads': '1', 'memory_limit': memory})
    connection.execute("SET temp_directory = ''")
    connection.execute('SET preserve_insertion_order = true')
    for name, columns in [('concepts', ['id', 'level']), ('topics', ['id', 'subfield', 'field', 'domain'])]:
        rows = []
        for item in entities[name].values():
            rows.append({column: item[column] if column in ('id', 'level') else item[column]['id'] for column in columns})
        connection.register(name + '_lookup', pa.Table.from_pylist(rows))
    return connection


def project(connection, source):
    for name in ('raw', 'concept_labels', 'topic_labels', 'audits', 'membership'):
        connection.execute(f'DROP TABLE IF EXISTS {name}')
    source_sql = 'input_batch' if isinstance(source, pa.Table) else f'read_parquet({literal(source)})'
    if isinstance(source, pa.Table):
        connection.register('input_batch', source)
    connection.execute(f'''CREATE TABLE raw AS SELECT row_number() OVER () AS row_index,
        id, publication_year, type, is_retracted, is_xpac, concepts, topics FROM {source_sql}''')
    connection.execute('''CREATE TABLE concept_labels AS SELECT raw.row_index, raw.id AS work_id,
        label.id AS attached_id, label.level AS attached_level, lookup.id, lookup.level
        FROM raw, unnest(raw.concepts) AS attached(label)
        LEFT JOIN concepts_lookup lookup ON lookup.id = label.id''')
    connection.execute('''CREATE TABLE topic_labels AS SELECT raw.row_index, raw.id AS work_id,
        label.id AS attached_id, lookup.id, lookup.subfield, lookup.field, lookup.domain,
        label.subfield.id AS attached_subfield, label.field.id AS attached_field, label.domain.id AS attached_domain
        FROM raw, unnest(raw.topics) AS attached(label)
        LEFT JOIN topics_lookup lookup ON lookup.id = label.id''')
    connection.execute('''CREATE TABLE audits AS
        SELECT row_index, work_id, 'unresolved_concept' AS kind, attached_id AS label_id,
               attached_id AS actual, NULL::VARCHAR AS expected, true AS blocking
        FROM concept_labels WHERE id IS NULL
        UNION ALL SELECT row_index, work_id, 'embedded_concept_level', attached_id,
            attached_level::VARCHAR, level::VARCHAR, false FROM concept_labels
            WHERE id IS NOT NULL AND attached_level IS DISTINCT FROM level
        UNION ALL SELECT row_index, work_id, 'unresolved_topic', attached_id, attached_id, NULL, true
            FROM topic_labels WHERE id IS NULL
        UNION ALL SELECT row_index, work_id, 'topic_subfield_conflict', attached_id, attached_subfield, subfield, true
            FROM topic_labels WHERE id IS NOT NULL AND attached_subfield IS DISTINCT FROM subfield
        UNION ALL SELECT row_index, work_id, 'topic_field_conflict', attached_id, attached_field, field, true
            FROM topic_labels WHERE id IS NOT NULL AND attached_field IS DISTINCT FROM field
        UNION ALL SELECT row_index, work_id, 'topic_domain_conflict', attached_id, attached_domain, domain, true
            FROM topic_labels WHERE id IS NOT NULL AND attached_domain IS DISTINCT FROM domain
        UNION ALL SELECT row_index, id, 'invalid_work_id', NULL, id, NULL, true FROM raw
            WHERE id IS NULL OR NOT regexp_full_match(id, 'https://openalex[.]org/W[1-9][0-9]*')
            OR try_cast(substr(id,23) AS UBIGINT) IS NULL''')
    connection.execute('''CREATE TABLE membership AS WITH concepts AS (
        SELECT row_index, list_sort(list_distinct(list(id) FILTER (WHERE level=0))) AS concept_l0_ids,
               list_sort(list_distinct(list(id) FILTER (WHERE level=1))) AS concept_l1_ids
        FROM concept_labels GROUP BY row_index
      ), topics AS (
        SELECT row_index, list_sort(list_distinct(list(field))) AS topic_field_ids,
               list_sort(list_distinct(list(subfield))) AS topic_subfield_ids
        FROM topic_labels GROUP BY row_index
      ), problems AS (
        SELECT row_index, list_sort(list_distinct(list(kind))) AS flags FROM audits GROUP BY row_index
      ) SELECT raw.id AS work_id, try_cast(substr(raw.id,23) AS UBIGINT) AS work_id_numeric,
        raw.publication_year, raw.type AS work_type, raw.is_retracted, raw.is_xpac,
        coalesce(concept_l0_ids, []::VARCHAR[]) AS concept_l0_ids,
        coalesce(concept_l1_ids, []::VARCHAR[]) AS concept_l1_ids,
        coalesce(topic_field_ids, []::VARCHAR[]) AS topic_field_ids,
        coalesce(topic_subfield_ids, []::VARCHAR[]) AS topic_subfield_ids,
        CASE WHEN raw.concepts IS NULL THEN 'null' WHEN len(raw.concepts)=0 THEN 'empty' ELSE 'present' END AS concept_source_list_state,
        CASE WHEN raw.topics IS NULL THEN 'null' WHEN len(raw.topics)=0 THEN 'empty' ELSE 'present' END AS topic_source_list_state,
        coalesce(flags, []::VARCHAR[]) AS membership_quality_flags
      FROM raw LEFT JOIN concepts USING (row_index) LEFT JOIN topics USING (row_index)
      LEFT JOIN problems USING (row_index)''')
    total, unique = connection.execute('SELECT count(*), count(DISTINCT work_id) FROM membership').fetchone()
    if total != unique:
        connection.execute('''INSERT INTO audits SELECT row_index, id, 'duplicate_work_id', NULL, id, NULL, true
            FROM raw WHERE id IN (SELECT work_id FROM membership GROUP BY work_id HAVING count(*)>1)''')
    coverage = {}
    for taxonomy, left, right, state in [('concepts', GROUPS[0], GROUPS[1], 'concept_source_list_state'),
                                         ('topics', GROUPS[2], GROUPS[3], 'topic_source_list_state')]:
        counts = connection.execute(f'''SELECT count(*) FILTER (WHERE {state}='present'),
           count(*) FILTER (WHERE len({left})>0), count(*) FILTER (WHERE len({right})>0),
           count(*) FILTER (WHERE len({left})>0 AND len({right})>0),
           count(*) FILTER (WHERE {state}='null'), count(*) FILTER (WHERE {state}='empty') FROM membership''').fetchone()
        coverage[taxonomy] = dict(zip(['tagged', 'l0', 'l1', 'both', 'null', 'empty'], counts))
    audit = connection.execute('SELECT kind, blocking, count(*) FROM audits GROUP BY ALL').fetchall()
    distribution = connection.execute('''SELECT count(*) FILTER (WHERE is_xpac), count(*) FILTER (WHERE is_xpac=false),
        max(len(concepts)), max(len(topics)), sum(len(concepts)), sum(len(topics)) FROM raw''').fetchone()
    return {'rows': total, 'unique_local_work_ids': unique, 'coverage': coverage,
            'source_distribution': dict(zip(['xpac', 'core', 'max_concepts', 'max_topics', 'concept_entries', 'topic_entries'], distribution)),
            'audit': [{'kind': kind, 'blocking': block, 'rows': rows} for kind, block, rows in audit]}


def count_sql(connection):
    rows = []
    for taxonomy, left, right in [('concepts', GROUPS[0], GROUPS[1]), ('topics', GROUPS[2], GROUPS[3])]:
        for kind, column in [('l0', left), ('l1', right)]:
            values = connection.execute(f'SELECT label, count(*)::BIGINT FROM membership, unnest({column}) AS nodes(label) GROUP BY label').fetchall()
            rows.extend({'taxonomy': taxonomy, 'kind': kind, 'l0_id': label if kind == 'l0' else None,
                         'l1_id': label if kind == 'l1' else None, 'count': count} for label, count in values)
        values = connection.execute(f'''SELECT left_id, right_id, count(*)::BIGINT FROM membership,
            unnest({left}) AS left_nodes(left_id), unnest({right}) AS right_nodes(right_id) GROUP BY ALL''').fetchall()
        rows.extend({'taxonomy': taxonomy, 'kind': 'joint', 'l0_id': left_id, 'l1_id': right_id, 'count': count}
                    for left_id, right_id, count in values)
    return rows


def encode_membership(table, nodes):
    dictionaries = [[node['id'] for node in nodes if node['taxonomy'] == taxonomy and node['level'] == level]
                    for taxonomy, level in [('concepts', 0), ('concepts', 1), ('topics', 0), ('topics', 1)]]
    output = io.BytesIO()
    output.write(struct.pack('<5I', table.num_rows, *(len(values) for values in dictionaries)))
    for column, identifiers in zip(GROUPS, dictionaries):
        lookup = {identifier: index for index, identifier in enumerate(identifiers)}
        values = table[column].combine_chunks()
        offsets = array.array('I', values.offsets.to_pylist())
        encoded = array.array('I', (lookup[identifier] for identifier in values.values.to_pylist()))
        if __import__('sys').byteorder != 'little':
            offsets.byteswap()
            encoded.byteswap()
        output.write(struct.pack('<I', len(encoded)))
        output.write(offsets.tobytes())
        output.write(encoded.tobytes())
    return output.getvalue(), dictionaries


def decode_counts(encoded, dictionaries):
    values = json.loads(encoded)
    rows = []
    cursor = 0
    for taxonomy, left, right in [('concepts', dictionaries[0], dictionaries[1]), ('topics', dictionaries[2], dictionaries[3])]:
        for kind, identifiers in [('l0', left), ('l1', right)]:
            for identifier in identifiers:
                count = values[cursor]
                cursor += 1
                if count:
                    rows.append({'taxonomy': taxonomy, 'kind': kind, 'l0_id': identifier if kind == 'l0' else None,
                                 'l1_id': identifier if kind == 'l1' else None, 'count': count})
        for left_id in left:
            for right_id in right:
                count = values[cursor]
                cursor += 1
                if count:
                    rows.append({'taxonomy': taxonomy, 'kind': 'joint', 'l0_id': left_id, 'l1_id': right_id, 'count': count})
    if cursor != len(values):
        raise ValueError('Invalid native output')
    return rows


def count_native(connection, nodes, binary):
    table = connection.execute('SELECT ' + ','.join(GROUPS) + ' FROM membership').fetch_arrow_table()
    encoded, dictionaries = encode_membership(table, nodes)
    output = subprocess.run([str(binary)], input=encoded, capture_output=True, check=True).stdout
    return decode_counts(output, dictionaries)


COUNT_SCHEMA = pa.schema([('taxonomy', pa.string()), ('kind', pa.string()), ('l0_id', pa.string()),
                          ('l1_id', pa.string()), ('count', pa.int64())])
