'use strict';
/**
 * Live Runtime e2e: open-and-run-caliper-measure.sieans
 * caliper → line_intersect → point_line_distance → var_calc gate.
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

function firstImageDataUrl(project) {
  const imgs = (project.sourceConfig && project.sourceConfig.images) || [];
  if (!imgs.length) throw new Error('no source images');
  const p = imgs[0];
  if (!fs.existsSync(p)) throw new Error('missing image ' + p);
  const buf = fs.readFileSync(p);
  const ext = path.extname(p).toLowerCase().replace('.', '') || 'png';
  const mime = ext === 'jpg' || ext === 'jpeg' ? 'jpeg' : 'png';
  return 'data:image/' + mime + ';base64,' + buf.toString('base64');
}

async function runProject(rel, label) {
  const project = JSON.parse(fs.readFileSync(path.join(root, rel), 'utf8'));
  const image = firstImageDataUrl(project);
  const data = fs.mkdtempSync(path.join(os.tmpdir(), 'sieans-cm-'));
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

function stepOut(project, results, op) {
  for (const r of results || []) {
    const step = (project.steps || []).find(s => s.id === r.id);
    if (step && step.operation === op) {
      return (r.output && r.output.result) || r.result || null;
    }
  }
  return null;
}

async function main() {
  const rel = 'projects/open-and-run-caliper-measure.sieans';
  if (!fs.existsSync(path.join(root, rel))) {
    bad('missing ' + rel);
    console.log(`\nFAIL ${fail}`);
    process.exit(1);
  }
  const proj = JSON.parse(fs.readFileSync(path.join(root, rel), 'utf8'));
  const ops = (proj.steps || []).map(s => s.operation);
  const need = ['preprocess', 'geometry', 'line_intersect', 'point_line_distance', 'var_calc'];
  if (need.every(o => ops.includes(o))) ok(`chain ops=${ops.join('→')}`);
  else bad(`chain incomplete: ${ops}`);

  const geo = (proj.steps || []).find(s => s.operation === 'geometry');
  if (geo && geo.params && geo.params.findMethod === 'caliper') ok('geometry findMethod=caliper');
  else bad('geometry not caliper');

  const li = (proj.steps || []).find(s => s.operation === 'line_intersect');
  const lip = (li && li.params) || {};
  if (lip.mode === 'bind' && lip.line1Field === 'lines[0]' && lip.line2Field === 'lines[1]') {
    ok(`line_intersect bind ${lip.line1Field}×${lip.line2Field}`);
  } else bad(`line_intersect bind weak: ${JSON.stringify(lip)}`);

  const pld = (proj.steps || []).find(s => s.operation === 'point_line_distance');
  const pp = (pld && pld.params) || {};
  if (pp.mode === 'bind' && pp.pointFrom === li.id && pp.lineField === 'lines[2]') {
    ok(`point_line_distance bind intersect→${pp.lineField}`);
  } else bad(`pld bind weak: ${JSON.stringify(pp)}`);

  const mw = fs.readFileSync(path.join(root, 'desktop/mainwindow.py'), 'utf8');
  if (mw.includes('open-and-run-caliper-measure.sieans')) ok('menu/open_example lists caliper-measure');
  else bad('mainwindow missing caliper-measure');

  const readme = fs.readFileSync(path.join(root, 'projects/README-open-and-run.md'), 'utf8');
  if (readme.includes('open-and-run-caliper-measure.sieans')) ok('README lists caliper-measure');
  else bad('README missing caliper-measure');

  const fc = fs.readFileSync(path.join(root, 'lib/flow-control.cjs'), 'utf8');
  if (fc.includes("bag.intersectX") && fc.includes("bag.distance") && fc.includes("'intersectX' in obj")) {
    ok('flow-control inject+pickPoint intersect/distance');
  } else bad('flow-control missing inject/pickPoint harden');

  const {project, flow, results, st} = await runProject(rel, 'caliper-measure');
  if (flow) {
    if (flow.passGate === 1 || flow.passGate === true) ok(`passGate=${flow.passGate}`);
    else bad(`passGate=${JSON.stringify(flow.passGate)} keys=${Object.keys(flow)}`);
    const lc = Number(flow.lineCount);
    if (lc >= 2) ok(`lineCount=${lc}`);
    else bad(`lineCount=${flow.lineCount}`);
    if (flow.intersectX != null && Number.isFinite(Number(flow.intersectX))) {
      ok(`intersectX=${flow.intersectX} intersectY=${flow.intersectY}`);
    } else bad(`intersect missing: X=${flow.intersectX} Y=${flow.intersectY}`);
    if (flow.pldDist != null && Number.isFinite(Number(flow.pldDist))) {
      ok(`pldDist=${flow.pldDist}`);
    } else bad(`pldDist missing: ${flow.pldDist}`);

    const g = stepOut(project, results, 'geometry');
    if (g && Array.isArray(g.lines) && g.lines.length >= 2) ok(`geometry lines=${g.lines.length}`);
    else bad(`geometry lines weak: ${g && g.lines && g.lines.length}`);

    const lir = stepOut(project, results, 'line_intersect');
    if (lir && lir.status === 'ok' && lir.intersectX != null) ok(`li status=${lir.status} x=${lir.intersectX}`);
    else bad(`li result weak: ${JSON.stringify(lir)}`);

    const pldr = stepOut(project, results, 'point_line_distance');
    if (pldr && pldr.status === 'ok' && Number.isFinite(Number(pldr.distance))) {
      ok(`pld status=${pldr.status} dist=${pldr.distance}`);
    } else bad(`pld result weak: ${JSON.stringify(pldr)}`);
  }

  console.log(`\n${fail ? 'FAIL' : 'PASS'} ${pass} ok / ${fail} fail`);
  process.exit(fail ? 1 : 0);
}

main().catch(e => { console.error(e); process.exit(1); });
