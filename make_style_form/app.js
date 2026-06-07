/* =========================================================
   make_style_form — app logic
   ---------------------------------------------------------
   อ่านค่าจาก form → generate CSS override block →
   วาง append หลัง base CSS (uploaded) → preview + download
   ========================================================= */

// ============================================================
// STATE
// ============================================================
const STATE = {
  baseCSS: '',           // content ของไฟล์ที่ upload (เริ่มเปล่า)
  baseName: '',          // ชื่อไฟล์
};


// ============================================================
// HELPERS — color math
// ============================================================
function hexToRgb(hex) {
  hex = hex.replace('#', '');
  if (hex.length === 3) hex = hex.split('').map(c => c + c).join('');
  const n = parseInt(hex, 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

function rgbToHex(r, g, b) {
  const toHex = v => Math.round(Math.max(0, Math.min(255, v))).toString(16).padStart(2, '0');
  return '#' + toHex(r) + toHex(g) + toHex(b);
}

function darken(hex, amount = 0.25) {
  const [r, g, b] = hexToRgb(hex);
  return rgbToHex(r * (1 - amount), g * (1 - amount), b * (1 - amount));
}

function lighten(hex, amount = 0.85) {
  const [r, g, b] = hexToRgb(hex);
  return rgbToHex(r + (255 - r) * amount, g + (255 - g) * amount, b + (255 - b) * amount);
}

// Blend hex color toward black by percent (0 = pure hex, 100 = pure black)
// ใช้สำหรับ heading ที่ต้องการให้เข้มขึ้น (กัน "จาง" ตอนพิมพ์ขาวดำ)
function blendToBlack(hex, percent) {
  const [r, g, b] = hexToRgb(hex);
  const t = Math.max(0, Math.min(100, percent)) / 100;
  return rgbToHex(r * (1 - t), g * (1 - t), b * (1 - t));
}


// ============================================================
// CONFIG — อ่านค่าจาก form
// ============================================================
function readConfig() {
  const accent = document.getElementById('accent').value;
  const autoDerive = document.getElementById('autoDerive').checked;
  const accentDk = autoDerive ? darken(accent, 0.30) : document.getElementById('accentDk').value;
  const accentLt = autoDerive ? lighten(accent, 0.88) : document.getElementById('accentLt').value;

  const hdScale = document.querySelector('input[name="hdScale"]:checked').value;
  let h1, h2, h3, h4;
  if (hdScale === 'compact')      [h1, h2, h3, h4] = [14, 12, 11, 10];
  else if (hdScale === 'airy')    [h1, h2, h3, h4] = [20, 16, 13, 11];
  else if (hdScale === 'custom') {
    h1 = +document.getElementById('h1size').value;
    h2 = +document.getElementById('h2size').value;
    h3 = +document.getElementById('h3size').value;
    h4 = +document.getElementById('h4size').value;
  } else                          [h1, h2, h3, h4] = [17, 14, 12, 10.5];

  return {
    accent, accentDk, accentLt,
    fontHd: document.getElementById('fontHd').value,
    fontBd: document.getElementById('fontBd').value,
    fontCd: document.getElementById('fontCd').value,
    h1, h2, h3, h4,
    h2under: document.querySelector('input[name="h2under"]:checked').value,
    underlineLen: +document.getElementById('underlineLen').value,
    h2svg: document.querySelector('input[name="h2svg"]:checked').value,
    printGray: document.getElementById('printGrayMode').checked,
    h1dark: +document.getElementById('h1dark').value,
    h2dark: +document.getElementById('h2dark').value,
    h3dark: +document.getElementById('h3dark').value,
    h4dark: +document.getElementById('h4dark').value,
    olStyle: document.querySelector('input[name="olStyle"]:checked').value,
    noteStyle: document.querySelector('input[name="noteStyle"]:checked').value,
    dropCap: document.getElementById('dropCap').checked,
    sinkage: document.getElementById('sinkage').checked,
    sinkAmount: +document.getElementById('sinkAmount').value,
    justifyBody: document.getElementById('justifyBody').checked,
    centerChapter: document.getElementById('centerChapter').checked,
  };
}


// ============================================================
// CSS GENERATORS — แต่ละส่วน
// ============================================================

function fontStack(name, type) {
  const thaiFallback = type === 'bd'
    ? "'IBM Plex Sans Thai Looped', 'Anuphan', sans-serif"
    : type === 'cd'
    ? "'IBM Plex Mono', 'JetBrains Mono', monospace"
    : "'IBM Plex Sans Thai', 'Sarabun', sans-serif";
  return `'${name}', ${thaiFallback}`;
}

// Font weight availability — Google Fonts API จะ fail ถ้าขอ weight ที่ไม่มี
// (เช่น Itim มีแค่ 400 — ขอ 300 แล้ว response 400 error)
const FONT_WEIGHTS = {
  // Heading — modern sans
  'Poppins':                   '300;400;500;600;700',
  'Prompt':                    '300;400;500;600;700',
  'Kanit':                     '300;400;500;600;700',
  'Krub':                      '300;400;500;600;700',
  'Bai Jamjuree':              '300;400;500;600;700',
  'KoHo':                      '300;400;500;600;700',
  'IBM Plex Sans Thai':        '300;400;500;600;700',
  // Display
  'Mitr':                      '300;400;500;600;700',
  'Chakra Petch':              '300;400;500;600;700',
  'Charm':                     '400;700',                    // ⚠ มีแค่ 2 weights
  // Handwritten / playful
  'Itim':                      '400',                        // ⚠ มี weight เดียว!
  'Mali':                      '300;400;500;600;700',
  // Classic / serif
  'Sarabun':                   '300;400;500;600;700',
  'Trirong':                   '300;400;500;600;700',
  // Body
  'IBM Plex Sans Thai Looped': '300;400;500',
  'Anuphan':                   '300;400;500;600;700',
  'Noto Sans Thai':            '300;400;500;600;700',
  'K2D':                       '300;400;500;600;700',
  'Maitree':                   '300;400;500;600;700',
  'Pridi':                     '300;400;500;600;700',
  // Code
  'IBM Plex Mono':             '300;400;500',
  'JetBrains Mono':            '400;500;700',
  'Roboto Mono':               '300;400;500;700',
  'Source Code Pro':           '300;400;500;700',
};

function genGoogleImport(c) {
  const families = new Set([c.fontHd, c.fontBd, c.fontCd]);
  const url = 'https://fonts.googleapis.com/css2?' +
    [...families].map(f => {
      const weights = FONT_WEIGHTS[f] || '400;500;700';   // safe fallback
      return `family=${f.replace(/ /g, '+')}:wght@${weights}`;
    }).join('&') +
    '&display=swap';
  return `/* === FONTS === */\n@import url('${url}');`;
}

function genVariables(c) {
  return `:root {
  --tpl-hd: ${fontStack(c.fontHd, 'hd')} !important;
  --tpl-bd: ${fontStack(c.fontBd, 'bd')} !important;
  --tpl-cd: ${fontStack(c.fontCd, 'cd')} !important;

  --tpl-accent:    ${c.accent} !important;
  --tpl-accent-dk: ${c.accentDk} !important;
  --tpl-accent-lt: ${c.accentLt} !important;
}`;
}

function genBody(c) {
  const align = c.justifyBody ? 'justify' : 'left';
  return `/* === BODY === */
html, body {
  font-family: var(--tpl-bd) !important;
  font-size: 9.6pt !important;
  line-height: 1.55 !important;
}
.content p {
  font-family: var(--tpl-bd) !important;
  font-size: 9.6pt !important;
  font-weight: 300 !important;
  line-height: 1.55 !important;
  text-align: ${align} !important;
  text-indent: 1.45em !important;
  margin: 0 0 6pt 0 !important;
  hyphens: auto !important;
}
.content ul, .content ol,
.content li, .content li > p {
  font-family: var(--tpl-bd) !important;
  font-size: 9.6pt !important;
  font-weight: 300 !important;
  line-height: 1.55 !important;
}`;
}

function genHeadings(c) {
  let h2css = '';
  if (c.h2under === 'none') {
    h2css = `border: none !important;\n  border-bottom: none !important;`;
  } else if (c.h2under === 'short') {
    h2css = `border: none !important;`;
  } else if (c.h2under === 'full') {
    h2css = `border: none !important;\n  border-bottom: 1.5pt solid var(--tpl-accent) !important;\n  padding: 0 0 4pt 0 !important;`;
  } else if (c.h2under === 'double') {
    h2css = `border: none !important;\n  border-bottom: 0.6pt solid var(--tpl-border, #ccc) !important;\n  padding: 0 0 4pt 0 !important;`;
  }

  const h2after = c.h2under === 'short' ? `
.content h2::after {
  content: "" !important;
  display: block !important;
  width: ${c.underlineLen}pt !important;
  height: 2pt !important;
  background: var(--tpl-accent) !important;
  margin-top: 5pt !important;
  border-radius: 1pt !important;
}` : c.h2under === 'double' ? `
.content h2::after {
  content: "" !important;
  display: block !important;
  height: 1.2pt !important;
  background: var(--tpl-accent) !important;
  margin-top: 2pt !important;
}` : `
.content h2::after { content: none !important; }`;

  // Blend accent-dk → black ตามความเข้มที่กำหนดต่อ heading
  // 0% = pure accent-dk (สด, อาจจางใน B&W) / 100% = pure black K100 (เข้มสุด)
  const h1color = blendToBlack(c.accentDk, c.h1dark);
  const h2color = blendToBlack(c.accentDk, c.h2dark);
  const h3color = blendToBlack(c.accentDk, c.h3dark);
  const h4color = blendToBlack(c.accentDk, c.h4dark);

  return `/* === HEADINGS ===
   Color blend: 0%=accent-dk / 100%=K100 (per-heading darkness)
   h1: ${c.h1dark}% / h2: ${c.h2dark}% / h3: ${c.h3dark}% / h4: ${c.h4dark}% */
.content h1 {
  font-family: var(--tpl-hd) !important;
  font-size: ${c.h1}pt !important;
  font-weight: 700 !important;
  color: ${h1color} !important;
  margin: ${Math.round(c.h1 * 1.3)}pt 0 ${Math.round(c.h1 * 0.6)}pt 0 !important;
  padding: 0 !important;
  background: transparent !important;
  border: none !important;
  line-height: 1.28 !important;
}
.content h2 {
  font-family: var(--tpl-hd) !important;
  font-size: ${c.h2}pt !important;
  font-weight: 700 !important;
  color: ${h2color} !important;
  background: transparent !important;
  margin: ${Math.round(c.h2 * 1.4)}pt 0 ${Math.round(c.h2 * 0.7)}pt 0 !important;
  padding: 0 !important;
  display: block !important;
  ${h2css}
  line-height: 1.3 !important;
}
.content h2::before { content: none !important; }${h2after}

.content h3 {
  font-family: var(--tpl-hd) !important;
  font-size: ${c.h3}pt !important;
  font-weight: 600 !important;
  color: ${h3color} !important;
  background: transparent !important;
  margin: ${Math.round(c.h3 * 1.2)}pt 0 ${Math.round(c.h3 * 0.5)}pt 0 !important;
  padding: 0 !important;
  border: none !important;
  position: static !important;
  line-height: 1.35 !important;
}
.content h3::before { content: none !important; }

.content h4 {
  font-family: var(--tpl-hd) !important;
  font-size: ${c.h4}pt !important;
  font-weight: 700 !important;
  color: ${h4color} !important;
  background: transparent !important;
  margin: ${Math.round(c.h4 * 1.2)}pt 0 ${Math.round(c.h4 * 0.5)}pt 0 !important;
  padding: 0 !important;
  border: none !important;
  position: static !important;
  text-transform: none !important;
  letter-spacing: 0 !important;
  line-height: 1.4 !important;
}
.content h4::before { content: none !important; }`;
}

function genChapter(c) {
  const align = c.centerChapter ? 'center' : 'left';
  const sink = c.sinkage ? `\n.chapter { padding-top: ${c.sinkAmount}mm !important; }` : '';
  return `/* === CHAPTER HEADER === */${sink}
.ch-hdr {
  display: block !important;
  text-align: ${align} !important;
  padding: 12pt 0 16pt 0 !important;
  margin: 0 0 24pt 0 !important;
  border: none !important;
  background: transparent !important;
  position: relative !important;
  min-height: auto !important;
}
.ch-hdr::after { content: none !important; }
.ch-num {
  display: block !important;
  font-family: var(--tpl-hd) !important;
  font-size: 10pt !important;
  font-weight: 600 !important;
  color: var(--tpl-accent) !important;
  text-transform: uppercase !important;
  letter-spacing: 3pt !important;
  margin: 0 0 10pt 0 !important;
  padding: 0 !important;
  min-width: 0 !important;
}
.ch-num::before { content: none !important; }
.ch-num::after  { content: none !important; }
.ch-title {
  display: block !important;
  font-family: var(--tpl-hd) !important;
  font-size: 24pt !important;
  font-weight: 700 !important;
  color: var(--tpl-accent-dk) !important;
  line-height: 1.2 !important;
  padding: 0 !important;
  border: none !important;
  border-left: none !important;
  margin: 0 !important;
}`;
}

function genOL(c) {
  // ─── Common selector list — รวมทุก variant explicit
  //    เพื่อให้ specificity (0,2,3) match กับ base CSS section 8f
  //    ป้องกัน edge case ที่ generic [style*="--ol-marker"] อาจหลุด
  const VARIANT_SELECTORS = `.content ol li::before,
.content ol[style*="--ol-marker: lower-alpha"] li::before,
.content ol[style*="--ol-marker:lower-alpha"]  li::before,
.content ol[style*="--ol-marker: upper-alpha"] li::before,
.content ol[style*="--ol-marker:upper-alpha"]  li::before,
.content ol[style*="--ol-marker: thai-alpha"]  li::before,
.content ol[style*="--ol-marker:thai-alpha"]   li::before,
.content ol[style*="--ol-marker: decimal"]     li::before,
.content ol[style*="--ol-marker:decimal"]      li::before`;

  // ─── Per-variant content fallback (กัน WeasyPrint รุ่นเก่า parse var() ใน counter() ไม่ได้)
  //    withDot = true (plain) เพิ่ม "." ต่อท้าย / false (circle, square, large) ไม่มี
  const variantFallback = (withDot) => {
    const dot = withDot ? ' "."' : '';
    return `/* Fallback content per variant — กรณี WeasyPrint รุ่นเก่าไม่อ่าน var() ใน counter() */
.content ol[style*="--ol-marker: lower-alpha"] li::before,
.content ol[style*="--ol-marker:lower-alpha"]  li::before { content: counter(ol-counter, lower-alpha)${dot} !important; }
.content ol[style*="--ol-marker: upper-alpha"] li::before,
.content ol[style*="--ol-marker:upper-alpha"]  li::before { content: counter(ol-counter, upper-alpha)${dot} !important; }
.content ol[style*="--ol-marker: thai-alpha"]  li::before,
.content ol[style*="--ol-marker:thai-alpha"]   li::before { content: counter(ol-counter, thai-alpha)${dot}  !important; }
.content ol[style*="--ol-marker: decimal"]     li::before,
.content ol[style*="--ol-marker:decimal"]      li::before { content: counter(ol-counter, decimal)${dot}     !important; }`;
  };

  if (c.olStyle === 'plain') {
    return `/* === OL — plain decimal + accent ===
   Marker เล็ก → top: 0 align กับ text baseline ตรงๆ */
.content ol { padding-left: 22pt !important; }
.content ol li { padding-left: 4pt !important; margin: 0 0 4pt 0 !important; }
${VARIANT_SELECTORS} {
  content: counter(ol-counter, var(--ol-marker, decimal)) "." !important;
  position: absolute !important;
  left: -20pt !important;
  top: 0 !important;
  width: 16pt !important;
  text-align: right !important;
  color: var(--tpl-accent) !important;
  font-weight: 700 !important;
  background: transparent !important;
  border-radius: 0 !important;
}

${variantFallback(true)}`;
  }

  if (c.olStyle === 'square') {
    return `/* === OL — square bracket ===
   กล่อง 18×16pt — top: -1pt align baseline */
.content ol { padding-left: 26pt !important; }
.content ol li { padding-left: 4pt !important; margin: 0 0 5pt 0 !important; min-height: 16pt !important; }
${VARIANT_SELECTORS} {
  content: counter(ol-counter, var(--ol-marker, decimal)) !important;
  position: absolute !important;
  left: -24pt !important;
  top: -1pt !important;
  width: 18pt !important;
  height: 16pt !important;
  background: var(--tpl-accent-lt) !important;
  color: var(--tpl-accent-dk) !important;
  border: 0.8pt solid var(--tpl-accent) !important;
  border-radius: 2pt !important;
  font-weight: 700 !important;
  font-size: 8.5pt !important;
  line-height: 16pt !important;
  text-align: center !important;
}

${variantFallback(false)}`;
  }

  if (c.olStyle === 'large') {
    return `/* === OL — large display ===
   ตัวเลข 18pt — top: -3pt align baseline */
.content ol { padding-left: 28pt !important; }
.content ol li { padding-left: 4pt !important; margin: 0 0 6pt 0 !important; min-height: 22pt !important; }
${VARIANT_SELECTORS} {
  content: counter(ol-counter, var(--ol-marker, decimal)) !important;
  position: absolute !important;
  left: -26pt !important;
  top: -3pt !important;
  font-family: var(--tpl-hd) !important;
  font-size: 18pt !important;
  font-weight: 700 !important;
  color: var(--tpl-accent) !important;
  background: transparent !important;
  border-radius: 0 !important;
}

${variantFallback(false)}`;
  }

  // default circle
  return `/* === OL — circle accent (default) ===
   วงกลม 19pt + line-height 19pt → char baseline ต่ำกว่า text baseline ~2pt
   → top: -2pt ดึงขึ้น เพื่อ align กับ text บรรทัดแรก */
.content ol { padding-left: 28pt !important; }
.content ol li {
  padding-left: 4pt !important;
  margin: 0 0 5pt 0 !important;
  min-height: 19pt !important;
}
${VARIANT_SELECTORS} {
  content: counter(ol-counter, var(--ol-marker, decimal)) !important;
  position: absolute !important;
  left: -26pt !important;
  top: -2pt !important;
  width: 19pt !important;
  height: 19pt !important;
  background: var(--tpl-accent) !important;
  color: #FFFFFF !important;
  font-family: var(--tpl-hd) !important;
  font-size: 9pt !important;
  font-weight: 700 !important;
  line-height: 19pt !important;
  text-align: center !important;
  border-radius: 50% !important;
  border: none !important;
}

${variantFallback(false)}`;
}

function genQuiz() {
  // quiz เอาวงกลมออกเสมอ — เป็น inline marker
  return `/* === QUIZ — inline marker (no circle) === */
.bd-grid.quiz ol li::before,
.bd-grid.quiz ol[style*="--ol-marker"] li::before {
  position: static !important;
  display: inline !important;
  left: auto !important;
  top: auto !important;
  width: auto !important;
  height: auto !important;
  min-height: 0 !important;
  background: transparent !important;
  border-radius: 0 !important;
  border: none !important;
  margin: 0 4pt 0 0 !important;
  padding: 0 !important;
  text-align: left !important;
  line-height: inherit !important;
  font-size: inherit !important;
  font-weight: 700 !important;
  color: var(--tpl-accent-dk) !important;
}
.bd-grid.quiz li {
  min-height: 0 !important;
  margin: 0 !important;
  padding: 0 10.5pt !important;
}`;
}

function genNote(c) {
  if (c.noteStyle === 'minimal') {
    return `/* === NOTE — minimal left stripe === */
.note {
  background: transparent !important;
  border: none !important;
  border-left: 1.5pt solid var(--tpl-accent) !important;
  border-radius: 0 !important;
  padding: 4pt 0 4pt 10pt !important;
  font-size: 9.6pt !important;
  line-height: 1.55 !important;
}
.note-label {
  font-family: var(--tpl-hd) !important;
  color: var(--tpl-accent-dk) !important;
  font-weight: 700 !important;
  font-size: 9.3pt !important;
  text-transform: uppercase !important;
}
.note p, .note li, .note span, .note strong { font-size: 9.6pt !important; line-height: 1.55 !important; }`;
  }
  if (c.noteStyle === 'bold') {
    return `/* === NOTE — bold border === */
.note {
  background: var(--tpl-accent-lt) !important;
  border: 0.8pt solid var(--tpl-accent) !important;
  border-left: 3pt solid var(--tpl-accent) !important;
  border-radius: 3pt !important;
  padding: 8pt 10pt !important;
  font-size: 9.6pt !important;
  line-height: 1.55 !important;
}
.note-label {
  font-family: var(--tpl-hd) !important;
  color: var(--tpl-accent-dk) !important;
  font-weight: 700 !important;
  font-size: 9.5pt !important;
  text-transform: uppercase !important;
  letter-spacing: 0.5pt !important;
}
.note p, .note li, .note span, .note strong { font-size: 9.6pt !important; line-height: 1.55 !important; }`;
  }
  if (c.noteStyle === 'amber') {
    return `/* === NOTE — amber handwritten === */
.note {
  background: #FFF8E1 !important;
  border: 0.5pt solid #C28800 !important;
  border-left: 3pt solid #C28800 !important;
  border-radius: 3pt !important;
  padding: 7pt 9pt !important;
  font-size: 9.6pt !important;
  line-height: 1.55 !important;
}
.note-label {
  font-family: var(--tpl-hd) !important;
  color: #6B4900 !important;
  font-weight: 700 !important;
  font-size: 9.5pt !important;
}
.note p, .note li, .note span, .note strong { font-size: 9.6pt !important; line-height: 1.55 !important; }`;
  }
  // simple
  return `/* === NOTE — simple === */
.note {
  background: var(--tpl-accent-lt) !important;
  border: 0.5pt solid var(--tpl-border, #d0d0d0) !important;
  border-left: 2.5pt solid var(--tpl-accent) !important;
  border-radius: 3pt !important;
  padding: 7pt 9pt !important;
  font-size: 9.6pt !important;
  line-height: 1.55 !important;
}
.note-label {
  font-family: var(--tpl-hd) !important;
  color: var(--tpl-accent-dk) !important;
  font-weight: 700 !important;
  font-size: 9.3pt !important;
  text-transform: uppercase !important;
  letter-spacing: 0.4pt !important;
}
.note p, .note li, .note span, .note strong { font-size: 9.6pt !important; line-height: 1.55 !important; }`;
}

function genCode() {
  return `/* === CODE BLOCKS === */
.code-block code, .line {
  font-family: var(--tpl-cd) !important;
  font-size: 9pt !important;
  line-height: 1.4 !important;
}
.inline-code, .content code:not(.line):not(pre code) {
  font-family: var(--tpl-cd) !important;
  font-size: 9pt !important;
  background: #F1F3F4 !important;
  color: var(--tpl-accent-dk) !important;
  border: 0.5pt solid var(--tpl-border, #d0d0d0) !important;
  border-radius: 2pt !important;
  padding: 0.5pt 2.5pt !important;
}
.code-lang-badge {
  background: var(--tpl-accent) !important;
  color: #FFFFFF !important;
  font-family: var(--tpl-cd) !important;
}`;
}

// ============================================================
// SVG decoration for h2 — inline data URI (WeasyPrint safe)
// ============================================================
function svgDataUri(type, color) {
  const c = color.replace('#', '%23');
  // viewBox 0 0 24 24 ทุกอัน → ปรับขนาด h2 รัน proportional
  const svgs = {
    // === Basic (simple shapes) ===
    bar:     `<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'><rect x='10' y='2' width='4' height='20' fill='${c}'/></svg>`,
    diamond: `<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'><path d='M12 3 L21 12 L12 21 L3 12 Z' stroke='${c}' stroke-width='2' fill='none'/></svg>`,
    chevron: `<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'><path d='M8 4 L16 12 L8 20' stroke='${c}' stroke-width='3' fill='none' stroke-linecap='round' stroke-linejoin='round'/></svg>`,
    dots:    `<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'><circle cx='4' cy='12' r='3' fill='${c}'/><circle cx='12' cy='12' r='3' fill='${c}'/><circle cx='20' cy='12' r='3' fill='${c}'/></svg>`,
    star:    `<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'><path d='M12 2 L14.5 9 L21.5 9 L16 13 L18 20 L12 16 L6 20 L8 13 L2.5 9 L9.5 9 Z' fill='${c}'/></svg>`,

    // === Decorative (complex, beautiful) ===
    fleuron: `<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'><path d='M12 3 C7 8 5 13 5 16 C5 19 8 20 12 20 C16 20 19 19 19 16 C19 13 17 8 12 3' stroke='${c}' stroke-width='1.5' fill='none'/><line x1='12' y1='6' x2='12' y2='19' stroke='${c}' stroke-width='1.2'/></svg>`,
    wave:    `<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'><path d='M2 14 Q6 6 12 12 T22 10' stroke='${c}' stroke-width='2' fill='none' stroke-linecap='round'/><circle cx='2' cy='14' r='1.2' fill='${c}'/><circle cx='22' cy='10' r='1.2' fill='${c}'/></svg>`,
    crown:   `<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'><path d='M3 20 L5 9 L9 13 L12 6 L15 13 L19 9 L21 20 Z' stroke='${c}' stroke-width='1.5' fill='none' stroke-linejoin='round'/><rect x='4' y='20' width='16' height='2' fill='${c}'/></svg>`,
    compass: `<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'><circle cx='12' cy='12' r='9' stroke='${c}' stroke-width='1.2' fill='none'/><path d='M12 3 L14 12 L10 12 Z' fill='${c}'/><path d='M12 21 L14 12 L10 12 Z' stroke='${c}' stroke-width='1' fill='none'/><circle cx='12' cy='12' r='1.2' fill='${c}'/></svg>`,
    quill:   `<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'><path d='M5 20 L19 6 L21 8 L7 22 Z' fill='${c}'/><path d='M5 20 L3 22 L4 23 L7 22 Z' fill='${c}'/><circle cx='20' cy='6' r='1.2' fill='${c}'/></svg>`,
    mandala: `<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'><circle cx='12' cy='12' r='5' stroke='${c}' stroke-width='1.5' fill='none'/><circle cx='12' cy='12' r='2' fill='${c}'/><g stroke='${c}' stroke-width='1.5' stroke-linecap='round'><line x1='12' y1='3' x2='12' y2='5.5'/><line x1='12' y1='18.5' x2='12' y2='21'/><line x1='3' y1='12' x2='5.5' y2='12'/><line x1='18.5' y1='12' x2='21' y2='12'/></g></svg>`,

    // === Grid 2×2 group ===
    squares_4: `<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'><path d='M7 3 L11 7 L7 11 L3 7 Z' fill='${c}'/><path d='M17 3 L21 7 L17 11 L13 7 Z' fill='${c}'/><path d='M7 13 L11 17 L7 21 L3 17 Z' fill='${c}'/><path d='M17 13 L21 17 L17 21 L13 17 Z' fill='${c}'/></svg>`,
    circles_4: `<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'><circle cx='8' cy='8' r='3' fill='${c}'/><circle cx='16' cy='8' r='3' fill='${c}'/><circle cx='8' cy='16' r='3' fill='${c}'/><circle cx='16' cy='16' r='3' fill='${c}'/></svg>`,
    windows:   `<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'><rect x='3' y='3' width='8.5' height='8.5' fill='${c}'/><rect x='12.5' y='3' width='8.5' height='8.5' fill='${c}'/><rect x='3' y='12.5' width='8.5' height='8.5' fill='${c}'/><rect x='12.5' y='12.5' width='8.5' height='8.5' fill='${c}'/></svg>`,
  };
  if (!svgs[type]) return '';
  return `url("data:image/svg+xml;utf8,${svgs[type]}")`;
}

function genH2Svg(c) {
  if (c.h2svg === 'none') return '';
  const uri = svgDataUri(c.h2svg, c.accent);
  if (!uri) return '';
  // override `content: none` ที่ genHeadings ตั้งไว้ก่อนหน้า (cascade last wins)
  // ใช้ background-image แทน content: url() เพราะคุม size/aspect ได้ดีกว่า + รองรับ WeasyPrint
  return `/* === H2 SVG decoration === */
.content h2::before {
  content: "" !important;
  display: inline-block !important;
  width: 14pt !important;
  height: 14pt !important;
  background-image: ${uri} !important;
  background-size: contain !important;
  background-repeat: no-repeat !important;
  background-position: center !important;
  vertical-align: middle !important;
  margin-right: 8pt !important;
  margin-bottom: 1.5pt !important;
}`;
}


function genDropCap(c) {
  if (!c.dropCap) return '';
  return `/* === DROP CAP === */
.drop-cap::first-letter {
  font-family: var(--tpl-hd) !important;
  font-size: 30pt !important;
  font-weight: 700 !important;
  color: var(--tpl-accent) !important;
  float: left !important;
  line-height: 0.85 !important;
  margin: 1pt 4pt 0 0 !important;
}`;
}

function genTOC(c) {
  // toc-title ใช้ blend เหมือน h1 — B&W toggle จะดันให้เข้มอัตโนมัติ
  const titleColor = blendToBlack(c.accentDk, c.h1dark);
  return `/* === TOC (สารบัญ) ===
   toc-title blend ตาม h1 darkness (${c.h1dark}%) */
.toc-title {
  font-family: var(--tpl-hd) !important;
  color: ${titleColor} !important;
  font-weight: 700 !important;
}
.toc-item {
  border-bottom: 0.4pt dashed var(--tpl-border, #d0d0d0) !important;
  color: var(--tpl-text) !important;
}
.toc-num {
  font-family: var(--tpl-hd) !important;
  color: var(--tpl-accent) !important;
  font-weight: 700 !important;
}
.toc-name {
  font-family: var(--tpl-bd) !important;
  color: var(--tpl-text) !important;
  font-weight: 500 !important;
}
.toc-leader {
  border-bottom: 0.4pt dotted var(--tpl-muted) !important;
}
.toc-page,
a.toc-item::after {
  font-family: var(--tpl-hd) !important;
  color: var(--tpl-muted) !important;
  font-weight: 500 !important;
}`;
}

function genPreface(c) {
  // preface-title blend ตาม h1 — สอดคล้องกัน (คำนำ = heading level 1)
  const titleColor = blendToBlack(c.accentDk, c.h1dark);
  return `/* === Preface (คำนำ) ===
   preface-title blend ตาม h1 darkness (${c.h1dark}%) */
.preface-title {
  font-family: var(--tpl-hd) !important;
  color: ${titleColor} !important;
  font-weight: 700 !important;
}
.preface-content p {
  font-family: var(--tpl-bd) !important;
  color: var(--tpl-text) !important;
}`;
}

function genMisc() {
  return `/* === MISC === */
.content strong, .content b { color: var(--tpl-accent-dk) !important; }
.content a { color: var(--tpl-accent) !important; }
.content mark { background: var(--tpl-accent-lt) !important; color: var(--tpl-accent-dk) !important; }
blockquote {
  border-left: 2.5pt solid var(--tpl-accent) !important;
  background: var(--tpl-accent-lt) !important;
  border-radius: 0 3pt 3pt 0 !important;
  padding: 7pt 10pt !important;
}
thead { background: var(--tpl-accent-lt) !important; }
th { color: var(--tpl-accent-dk) !important; border-bottom: 0.8pt solid var(--tpl-accent) !important; }
.img-marker {
  background: var(--tpl-accent) !important;
  color: #FFFFFF !important;
  border: 2px solid #FFFFFF !important;
}`;
}


// ============================================================
// MAIN — generate full CSS
// ============================================================
function generate() {
  const c = readConfig();

  const sections = [
    genGoogleImport(c),
    genVariables(c),
    genBody(c),
    genHeadings(c),
    genH2Svg(c),
    genChapter(c),
    genOL(c),
    genQuiz(),
    genNote(c),
    genCode(),
    genDropCap(c),
    genTOC(c),
    genPreface(c),
    genMisc(),
  ].filter(Boolean).join('\n\n\n');

  const header = `/* =========================================================
   style.css — generated by make_style_form
   ${new Date().toISOString().split('T')[0]}
   ---------------------------------------------------------
   ${STATE.baseName ? `Base: ${STATE.baseName}` : 'Base: (none — generated from scratch)'}
   Accent: ${c.accent} / Heading scale: ${c.h1}-${c.h2}-${c.h3}-${c.h4}pt
   Fonts: ${c.fontHd} / ${c.fontBd} / ${c.fontCd}
   ========================================================= */`;

  let output;
  if (STATE.baseCSS) {
    output = STATE.baseCSS +
      '\n\n\n/* ============================================================\n' +
      '   FORM ADJUSTMENTS — appended by make_style_form\n' +
      '   ============================================================ */\n\n' +
      sections;
  } else {
    output = header + '\n\n\n' + sections;
  }

  // update preview
  document.querySelector('#output code').textContent = output;
  document.getElementById('status').textContent =
    `✓ ${output.split('\n').length} lines · ${(output.length / 1024).toFixed(1)} KB`;

  return output;
}


// ============================================================
// EVENT HANDLERS
// ============================================================

// Form changes → regenerate
function bindForm() {
  const inputs = document.querySelectorAll('input, select');
  inputs.forEach(el => {
    el.addEventListener('change', () => {
      handleInputChange();
      generate();
    });
    if (el.type === 'range' || el.type === 'color' || el.type === 'number') {
      el.addEventListener('input', () => {
        handleInputChange();
        generate();
      });
    }
  });
}

function handleInputChange() {
  // sync derived colors
  const autoDerive = document.getElementById('autoDerive').checked;
  const accent = document.getElementById('accent').value;
  if (autoDerive) {
    document.getElementById('accentDk').value = darken(accent, 0.30);
    document.getElementById('accentLt').value = lighten(accent, 0.88);
  }
  document.getElementById('accentDk').disabled = autoDerive;
  document.getElementById('accentLt').disabled = autoDerive;

  // sync sliders display
  document.getElementById('underlineLenVal').textContent =
    document.getElementById('underlineLen').value;
  document.getElementById('sinkVal').textContent =
    document.getElementById('sinkAmount').value;

  // sync heading darkness slider values
  ['h1', 'h2', 'h3', 'h4'].forEach(h => {
    const val = document.getElementById(h + 'dark').value;
    document.getElementById(h + 'darkVal').textContent = val;
  });

  // toggle sinkage row
  const sink = document.getElementById('sinkage').checked;
  document.getElementById('sinkRow').hidden = !sink;

  // active swatch
  document.querySelectorAll('.swatch').forEach(s => {
    s.classList.toggle('active', s.dataset.hex.toLowerCase() === accent.toLowerCase());
  });
}

// "พิมพ์ขาวดำ" toggle → preset sliders auto (รัน BEFORE bindForm's generic handler)
function bindGrayModeToggle() {
  document.getElementById('printGrayMode').addEventListener('change', (e) => {
    const checked = e.target.checked;
    // Recommended defaults: h1=100, h2=100, h3=85, h4=70
    const preset = checked ? [100, 100, 85, 70] : [0, 0, 0, 0];
    ['h1', 'h2', 'h3', 'h4'].forEach((h, i) => {
      document.getElementById(h + 'dark').value = preset[i];
    });
    // bindForm's generic listener will trigger generate() หลังจาก handler นี้
  });
}

// Swatches
function bindSwatches() {
  document.querySelectorAll('.swatch').forEach(s => {
    s.addEventListener('click', () => {
      document.getElementById('accent').value = s.dataset.hex;
      handleInputChange();
      generate();
    });
  });
}

// File upload (click + drag-drop)
function bindUpload() {
  const input = document.getElementById('upload');
  const drop = document.getElementById('dropArea');

  function handleFile(file) {
    if (!file || !file.name.endsWith('.css')) {
      alert('กรุณาเลือกไฟล์ .css เท่านั้น');
      return;
    }
    const reader = new FileReader();
    reader.onload = e => {
      STATE.baseCSS = e.target.result;
      STATE.baseName = file.name;
      document.getElementById('fileName').textContent = file.name;
      document.getElementById('fileSize').textContent = `${(file.size / 1024).toFixed(1)} KB`;
      generate();
    };
    reader.readAsText(file);
  }

  input.addEventListener('change', e => handleFile(e.target.files[0]));

  ['dragenter', 'dragover'].forEach(ev =>
    drop.addEventListener(ev, e => { e.preventDefault(); drop.classList.add('drag'); })
  );
  ['dragleave', 'drop'].forEach(ev =>
    drop.addEventListener(ev, e => { e.preventDefault(); drop.classList.remove('drag'); })
  );
  drop.addEventListener('drop', e => {
    if (e.dataTransfer.files[0]) handleFile(e.dataTransfer.files[0]);
  });
}

// Download
function bindDownload() {
  document.getElementById('downloadBtn').addEventListener('click', () => {
    const css = generate();
    const blob = new Blob([css], { type: 'text/css' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = STATE.baseName
      ? STATE.baseName.replace('.css', '_custom.css')
      : 'style.css';
    a.click();
    URL.revokeObjectURL(url);
  });
}

// Copy to clipboard
function bindCopy() {
  document.getElementById('copyBtn').addEventListener('click', async () => {
    const css = generate();
    try {
      await navigator.clipboard.writeText(css);
      const btn = document.getElementById('copyBtn');
      const old = btn.textContent;
      btn.textContent = '✓ Copied!';
      setTimeout(() => { btn.textContent = old; }, 1500);
    } catch {
      alert('ไม่สามารถ copy ได้ — browser อาจ block');
    }
  });
}

// Reset
function bindReset() {
  document.getElementById('resetBtn').addEventListener('click', () => {
    if (!confirm('Reset ค่าทั้งหมดเป็น default?')) return;
    document.querySelector('form, .form')?.reset?.();
    // manual reset (form element not used)
    document.getElementById('accent').value = '#1A73E8';
    document.getElementById('autoDerive').checked = true;
    document.getElementById('fontHd').value = 'Poppins';
    document.getElementById('fontBd').value = 'IBM Plex Sans Thai Looped';
    document.getElementById('fontCd').value = 'IBM Plex Mono';
    document.querySelector('input[name="hdScale"][value="standard"]').checked = true;
    document.querySelector('input[name="h2under"][value="short"]').checked = true;
    document.getElementById('underlineLen').value = 50;
    document.querySelector('input[name="h2svg"][value="none"]').checked = true;
    document.querySelector('input[name="olStyle"][value="circle"]').checked = true;
    document.querySelector('input[name="noteStyle"][value="simple"]').checked = true;
    document.getElementById('dropCap').checked = false;
    document.getElementById('sinkage').checked = false;
    document.getElementById('sinkAmount').value = 35;
    document.getElementById('justifyBody').checked = false;
    document.getElementById('centerChapter').checked = false;
    document.getElementById('printGrayMode').checked = false;
    document.getElementById('h1dark').value = 0;
    document.getElementById('h2dark').value = 0;
    document.getElementById('h3dark').value = 0;
    document.getElementById('h4dark').value = 0;
    STATE.baseCSS = '';
    STATE.baseName = '';
    document.getElementById('fileName').textContent = 'ลากไฟล์ลงตรงนี้ หรือคลิกเพื่อเลือก';
    document.getElementById('fileSize').textContent = 'ยังไม่มีไฟล์';
    handleInputChange();
    generate();
  });
}


// ============================================================
// INIT
// ============================================================
document.addEventListener('DOMContentLoaded', () => {
  bindGrayModeToggle();   // ต้อง bind ก่อน bindForm — handler รันตามลำดับ register
  bindForm();
  bindSwatches();
  bindUpload();
  bindDownload();
  bindCopy();
  bindReset();
  handleInputChange();
  generate();
});
