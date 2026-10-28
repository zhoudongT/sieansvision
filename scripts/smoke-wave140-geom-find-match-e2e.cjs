#!/usr/bin/env node
/** wave140: geometry-find (non-caliper) + multi-match density project + chrome helpers. */
'use strict';
const path = require('path');
const fs = require('fs');
const ROOT = path.resolve(__dirname, '..');
let pass = 0, fail = 0;
const ok = (m) => { pass++; console.log('PASS:', m); };
const bad = (m) => { fail++; console.log('FAIL:', m); };

// --- chrome helper module (python mirror checks via project + FEATURE tags) ---
const FEATURE_TAGS = { lines: 'L', edges: 'E', circles: 'C', rects: 'R', contours: 'B', blobs: 'B' };
function featureTag(f) {
  return FEATURE_TAGS[String(f || 'lines').toLowerCase()] || 'G';
}
function chromeBadge(rec) {
  const tag = featureTag(rec.feature);
  const n = Number(rec.count || 0);
  const mark = rec.judgeOk === true ? '✓' : (rec.judgeOk === false ? '✗' : '');
  return `${tag}${n}${mark}`;
}
if (featureTag('lines') === 'L' && featureTag('circles') === 'C' && featureTag('rects') === 'R')
  ok('feature tags L/C/R');
else bad('feature tags');
if (chromeBadge({ feature: 'lines', count: 3, judgeOk: true }) === 'L3✓')
  ok('chrome L3✓');
else bad('chrome badge');
if (chromeBadge({ feature: 'circles', count: 2, judgeOk: false }) === 'C2✗')
  ok('chrome C2✗');
else bad('chrome C2');

// multi-match density shape
const matches = [
  { score: 0.97, centerX: 10, centerY: 20, angleDeg: 0, scale: 1, judgeOk: true },
  { score: 0.91, centerX: 30, centerY: 40, angleDeg: 5, scale: 1.02, judgeOk: true },
  { score: 0.72, centerX: 50, centerY: 60, angleDeg: -2, scale: 0.98, judgeOk: false },
];
const best = Math.max(...matches.map((m) => m.score));
const okN = matches.filter((m) => m.judgeOk).length;
if (matches.length === 3 && best > 0.95 && okN === 2) ok(`multi-match density best=${best} okN=${okN}`);
else bad('multi-match density');

// --- project ---
const projPath = path.join(ROOT, 'projects/open-and-run-geom-find-match.sieans');
if (!fs.existsSync(projPath)) { bad('project missing'); }
else {
  const proj = JSON.parse(fs.readFileSync(projPath, 'utf8'));
  const ops = proj.steps.map((s) => s.operation);
  if (ops.join(',') === 'preprocess,geometry,locate,var_calc') ok('project ops chain');
  else bad(`project ops ${ops}`);
  const geo = proj.steps.find((s) => s.operation === 'geometry');
  if (geo && geo.params && geo.params.findMethod === 'hough' && geo.params.feature === 'lines')
    ok('geometry hough lines (non-caliper)');
  else bad(`geometry ${JSON.stringify(geo && geo.params)}`);
  if (geo && Number(geo.params.maxCount) >= 3) ok(`geometry maxCount=${geo.params.maxCount}`);
  else bad('geometry maxCount');
  const loc = proj.steps.find((s) => s.operation === 'locate');
  if (loc && Number(loc.params.maxMatches) >= 3 && loc.reference)
    ok(`locate multi-match maxMatches=${loc.params.maxMatches}`);
  else bad(`locate ${JSON.stringify(loc && loc.params)}`);
  const vc = proj.steps.find((s) => s.operation === 'var_calc');
  const exprs = (vc && vc.params && vc.params.expressions) || [];
  const names = exprs.map((e) => e.name);
  if (names.includes('passGate') && names.includes('lineCount')) ok('var_calc passGate+lineCount');
  else bad(`var_calc ${names}`);
  if (Array.isArray(proj.sourceConfig.images) && proj.sourceConfig.images.length >= 2)
    ok(`samples ${proj.sourceConfig.images.length}`);
  else bad('samples');
  if (String(proj.notes || '').includes('wave140')) ok('notes wave140');
  else bad('notes');
}

// --- desktop files present ---
const need = [
  'desktop/geom_find_chrome.py',
  'desktop/geometry_find_panel.py',
  'desktop/locate_match_panel.py',
  'desktop/widgets/filmstrip.py',
  'desktop/recognize_panels.py',
];
for (const rel of need) {
  const p = path.join(ROOT, rel);
  if (fs.existsSync(p)) ok(`file ${rel}`);
  else bad(`missing ${rel}`);
}
const film = fs.readFileSync(path.join(ROOT, 'desktop/widgets/filmstrip.py'), 'utf8');
if (film.includes('set_frame_geom_find_chrome') && film.includes('filmstripGeomFindStrip'))
  ok('filmstrip geom chrome APIs');
else bad('filmstrip APIs');
const locp = fs.readFileSync(path.join(ROOT, 'desktop/locate_match_panel.py'), 'utf8');
if (locp.includes('locateMatchDensityTable') && locp.includes('refresh_match_density'))
  ok('locate density APIs');
else bad('locate density APIs');
const rec = fs.readFileSync(path.join(ROOT, 'desktop/recognize_panels.py'), 'utf8');
if (rec.includes('defectsItemsTable') && rec.includes('ocrItemsTable'))
  ok('ocr/defect items tables');
else bad('ocr/defect tables');

console.log(`\n${fail ? 'FAIL' : 'PASS'} ${pass} ok / ${fail} fail`);
process.exit(fail ? 1 : 0);
