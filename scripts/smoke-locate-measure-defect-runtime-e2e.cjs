'use strict';
/**
 * Live Runtime e2e: open-and-run-locate-measure-defect.sieans
 * locate → pose_correct → measure → defects → var_calc gate.
 * No robot SDK / no push / no field hardware.
 */
const fs = require('fs');
const os = require('os');
const path = require('path');
const {Runtime} = require('../lib/runtime.cjs');
const vision = require('../lib/vision-client.cjs');

const root = path.resolve(__dirname, '..');
let pass = 0, fail = 0;
const ok = (m) => { pass++; console.log('PASS:', m); };
const bad = (m) => { fail++; console.log('FAIL:', m); };

function resolveImage(p) {
  if (!p) return null;
  if (path.isAbsolute(p) && fs.existsSync(p)) return p;
  const joined = path.join(root, p);
  if (fs.existsSync(joined)) return joined;
  return p;
}

function firstImageDataUrl(project) {
  const imgs = (project.sourceConfig && project.sourceConfig.images) || [];
  if (!imgs.length) throw new Error('no source images');
  const resolved = resolveImage(imgs[0]);
  if (!fs.existsSync(resolved)) throw new Error('missing image ' + imgs[0] + ' → ' + resolved);
  const buf = fs.readFileSync(resolved);
  const ext = path.extname(resolved).toLowerCase().replace('.', '') || 'png';
  const mime = ext === 'jpg' || ext === 'jpeg' ? 'jpeg' : 'png';
  return 'data:image/' + mime + ';base64,' + buf.toString('base64');
}

async function runProject(rel, label) {
  const project = JSON.parse(fs.readFileSync(path.join(root, rel), 'utf8'));
  const image = firstImageDataUrl(project);
  const data = fs.mkdtempSync(path.join(os.tmpdir(), 'sieans-lmd-'));
  const runtime = new Runtime(data, vision, null);
  const started = runtime.start({project, image, allowScripts: false});
  for (let i = 0; i < 500; i++) {
    await new Promise(r => setTimeout(r, 50));
    const st = runtime.poll(started.id);
    if (st.state !== 'running') {
      if (st.state !== 'completed') {
        bad(`${label} state=${st.state} err=${st.error || ''}`);
        return {project, flow: null, results: [], st};
      }
      const flow = (st.variables && st.variables.flow) || {};
      return {project, flow, results: st.results || [], st};
    }
  }
  bad(`${label} timeout`);
  return {project, flow: null, results: [], st: null};
}

async function main() {
  const rel = 'projects/open-and-run-locate-measure-defect.sieans';
  if (!fs.existsSync(path.join(root, rel))) {
    bad('missing ' + rel);
    console.log(`\n${pass} PASS / ${fail} FAIL`);
    process.exit(1);
  }
  const proj = JSON.parse(fs.readFileSync(path.join(root, rel), 'utf8'));
  const ops = (proj.steps || []).map(s => s.operation);
  const need = ['locate', 'pose_correct', 'measure', 'defects', 'var_calc'];
  if (need.every(o => ops.includes(o))) ok(`chain ops=${ops.join('→')}`);
  else bad(`chain incomplete: ${ops}`);

  const meta = ((proj.runUi || {}).meta) || {};
  if (meta.openAndRun && Array.isArray(meta.watchKeys) && meta.watchKeys.includes('passGate')) {
    ok(`openAndRun watchKeys=${meta.watchKeys.length}`);
  } else bad('openAndRun/watchKeys missing');

  const hw = proj.hostWatch || {};
  if (hw.pinGroups && hw.pinGroups['检测链']) ok('hostWatch pinGroups 检测链');
  else bad('hostWatch pinGroups missing');

  const cm = proj.commManager || {};
  const sends = cm.sendEvents || [];
  if (sends.some(e => String(e.message || '').includes('${flow.'))) ok('comm sendEvents ${} templates');
  else bad('comm sendEvents missing ${}');

  const mw = fs.readFileSync(path.join(root, 'desktop/mainwindow.py'), 'utf8');
  if (mw.includes('open-and-run-locate-measure-defect.sieans')) ok('mainwindow lists sample');
  else bad('mainwindow missing sample');

  const readme = fs.readFileSync(path.join(root, 'projects/README-open-and-run.md'), 'utf8');
  if (readme.includes('open-and-run-locate-measure-defect.sieans')) ok('README lists sample');
  else bad('README missing sample');

  const {project, flow, results, st} = await runProject(rel, 'locate-measure-defect');
  if (flow) {
    const score = Number(flow.matchScore);
    if (score >= 0.7) ok(`matchScore=${score}`);
    else bad(`matchScore=${flow.matchScore}`);
    const mc = Number(flow.measureCount);
    if (mc > 0) ok(`measureCount=${mc}`);
    else bad(`measureCount=${flow.measureCount}`);
    const dc = Number(flow.defectCount);
    if (Number.isFinite(dc)) ok(`defectCount=${dc}`);
    else bad(`defectCount=${flow.defectCount}`);
    if (flow.defectOk === 1 || flow.defectOk === true || Number(flow.defectOk) === 1) {
      ok(`defectOk=${flow.defectOk}`);
    } else bad(`defectOk=${JSON.stringify(flow.defectOk)}`);
    if (flow.passGate === 1 || flow.passGate === true || Number(flow.passGate) === 1) {
      ok(`passGate=${flow.passGate}`);
    } else bad(`passGate=${JSON.stringify(flow.passGate)} keys=${Object.keys(flow)}`);
  }

  console.log(`\n${pass} PASS / ${fail} FAIL`);
  process.exit(fail ? 1 : 0);
}

main().catch(err => {
  console.error(err);
  process.exit(1);
});
