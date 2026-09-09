import {readdir,readFile,stat} from 'node:fs/promises';
import path from 'node:path';
import assert from 'node:assert/strict';
async function files(dir){const out=[];for(const entry of await readdir(dir,{withFileTypes:true})){const p=path.join(dir,entry.name);if(entry.isDirectory())out.push(...await files(p));else out.push(p)}return out}
const allowed=new Set(['report.json','samples.json']);
for(const dir of ['public','dist']){
 const list=await files(dir);
 for(const p of list){assert(!/\.(gz|parquet|csv|ndjson|jsonl)$/i.test(p),`Raw data asset prohibited: ${p}`);if(p.endsWith('.json')||p.includes(`${path.sep}data${path.sep}`))assert(allowed.has(path.basename(p)),`Unexpected public data: ${p}`)}
 const report=JSON.parse(await readFile(path.join(dir,'data/report.json'),'utf8'));
 const samples=JSON.parse(await readFile(path.join(dir,'data/samples.json'),'utf8'));
 assert.equal(report.schema_version,2);assert.equal(samples.schema_version,2);
 assert(samples.items.length<=36);assert.equal(samples.sample_count,samples.items.length);
 assert(!('papers' in report));assert(!('items' in report));
 assert.equal(report.trend.retracted.reduce((n,r)=>n+r.count,0),report.summary.paper_count-report.meta.quality.missing_retraction_date_papers);
 const bytes=(await stat(path.join(dir,'data/report.json'))).size+(await stat(path.join(dir,'data/samples.json'))).size;
 assert(bytes<2*1024*1024,`Statistics payload exceeds 2 MiB budget: ${bytes}`);
 console.log(`${dir}: only aggregate statistics + ${samples.items.length} samples; ${bytes.toLocaleString()} bytes`);
}
