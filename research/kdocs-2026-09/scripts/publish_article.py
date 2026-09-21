from pathlib import Path
import json
import time

exec(Path('/tmp/retraction-kdocs-20260916/nick_publish.py').read_text().split('old=call(')[0])
article=(OUT/'公众号综述_撤稿记录里的学科地图.md').read_text()
assert all(section in article for section in ['一、研究问题、数据和分类体系','二、Concepts 体系下的结果','三、Topics 体系下的结果','四、两套体系结果的比较与分析','五、结论'])
assert not (OUT/'article-create.json').exists()
created=call('drive','create-file-with-content',{'name':'撤稿记录里的学科地图：为什么换一种分类，榜首就变了？','file_extension':'otl','content':article},'article-create')
file_id=created.get('file_id') or created.get('id')
assert file_id,created
info=call('drive','get-file-info',{'file_id':file_id},'article-info')
roles=call('drive','list-drive-roles',{'drive_id':info['drive_id']},'article-roles')
role=next(item['id'] for item in roles['items'] if item['code']=='viewable')
shared=call('drive','share-file',{'file_id':file_id,'scope':'anyone','role_id':role},'article-share')
read=call('drive','read-file',{'file_id':file_id},'article-read')
for attempt in range(12):
    if read.get('status')!='pending':break
    time.sleep(5)
    read=call('drive','read-file',{'file_id':file_id,'task_id':read['task_id']},'article-read')
content=read.get('content','')
assert all(text in content for text in ['58,345','25,748','12,957','五、结论','延伸阅读与数据出处'])
assert not read.get('warnings'),read.get('warnings')
print(json.dumps({'file_id':file_id,'url':shared.get('url') or info.get('link_url'),'characters':len(article),'readback_characters':len(content)},ensure_ascii=False))
