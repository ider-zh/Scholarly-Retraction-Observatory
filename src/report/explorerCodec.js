import {unzlibSync} from 'fflate';
import {sha256} from '@noble/hashes/sha2.js';

export function decodeExplorer(value) {
  if (!value || value.encoding === undefined) return value;
  if (Object.keys(value).length !== 4 || !Object.keys(value).every(key => ['encoding', 'bytes', 'sha256', 'data'].includes(key)) || value.encoding !== 'zlib-json-v1' || !Number.isSafeInteger(value.bytes) || value.bytes < 1 || value.bytes > 8 * 1024 * 1024 || typeof value.data !== 'string' || value.data.length > 2 * 1024 * 1024 || !/^[a-f0-9]{64}$/.test(value.sha256)) throw new Error('Invalid compressed explorer envelope');
  const compressed = Uint8Array.from(atob(value.data), character => character.charCodeAt(0));
  const raw = unzlibSync(compressed, {out: new Uint8Array(value.bytes+1)});
  const hash = [...sha256(raw)].map(value => value.toString(16).padStart(2, '0')).join('');
  if (raw.length !== value.bytes || hash !== value.sha256) throw new Error('Explorer decoded integrity mismatch');
  return JSON.parse(new TextDecoder('utf-8', {fatal: true}).decode(raw));
}
