import base64
import json
from pathlib import Path
import subprocess
import sys

OUT = Path('/tmp/retraction-kdocs-20260916')

def call(service, action, payload, output):
    process = subprocess.run(['kdocs-cli', service, action, '-', '--compact', '--timeout', '180000'],
        input=json.dumps(payload, ensure_ascii=False), text=True, capture_output=True, timeout=200)
    try:
        result = json.loads(process.stdout)
    except ValueError:
        print('Non-JSON response; exit:', process.returncode)
        print(process.stdout[:1800])
        raise SystemExit(1)
    (OUT / output).write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(json.dumps(result, ensure_ascii=False)[:6500])
    if process.returncode or result.get('code', 0) not in [0, '0']:
        raise SystemExit(1)
    return result

if sys.argv[1] == 'upload':
    path = OUT / '撤稿集中在哪里_学科专题_2000-2025.pptx'
    call('drive', 'upload-new-file', {'name': path.name, 'content_base64': base64.b64encode(path.read_bytes()).decode()}, 'upload-result.json')
else:
    call(sys.argv[1], sys.argv[2], json.loads(sys.argv[3]), sys.argv[4])
