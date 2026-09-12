import test from 'node:test';
import assert from 'node:assert/strict';
import {mkdtemp, mkdir, readFile, rm, writeFile} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {publicationBuilds, writePublicationBuilds} from '../scripts/publication-builds.mjs';

const report = {meta: {generated_at: '2026-09-09T06:38:33.005302+00:00', as_of: '2026-09-09'}};
const manifest = {generated_at: '2026-09-12T03:35:47.806903+00:00', rw_snapshot_date: '2026-09-10', oa_snapshot_date: '2026-06-26'};
const pptBuiltAt = '2026-09-12T08:00:00.000Z';

test('Publication build dates distinguish report data, deck generation and source cutoffs', () => {
  const metadata = publicationBuilds(report, manifest, pptBuiltAt);
  assert.equal(metadata.v1.builtAt, report.meta.generated_at);
  assert.equal(metadata.v2.builtAt, manifest.generated_at);
  assert.equal(metadata.ppt.builtAt, pptBuiltAt);
  assert.equal(metadata.v1.label, '报告数据构建时间');
  assert.equal(metadata.ppt.label, '演示稿构建时间');
  assert.deepEqual(metadata.v1.sourceDates, [{source: 'RW', date: '2026-09-09'}]);
  assert.deepEqual(metadata.ppt.sourceDates, metadata.v2.sourceDates);
  assert.equal(metadata.v2.sourceDates[1].date, '2026-06-26');
});

test('Missing, invalid and timezone-free build timestamps fail rather than fabricating dates', () => {
  for (const invalid of [undefined, null, '', 'invalid', '2026-09-12', '2026-09-12T08:00:00', '2026-13-12T08:00:00Z', '2026-02-30T08:00:00Z']) {
    assert.throws(() => publicationBuilds(report, manifest, invalid), /Invalid HTML-PPT build time/);
  }
  assert.throws(() => publicationBuilds({meta: {...report.meta, generated_at: ''}}, manifest, pptBuiltAt), /Report v1 build time/);
  assert.throws(() => publicationBuilds(report, {...manifest, generated_at: ''}, pptBuiltAt), /Report v2 build time/);
  assert.throws(() => publicationBuilds(report, {...manifest, oa_snapshot_date: '2026-02-30'}, pptBuiltAt), /OpenAlex snapshot date/);
});

test('Build metadata writer reads published inputs without modifying them', async () => {
  const root = await mkdtemp(join(tmpdir(), 'publication-builds-'));
  try {
    await mkdir(join(root, 'public/data/snapshot'), {recursive: true});
    await mkdir(join(root, 'src'));
    const inputs = [['public/data/report.json', report], ['public/data/snapshot/manifest.json', manifest]];
    for (const [path, data] of inputs) await writeFile(join(root, path), JSON.stringify(data));
    const metadata = await writePublicationBuilds(pptBuiltAt, {root});
    assert.equal(await readFile(join(root, 'src/publication-builds.js'), 'utf8'), `export const publicationBuilds = ${JSON.stringify(metadata, null, 2)};\n`);
    for (const [path, data] of inputs) assert.equal(await readFile(join(root, path), 'utf8'), JSON.stringify(data));
  } finally {
    await rm(root, {recursive: true, force: true});
  }
});
