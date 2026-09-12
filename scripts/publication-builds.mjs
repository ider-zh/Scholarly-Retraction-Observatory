import {readFile, writeFile} from 'node:fs/promises';
import {fileURLToPath} from 'node:url';
import {resolve} from 'node:path';

const repoRoot = fileURLToPath(new URL('../', import.meta.url));

function requireTimestamp(value, name) {
  if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$/.test(value) || !Number.isFinite(Date.parse(value))) {
    throw new Error(`Invalid ${name}: an ISO datetime with a timezone is required`);
  }
  requireDate(value.slice(0, 10), name);
  return value;
}

function requireDate(value, name) {
  if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(value) || !Number.isFinite(Date.parse(value)) || new Date(value).toISOString().slice(0, 10) !== value) {
    throw new Error(`Invalid ${name}: an ISO calendar date is required`);
  }
  return value;
}

export function publicationBuilds(report, manifest, pptBuiltAt) {
  const sourceDates = [
    {source: 'RW', date: requireDate(manifest.rw_snapshot_date, 'RW snapshot date')},
    {source: 'OpenAlex', date: requireDate(manifest.oa_snapshot_date, 'OpenAlex snapshot date')},
  ];
  return {
    v1: {builtAt: requireTimestamp(report.meta.generated_at, 'Report v1 build time'), label: '报告数据构建时间', sourceDates: [{source: 'RW', date: requireDate(report.meta.as_of, 'Report v1 cutoff')}]},
    v2: {builtAt: requireTimestamp(manifest.generated_at, 'Report v2 build time'), label: '报告数据构建时间', sourceDates},
    ppt: {builtAt: requireTimestamp(pptBuiltAt, 'HTML-PPT build time'), label: '演示稿构建时间', sourceDates},
  };
}

export async function writePublicationBuilds(pptBuiltAt, {root = repoRoot} = {}) {
  const report = JSON.parse(await readFile(resolve(root, 'public/data/report.json'), 'utf8'));
  const manifest = JSON.parse(await readFile(resolve(root, 'public/data/snapshot/manifest.json'), 'utf8'));
  const metadata = publicationBuilds(report, manifest, pptBuiltAt);
  await writeFile(resolve(root, 'src/publication-builds.js'), `export const publicationBuilds = ${JSON.stringify(metadata, null, 2)};\n`);
  return metadata;
}
