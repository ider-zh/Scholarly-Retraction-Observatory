from pathlib import Path
import json,base64,hashlib,time,urllib.request
import pymupdf

exec(Path('/tmp/retraction-kdocs-20260916/nick_publish.py').read_text().split('old=call(')[0])
assert not (OUT/'neutral-upload.json').exists()
path=OUT/'OpenAlex撤稿研究_方法与结果综述.docx'
binary=path.read_bytes()
uploaded=call('drive','upload-new-file',{'name':path.name,'content_base64':base64.b64encode(binary).decode()},'neutral-upload')
file_id=uploaded['id']
info=call('drive','get-file-info',{'file_id':file_id},'neutral-info')
assert info['hash']['sum']==hashlib.sha1(binary).hexdigest()
roles=call('drive','list-drive-roles',{'drive_id':info['drive_id']},'neutral-roles')
role=next(item['id'] for item in roles['items'] if item['code']=='viewable')
share=call('drive','share-file',{'file_id':file_id,'scope':'anyone','role_id':role},'neutral-share')
task=call('wps','export',{'file_id':file_id,'format':'pdf'},'neutral-export')
for attempt in range(18):
    time.sleep(10)
    status=call('wps','query-export',{'format':'pdf','task_id':task['task_id'],'task_type':task.get('task_type','normal_export')},'neutral-export-status')
    if status.get('status')=='finished':break
else:raise RuntimeError('Export pending')
with urllib.request.urlopen(status['data']['url'],timeout=120) as response:pdf=response.read()
(OUT/'neutral-cloud.pdf').write_bytes(pdf)
document=pymupdf.open(stream=pdf,filetype='pdf')
assert 3<=len(document)<=5
content=''.join(page.get_text() for page in document)
assert all(term in content for term in ['58,345','五、结论','21.53%','4.69%','资料来源'])
for number,page in enumerate(document,1):page.get_pixmap().save(OUT/f'neutral-cloud-{number}.png')
print(json.dumps({'url':share['url'],'pages':len(document),'characters':len(content)},ensure_ascii=False))
