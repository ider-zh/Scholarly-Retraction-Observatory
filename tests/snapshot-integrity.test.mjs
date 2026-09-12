import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {webcrypto} from 'node:crypto';
import {verifyReportBytes} from '../src/report/integrity.js';

test('native and HTTP fallback verify every published chunk identically', async () => {
  const manifest = JSON.parse(readFileSync('public/data/snapshot/manifest.json'));
  for (const file of manifest.files) {
    const bytes = new Uint8Array(readFileSync(`public/${file.path}`)).buffer;
    await verifyReportBytes(bytes, file, null);
    await verifyReportBytes(bytes, file, webcrypto.subtle);
  }
});

test('HTTP fallback matches the SHA-256 abc vector and rejects corruption', async () => {
  const bytes = new TextEncoder().encode('abc').buffer;
  const expected = {bytes: 3, sha256: 'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad'};
  for (const subtle of [null, webcrypto.subtle]) {
    await verifyReportBytes(bytes, expected, subtle);
    await assert.rejects(verifyReportBytes(new TextEncoder().encode('abd').buffer, expected, subtle), /校验失败/);
    await assert.rejects(verifyReportBytes(bytes, {...expected, bytes: 4}, subtle), /大小不匹配/);
  }
});

test('native digest errors fail closed instead of bypassing verification', async () => {
  await assert.rejects(verifyReportBytes(new ArrayBuffer(3), {bytes: 3}, {digest: async () => {throw new Error('digest refused');}}), /digest refused/);
});
