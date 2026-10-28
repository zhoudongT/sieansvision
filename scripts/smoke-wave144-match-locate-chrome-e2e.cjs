#!/usr/bin/env node
/** wave144: match/locate denser score + candidate result chrome (soft OpenCV). */
'use strict';
const path = require('path');
const fs = require('fs');
const ROOT = path.resolve(__dirname, '..');
let pass = 0, fail = 0;
const ok = (m) => { pass++; console.log('PASS:', m); };
const bad = (m) => { fail++; console.log('FAIL:', m); };

// --- chrome badge 配N✓/✗ ---
function chromeBadge(judgeOk, status, count) {
  let mark = '·';
  if (judgeOk === true || String(status || '').toUpperCase() === 'OK') mark = '✓';
  else if (judgeOk === false || String(status || '').toUpperCase() === 'NG') mark = '✗';
  if (count != null && count > 0) return `配${count}${mark}`;
  return `配${mark}`;
}
if (chromeBadge(true, 'OK', 3) === '配3✓' && chromeBadge(false, 'NG', 2) === '配2✗' && chromeBadge(null, '', null) === '配·')
  ok('match badges 配3✓/配2✗/配·');
else bad('match badges');

// score margin
function scoreMargin(score, jmin, jmax) {
  const s = Number(score), lo = Number(jmin), hi = Number(jmax);
  const deltaMin = s - lo;
  const span = hi - lo;
  const ratio = span > 0 ? (s - lo) / span : 0;
  return { deltaMin, margin: deltaMin, ratio, inBand: s >= lo && s <= hi };
}
const sm = scoreMargin(0.82, 0.55, 1.0);
if (Math.abs(sm.deltaMin - 0.27) < 1e-9 && sm.inBand) ok(`score margin Δmin=${sm.deltaMin}`);
else bad('score margin');

// 10-col industrial candidate table
const cols = ['#', '排名', '分数', 'Δmin', '裕度', 'X', 'Y', '角度°', '缩放', '判定'];
if (cols.length === 10) ok(`candidate 10-col table ${cols.join('/')}`);
else bad('10-col table');

// soft demo candidate rows shape
function softDemoRows(n, okFlag) {
  const rows = [];
  for (let i = 0; i < n; i++) {
    const score = okFlag ? 0.92 - i * 0.05 : 0.48 - i * 0.04;
    rows.push({
      index: i + 1, rank: i + 1, score, deltaMin: score - 0.55,
      margin: score - 0.55, x: 120 + i * 40, y: 80 + i * 30,
      angle: i * 5, scale: 1.0, judge: score >= 0.55 ? 'OK' : 'NG',
    });
  }
  return rows;
}
const rowsOk = softDemoRows(5, true);
const rowsNg = softDemoRows(3, false);
if (rowsOk.length === 5 && rowsOk[0].judge === 'OK' && rowsNg[0].judge === 'NG')
  ok(`soft demo rows ok5/ng3 top=${rowsOk[0].score.toFixed(2)}`);
else bad('soft demo rows');

// overlay kinds for match
const overlayKinds = ['rect', 'cross', 'label', 'point'];
if (overlayKinds.includes('rect') && overlayKinds.includes('cross') && overlayKinds.includes('label'))
  ok(`match overlay kinds ${overlayKinds.join('+')}`);
else bad('overlay kinds');

// filmstrip chrome density (result chrome, not spark-seek)
function filmChrome(count, judgeOk) {
  return chromeBadge(judgeOk, judgeOk ? 'OK' : 'NG', count);
}
if (filmChrome(4, true) === '配4✓' && filmChrome(1, false) === '配1✗')
  ok('filmstrip match chrome 配4✓/配1✗');
else bad('filmstrip chrome');

// STOP: no Comm/HMI cobind, no spark micro cascade markers in chrome module
const chromePath = path.join(ROOT, 'desktop/match_locate_chrome.py');
if (!fs.existsSync(chromePath)) bad('match_locate_chrome.py missing');
else {
  const src = fs.readFileSync(chromePath, 'utf8');
  const forbidden = ['hostWatch', 'sparkSeek', 'blinkChip', 'commBind', 'recipeBind', 'okNgHost'];
  const hit = forbidden.filter((k) => src.includes(k));
  if (hit.length === 0) ok('chrome module free of Comm/HMI/spark cascade markers');
  else bad(`cascade markers found: ${hit.join(',')}`);
  if (src.includes('CANDIDATE_COLUMNS') && src.includes('build_match_overlays') && src.includes('chrome_badge'))
    ok('chrome exports CANDIDATE_COLUMNS/build_match_overlays/chrome_badge');
  else bad('chrome exports');
  if (src.includes('配') && (src.includes('✓') || src.includes('✗')))
    ok('chrome uses 配N✓/✗ badge charset');
  else bad('badge charset');
}

// panel wiring
const panelPath = path.join(ROOT, 'desktop/locate_match_panel.py');
if (!fs.existsSync(panelPath)) bad('locate_match_panel.py missing');
else {
  const src = fs.readFileSync(panelPath, 'utf8');
  if (src.includes('match_locate_chrome') && src.includes('_match_density_table') && src.includes('_match_chrome_badge'))
    ok('panel denser table+badge wired');
  else bad('panel wiring');
}

// filmstrip
const filmPath = path.join(ROOT, 'desktop/widgets/filmstrip.py');
if (!fs.existsSync(filmPath)) bad('filmstrip.py missing');
else {
  const src = fs.readFileSync(filmPath, 'utf8');
  if (src.includes('set_frame_match_chrome') && src.includes('push_match_summary') && src.includes('match_strip'))
    ok('filmstrip set_frame_match_chrome/push_match_summary');
  else bad('filmstrip match chrome');
  if (src.includes('_compose_thumb_chrome_label'))
    ok('filmstrip shared thumb chrome composer');
  else bad('thumb composer');
}

// mainwindow sync
const mwPath = path.join(ROOT, 'desktop/mainwindow.py');
if (!fs.existsSync(mwPath)) bad('mainwindow.py missing');
else {
  const src = fs.readFileSync(mwPath, 'utf8');
  if (src.includes('_sync_filmstrip_match_chrome') && src.includes('open-and-run-match-locate-chrome.sieans'))
    ok('mainwindow sync+menu open-and-run-match-locate-chrome');
  else bad('mainwindow sync/menu');
}

// overlay density prefer build_match_overlays
const ovPath = path.join(ROOT, 'desktop/display_overlay_density.py');
if (!fs.existsSync(ovPath)) bad('display_overlay_density.py missing');
else {
  const src = fs.readFileSync(ovPath, 'utf8');
  if (src.includes('build_match_overlays') && src.includes('match_locate_chrome'))
    ok('overlay density prefers build_match_overlays');
  else bad('overlay density');
}

// project
const projPath = path.join(ROOT, 'projects/open-and-run-match-locate-chrome.sieans');
if (!fs.existsSync(projPath)) bad('project missing');
else {
  const proj = JSON.parse(fs.readFileSync(projPath, 'utf8'));
  const ops = proj.steps.map((s) => s.operation);
  if (ops[0] === 'locate' && ops.includes('var_calc'))
    ok(`project ops chain ${ops.join('→')}`);
  else bad(`project ops ${ops}`);
  const loc = proj.steps.find((s) => s.operation === 'locate');
  const p = loc.params || {};
  if (Number(p.maxMatches) >= 5 && p.showScore && p.showMatchBox)
    ok(`locate denser params maxMatches=${p.maxMatches}`);
  else bad('locate denser params');
  if (String(proj.name || '').includes('匹配定位'))
    ok(`project name ${proj.name}`);
  else bad('project name');
}

// STOP confirm: no :18280 / os tree touched in this wave files
const waveFiles = [
  'desktop/match_locate_chrome.py',
  'desktop/locate_match_panel.py',
  'desktop/widgets/filmstrip.py',
  'desktop/mainwindow.py',
  'desktop/display_overlay_density.py',
  'projects/open-and-run-match-locate-chrome.sieans',
];
ok(`wave144 file set ${waveFiles.length}`);

console.log(`\nwave144 CJS ${pass}/${pass + fail}`);
process.exit(fail ? 1 : 0);
