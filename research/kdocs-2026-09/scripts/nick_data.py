from pathlib import Path

source_code = Path('/tmp/retraction-kdocs-20260916/event_analysis.py').read_text()
source_code = source_code.replace("OUT = BASE / 'event-year'", "OUT = Path('/tmp/retraction-nick-20260920')")
source_code = source_code.replace("connection.executemany('INSERT INTO matched VALUES (?)', [(identifier,) for identifier in sorted(matched)])", "connection.execute('BEGIN'); connection.executemany('INSERT INTO matched VALUES (?)', [(identifier,) for identifier in sorted(matched)]); connection.execute('COMMIT')")
exec(compile(source_code, 'verified-event-extraction', 'exec'))

uncertain = set()
for paper in papers:
    identifier = matches[paper['id']]['selected_id']
    if identifier in selected and 'Date of Article and/or Notice Unknown' in paper['reasons']:
        uncertain.add(identifier)
summary['date_uncertainty_tagged_works'] = len(uncertain)
summary['date_uncertainty_percent'] = len(uncertain) / len(selected) * 100
(OUT / 'analysis.json').write_text(json.dumps({'summary': summary, 'groups': result}, ensure_ascii=False, indent=2))
old = json.loads((BASE / 'event-year/analysis.json').read_text())
assert result == old['groups']
assert summary['total'] == 58345
print('MATCHED_DATE_UNCERTAINTY', len(uncertain), summary['date_uncertainty_percent'])
