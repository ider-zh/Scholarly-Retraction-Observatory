import json
import pathlib
import subprocess
import time

OUT = pathlib.Path('/tmp/retraction-kdocs-20260916')
FILE_ID = 'x64Tp1SAxrMGCHR4gsEdrxjYd7JMyM7bP'
SLIDE_ID = 150995226
TEXTS = {
    3: '缺少标签的文献记录数，不是缺少学科类别',
    4: '表内单位：条文献记录。L0 共有 19 个主学科；14 是缺少 L0 标签的 OA 撤稿候选数。\n三列总体依次为 77,414 条、59,028 条、220,305,891 条（2000–2025 年发表）。',
    6: 'Concepts 有标签不等于分类准确。观察截至 2026-06-26；2026 年不完整，不并入主分析。',
    10: 'L0 缺失比例：OA 0.0181% ｜匹配 RW 0.0017% ｜全部发文 1.8751%。\nL1 缺失比例：OA 1.0838% ｜匹配 RW 0.6692% ｜全部发文 20.9147%。',
    11: '本页仅描述标签覆盖，未检验曲线下降的原因；不能据此归因于标签缺失或观察窗口。',
}

def call(action, shape_id, **kwargs):
    payload = dict(file_id=FILE_ID, slide_id=SLIDE_ID, shape_id=shape_id, action=action, **kwargs)
    process = subprocess.run(['kdocs-cli', 'wpp', 'write-shape', '-', '--compact'],
        input=json.dumps(payload, ensure_ascii=False), text=True, capture_output=True, timeout=90)
    response = json.loads(process.stdout)
    (OUT / f'update27-{action}-{shape_id}.json').write_text(json.dumps(response, ensure_ascii=False))
    current = response
    while isinstance(current, dict):
        if current.get('code', 0) not in (0, '0'):
            print(response)
            raise SystemExit(1)
        current = current.get('data')
    assert process.returncode == 0
    print(action, shape_id, 'OK', flush=True)
    time.sleep(1)

for shape_id, content in TEXTS.items():
    call('shapes_texts_update', shape_id, text=content)
call('update_attr', 4, height=50.4)
call('update_attr', 10, top=403.2, height=64.8)
