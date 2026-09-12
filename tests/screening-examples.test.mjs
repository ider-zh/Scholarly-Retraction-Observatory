import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {validateChunk} from '../src/report/schema.js';
import {validateScreeningExamples} from '../src/report/screeningExamples.js';
import {screeningExamplesAsset} from '../src/report/screeningExamplesAsset.js';

const raw = await readFile('public/data/screening-examples.json');
const data = JSON.parse(raw);
const manifest = JSON.parse(await readFile('public/data/snapshot/manifest.json','utf8'));
const overview = validateChunk(JSON.parse(await readFile('public/data/snapshot/overview.json','utf8')), manifest, 'overview');
const chart = overview.charts.find(chart => chart.chart_id === 'screening');

test('Bounded exclusion examples match verified screening population and byte contract', () => {
  assert.equal(raw.length, screeningExamplesAsset.bytes);
  assert.equal(createHash('sha256').update(raw).digest('hex'), screeningExamplesAsset.sha256);
  assert.equal(validateScreeningExamples(data, manifest, chart), data);
  assert.equal(data.sample_count, 10);
  for (const stratum of Object.keys(data.stratum_counts)) assert.equal(data.items.filter(row=>row.stratum===stratum).length, 2);
  assert(data.items.some(row=>row.type==='review' && row.document_role==='original_supported'));
  assert(data.items.some(row=>row.document_role==='suspected_notice' && row.title.startsWith('Retracted:')));
});

test('Examples fail closed for stale sources, screening totals or invented reasons', () => {
  assert.throws(()=>validateScreeningExamples(data,{...manifest,oa_snapshot_date:'2000-01-01'},chart),/不匹配/);
  assert.throws(()=>validateScreeningExamples({...data,screening_counts:{}},manifest,chart),/数量不一致/);
  assert.throws(()=>validateScreeningExamples({...data,items:[...data.items,...data.items]},manifest,chart),/数量/);
  assert.throws(()=>validateScreeningExamples({...data,items:data.items.map((row,index)=>index ? row : {...row,type:'article',document_role:'unresolved',original_evidence:false,notice_evidence:false,title_suspected:false})},manifest,chart),/排除规则/);
  assert.throws(()=>validateScreeningExamples({...data,items:data.items.map((row,index)=>index ? row : {...row,authorships:[]})},manifest,chart),/非许可字段/);
});

test('Reassessed examples cannot swap current decisions or inject unsupported fields', () => {
  if (data.schema_version !== 2) return;
  assert(data.items.some(row => row.current_outcome === 'retained_A1'));
  assert(data.items.some(row => row.current_outcome === 'excluded_known_notice'));
  const changed = change => ({...data, items: data.items.map((row, index) => index ? row : {...row, ...change(row)})});
  assert.throws(() => validateScreeningExamples(changed(() => ({current_uncertain: false})), manifest, chart), /非许可字段/);
  assert.throws(() => validateScreeningExamples(changed(row => ({current_outcome: row.current_outcome === 'retained_A1' ? 'excluded_known_notice' : 'retained_A1'})), manifest, chart), /新筛选/);
});
