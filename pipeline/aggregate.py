"""Publish compact, precomputed statistics. Never publish the analytical corpus."""
from collections import Counter, defaultdict
import hashlib

LAG_EDGES = (0, 365.25, 730.5, 1826.25, 3652.5, float('inf'))
LAG_LABELS = ('不足 1 年', '1–2 年', '2–5 年', '5–10 年', '10 年及以上')

def percentile(values, q):
    if not values: return None
    values = sorted(values); pos = (len(values)-1)*q; low = int(pos)
    return round(values[low]+(values[min(low+1,len(values)-1)]-values[low])*(pos-low), 2)

def lag_stats(papers):
    values = [p['lag_days'] for p in papers if p.get('lag_days') is not None]
    return {'n':len(values),'p25_days':percentile(values,.25),'median_days':percentile(values,.5),
            'p75_days':percentile(values,.75),'histogram':[{'label':name,'count':sum(a<=d<b for d in values)} for name,a,b in zip(LAG_LABELS,LAG_EDGES,LAG_EDGES[1:])]}

def timeseries(papers, current_year):
    out = {}
    for clock in ('published','retracted'):
        counts=Counter(int(p[clock][:4]) for p in papers if p.get(clock))
        out[clock]=[{'year':y,'count':counts.get(y,0),'partial':y==current_year} for y in range(min(counts,default=current_year),current_year+1)]
    return out

def members(p, taxonomy, dimension):
    if taxonomy=='rw':return {v:v for v in p.get(dimension,[])}
    oa=p.get('oa') or {}
    if dimension=='subjects':return {oa.get('field_id') or oa['field']:oa['field']} if oa.get('field') else {}
    return oa.get(dimension) or {}

def leaders(papers, taxonomy, dimension, limit=20):
    names={}; full=Counter();fractional=Counter();covered=0
    for p in papers:
        vs=members(p,taxonomy,dimension)
        if vs:covered+=1
        for k,n in vs.items():names[k]=n;full[k]+=1;fractional[k]+=1/len(vs)
    def top(c):return [{'id':k,'name':names[k],'count':round(v,3)} for k,v in sorted(c.items(),key=lambda kv:(-kv[1],kv[0]))[:limit]]
    return {'full':top(full),'fractional':top(fractional),'known_papers':covered,'unique_entities':len(full),'scope_papers':len(papers),'limit':limit}

def disciplines(papers,taxonomy,current_year):
    groups=defaultdict(list);names={};weights=Counter()
    for p in papers:
        vs=members(p,taxonomy,'subjects')
        for k,n in vs.items():groups[k].append(p);names[k]=n;weights[k]+=1/len(vs)
    data=[]
    for k,ps in groups.items():
        ts=timeseries(ps,current_year);counts={v['year']:v['count'] for v in ts['retracted']}
        previous=counts.get(current_year-2,0);latest=counts.get(current_year-1,0)
        data.append({'id':k,'name':names[k],'count':len(ps),'fractional_count':round(weights[k],3),'lag':lag_stats(ps),'trend':ts,
                     'growth':{'base_year':current_year-2,'year':current_year-1,'base':previous,'latest':latest,'percent':round((latest-previous)/previous*100,2) if previous else None,'small_base':previous<20}})
    return sorted(data,key=lambda d:(-d['count'],d['name']))

def insights(papers,meta,ts,lag):
    counts={p['year']:p['count'] for p in ts['retracted'] if not p['partial']}
    current=meta['partial_year'];items=[]
    if counts:
        peak=max(counts,key=counts.get)
        items.append({'kind':'observation','title':'撤稿数量的历史峰值','text':f'在本快照的完整日历年中，{peak} 年记录了 {counts[peak]:,} 篇撤稿原论文，为最高值。',
                      'interpretation':'集中撤稿和调查处理节奏都可能改变年度数量。仅凭这个峰值，不能推断该年的学术不端发生率最高。',
                      'evidence':{'peak_year':peak,'peak_count':counts[peak]}})
    base=counts.get(current-2,0);latest=counts.get(current-1,0)
    if base:
        growth=(latest-base)/base*100
        items.append({'kind':'observation','title':'最近两个完整年度','text':f'{current-1} 年为 {latest:,} 篇，{current-2} 年为 {base:,} 篇，数量同比 {growth:+.1f}%。',
                      'interpretation':'这比较的是撤稿发生数量，不是按发文量标准化的撤稿率；数据回补可能改变历史数值。',
                      'evidence':{'base':base,'latest':latest,'percent':round(growth,2)}})
    if lag['n']:
        items.append({'kind':'observation','title':'撤稿有明显的时间滞后','text':f'有效日期样本 {lag["n"]:,} 篇；发表至撤稿的中位时间为 {lag["median_days"]/365.25:.2f} 年。',
                      'interpretation':'较近发表年份的论文观察期较短，不能据其较少的累计撤稿数量判断质量更高。这里只描述已撤稿样本。',
                      'evidence':{'lag_sample_size':lag['n'],'median_days':lag['median_days']}})
    return items

def aggregate(papers, meta, audit=None, sample_limit=36):
    current=meta['partial_year'];ts=timeseries(papers,current);lag=lag_stats(papers)
    oa=[p for p in papers if p.get('oa')]
    report={'schema_version':2,'meta':meta,'summary':{'paper_count':len(papers),'lag':lag,'missing_publication_date':sum(not p.get('published') for p in papers),
             'known_subject_papers':sum(bool(p.get('subjects')) for p in papers)},'trend':ts,'taxonomies':{},'audit':audit,
             'insights':insights(papers,meta,ts,lag)}
    for taxonomy,ps in [('rw',papers),('oa',oa)]:
        report['taxonomies'][taxonomy]={'scope_papers':len(ps),'disciplines':disciplines(ps,taxonomy,current),
            'institutions':leaders(ps,taxonomy,'institutions'),'authors':leaders(ps,taxonomy,'authors')}
    # Fixed-size, deterministic illustration sample; not the data behind the charts.
    samples=sorted(papers,key=lambda p:hashlib.sha256(p['id'].encode()).hexdigest())[:sample_limit]
    samples=[{k:p.get(k) for k in ('id','doi','title','published','retracted','lag_days','subjects','rw_ids')} for p in samples]
    return report,{'schema_version':2,'source_papers':len(papers),'sample_count':len(samples),
        'selection':'Deterministic SHA-256 ordering by canonical paper ID; illustration only, not used for statistics.', 'items':samples}
