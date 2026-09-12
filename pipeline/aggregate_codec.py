"""Lossless columnar encoding for uniform aggregate rows, never source records."""

import base64
import hashlib
import json
import zlib


def pack_json(value):
    raw = json.dumps(value, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode()
    return {'encoding': 'zlib-json-v1', 'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest(),
            'data': base64.b64encode(zlib.compress(raw, level=9)).decode('ascii')}


def pack_explorer(explorer):
    return pack_json(explorer) if sum(len(taxonomy['nodes']) for taxonomy in explorer['taxonomies']) >= 1000 else explorer


def pack_chart(chart):
    rows = chart['rows']
    if len(rows) < 50:
        return chart
    columns = list(rows[0])
    if any(set(row) != set(columns) for row in rows):
        return chart
    packed = {key: value for key, value in chart.items() if key != 'rows'}
    values = [[row[column] for column in columns] for row in rows]
    encoded = pack_json(values)
    packed.update(row_columns=columns, row_values=encoded if encoded['bytes'] >= 5000 else values)
    return packed
