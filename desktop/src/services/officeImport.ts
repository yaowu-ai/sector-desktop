// Shared, bounded Office ZIP reader. The caller selects the only entry it needs.
export async function readOfficeZipEntry(buffer: ArrayBuffer, target: string, maxSize = 8 * 1024 * 1024): Promise<string> {
  const view = new DataView(buffer);
  const bytes = new Uint8Array(buffer);
  const fail = () => new Error('Office ZIP 文件结构损坏，请另存为 .docx 或 UTF-8 .txt');
  const range = (offset: number, length: number) => {
    if (offset < 0 || length < 0 || offset + length > bytes.length) throw fail();
  };
  let end = -1;
  for (let i = bytes.length - 22; i >= Math.max(0, bytes.length - 65557); i--) {
    if (view.getUint32(i, true) === 0x06054b50 && i + 22 + view.getUint16(i + 20, true) === bytes.length) { end = i; break; }
  }
  if (end < 0) throw fail();
  if (view.getUint16(end + 4, true) || view.getUint16(end + 6, true)) throw fail();
  const count = view.getUint16(end + 10, true);
  if (count > 10000 || count !== view.getUint16(end + 8, true)) throw fail();
  let offset = view.getUint32(end + 16, true);
  const directoryEnd = offset + view.getUint32(end + 12, true);
  if (directoryEnd !== end) throw fail();
  let found: { start: number; size: number; plainSize: number; compression: number; crc: number } | undefined;
  for (let i = 0; i < count; i++) {
    range(offset, 46);
    if (view.getUint32(offset, true) !== 0x02014b50) throw fail();
    const nameSize = view.getUint16(offset + 28, true);
    const next = offset + 46 + nameSize + view.getUint16(offset + 30, true) + view.getUint16(offset + 32, true);
    range(offset, next - offset);
    if (next > directoryEnd) throw fail();
    const name = new TextDecoder('utf-8', { fatal: true }).decode(bytes.subarray(offset + 46, offset + 46 + nameSize));
    if (name === target) {
      if (found || view.getUint16(offset + 8, true) & 1) throw fail();
      const local = view.getUint32(offset + 42, true);
      range(local, 30);
      if (view.getUint32(local, true) !== 0x04034b50) throw fail();
      const localNameSize = view.getUint16(local + 26, true);
      range(local + 30, localNameSize);
      const localName = new TextDecoder('utf-8', { fatal: true }).decode(bytes.subarray(local + 30, local + 30 + localNameSize));
      if (localName !== target || view.getUint16(local + 8, true) !== view.getUint16(offset + 10, true) || view.getUint16(local + 6, true) & 1) throw fail();
      const start = local + 30 + localNameSize + view.getUint16(local + 28, true);
      const size = view.getUint32(offset + 20, true);
      const plainSize = view.getUint32(offset + 24, true);
      range(start, size);
      if (start + size > view.getUint32(end + 16, true) || plainSize > maxSize) throw new Error('DOCX 正文超过 8 MiB 上限');
      found = { start, size, plainSize, compression: view.getUint16(offset + 10, true), crc: view.getUint32(offset + 16, true) };
    }
    offset = next;
  }
  if (!found || offset !== directoryEnd) throw fail();
  const compressed = bytes.slice(found.start, found.start + found.size);
  let output: Uint8Array;
  if (found.compression === 0) output = compressed;
  else {
    if (found.compression !== 8) throw fail();
    let stream: ReadableStream<Uint8Array>;
    try { stream = new Blob([compressed]).stream().pipeThrough(new DecompressionStream('deflate-raw')); }
    catch { throw new Error('当前 WebView2 不支持 DOCX 解压，请更新 WebView2 或另存为 UTF-8 .txt'); }
    const reader = stream.getReader();
    const chunks: Uint8Array[] = [];
    let length = 0;
    try {
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        length += value.length;
        if (length > maxSize) { await reader.cancel(); throw new Error('DOCX 正文超过 8 MiB 上限'); }
        chunks.push(value);
      }
    } finally { reader.releaseLock(); }
    output = new Uint8Array(length);
    let position = 0;
    for (const chunk of chunks) { output.set(chunk, position); position += chunk.length; }
  }
  if (output.length > maxSize || output.length !== found.plainSize) throw fail();
  let crc = 0xffffffff;
  for (const byte of output) {
    crc ^= byte;
    for (let bit = 0; bit < 8; bit++) crc = (crc >>> 1) ^ ((crc & 1) ? 0xedb88320 : 0);
  }
  if (((crc ^ 0xffffffff) >>> 0) !== found.crc) throw fail();
  return new TextDecoder('utf-8', { fatal: true }).decode(output);
}
