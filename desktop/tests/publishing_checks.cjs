const assert = require('node:assert/strict');
const fs = require('node:fs');
const ts = require('typescript');
const vm = require('node:vm');
const path = require('node:path');
function load(name) {
  const filename = path.resolve(__dirname, '../src/services', name + '.ts');
  const code = ts.transpileModule(fs.readFileSync(filename, 'utf8'), { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 } }).outputText;
  const exports = {};
  vm.runInNewContext(code, { exports, require: (name) => load(name.replace('./', '')), TextDecoder, TextEncoder, DataView, Uint8Array, Blob, Response, DecompressionStream, URL, DOMParser: global.DOMParser });
  return exports;
}
(async () => {
  const { readOfficeZipEntry } = load('officeImport');
  function zip(entries, compress = false) {
    const locals = [], centrals = []; let offset = 0;
    for (const [name, text] of entries) {
      const nameBytes = Buffer.from(name), bytes = Buffer.from(text);
      const packed = compress ? require('node:zlib').deflateRawSync(bytes) : bytes;
      let crc = 0xffffffff;
      for (const byte of bytes) { crc ^= byte; for (let bit = 0; bit < 8; bit++) crc = (crc >>> 1) ^ ((crc & 1) ? 0xedb88320 : 0); }
      crc = (crc ^ 0xffffffff) >>> 0;
      const local = Buffer.alloc(30), central = Buffer.alloc(46);
      local.writeUInt32LE(0x04034b50); local.writeUInt32LE(crc, 14); local.writeUInt16LE(compress ? 8 : 0, 8); local.writeUInt32LE(packed.length, 18); local.writeUInt32LE(bytes.length, 22); local.writeUInt16LE(nameBytes.length, 26);
      central.writeUInt32LE(0x02014b50); central.writeUInt32LE(crc, 16); central.writeUInt16LE(compress ? 8 : 0, 10); central.writeUInt32LE(packed.length, 20); central.writeUInt32LE(bytes.length, 24); central.writeUInt16LE(nameBytes.length, 28); central.writeUInt32LE(offset, 42);
      locals.push(local, nameBytes, packed); centrals.push(central, nameBytes); offset += 30 + nameBytes.length + packed.length;
    }
    const directory = Buffer.concat(centrals), end = Buffer.alloc(22);
    end.writeUInt32LE(0x06054b50); end.writeUInt16LE(entries.length, 8); end.writeUInt16LE(entries.length, 10); end.writeUInt32LE(directory.length, 12); end.writeUInt32LE(offset, 16);
    return Uint8Array.from(Buffer.concat([...locals, directory, end])).buffer;
  }
  const archive = zip([['word/document.xml', '<body>海边</body>'], ['word/media/picture.bin', 'ignored']]);
  assert.equal(await readOfficeZipEntry(archive, 'word/document.xml'), '<body>海边</body>');
  assert.equal(await readOfficeZipEntry(zip([['word/document.xml', '海边\n\n#旅行']], true), 'word/document.xml'), '海边\n\n#旅行');
  await assert.rejects(readOfficeZipEntry(archive, 'missing.xml'), /Office ZIP/);
  await assert.rejects(readOfficeZipEntry(archive, 'word/document.xml', 2), /8 MiB/);
  await assert.rejects(readOfficeZipEntry(zip([['word/document.xml','one'],['word/document.xml','two']]), 'word/document.xml'), /Office ZIP/);
  const corrupt = archive.slice(0); new Uint8Array(corrupt)[30 + 'word/document.xml'.length] ^= 1;
  await assert.rejects(readOfficeZipEntry(corrupt, 'word/document.xml'), /Office ZIP/);
  const { importCaptionFile } = load('captionImport');
  assert.throws(() => load('captionImport').extractCaptionDocument('<!DOCTYPE doc><w:p/>'), /DOCX/);
  const file = (name, bytes) => ({ name, size: bytes.length, arrayBuffer: async () => Uint8Array.from(bytes).buffer });
  assert.equal(await importCaptionFile(file('caption.txt', Buffer.from('\ufeff 海边\r\n\r\n#旅行😀\r'))), ' 海边\n\n#旅行😀\n');
  assert.equal((await importCaptionFile(file('long.txt', Buffer.from('a'.repeat(4001))))).length, 4001);
  await assert.rejects(importCaptionFile(file('bad.txt', [0xff])), /UTF-8/);
  await assert.rejects(importCaptionFile(file('old.doc', [1])), /docx/);
  await assert.rejects(importCaptionFile(file('bad.docx', [1,2])), /Office|DOCX|ZIP/);
  await assert.rejects(importCaptionFile({ name: 'big.txt', size: 2097153 }), /2 MiB/);
  const { buildPublishRequest, safeTikTokPostUrl, publicationDateFilter, formatPublishEvidence } = load('publishing');
  const evidence = formatPublishEvidence(JSON.stringify({ observed_at: '2026-10-15T04:00:00Z', reason: '本人主页精确作品ID、作者和文案一致', match_basis: 'exact_post_id_and_detail', correlated_post_id: '101', candidate_ids: ['100', '101'], screenshot_path: 'D:\\data\\publish-evidence\\r1\\latest.png' }));
  assert.ok(evidence.includes('核验时间：'));
  assert.ok(evidence.includes('确认依据：作品 ID、作者及文案一致'));
  assert.ok(evidence.includes('作品 ID：101'));
  assert.ok(evidence.includes('候选作品数：2'));
  assert.ok(evidence.includes('截图路径：D:\\data\\publish-evidence\\r1\\latest.png'));
  assert.equal(formatPublishEvidence('{broken'), '核验证据无法读取');
  assert.equal(formatPublishEvidence(null), '暂无核验证据；未保存截图');
  const dto = buildPublishRequest('r1', 'selected', ['a', 'b', 'a'], 'D:\\海边.mp4', '海边\n😀');
  assert.deepEqual(JSON.parse(JSON.stringify(dto.accountIds)), ['a', 'b']);
  assert.equal(dto.caption, '海边\n😀');
  const inputIds = ['a'];
  const fixed = buildPublishRequest('fixed', 'selected', inputIds, 'D:\\v.mp4', 'original');
  inputIds.push('b');
  assert.equal(fixed.accountIds.length, 1);
  assert.equal(buildPublishRequest('empty', 'single', ['a'], 'D:\\v.mp4', '').caption, '');
  assert.throws(() => buildPublishRequest('nul', 'single', ['a'], 'D:\\v.mp4', '\0'), /控制字符/);
  assert.equal(buildPublishRequest('r2', 'all', ['a'], 'D:\\v.mp4', '').accountIds.length, 0);
  assert.throws(() => buildPublishRequest('r', 'single', ['a','b'], 'D:\\v.mp4', ''), /一个/);
  assert.throws(() => buildPublishRequest('r', 'all', [], 'D:\\v.mp4', '😀'.repeat(2001)), /4000/);
  assert.equal(safeTikTokPostUrl('https://www.tiktok.com/@alice/video/101'), true);
  for (const url of ['javascript:alert(1)', 'https://tiktok.com.evil/@a/video/1', 'https://www.tiktok.com/@alice', 'https://evil@www.tiktok.com/@a/video/1']) assert.equal(safeTikTokPostUrl(url), false);
  assert.equal(publicationDateFilter('2026-10-15', '2026-10-15').from, new Date(2026,9,15).toISOString());
  console.log('publishing focused checks PASS (caption/request/link/date; no component proof)');
})().catch(error => { console.error(error); process.exitCode = 1; });
