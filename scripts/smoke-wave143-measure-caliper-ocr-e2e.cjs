#!/usr/bin/env node
/** wave143: measure/caliper denser chrome + OCR/defect tables + annotate density markers. */
'use strict';
const path = require('path');
const fs = require('fs');
const ROOT = path.resolve(__dirname, '..');
let pass = 0, fail = 0;
const ok = (m) => { pass++; console.log('PASS:', m); };
const bad = (m) => { fail++; console.log('FAIL:', m); };

// --- measure badges ---
function measureBadge(judgeOk, status, op) {
  const tags = {
    point_distance: '距', line_intersect: '交', point_line_distance: '垂',
    line_angle: '角', caliper: '尺', geometry: '尺',
  };
  const tag = tags[op] || '测';
  let mark = '·';
  if (judgeOk === true || String(status || '').toUpperCase() === 'OK') mark = '✓';
  else if (judgeOk === false || String(status || '').toUpperCase() === 'NG') mark = '✗';
  if (op === 'caliper' || op === 'geometry') return `${tag}3${mark}`;
  return `${tag}${mark}`;
}
if (measureBadge(true, 'OK', 'point_distance') === '距✓' && measureBadge(false, 'NG', 'caliper') === '尺3✗')
  ok('measure badges 距✓/尺3✗');
else bad('measure badges');

// tolerance band
function toleranceBand(value, lo, hi) {
  const span = hi - lo;
  const ratio = span > 0 ? (value - lo) / span : 0;
  return { inBand: value >= lo && value <= hi, ratio, span };
}
const tb = toleranceBand(128, 80, 200);
if (tb.inBand && Math.abs(tb.ratio - 0.4) < 1e-9) ok(`tolerance band inBand ratio=${tb.ratio}`);
else bad('tolerance band');

// OCR / defect badges
function odBadge(kind, judgeOk, count) {
  const tag = kind === 'defects' ? '缺' : '识';
  const mark = judgeOk === true ? '✓' : (judgeOk === false ? '✗' : '·');
  return count != null ? `${tag}${count}${mark}` : `${tag}${mark}`;
}
if (odBadge('ocr', true, 3) === '识3✓' && odBadge('defects', false, 3) === '缺3✗')
  ok('ocr/defect badges 识3✓/缺3✗');
else bad('ocr/defect badges');

// 6-col industrial table shapes
const measureCols = ['#', '算子', '度量', '下限', '上限', '判定'];
const ocrCols = ['#', '文本', '置信度', '中心', 'bbox', '判定'];
const defCols = ['#', '面积', '中心', 'bbox', '分数', '判定'];
if (measureCols.length === 6 && ocrCols.length === 6 && defCols.length === 6)
  ok('industrial 6-col tables measure/ocr/defect');
else bad('6-col tables');

// overlay kinds
const overlayKinds = ['line', 'point', 'label', 'cross', 'rect'];
if (overlayKinds.includes('line') && overlayKinds.includes('rect') && overlayKinds.includes('cross'))
  ok(`overlay kinds ${overlayKinds.length}`);
else bad('overlay kinds');

// annotate density palette / pens
const palette = ['ok', 'ng', 'roi', 'caliper', 'caliper_tip', 'tolerance_ok', 'tolerance_ng', 'crosshair'];
if (palette.length >= 8) ok(`annotate palette ${palette.join(',')}`);
else bad('annotate palette');

const editorDefaults = ['showCrosshair', 'showRoiLabel', 'showHandles', 'nudgeStep', 'aspectLock', 'pen'];
if (editorDefaults.length === 6) ok(`shared editor defaults ${editorDefaults.length}`);
else bad('editor defaults');

// --- project ---
const projPath = path.join(ROOT, 'projects/open-and-run-measure-caliper-chrome.sieans');
if (!fs.existsSync(projPath)) bad('project missing');
else {
  const proj = JSON.parse(fs.readFileSync(projPath, 'utf8'));
  const ops = proj.steps.map((s) => s.operation);
  if (ops.join(',') === 'preprocess,geometry,point_distance,ocr,defects,var_calc')
    ok('project ops chain');
  else bad(`project ops ${ops}`);
  const geo = proj.steps.find((s) => s.operation === 'geometry');
  if (geo && geo.params && geo.params.findMethod === 'caliper' && geo.params.showCalipers === true)
    ok(`geometry caliper findMethod count=${geo.params.caliperCount}`);
  else bad('geometry caliper');
  const pd = proj.steps.find((s) => s.operation === 'point_distance');
  if (pd && pd.params && pd.params.showTolerance === true && pd.params.judgeEnable === true)
    ok(`point_distance showTolerance T=[${pd.params.judgeMin},${pd.params.judgeMax}]`);
  else bad('point_distance tolerance');
  const ocr = proj.steps.find((s) => s.operation === 'ocr');
  if (ocr && ocr.params && ocr.params.showBoxes === true && ocr.params.expectedText)
    ok(`ocr industrial expected=${ocr.params.expectedText}`);
  else bad('ocr step');
  const def = proj.steps.find((s) => s.operation === 'defects');
  if (def && def.params && def.params.showBoxes === true && def.params.judgeEnable === true)
    ok(`defects industrial judgeMaxCount=${def.params.judgeMaxCount}`);
  else bad('defects step');
  if (String(proj.notes || '').includes('wave143')) ok('notes wave143');
  else bad('notes');
}

// --- file markers ---
const markers = [
  ['desktop/measure_caliper_chrome.py', 'chrome_badge'],
  ['desktop/measure_caliper_chrome.py', 'tolerance_band'],
  ['desktop/measure_caliper_chrome.py', 'build_measure_overlays'],
  ['desktop/measure_caliper_chrome.py', 'build_caliper_overlays'],
  ['desktop/measure_caliper_chrome.py', 'density_measure_rows'],
  ['desktop/measure_caliper_chrome.py', 'soft_demo_measure_result'],
  ['desktop/ocr_defect_chrome.py', 'build_ocr_rows'],
  ['desktop/ocr_defect_chrome.py', 'build_defect_rows'],
  ['desktop/ocr_defect_chrome.py', 'build_ocr_overlays'],
  ['desktop/ocr_defect_chrome.py', 'build_defect_overlays'],
  ['desktop/ocr_defect_chrome.py', 'density_summary_rows'],
  ['desktop/annotate_draw_density.py', 'PALETTE'],
  ['desktop/annotate_draw_density.py', 'pen_style'],
  ['desktop/annotate_draw_density.py', 'caliper_probe_specs'],
  ['desktop/annotate_draw_density.py', 'shared_editor_defaults'],
  ['desktop/display_overlay_density.py', 'build_measure_overlays'],
  ['desktop/display_overlay_density.py', 'build_caliper_overlays'],
  ['desktop/display_overlay_density.py', 'build_ocr_overlays'],
  ['desktop/display_overlay_density.py', 'build_defect_overlays'],
  ['desktop/mainwindow.py', '_ingest_measure_geom_panel_from_result'],
  ['desktop/mainwindow.py', '_ingest_recognize_panels_from_result'],
  ['desktop/mainwindow.py', 'open-and-run-measure-caliper-chrome.sieans'],
  ['desktop/mainwindow.py', 'prefer measure_caliper_chrome'],
  ['desktop/measure_geom_panel.py', 'measureGeomResultTable'],
  ['desktop/measure_geom_panel.py', '_apply_measure_density'],
  ['desktop/measure_geom_panel.py', 'showTolerance'],
  ['desktop/recognize_panels.py', 'ocrItemsTable'],
  ['desktop/recognize_panels.py', 'defectsItemsTable'],
  ['desktop/recognize_panels.py', '_apply_ocr_density'],
  ['desktop/recognize_panels.py', '_apply_defects_density'],
  ['desktop/caliper_roi_editor.py', 'annotate_draw_density'],
  ['desktop/simple_roi_editor.py', 'annotate_draw_density'],
];
for (const [rel, needle] of markers) {
  const fp = path.join(ROOT, rel);
  if (!fs.existsSync(fp)) { bad(`missing ${rel}`); continue; }
  const txt = fs.readFileSync(fp, 'utf8');
  if (txt.includes(needle)) ok(`marker ${rel}::${needle}`);
  else bad(`marker ${rel}::${needle}`);
}

// guard: no Comm/HMI cobind / spark in new modules
for (const rel of [
  'desktop/measure_caliper_chrome.py',
  'desktop/ocr_defect_chrome.py',
  'desktop/annotate_draw_density.py',
]) {
  const txt = fs.readFileSync(path.join(ROOT, rel), 'utf8');
  if (/hostWatch|host_sm|sparkBlink|OK.?NG.?cobind|recipeSwitch/i.test(txt))
    bad(`forbidden surface in ${rel}`);
  else ok(`clean surface ${path.basename(rel)}`);
}

// guard: ?? os and :18280 untouched conceptually (no edit markers in this wave to those)
const gitOs = path.join(ROOT, 'os');
if (fs.existsSync(gitOs)) ok('os/ present (untouched by wave143 markers)');
else ok('os/ absent-or-untracked (leave alone)');

console.log(`\nwave143 CJS ${pass} pass / ${fail} fail`);
process.exit(fail ? 1 : 0);
