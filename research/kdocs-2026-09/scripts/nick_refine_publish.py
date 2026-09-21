from pathlib import Path
import json
import base64
import hashlib
import time
import urllib.request
import pymupdf

exec(Path('/tmp/retraction-kdocs-20260916/nick_publish.py').read_text().split("old=call(")[0])
deliveries=json.loads((OUT/'DELIVERY.json').read_text())
for key,filename,service in [('ppt','学科撤稿研究_尼克简报_20260920.pptx','wpp'),('word','学科撤稿研究_综述_20260920.docx','wps')]:
    record=deliveries[key]
    info=call('drive','get-file-info',{'file_id':record['id']},f'refine-{key}-before')
    assert info['id']==record['id']
    binary=(OUT/filename).read_bytes()
    call('drive','upload-replace-file',{'file_id':record['id'],'drive_id':info['drive_id'],'parent_id':info['parent_id'],'content_base64':base64.b64encode(binary).decode()},f'refine-{key}-upload')
    updated=call('drive','get-file-info',{'file_id':record['id']},f'refine-{key}-after')
    assert updated['hash']['sum']==hashlib.sha1(binary).hexdigest()
    assert updated['size']==len(binary)
    share=call('drive','get-share-info',{'file_id':record['id']},f'refine-{key}-share')
    assert share['scope']=='anyone' and share['status']=='open' and str(share['role_id'])=='20417464'
    record.update(sha1=updated['hash']['sum'],size=len(binary),version=updated['version'])
    (OUT/'DELIVERY.json').write_text(json.dumps(deliveries,ensure_ascii=False,indent=2))
    parameters={'file_id':record['id'],'format':'pdf'}
    if key=='ppt':parameters.update(from_page=1,to_page=19)
    task=call(service,'export-pdf' if key=='ppt' else 'export',parameters,f'refine-{key}-export')
    for attempt in range(18):
        time.sleep(10)
        query={'task_id':task['task_id'],'task_type':task.get('task_type','normal_export')}
        if key=='word':query['format']='pdf'
        status=call(service,'export-pdf' if key=='ppt' else 'query-export',query,f'refine-{key}-export-status')
        if status.get('status')=='finished':break
    else:raise RuntimeError('Export pending; resume task')
    with urllib.request.urlopen(status['data']['url'],timeout=120) as response:pdf=response.read()
    (OUT/f'refine-{key}-cloud.pdf').write_bytes(pdf)
    document=pymupdf.open(stream=pdf,filetype='pdf')
    assert len(document)==19 if key=='ppt' else 3<=len(document)<=5
    for number,page in enumerate(document,1):
        page.get_pixmap(matrix=pymupdf.Matrix(1,1)).save(OUT/f'refine-{key}-cloud-{number}.png')
    record['cloud_pages']=len(document)
    (OUT/'DELIVERY.json').write_text(json.dumps(deliveries,ensure_ascii=False,indent=2))
    print(key,record,flush=True)
