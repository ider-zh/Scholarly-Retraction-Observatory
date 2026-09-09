'use strict';
const $=id=>document.getElementById(id), esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let all=[],meta={},filtered=[],searched=[],page=0,trendRows=[];
const fmt=n=>Number(n).toLocaleString('zh-CN',{maximumFractionDigits:1});
const year=d=>d?Number(d.slice(0,4)):null;
const quantile=(arr,q)=>{if(!arr.length)return null;const a=[...arr].sort((a,b)=>a-b),i=(a.length-1)*q,j=Math.floor(i);return a[j]+(a[Math.min(j+1,a.length-1)]-a[j])*(i-j)};
const lagText=n=>n==null?'—':(n/365.25).toFixed(2);
function values(p,kind){
 if($('taxonomy').value==='oa'){
  if(kind==='subjects')return p.oa?.field?[{id:p.oa.field_id||p.oa.field,name:p.oa.field}]:[];
  return Object.entries(p.oa?.[kind]||{}).map(([id,name])=>({id,name}));
 }
 return (p[kind]||[]).map(s=>({id:s,name:s}));
}
function eligible(p){return $('taxonomy').value!=='oa'||!!p.oa?.field}
function selected(p){return !$('subject').value||values(p,'subjects').some(v=>v.id===$('subject').value)}
function tally(rows,kind){const map=new Map();for(const p of rows){const vs=values(p,kind);for(const v of vs){const old=map.get(v.id)||{name:v.name,id:v.id,count:0};old.count+=$('counting').value==='fractional'?1/vs.length:1;map.set(v.id,old)}}return [...map.values()].sort((a,b)=>b.count-a.count||a.name.localeCompare(b.name))}
function ranks(id,rows,limit=15){const top=rows.slice(0,limit),max=top[0]?.count||1;$(id).innerHTML=top.length?top.map(r=>`<div class="rank"><span class="name" title="${esc(r.id)}">${esc(r.name)}</span><span class="bar"><i style="width:${100*r.count/max}%"></i></span><b>${fmt(r.count)}</b></div>`).join(''):'<div class="empty">当前筛选下没有可用记录</div>'}
function subjectOptions(){const map=new Map();for(const p of all)for(const v of values(p,'subjects'))map.set(v.id,v.name);$('subject').innerHTML='<option value="">全部学科</option>'+[...map].sort((a,b)=>a[1].localeCompare(b[1])).map(([id,n])=>`<option value="${esc(id)}">${esc(n)}</option>`).join('')}
function trend(){
 const start=+$('from').value,end=+$('to').value,clock=$('clock').value,counts=new Map();
 for(const p of filtered){const y=year(p[clock]);counts.set(y,(counts.get(y)||0)+1)}
 trendRows=Array.from({length:end-start+1},(_,i)=>({year:start+i,count:counts.get(start+i)||0}));
 const w=1100,h=260,left=65,bottom=38,top=20,width=w-left-12,height=h-bottom-top,max=Math.max(1,...trendRows.map(r=>r.count)),step=width/trendRows.length;
 let s=`<svg viewBox="0 0 ${w} ${h}" role="img" aria-label="${esc($('clock').selectedOptions[0].text)}数量趋势"><title>每年论文数量；详细数值可导出 CSV</title>`;
 for(let i=0;i<=4;i++){const y=top+height-i*height/4;s+=`<line x1="${left}" x2="${w}" y1="${y}" y2="${y}" stroke="#e5edf3"/><text x="${left-10}" y="${y+5}" text-anchor="end" font-size="14" fill="#5e7081">${fmt(max*i/4)}</text>`}
 trendRows.forEach((r,i)=>{const bh=r.count/max*height,x=left+i*step+step*.15;s+=`<rect x="${x}" y="${top+height-bh}" width="${Math.max(.5,step*.7)}" height="${bh}" fill="${r.year===meta.partial_year?'#73bdce':'#1659cc'}"><title>${r.year}: ${r.count} 篇</title></rect>`;if(i%Math.max(1,Math.ceil(trendRows.length/15))===0||i===trendRows.length-1)s+=`<text x="${x+step*.35}" y="${h-10}" text-anchor="middle" font-size="14" fill="#5e7081">${r.year}</text>`});
 $('trend').innerHTML=s+'</svg>';$('trend-title').textContent=clock==='retracted'?'实际撤稿年份 · 时间趋势':'原论文发表年份 · 已撤稿论文队列';
}
function growth(){
 const y=meta.partial_year-1,base=all.filter(p=>eligible(p)&&selected(p)),latest=base.filter(p=>year(p.retracted)===y),prior=base.filter(p=>year(p.retracted)===y-1),a=new Map(tally(latest,'subjects').map(x=>[x.id,x.count])),b=new Map(tally(prior,'subjects').map(x=>[x.id,x.count]));
 $('prior-year').textContent=String(y-1)+' 撤稿';$('last-year').textContent=String(y)+' 撤稿';
 const bySubject=new Map();for(const p of filtered)for(const v of values(p,'subjects')){if(!bySubject.has(v.id))bySubject.set(v.id,[]);if(p.lag_days!=null)bySubject.get(v.id).push(p.lag_days)}
 $('growth').innerHTML=tally(filtered,'subjects').map(r=>{const lags=bySubject.get(r.id)||[],now=a.get(r.id)||0,prev=b.get(r.id)||0,rate=prev?((now-prev)/prev*100).toFixed(1)+'%':'—（基期为零）';return `<tr><td>${esc(r.name)}</td><td>${fmt(r.count)}</td><td>${lags.length}</td><td>${lagText(quantile(lags,.25))}</td><td>${lagText(quantile(lags,.5))}</td><td>${lagText(quantile(lags,.75))}</td><td>${fmt(prev)}</td><td>${fmt(now)}</td><td>${rate}${prev>0&&prev<20?' · 小基数':''}</td></tr>`}).join('')||'<tr><td colspan="9">没有可用数据</td></tr>';
}
function render(){
 const start=+$('from').value,end=+$('to').value;if(!Number.isInteger(start)||!Number.isInteger(end)||start>end||end-start>300||start<1600||end>2200){$('scope').textContent='请输入有效年份范围（最多 301 年）。';return}
 filtered=all.filter(p=>eligible(p)&&selected(p)&&year(p[$('clock').value])>=start&&year(p[$('clock').value])<=end&&p[$('clock').value]);
 const lag=filtered.filter(p=>p.lag_days!=null).map(p=>p.lag_days),withOa=filtered.filter(p=>p.oa).length,unknown=all.filter(p=>eligible(p)&&selected(p)&&!p[$('clock').value]).length;
 $('scope').textContent=`${$('clock').selectedOptions[0].text} ${start}–${end} · ${$('taxonomy').selectedOptions[0].text} · ${$('counting').selectedOptions[0].text} · 日期缺失而未进入筛选：${fmt(unknown)} 篇`;
 $('stats').innerHTML=[['筛选内原论文',fmt(filtered.length),'按 DOI / PMID / RW ID 去重'],['撤稿时滞中位数',lagText(quantile(lag,.5))+' 年',`有效日期样本 ${fmt(lag.length)} 篇`],['覆盖学科',fmt(tally(filtered,'subjects').length),'多标签全计数合计可能超过论文数'],['OpenAlex 匹配',filtered.length?(withOa/filtered.length*100).toFixed(1)+'%':'—',`${fmt(withOa)} / ${fmt(filtered.length)} 篇`]].map(([t,v,n])=>`<div class="stat"><small>${t}</small><strong>${v}</strong><p>${n}</p></div>`).join('');
 trend();ranks('subjects',tally(filtered,'subjects'),20);ranks('institutions',tally(filtered,'institutions'));ranks('authors',tally(filtered,'authors'));
 const bounds=[0,1,2,5,10,Infinity],bins=bounds.slice(0,-1).map((v,i)=>({name:i===4?'10 年及以上':`${v}–${bounds[i+1]} 年`,count:lag.filter(d=>d/365.25>=v&&d/365.25<bounds[i+1]).length}));ranks('lag',bins);
 const oa=$('taxonomy').value==='oa';$('institution-note').textContent=oa?'按论文署名的 OpenAlex Institution ID 计数，仅含有主学科的已匹配论文。':'Retraction Watch 原始机构字符串，未做机构归一化；院系或地址变体可能拆成多条。';$('author-note').textContent=oa?'按 OpenAlex Author ID 计数，身份消歧仍可能出错；超长作者列表可能被截断。':'Retraction Watch 原始作者姓名，未做身份消歧；同名者可能被合并。';
 growth();page=0;search();
}
function search(){const q=$('search').value.trim().toLowerCase();searched=filtered.filter(p=>!q||[p.title,p.doi,...p.authors,...p.institutions].join(' ').toLowerCase().includes(q));page=0;papers()}
function papers(){const n=50,max=Math.max(1,Math.ceil(searched.length/n));page=Math.max(0,Math.min(page,max-1));$('paper-summary').textContent=`${fmt(searched.length)} 篇符合筛选及搜索条件；每页 50 篇。`;$('page-label').textContent=`${page+1} / ${max}`;$('prev').disabled=page===0;$('next').disabled=page>=max-1;
 $('papers').innerHTML=searched.slice(page*n,(page+1)*n).map(p=>`<tr><td>${p.doi?`<a href="https://doi.org/${esc(encodeURI(p.doi))}" target="_blank" rel="noopener noreferrer">${esc(p.title)}</a>`:esc(p.title)}<br><small>RW ${esc(p.rw_ids.join(', '))}</small></td><td>${p.published||'未知'}</td><td>${p.retracted||'未知'}</td><td>${lagText(p.lag_days)}</td><td>${p.oa?`<a href="${esc(p.oa.id)}" target="_blank" rel="noopener noreferrer">查看记录</a>`:'未匹配'}</td></tr>`).join('')||'<tr><td colspan="5">没有符合条件的论文</td></tr>';
}
function csv(name,header,rows){const cell=v=>'"'+String(v??'').replace(/^[=+@\-\t\r]/,"'$&").replace(/"/g,'""')+'"';const blob=new Blob(['\ufeff'+[header,...rows].map(r=>r.map(cell).join(',')).join('\r\n')],{type:'text/csv;charset=utf-8'}),a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000)}
async function boot(){try{
 const response=await fetch('data/manifest.json');if(!response.ok)throw Error('缺少数据清单，请先运行数据构建');const m=await response.json();meta=m.meta;
 for(let i=0;i<m.shards.length;i+=4){const batch=await Promise.all(m.shards.slice(i,i+4).map(async f=>{const r=await fetch('data/'+f);if(!r.ok)throw Error('数据分片加载失败');if(f.endsWith('.gz')){if(!globalThis.DecompressionStream)throw Error('请使用支持 gzip 解压的现代浏览器');return new Response(r.body.pipeThrough(new DecompressionStream('gzip'))).json()}return r.json()}));for(const rows of batch)all.push(...rows);$('status').textContent=`已加载 ${fmt(all.length)} / ${fmt(meta.paper_count)} 篇…`}
 if(all.length!==meta.paper_count)throw Error('数据总量校验失败');
 $('snapshot').innerHTML=`快照截止 ${esc(meta.as_of)}<br>全库 ${fmt(meta.paper_count)} 篇去重论文`;
 const e=meta.openalex;$('status').textContent=`真实数据 · Retraction Watch 全文件构建。OpenAlex 已匹配 ${fmt(e.matched_papers)} 篇；${e.selection==='all DOI'?'已查询全部可用 DOI。':'当前仅部分匹配，OpenAlex 视图不能代表全库分布。'}统计截至 ${meta.as_of}，不代表全球全部撤稿。`;
 $('to').value=meta.partial_year;subjectOptions();render();
 const q=meta.quality;$('quality').innerHTML='<div class="quality-grid">'+[['源文件行数',q.source_rows],['纳入撤稿通知行',meta.notice_count],['合并的重复论文行',q.duplicate_paper_rows||0],['缺失原论文 DOI',q.missing_doi_papers||0],['缺失撤稿日期',q.missing_retraction_date_papers||0],['负时滞排除',q.negative_lag_papers||0],['OpenAlex 已查询 DOI',e.attempted_dois],['OpenAlex 匹配论文',e.matched_papers],['OpenAlex corpus',e.corpus]].map(([k,v])=>`<div>${k}<b>${typeof v==='number'?fmt(v):esc(v)}</b></div>`).join('')+'</div>';
 for(const id of ['clock','from','to','subject','counting'])$(id).addEventListener('change',render);
 $('taxonomy').addEventListener('change',()=>{subjectOptions();render()});$('search').addEventListener('input',search);
 $('reset').onclick=()=>{$('clock').value='retracted';$('from').value=2000;$('to').value=meta.partial_year;$('taxonomy').value='rw';$('counting').value='full';$('search').value='';subjectOptions();render()};
 $('prev').onclick=()=>{page--;papers()};$('next').onclick=()=>{page++;papers()};
 $('export-trend').onclick=()=>csv('retraction-trend.csv',['year','unique_papers','date_basis','taxonomy','subject','as_of'],trendRows.map(r=>[r.year,r.count,$('clock').value,$('taxonomy').value,$('subject').value,meta.as_of]));
 $('export-papers').onclick=()=>csv('retracted-papers.csv',['id','title','doi','publication_date','retraction_date','lag_days','subjects','authors_raw','institutions_raw','openalex_id','rw_ids'],searched.map(p=>[p.id,p.title,p.doi,p.published,p.retracted,p.lag_days,p.subjects.join(';'),p.authors.join(';'),p.institutions.join(';'),p.oa?.id,p.rw_ids.join(';')]));
 }catch(e){$('status').textContent='数据加载失败：'+e.message;}}
boot();
