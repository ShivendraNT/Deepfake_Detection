// Build the Round 1 submission PDF and per-page PNG previews from src/deck.html.
//
//   node docs/pitch/round1/build.mjs
//
// Needs Node 18+ and the `playwright` package with Chromium (see README.md).
// Output: Satyapan_Round1_Submission.pdf and preview/page-NN.png next to this file.
// The script also prints layout warnings (text overflowing its box, content leaving the
// 1280x720 page, text smaller than 13 px). A clean build prints "layout: OK".
import { createRequire } from 'node:module';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const require = createRequire(import.meta.url);
let chromium;
try {
  ({ chromium } = require('playwright'));
} catch {
  console.error('Cannot find the "playwright" package. Run: npm install playwright (see README.md).');
  process.exit(1);
}

const here = path.dirname(fileURLToPath(import.meta.url));
const src = path.join(here, 'src', 'deck.html');
const pdfOut = path.join(here, 'Satyapan_Round1_Submission.pdf');
const prevDir = path.join(here, 'preview');

const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1280, height: 720 }, deviceScaleFactor: 1 });
await page.goto(pathToFileURL(src).href, { waitUntil: 'load' });
await page.evaluate(async () => { await document.fonts.ready; });

// ---- layout checks (screen media, same layout as print) ----
const warnings = await page.evaluate(() => {
  const out = [];
  const slides = [...document.querySelectorAll('section.slide')];
  slides.forEach((s, i) => {
    const id = s.dataset.page || `#${i + 1}`;
    const sb = s.getBoundingClientRect();
    s.querySelectorAll('*').forEach((el) => {
      const cs = getComputedStyle(el);
      if (cs.display === 'none' || cs.visibility === 'hidden') return;
      const r = el.getBoundingClientRect();
      if (r.width === 0 || r.height === 0) return;
      if (el.closest('svg') && el.tagName.toLowerCase() !== 'svg' && !el.closest('foreignObject')) {
        // SVG primitives: only check they stay on the page
      }
      if (r.right > sb.right + 1 || r.bottom > sb.bottom + 1 || r.left < sb.left - 1 || r.top < sb.top - 1) {
        if (!el.closest('.crop')) out.push(`${id}: <${el.tagName.toLowerCase()} class="${el.className && el.className.baseVal !== undefined ? el.className.baseVal : el.className}"> leaves the page`);
      }
      const ov = ['hidden', 'clip'].includes(cs.overflow) || ['hidden', 'clip'].includes(cs.overflowY);
      if (ov && !el.classList.contains('crop') && (el.scrollHeight > el.clientHeight + 2 || el.scrollWidth > el.clientWidth + 2)) {
        out.push(`${id}: <${el.tagName.toLowerCase()} class="${el.className}"> content clipped (${el.scrollHeight}>${el.clientHeight})`);
      }
      // text size: elements that directly contain text
      const hasText = [...el.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim().length > 0);
      if (hasText) {
        const fs = parseFloat(cs.fontSize);
        if (fs < 12.9) out.push(`${id}: small text ${fs}px: "${el.textContent.trim().slice(0, 40)}"`);
      }
    });
    // children of .fill containers must not overflow their parent
    // boxes whose content spills out of them (visible overflow is not clipped, so check sizes)
    s.querySelectorAll('div, td').forEach((el) => {
      const host = el.parentElement && el.parentElement.tagName.toLowerCase() === 'foreignobject' ? el.parentElement : el;
      const hb = host.getBoundingClientRect();
      let bottom = 0;
      el.querySelectorAll('*').forEach((c) => { if (c.closest('.crop') && !c.classList.contains('crop')) return; const r = c.getBoundingClientRect(); if (r.height > 0) bottom = Math.max(bottom, r.bottom); });
      if (host !== el) bottom = Math.max(bottom, el.getBoundingClientRect().bottom);
      if (bottom > hb.bottom + 2) out.push(`${id}: <${el.tagName.toLowerCase()} class="${el.className && el.className.baseVal !== undefined ? el.className.baseVal : el.className}"> content spills ${Math.round(bottom - hb.bottom)}px below its box: "${el.textContent.trim().slice(0, 40)}"`);
    });
    s.querySelectorAll('.chk').forEach((el) => {
      if (el.scrollHeight > el.clientHeight + 2) out.push(`${id}: .chk box overflows (${el.scrollHeight}>${el.clientHeight}) "${el.textContent.trim().slice(0, 40)}"`);
    });
  });
  return out;
});

// ---- PDF ----
await page.pdf({
  path: pdfOut,
  width: '1280px',
  height: '720px',
  printBackground: true,
  preferCSSPageSize: true,
  margin: { top: '0', right: '0', bottom: '0', left: '0' },
});

// ---- PNG previews (one per page) ----
fs.mkdirSync(prevDir, { recursive: true });
for (const f of fs.readdirSync(prevDir)) if (f.endsWith('.png')) fs.unlinkSync(path.join(prevDir, f));
const slides = await page.locator('section.slide').all();
for (let i = 0; i < slides.length; i++) {
  const n = String(i + 1).padStart(2, '0');
  const label = (await slides[i].getAttribute('data-page')) || n;
  await slides[i].screenshot({ path: path.join(prevDir, `page-${n}-${label}.png`) });
}
await browser.close();

console.log(`PDF: ${pdfOut} (${slides.length} pages)`);
if (warnings.length) {
  console.log(`layout: ${warnings.length} warning(s)`);
  for (const w of warnings) console.log('  - ' + w);
} else {
  console.log('layout: OK');
}
