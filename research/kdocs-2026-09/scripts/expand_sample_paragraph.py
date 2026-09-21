from pathlib import Path
import json,time,re

exec(Path('/tmp/retraction-kdocs-20260916/nick_publish.py').read_text().split('old=call(')[0])
file_id='HpnpbEfzw9MTkYG1ZCwRxxkLww9bBHRZr'
before=json.loads((OUT/'explanation-read-before.json').read_text())['data']
if 'code' in before:before=before['data']
content=before['content']
old=next(line.strip() for line in content.splitlines() if line.startswith('样本形成过程为：'))
new=(OUT/'样本形成过程_详细说明.txt').read_text().strip()
assert content.count(old)==1
assert not (OUT/'explanation-replace.json').exists()
call('wps','texts.replace',{'file_id':file_id,'find_text':old,'is_all':False,'replace_text':new},'explanation-replace')
time.sleep(3)
after=call('drive','read-file',{'file_id':file_id},'explanation-read-after')
for attempt in range(12):
    if after.get('status')!='pending':break
    time.sleep(5)
    after=call('drive','read-file',{'file_id':file_id,'task_id':after['task_id']},'explanation-read-after')
clean=lambda text:re.sub(r'\s','',text)
assert clean(new) in clean(after['content']),'New text not verified'
assert clean(content.replace(old,''))==clean(after['content'].replace(new,'')),'Inspect remainder before claiming unchanged'
print('Target paragraph replaced and remaining article verified unchanged.')
