import test from 'node:test';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {deflateSync} from 'node:zlib';
import {decodeExplorer} from '../src/report/explorerCodec.js';

function encode(raw) {
  return {encoding: 'zlib-json-v1', bytes: raw.length, sha256: createHash('sha256').update(raw).digest('hex'), data: deflateSync(raw).toString('base64')};
}

test('standard zlib explorer encoding preserves exact JSON, zero and null', () => {
  const original = {version: 'test', label: '具体研究主题', values: [0, null, 50331, .0123]};
  assert.deepEqual(decodeExplorer(encode(Buffer.from(JSON.stringify(original)))), original);
  assert.equal(decodeExplorer(original), original);
});

test('compressed explorers reject unknown encoding, ambiguous fields, corruption and decompression overflow', () => {
  const raw = Buffer.from('{"values":[1]}'), encoded = encode(raw);
  for (const mutation of [{encoding: 'unknown'}, {papers: []}, {bytes: 9*1024*1024}, {sha256: '0'.repeat(64)}, {bytes: encoded.bytes-1}, {data: 'invalid'}]) assert.throws(() => decodeExplorer({...encoded, ...mutation}));
  const extended = encode(Buffer.concat([raw, Buffer.from(' ')]));
  assert.throws(() => decodeExplorer({...extended, bytes: encoded.bytes, sha256: encoded.sha256}), /integrity/);
});
