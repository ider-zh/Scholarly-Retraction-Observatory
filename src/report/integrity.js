import {sha256} from '@noble/hashes/sha2.js';

export async function verifyReportBytes(bytes, expected, subtle = globalThis.crypto?.subtle) {
  if (bytes.byteLength !== expected.bytes) throw new Error('报告文件大小不匹配，请重新加载');
  const digest = subtle ? new Uint8Array(await subtle.digest('SHA-256', bytes)) : sha256(new Uint8Array(bytes));
  const hash = [...digest].map(value => value.toString(16).padStart(2, '0')).join('');
  if (hash !== expected.sha256) throw new Error('报告文件校验失败，请重新加载');
}
