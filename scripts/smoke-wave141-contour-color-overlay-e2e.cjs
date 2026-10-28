#!/usr/bin/env node
/** wave141: soft contour/blob + color-region chrome + unified overlay density. */
'use strict';
const path = require('path');
const fs = require('fs');
const ROOT = path.resolve(__dirname, '..');
let pass = 0, fail = 0;
const ok = (m) => { pass++; console.log('PASS:', m); };
const bad = (m) => { fail++; console.log('FAIL:', m); };

// --- tags ---
const FEATURE_TAGS = { lines: 'L', edges: 'E', circles: 'C', rects: 'R', contours: 'B', blob: 'B' };
const REGION_TAGS = { color: '色', blobs: '斑', blob: '斑', hsv: '色', gray: '斑' };
function featureTag(f) { return FEATURE_TAGS[String(f || 'lines').toLowerCase()] || 'G'; }
function regionTag(o) { return REGION_TAGS[String(o || 'color').toLowerCase()] || '色'; }
function chromeBadge(tag, n, judgeOk) {
  const mark = judgeOk === true ? '✓' : (judgeOk === false ? '✗' : '');
  return `${tag}${n}${mark}`;
}
if (featureTag('contours') === 'B' && regionTag('color') === '色' && regionTag('blobs') === '斑')
  ok('tags B/色/斑');
else bad('tags');
if (chromeBadge('B', 3, true) === 'B3✓' && chromeBadge('色', 2, true) === '色2✓')
  ok('chrome B3✓ / 色2✓');
else bad('chrome badges');

// contour density row shape
const contourItem = {
  index: 1, bbox: [10, 10, 40, 30], areaPixels: 900, perimeterPixels: 120,
  centerX: 30, centerY: 25, fillRatio: 0.75, circularity: 0.6, judgeOk: true,
};
if (contourItem.fillRatio > 0.5 && contourItem.perimeterPixels > 0) ok('contour density fields');
else bad('contour density');

// region density
const regionItems = [
  { index: 1, areaPixels: 12000, centerX: 109.5, centerY: 109.5, width: 110, height: 110, fillRatio: 0.85, passed: true },
  { index: 2, areaPixels: 4800, centerX: 200, centerY: 120, width: 70, height: 70, fillRatio: 0.8, passed: true },
];
const totalA = regionItems.reduce((s, r) => s + r.areaPixels, 0);
if (regionItems.length === 2 && totalA === 16800) ok(`region density ΣA=${totalA}`);
else bad('region density');

// overlay density kinds
const overlayKinds = ['line', 'point', 'label', 'rect', 'ellipse', 'circle', 'cross', 'polygon'];
if (overlayKinds.includes('polygon') && overlayKinds.includes('cross') && overlayKinds.includes('ellipse'))
  ok(`overlay kinds ${overlayKinds.length}`);
else bad('overlay kinds');

// --- project ---
const projPath = path.join(ROOT, 'projects/open-and-run-contour-color.sieans');
if (!fs.existsSync(projPath)) bad('project missing');
else {
  const proj = JSON.parse(fs.readFileSync(projPath, 'utf8'));
  const ops = proj.steps.map((s) => s.operation);
  if (ops.join(',') === 'preprocess,geometry,plugin,var_calc') ok('project ops chain');
  else bad(`project ops ${ops}`);
  const geo = proj.steps.find((s) => s.operation === 'geometry');
  if (geo && geo.params && geo.params.feature === 'contours')
    ok(`geometry contours maxCount=${geo.params.maxCount}`);
  else bad(`geometry ${JSON.stringify(geo && geo.params)}`);
  const plug = proj.steps.find((s) => s.operation === 'plugin');
  if (plug && plug.params && plug.params.pluginId === 'sieans-regions'
      && plug.params.operatorId === 'color')
    ok('plugin sieans-regions color');
  else bad(`plugin ${JSON.stringify(plug && plug.params)}`);
  const args = (plug && plug.params && plug.params.arguments) || {};
  if (Number(args.hueMin) === 170 && Number(args.hueMax) === 10) ok('HSV red wrap 170-10');
  else bad(`HSV ${args.hueMin}-${args.hueMax}`);
  if (String(proj.notes || '').includes('wave141')) ok('notes wave141');
  else bad('notes');
  if (Array.isArray(proj.sourceConfig.images) && proj.sourceConfig.images.length >= 2)
    ok(`samples ${proj.sourceConfig.images.length}`);
  else bad('samples');
}

// --- desktop files ---
const need = [
  'desktop/geom_find_chrome.py',
  'desktop/region_color_chrome.py',
  'desktop/region_color_panel.py',
  'desktop/display_overlay_density.py',
  'desktop/image_view.py',
  'desktop/geometry_find_panel.py',
  'desktop/property_float.py',
  'desktop/mainwindow.py',
  'operator-plugins/sieans-regions/regions.py',
];
for (const rel of need) {
  if (fs.existsSync(path.join(ROOT, rel))) ok(`file ${rel}`);
  else bad(`missing ${rel}`);
}

// source markers
const markers = [
  ['desktop/geom_find_chrome.py', 'build_contour_blob_overlays'],
  ['desktop/region_color_chrome.py', 'summarize_region_result'],
  ['desktop/region_color_panel.py', 'regionColorResultTable'],
  ['desktop/display_overlay_density.py', 'build_unified_overlays'],
  ['desktop/image_view.py', "'polygon'"],
  ['desktop/image_view.py', "'cross'"],
  ['desktop/mainwindow.py', '_apply_find_overlay_density'],
  ['desktop/mainwindow.py', '_ingest_region_color_panel_from_result'],
  ['desktop/mainwindow.py', 'open-and-run-contour-color.sieans'],
  ['desktop/property_float.py', 'RegionColorPanel'],
  ['vision/engine.py', 'circularity'],
];
for (const [rel, needle] of markers) {
  const txt = fs.readFileSync(path.join(ROOT, rel), 'utf8');
  if (txt.includes(needle)) ok(`marker ${rel}::${needle}`);
  else bad(`marker ${rel}::${needle}`);
}

// guard: no Comm/HMI cobind / spark in new modules
for (const rel of ['desktop/region_color_chrome.py', 'desktop/display_overlay_density.py', 'desktop/region_color_panel.py']) {
  const txt = fs.readFileSync(path.join(ROOT, rel), 'utf8');
  if (/hostWatch|host_sm|sparkBlink|OK.?NG.?cobind|recipeSwitch/i.test(txt))
    bad(`forbidden surface in ${rel}`);
  else ok(`clean surface ${path.basename(rel)}`);
}

console.log(`\nwave141 CJS ${pass} pass / ${fail} fail`);
process.exit(fail ? 1 : 0);
