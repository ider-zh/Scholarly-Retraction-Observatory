from pathlib import Path
import json,hashlib,base64,time,urllib.request
import pymupdf

exec(Path('/tmp/retraction-kdocs-20260916/nick_publish.py').read_text().split('old=call(')[0])
OUT=Path('/tmp/retraction-dark-20260921')
metadata_path=Path('/tmp/retraction-nick-20260920/DELIVERY.json')
metadata=json.loads(metadata_path.read_text())
record=metadata['ppt']
info=call('drive','get-file-info',{'file_id':record['id']},'cloud-before')
assert info['hash']['sum']=='35798ea71877cb88ee6ddfbd524ada206a20dfa9','Cloud has changed; preserve edits'
path=OUT/'OpenAlex撤稿的学科分布与年度变化_深色版.pptx'
binary=path.read_bytes()
call('drive','upload-replace-file',{'file_id':record['id'],'drive_id':info['drive_id'],'parent_id':info['parent_id'],
    'content_base64':base64.b64encode(binary).decode()},'cloud-replaced')
updated=call('drive','get-file-info',{'file_id':record['id']},'cloud-after')
assert updated['hash']['sum']==hashlib.sha1(binary).hexdigest() and updated['size']==len(binary)
shared=call('drive','get-share-info',{'file_id':record['id']},'cloud-share')
assert shared['scope']=='anyone' and shared['status']=='open' and str(shared['role_id'])=='20417464'
record.update(sha1=updated['hash']['sum'],size=len(binary),version=updated['version'],local_path=str(path))
metadata_path.write_text(json.dumps(metadata,ensure_ascii=False,indent=2))
task=call('wpp','export-pdf',{'file_id':record['id'],'format':'pdf','from_page':1,'to_page':19},'cloud-export')
for attempt in range(18):
    time.sleep(10)
    status=call('wpp','export-pdf',{'task_id':task['task_id'],'task_type':task.get('task_type','normal_export')},'cloud-export-status')
    if status.get('status')=='finished':break
else:raise RuntimeError('Export pending; resume existing task')
with urllib.request.urlopen(status['data']['url'],timeout=120) as response:pdf=response.read()
(OUT/'cloud.pdf').write_bytes(pdf)
document=pymupdf.open(stream=pdf,filetype='pdf')
assert len(document)==19
for number,page in enumerate(document,1):
    page.get_pixmap(matrix=pymupdf.Matrix(1.5,1.5)).save(OUT/f'cloud-{number}.png')
for number,needles in {2:['510,372,821','115,627','66,700','72,476','58,345'],
    3:['65,026','284','4,516','2024-02-12'],4:['W4210257207','0.0017%','2022-02-01']}.items():
    text= document[number-1].get_text()
    for needle in needles:assert needle in text,(number,needle)
record['cloud_pages']=len(document)
metadata_path.write_text(json.dumps(metadata,ensure_ascii=False,indent=2))
(OUT/'DELIVERY.json').write_text(json.dumps(record,ensure_ascii=False,indent=2))
print(json.dumps(record,ensure_ascii=False))
