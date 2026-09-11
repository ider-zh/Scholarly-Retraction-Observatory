"""Lossless columnar encoding for uniform aggregate rows, never source records."""


def pack_chart(chart):
    rows = chart['rows']
    if len(rows) < 50:
        return chart
    columns = list(rows[0])
    if any(set(row) != set(columns) for row in rows):
        return chart
    packed = {key: value for key, value in chart.items() if key != 'rows'}
    packed.update(row_columns=columns, row_values=[[row[column] for column in columns] for row in rows])
    return packed
