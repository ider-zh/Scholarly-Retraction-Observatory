import base64
import hashlib
import json
from pathlib import Path
import subprocess
import time
import urllib.request

import pymupdf

OUT = Path('/tmp/retraction-kdocs-20260916/event-year')
FILE_ID = 'x64Tp1SAxrMGCHR4gsEdrxjYd7JMyM7bP'

def call(service, action, payload, name):
    process = subprocess.run(['rtk', 'proxy', 'kdocs-cli', service, action, '-', '--compact', '--timeout', '180000'],
        input=json.dumps(payload), capture_output=True, text=True, timeout=200)
    result = json.loads(process.stdout)
    (OUT / f'{name}.json').write_text(json.dumps(result, ensure_ascii=False, indent=2))
    assert process.returncode == 0 and result.get('code') == 0, name
    data = result['data']
    if 'code' in data:
        assert data['code'] == 0, name
        data = data['data']
    return data

assert json.loads((OUT / 'verification.json').read_text())['all_old_chart_images_identical']
before = call('drive', 'get-file-info', {'file_id': FILE_ID}, 'cloud-before')
assert before['hash']['sum'] == 'a823f4434f5024d7473741d3d10b522d83db195d', 'Cloud changed since last reviewed version; stop to preserve owner edits.'
binary = (OUT / 'retraction-event-year.pptx').read_bytes()
uploaded = call('drive', 'upload-replace-file', {'file_id': FILE_ID, 'drive_id': before['drive_id'],
    'parent_id': before['parent_id'], 'content_base64': base64.b64encode(binary).decode()}, 'cloud-upload')
after = call('drive', 'get-file-info', {'file_id': FILE_ID}, 'cloud-after')
assert after['hash']['sum'] == hashlib.sha1(binary).hexdigest()
assert after['size'] == len(binary)
share = call('drive', 'get-share-info', {'file_id': FILE_ID}, 'cloud-share')
assert share['scope'] == 'anyone' and share['status'] == 'open' and str(share['role_id']) == '20417464'
print(json.dumps({'version': after['version'], 'size': after['size'], 'sha1_verified': True, 'public_view_preserved': True}), flush=True)
task = call('wpp', 'export-pdf', {'file_id': FILE_ID, 'format': 'pdf', 'from_page': 1, 'to_page': 38}, 'cloud-export')
for attempt in range(12):
    time.sleep(10)
    result = call('wpp', 'export-pdf', {'task_id': task['task_id'], 'task_type': task['task_type']}, 'cloud-export-status')
    if result.get('status') == 'finished':
        break
else:
    raise RuntimeError('Export still pending; resume the existing task, do not start another.')
with urllib.request.urlopen(result['data']['url'], timeout=120) as response:
    pdf = response.read()
(OUT / 'cloud-final.pdf').write_bytes(pdf)
document = pymupdf.open(stream=pdf, filetype='pdf')
assert len(document) == 38
for number in [1,25,26,29,30,31,32,33,34,35,36,37,38]:
    page = document[number-1]
    assert '撤稿' in page.get_text()
    page.get_pixmap(matrix=pymupdf.Matrix(1.25,1.25)).save(OUT / f'cloud-{number}.png')
assert '58,345' in document[29].get_text()
assert '213' in document[29].get_text()
print(json.dumps({'cloud_pages': len(document), 'event_chapter': [30,36], 'url': after['link_url']}), flush=True)
