import base64
import hashlib
import json
from pathlib import Path
import subprocess
import time
import urllib.request

import pymupdf

OUT = Path('/tmp/retraction-nick-20260920')

def call(service, action, payload, name):
    process = subprocess.run(['rtk','proxy','kdocs-cli',service,action,'-','--compact','--timeout','180000'],
        input=json.dumps(payload,ensure_ascii=False),capture_output=True,text=True,timeout=200)
    result=json.loads(process.stdout)
    (OUT/f'{name}.json').write_text(json.dumps(result,ensure_ascii=False,indent=2))
    assert process.returncode==0 and result.get('code')==0,name
    data=result['data']
    if 'code' in data:
        assert data['code']==0,name
        data=data['data']
    return data

old=call('drive','get-file-info',{'file_id':'x64Tp1SAxrMGCHR4gsEdrxjYd7JMyM7bP'},'previous-report-info')
assert old['hash']['sum']=='85e09c9d12e8c04a6b2418e3cbf9c0c2373ca90c'
roles=call('drive','list-drive-roles',{'drive_id':old['drive_id']},'roles')
role=next(item['id'] for item in roles['items'] if item['code']=='viewable')
deliveries={}
for key,filename,service in [('ppt','学科撤稿研究_尼克简报_20260920.pptx','wpp'),('word','学科撤稿研究_综述_20260920.docx','wps')]:
    assert not (OUT/f'{key}-upload.json').exists(), 'Existing upload log: inspect and resume rather than duplicate.'
    binary=(OUT/filename).read_bytes()
    uploaded=call('drive','upload-new-file',{'name':filename,'content_base64':base64.b64encode(binary).decode()},f'{key}-upload')
    file_id=uploaded['id']
    info=call('drive','get-file-info',{'file_id':file_id},f'{key}-info')
    assert info['hash']['sum']==hashlib.sha1(binary).hexdigest() and info['size']==len(binary)
    share=call('drive','share-file',{'file_id':file_id,'scope':'anyone','role_id':role},f'{key}-share')
    verified=call('drive','get-share-info',{'file_id':file_id},f'{key}-share-verified')
    assert verified['scope']=='anyone' and verified['status']=='open' and verified['role_id']==role
    deliveries[key]={'id':file_id,'url':share['url'],'size':len(binary),'sha1':info['hash']['sum']}
    print(json.dumps({key:deliveries[key]},ensure_ascii=False),flush=True)
    parameters={'file_id':file_id,'format':'pdf'}
    if key=='ppt':parameters.update({'from_page':1,'to_page':15})
    task=call(service,'export-pdf' if key=='ppt' else 'export',parameters,f'{key}-export')
    for attempt in range(18):
        time.sleep(10)
        query={'task_id':task['task_id'],'task_type':task.get('task_type','normal_export')}
        if key=='word':query['format']='pdf'
        status=call(service,'export-pdf' if key=='ppt' else 'query-export',query,f'{key}-export-status')
        if status.get('status')=='finished':break
    else:raise RuntimeError('Export pending; resume the existing task.')
    with urllib.request.urlopen(status['data']['url'],timeout=120) as response:pdf=response.read()
    (OUT/f'{key}-cloud.pdf').write_bytes(pdf)
    document=pymupdf.open(stream=pdf,filetype='pdf')
    if key=='ppt':assert len(document)==15
    else:assert 3<=len(document)<=5
    for number,page in enumerate(document,1):
        page.get_pixmap(matrix=pymupdf.Matrix(1.2,1.2)).save(OUT/f'{key}-cloud-{number}.png')
    deliveries[key]['cloud_pages']=len(document)
    print(key,'cloud pages',len(document),flush=True)
(OUT/'DELIVERY.json').write_text(json.dumps(deliveries,ensure_ascii=False,indent=2))
print(json.dumps(deliveries,ensure_ascii=False),flush=True)
