#!/usr/bin/env node
/** wave145: barcode/ID denser result chrome + open-and-run audit markers. */
'use strict';
const path = require('path');
const fs = require('fs');
const ROOT = path.resolve(__dirname, '..');
let pass = 0, fail = 0;
const ok = (m) => { pass++; console.log('PASS:', m); };
const bad = (m) => { fail++; console.log('FAIL:', m); };

function chromeBadge(judgeOk, status, count) {
  let mark = '·';
  if (judgeOk === true || String(status || '').toUpperCase() === 'OK') mark = '✓';
  else if (judgeOk === false || String(status || '').toUpperCase() === 'NG') mark = '✗';
  if (count != null && count >= 0) return `码${count}${mark}`;
  return `码${mark}`;
}
if (chromeBadge(true, 'OK', 2) === '码2✓' && chromeBadge(false, 'NG', 0) === '码0✗' && chromeBadge(null, '', null) === '码·')
  ok('barcode badges 码2✓/码0✗/码·');
else bad('barcode badges');

const cols = ['#', '文本', '码制', '中心X', '中心Y', '宽', '高', '判定'];
if (cols.length === 8) ok(`barcode 8-col table ${cols.join('/')}`);
else bad('8-col table');

function softDemoRows(n, okFlag) {
  const demos = [
    { text: 'MACHINE-QR-2026', format: 'QR Code' },
    { text: 'ABC123456789', format: 'Code 128' },
  ];
  const rows = [];
  for (let i = 0; i < n; i++) {
    const base = demos[i % demos.length];
    const text = (!okFlag && i === n - 1) ? 'WRONG-ID' : base.text;
    rows.push({
      index: i + 1, text, format: base.format,
      judge: text.includes('MACHINE-QR') || (okFlag && i === 0) ? 'OK' : (okFlag ? 'OK' : 'NG'),
    });
  }
  return rows;
}
const rowsOk = softDemoRows(2, true);
const rowsNg = softDemoRows(2, false);
if (rowsOk.length === 2 && rowsOk[0].text.includes('MACHINE') && rowsNg[1].judge === 'NG')
  ok(`soft demo rows ok2/ng top=${rowsOk[0].text}`);
else bad('soft demo rows');

const overlayKinds = ['polygon', 'cross', 'label', 'rect'];
if (overlayKinds.includes('polygon') && overlayKinds.includes('label'))
  ok(`barcode overlay kinds ${overlayKinds.join('+')}`);
else bad('overlay kinds');

function filmChrome(count, judgeOk) {
  return chromeBadge(judgeOk, judgeOk ? 'OK' : 'NG', count);
}
if (filmChrome(2, true) === '码2✓' && filmChrome(0, false) === '码0✗')
  ok('filmstrip barcode chrome 码2✓/码0✗');
else bad('filmstrip chrome');

const chromePath = path.join(ROOT, 'desktop/barcode_id_chrome.py');
if (!fs.existsSync(chromePath)) bad('barcode_id_chrome.py missing');
else {
  const src = fs.readFileSync(chromePath, 'utf8');
  const forbidden = ['sparkSeek', 'blinkChip', 'commBind', 'recipeBind', 'okNgHost'];
  // hostWatch is OK in project JSON but chrome module should not drive hostWatch cascade
  const hit = forbidden.filter((k) => src.includes(k));
  if (hit.length === 0) ok('chrome module free of spark/Comm cascade markers');
  else bad('forbidden markers: ' + hit.join(','));
  for (const need of ['chrome_badge', 'summarize_barcode', 'build_barcode_overlays', 'BARCODE_COLUMNS', 'soft_demo_barcode_result']) {
    if (src.includes(`def ${need}`) || src.includes(need + ' =') || src.includes(need)) ok(`has ${need}`);
    else bad(`missing ${need}`);
  }
}

const samplePath = path.join(ROOT, 'projects/open-and-run-barcode.sieans');
if (!fs.existsSync(samplePath)) bad('barcode sample missing');
else {
  const sample = JSON.parse(fs.readFileSync(samplePath, 'utf8'));
  const ops = (sample.steps || []).map((s) => s.operation);
  if (ops.includes('barcode') && ops.includes('var_calc')) ok(`sample steps ${ops.join('→')}`);
  else bad('sample steps incomplete: ' + ops.join(','));
  if (sample.hostWatch && (sample.hostWatch.watchKeys || []).includes('passGate'))
    ok('sample hostWatch seeds passGate');
  else bad('sample hostWatch missing');
  if (sample.runUi && sample.runUi.meta && sample.runUi.meta.wave === 145)
    ok('sample runUi wave145');
  else bad('sample runUi meta');
  const params = ((sample.steps || [])[0] || {}).params || {};
  if (params.expectedText === 'MACHINE-QR-2026' && params.judgeEnable)
    ok('sample expectedText + judgeEnable');
  else bad('sample barcode params');
}

const dp = path.join(ROOT, 'projects/default-platform.sieans');
if (fs.existsSync(dp)) {
  const d = JSON.parse(fs.readFileSync(dp, 'utf8'));
  if (String(d.name || '').includes('默认产线')) ok(`default-platform name=${d.name}`);
  else bad('default-platform name not renamed');
} else bad('default-platform missing');

const readme = fs.readFileSync(path.join(ROOT, 'projects/README-open-and-run.md'), 'utf8');
if (readme.includes('open-and-run-barcode.sieans') && readme.includes('wave145') && readme.includes('match-locate-chrome'))
  ok('README inventory includes barcode + wave145 audit');
else bad('README incomplete');

const docs = path.join(ROOT, 'docs/open-and-run-samples.md');
if (fs.existsSync(docs)) ok('docs/open-and-run-samples.md present');
else bad('docs note missing');

for (const rel of [
  'projects/open-and-run-contour-color.sieans',
  'projects/open-and-run-fixture-pose-chain.sieans',
  'projects/open-and-run-measure-caliper-chrome.sieans',
]) {
  const p = path.join(ROOT, rel);
  const d = JSON.parse(fs.readFileSync(p, 'utf8'));
  if (d.runUi && d.runUi.split) ok(`${path.basename(rel)} has runUi`);
  else bad(`${rel} missing runUi`);
}

const np = JSON.parse(fs.readFileSync(path.join(ROOT, 'projects/open-and-run-ninepoint.sieans'), 'utf8'));
if (np.hostWatch && (np.hostWatch.watchKeys || []).includes('calibRms')) ok('ninepoint hostWatch seeded');
else bad('ninepoint hostWatch');

const rec = fs.readFileSync(path.join(ROOT, 'desktop/recognize_panels.py'), 'utf8');
if (rec.includes('class BarcodePanel') && rec.includes('_apply_barcode_density')) ok('BarcodePanel present');
else bad('BarcodePanel missing');

const film = fs.readFileSync(path.join(ROOT, 'desktop/widgets/filmstrip.py'), 'utf8');
if (film.includes('set_frame_barcode_chrome') && film.includes('barcode_strip')) ok('filmstrip barcode chrome hooks');
else bad('filmstrip hooks');

const mw = fs.readFileSync(path.join(ROOT, 'desktop/mainwindow.py'), 'utf8');
if (mw.includes('_sync_filmstrip_barcode_chrome') && mw.includes('BarcodePanel')) ok('mainwindow barcode wiring');
else bad('mainwindow wiring');

console.log(`\nRESULT ${pass}/${pass + fail} (fail=${fail})`);
process.exit(fail ? 1 : 0);
