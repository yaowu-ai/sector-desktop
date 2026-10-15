import { readOfficeZipEntry } from './officeImport';

const WORD = 'http://schemas.openxmlformats.org/wordprocessingml/2006/main';
export async function importCaptionFile(file: File): Promise<string> {
  if (file.size > 2 * 1024 * 1024) throw new Error('文案文件不能超过 2 MiB');
  const extension = file.name.split('.').pop()?.toLowerCase();
  if (extension !== 'txt' && extension !== 'docx') throw new Error('请另存为 .docx 或 UTF-8 .txt');
  const buffer = await file.arrayBuffer();
  if (buffer.byteLength > 2 * 1024 * 1024) throw new Error('文案文件不能超过 2 MiB');
  if (extension === 'txt') {
    try { return new TextDecoder('utf-8', { fatal: true }).decode(buffer).replace(/\r\n?/g, '\n'); }
    catch { throw new Error('文案无法按 UTF-8 解码，请另存为 UTF-8 .txt'); }
  }
  return extractCaptionDocument(await readOfficeZipEntry(buffer, 'word/document.xml'));
}

export function extractCaptionDocument(xml: string): string {
  const invalid = () => new Error('DOCX 正文含不支持或损坏的内容，请另存为 UTF-8 .txt');
  if (/<!DOCTYPE|<!ENTITY/i.test(xml)) throw invalid();
  const document = new DOMParser().parseFromString(xml, 'application/xml');
  if (document.getElementsByTagName('parsererror').length) throw invalid();
  const bodies = document.getElementsByTagNameNS(WORD, 'body');
  if (bodies.length !== 1) throw invalid();
  const body = bodies[0];
  // Do not silently drop tables, tracked changes, text boxes or nested paragraphs.
  for (const tag of ['tbl', 'ins', 'del', 'moveFrom', 'moveTo', 'txbxContent', 'sdt', 'altChunk', 'pPrChange', 'rPrChange', 'sectPrChange']) {
    if (body.getElementsByTagNameNS(WORD, tag).length) throw invalid();
  }
  const paragraphs: string[] = [];
  for (const child of Array.from(body.children)) {
    if (child.namespaceURI !== WORD || !['p', 'sectPr'].includes(child.localName)) throw invalid();
    if (child.localName !== 'p') continue;
    if (child.getElementsByTagNameNS(WORD, 'p').length) throw invalid();
    const read = (element: Element): string => {
      if (element.namespaceURI === WORD) {
        if (element.localName === 't') return element.textContent ?? '';
        if (element.localName === 'br' || element.localName === 'cr') return '\n';
        if (element.localName === 'tab') return '\t';
        if (element.localName === 'noBreakHyphen') return '\u2011';
        if (element.localName === 'softHyphen') return '\u00ad';
        if (['drawing', 'pict', 'pPr', 'rPr', 'sectPr'].includes(element.localName)) return '';
        if (['bookmarkStart', 'bookmarkEnd', 'proofErr', 'permStart', 'permEnd', 'lastRenderedPageBreak'].includes(element.localName)) return '';
        if (!['p', 'r', 'hyperlink'].includes(element.localName)) throw invalid();
      } else throw invalid();
      return Array.from(element.children).map(read).join('');
    };
    paragraphs.push(read(child));
  }
  if (!paragraphs.length) throw invalid();
  return paragraphs.join('\n');
}
