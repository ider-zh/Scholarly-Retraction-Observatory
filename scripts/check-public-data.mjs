import {readdir,readFile,stat} from 'node:fs/promises';
import path from 'node:path';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {SNAPSHOT_PATHS, validateManifest, validateChunk} from '../src/report/schema.js';
import {validateScreeningExamples} from '../src/report/screeningExamples.js';
import {screeningExamplesAsset} from '../src/report/screeningExamplesAsset.js';
async function files(dir){const out=[];for(const entry of await readdir(dir,{withFileTypes:true})){const p=path.join(dir,entry.name);if(entry.isDirectory())out.push(...await files(p));else out.push(p)}return out}
const allowed=new Set(['data/report.json','data/samples.json','data/screening-examples.json',...SNAPSHOT_PATHS]);
const directories=process.argv[2]==='--root'?[process.argv[3]]:['public','dist'];
for(const dir of directories){
 const list=await files(dir);
 for(const p of list){assert(!/\.(gz|parquet|csv|ndjson|jsonl|duckdb|sqlite|db)$/i.test(p),`Raw data asset prohibited: ${p}`);if(p.endsWith('.json')||p.includes(`${path.sep}data${path.sep}`))assert(allowed.has(path.relative(dir,p).split(path.sep).join('/')),`Unexpected public data: ${p}`)}
 const report=JSON.parse(await readFile(path.join(dir,'data/report.json'),'utf8'));
 const samples=JSON.parse(await readFile(path.join(dir,'data/samples.json'),'utf8'));
 assert.deepEqual(Object.keys(report.taxonomies),['rw']);
 for(const child of report.taxonomies.rw.disciplines){const parent=report.taxonomies.rw.domains.find(x=>x.id===child.parent_id);assert(parent);assert(child.count<=parent.count)}
 assert(report.source_background.sources.length>=3);
 assert.equal(report.schema_version,2);assert.equal(samples.schema_version,2);
 assert(samples.items.length<=36);assert.equal(samples.sample_count,samples.items.length);
 assert(!('papers' in report));assert(!('items' in report));
 assert.equal(report.trend.retracted.reduce((n,r)=>n+r.count,0),report.summary.paper_count-report.meta.quality.missing_retraction_date_papers);
 const snapshotFiles=list.filter(file=>path.relative(dir,file).split(path.sep).join('/').startsWith('data/snapshot/'));
 let exclusionSamples = 0;
 if(snapshotFiles.length){
  assert.equal(snapshotFiles.length,SNAPSHOT_PATHS.length,'Incomplete v3 release');
  const manifest=validateManifest(JSON.parse(await readFile(path.join(dir,'data/snapshot/manifest.json'),'utf8')));
  for(const file of manifest.files){
   const raw=await readFile(path.join(dir,file.path));
   assert.equal(raw.length,file.bytes,'Chunk size mismatch');
   assert.equal(createHash('sha256').update(raw).digest('hex'),file.sha256,'Chunk hash mismatch');
   validateChunk(JSON.parse(raw.toString('utf8')),manifest,path.basename(file.path,'.json'));
  }
  const examplePath = path.join(dir,'data/screening-examples.json');
  if(list.includes(examplePath)) {
   const raw = await readFile(examplePath);
   assert.equal(raw.length,screeningExamplesAsset.bytes,'Exclusion sample size mismatch');
   assert.equal(createHash('sha256').update(raw).digest('hex'),screeningExamplesAsset.sha256,'Exclusion sample hash mismatch');
   const overview = validateChunk(JSON.parse(await readFile(path.join(dir,'data/snapshot/overview.json'),'utf8')),manifest,'overview');
   exclusionSamples = validateScreeningExamples(JSON.parse(raw),manifest,overview.charts.find(chart=>chart.chart_id==='screening')).sample_count;
  }
 }
 const bytes=(await Promise.all(list.filter(file=>allowed.has(path.relative(dir,file).split(path.sep).join('/'))).map(async file=>(await stat(file)).size))).reduce((sum,size)=>sum+size,0);
 assert(bytes<2*1024*1024,`Statistics payload exceeds 2 MiB budget: ${bytes}`);
 console.log(`${dir}: aggregate statistics + ${samples.items.length} RW samples + ${exclusionSamples} bounded exclusion examples; ${bytes.toLocaleString()} bytes`);
}
