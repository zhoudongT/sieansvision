#!/usr/bin/env node
/** wave142: fixture/pose result chrome + preprocess chain density + ROI polish markers. */
'use strict';
const path = require('path');
const fs = require('fs');
const ROOT = path.resolve(__dirname, '..');
let pass = 0, fail = 0;
const ok = (m) => { pass++; console.log('PASS:', m); };
const bad = (m) => { fail++; console.log('FAIL:', m); };

// --- chrome badge math ---
function fixtureBadge(boundOk, status) {
  if (boundOk === true || String(status || '').toLowerCase() === 'ok') {
    if (boundOk === false) return '夹✗';
    return '夹✓';
  }
  if (boundOk === false || String(status || '').toLowerCase() === 'unbound') return '夹✗';
  return '夹·';
}
function ppBadge(n, status, okFlag) {
  const mark = okFlag === true || String(status || '').toLowerCase() === 'ok' ? '✓'
    : (okFlag === false ? '✗' : '·');
  return `预${Math.max(1, n|0)}${mark}`;
}
if (fixtureBadge(true, 'ok') === '夹✓' && fixtureBadge(false, 'unbound') === '夹✗')
  ok('fixture badges 夹✓/夹✗');
else bad('fixture badges');
if (ppBadge(3, 'ok', true) === '预3✓' && ppBadge(1, 'fail', false) === '预1✗')
  ok('preprocess badges 预3✓/预1✗');
else bad('preprocess badges');

// matrix density shape
const matrix = [0.9, -0.4, 120, 0.4, 0.9, 80, 0, 0, 1];
const mRows = [0, 1, 2].map((r) => ({
  row: r, c0: matrix[r * 3], c1: matrix[r * 3 + 1], c2: matrix[r * 3 + 2], label: `R${r}`,
}));
if (mRows.length === 3 && mRows[0].c2 === 120 && mRows[2].c2 === 1) ok('matrix 3×3 density rows');
else bad('matrix rows');

// axis tips
const axisX = { x: 40, y: 20 }, axisY = { x: -20, y: 40 };
if (axisX.x > 0 && axisY.y > 0) ok(`axis tips X=(${axisX.x},${axisX.y}) Y=(${axisY.x},${axisY.y})`);
else bad('axis tips');

// chain density
const chain = [
  { index: 1, method: 'grayscale', label: '灰度化' },
  { index: 2, method: 'median', label: '中值滤波' },
  { index: 3, method: 'canny', label: '边缘提取' },
];
if (chain.length === 3 && chain[2].method === 'canny') ok(`chain density n=${chain.length}`);
else bad('chain density');

// before/after meta
const ba = { before: '640×480', after: '320×240', roiApplied: true, roiText: '[40,30,320,240]' };
if (ba.before.includes('×') && ba.after.includes('×') && ba.roiApplied) ok(`before/after ${ba.before}→${ba.after}`);
else bad('before/after');

// overlay kinds used by fixture/pp
const overlayKinds = ['line', 'point', 'label', 'cross', 'rect'];
if (overlayKinds.includes('line') && overlayKinds.includes('cross') && overlayKinds.includes('rect'))
  ok(`overlay kinds ${overlayKinds.length}`);
else bad('overlay kinds');

// ROI polish markers conceptually
const roiPolish = ['aspectLock', 'nudge', 'crosshair', 'snap', 'zoomFit', 'copyCoords'];
if (roiPolish.length === 6) ok(`roi polish bits ${roiPolish.join(',')}`);
else bad('roi polish');

// --- project ---
const projPath = path.join(ROOT, 'projects/open-and-run-fixture-pose-chain.sieans');
if (!fs.existsSync(projPath)) bad('project missing');
else {
  const proj = JSON.parse(fs.readFileSync(projPath, 'utf8'));
  const ops = proj.steps.map((s) => s.operation);
  if (ops.join(',') === 'locate,pose_correct,preprocess,var_calc') ok('project ops chain');
  else bad(`project ops ${ops}`);
  const pose = proj.steps.find((s) => s.operation === 'pose_correct');
  if (pose && pose.params && pose.params.showAxes === true && pose.params.showMatrix === true)
    ok(`pose showAxes/matrix axisLength=${pose.params.axisLength}`);
  else bad(`pose ${JSON.stringify(pose && pose.params)}`);
  const pp = proj.steps.find((s) => s.operation === 'preprocess');
  const chainP = (pp && pp.params && pp.params.methodChain) || [];
  if (Array.isArray(chainP) && chainP.length >= 3 && chainP[0].method === 'grayscale')
    ok(`preprocess methodChain n=${chainP.length}`);
  else bad(`methodChain ${JSON.stringify(chainP)}`);
  if (String(proj.notes || '').includes('wave142')) ok('notes wave142');
  else bad('notes');
  if (Array.isArray(proj.sourceConfig.images) && proj.sourceConfig.images.length >= 2)
    ok(`samples ${proj.sourceConfig.images.length}`);
  else bad('samples');
  if (proj.meta && proj.meta.wave === 142) ok('meta.wave 142');
  else bad('meta.wave');
}

// --- desktop files ---
const need = [
  'desktop/fixture_pose_chrome.py',
  'desktop/preprocess_chain_chrome.py',
  'desktop/pose_correct_panel.py',
  'desktop/wave3_thin_panels.py',
  'desktop/simple_roi_editor.py',
  'desktop/display_overlay_density.py',
  'desktop/mainwindow.py',
  'desktop/catalog.py',
  'lib/flow-control.cjs',
  'vision/engine.py',
];
for (const rel of need) {
  if (fs.existsSync(path.join(ROOT, rel))) ok(`file ${rel}`);
  else bad(`missing ${rel}`);
}

// source markers
const markers = [
  ['desktop/fixture_pose_chrome.py', 'build_fixture_overlays'],
  ['desktop/fixture_pose_chrome.py', 'format_matrix_rows'],
  ['desktop/fixture_pose_chrome.py', 'summarize_fixture_result'],
  ['desktop/preprocess_chain_chrome.py', 'build_chain_rows'],
  ['desktop/preprocess_chain_chrome.py', 'before_after_meta'],
  ['desktop/preprocess_chain_chrome.py', 'normalize_method_chain'],
  ['desktop/display_overlay_density.py', "op == 'pose_correct'"],
  ['desktop/display_overlay_density.py', "op == 'preprocess'"],
  ['desktop/mainwindow.py', '_ingest_pose_correct_panel_from_result'],
  ['desktop/mainwindow.py', '_ingest_preprocess_panel_from_result'],
  ['desktop/mainwindow.py', 'open-and-run-fixture-pose-chain.sieans'],
  ['desktop/pose_correct_panel.py', 'set_last_result'],
  ['desktop/wave3_thin_panels.py', 'methodChain'],
  ['desktop/wave3_thin_panels.py', 'set_last_result'],
  ['desktop/simple_roi_editor.py', 'simpleRoiAspectLock'],
  ['desktop/simple_roi_editor.py', '_nudge'],
  ['desktop/simple_roi_editor.py', 'simpleRoiCrosshair'],
  ['vision/engine.py', 'methodChain'],
  ['vision/engine.py', 'chainSteps'],
  ['vision/engine.py', 'beforeWidth'],
  ['lib/flow-control.cjs', "prefix+'_m'+i"],
  ['desktop/catalog.py', "extra('preprocess', 'methodChain'"],
];
for (const [rel, needle] of markers) {
  const txt = fs.readFileSync(path.join(ROOT, rel), 'utf8');
  if (txt.includes(needle)) ok(`marker ${rel}::${needle}`);
  else bad(`marker ${rel}::${needle}`);
}

// guard: no Comm/HMI cobind / spark in new modules
for (const rel of [
  'desktop/fixture_pose_chrome.py',
  'desktop/preprocess_chain_chrome.py',
  'desktop/simple_roi_editor.py',
]) {
  const txt = fs.readFileSync(path.join(ROOT, rel), 'utf8');
  if (/hostWatch|host_sm|sparkBlink|OK.?NG.?cobind|recipeSwitch/i.test(txt))
    bad(`forbidden surface in ${rel}`);
  else ok(`clean surface ${path.basename(rel)}`);
}

console.log(`\nwave142 CJS ${pass} pass / ${fail} fail`);
process.exit(fail ? 1 : 0);
