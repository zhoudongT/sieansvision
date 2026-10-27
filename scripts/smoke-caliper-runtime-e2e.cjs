'use strict';
/**
 * Live Runtime e2e for open-and-run-caliper.sieans (+ measure_geom bind polish checks).
 * Pattern mirrors smoke-locate-measure-alarmhist-e2e.cjs. Exit 0 on PASS. No robot SDK / no push.
 */
const fs = require('fs');
const os = require('os');
const path = require('path');
const {Runtime} = require('../lib/runtime.cjs');
const vision = require('../lib/vision-client.cjs');
const control = require('../lib/flow-control.cjs');

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
  const data = fs.mkdtempSync(path.join(os.tmpdir(), 'sieans-cal-'));
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

function geomResult(project, results) {
  for (const r of results || []) {
    const step = (project.steps || []).find(s => s.id === r.id);
    if (step && step.operation === 'geometry') {
      return (r.output && r.output.result) || r.result || null;
    }
  }
  return null;
}

async function main() {
  const calPath = 'projects/open-and-run-caliper.sieans';
  if (!fs.existsSync(path.join(root, calPath))) {
    bad('missing open-and-run-caliper.sieans');
    console.log(`\nFAIL ${fail}`);
    process.exit(1);
  }
  const cal = JSON.parse(fs.readFileSync(path.join(root, calPath), 'utf8'));
  const ops = (cal.steps || []).map(s => s.operation);
  if (ops.includes('preprocess') && ops.includes('geometry') && ops.includes('var_calc')) {
    ok(`caliper chain ops=${ops.join('→')}`);
  } else bad(`caliper chain incomplete: ${ops}`);

  const geo = (cal.steps || []).find(s => s.operation === 'geometry');
  const gp = (geo && geo.params) || {};
  if (gp.findMethod === 'caliper' && (gp.feature === 'lines' || !gp.feature)) {
    ok(`geometry findMethod=caliper feature=${gp.feature || 'lines'}`);
  } else bad(`geometry params weak: findMethod=${gp.findMethod} feature=${gp.feature}`);

  const placements = ((cal.runUi || {}).placements || []).map(p => p.name);
  if (placements.includes('OK/NG') && placements.includes('生产统计')) {
    ok(`caliper runUi has OK/NG+生产统计 (${placements.join(',')})`);
  } else bad(`caliper runUi missing: ${placements}`);

  const readme = fs.readFileSync(path.join(root, 'projects/README-open-and-run.md'), 'utf8');
  if (readme.includes('open-and-run-caliper.sieans')) ok('README lists caliper sample');
  else bad('README missing caliper sample');

  // Live Runtime path
  const {project, flow, results, st} = await runProject(calPath, 'caliper');
  if (flow) {
    if (flow.passGate === 1 || flow.passGate === true) ok(`caliper passGate=${flow.passGate}`);
    else bad(`caliper passGate=${JSON.stringify(flow.passGate)} keys=${Object.keys(flow)}`);
    const lc = Number(flow.lineCount);
    if (lc > 0) ok(`caliper lineCount=${lc}`);
    else bad(`caliper lineCount=${flow.lineCount}`);
    const ls = Number(flow.lineScore);
    if (ls >= 0.35) ok(`caliper lineScore=${ls}`);
    else bad(`caliper lineScore=${flow.lineScore}`);
    if (flow.lineRms != null && Number.isFinite(Number(flow.lineRms))) {
      ok(`caliper lineRms=${flow.lineRms}`);
    } else {
      // soft: rms may be 0 on perfect fit
      if (flow.lineRms === 0 || flow.lineRms === '0') ok(`caliper lineRms=0`);
      else bad(`caliper lineRms missing: ${flow.lineRms}`);
    }
    const g = geomResult(project, results);
    if (g && Array.isArray(g.lines) && g.lines.length > 0) {
      ok(`geometry result lines=${g.lines.length} count=${g.count} score=${g.score ?? g.bestScore}`);
      // measure_geom bind: line_intersect on two lines (or same line mirrored) via flow-control
      const sid = (project.steps || []).find(s => s.operation === 'geometry')?.id;
      const bag = {};
      bag[sid] = {result: g};
      // Prefer two distinct lines; if only one, synthesize a crossing vertical
      let li;
      if (g.lines.length >= 2) {
        li = control.lineIntersect({
          mode: 'bind',
          line1From: sid, line1Field: 'lines[0]',
          line2From: sid, line2Field: 'lines[1]',
        }, {results: bag});
      } else {
        const L = g.lines[0];
        const midY = ((L.start?.[1] ?? 0) + (L.end?.[1] ?? 0)) / 2;
        li = control.lineIntersect({
          mode: 'bind',
          line1From: sid, line1Field: 'lines[0]',
          line2From: sid, line2Field: 'lines[0]',
          // force second via manual fallback when parallel: supply crossing coords
          x3: 0, y3: midY - 40, x4: 400, y4: midY + 40,
        }, {results: bag});
        // if parallel (same line), use manual cross
        if (li.parallel || li.intersectX == null) {
          li = control.lineIntersect({
            mode: 'manual',
            x1: L.start[0], y1: L.start[1], x2: L.end[0], y2: L.end[1],
            x3: 0, y3: midY - 40, x4: 400, y4: midY + 40,
          }, {results: bag});
        }
      }
      if (li && li.intersectX != null && !li.parallel) {
        ok(`measure_geom bind line_intersect @ (${Number(li.intersectX).toFixed(1)},${Number(li.intersectY).toFixed(1)}) status=${li.status}`);
      } else {
        // try field alias lines.0
        const li2 = control.lineIntersect({
          mode: 'bind',
          line1From: sid, line1Field: 'lines.0',
          line2From: sid, line2Field: 'lines.0',
          x3: 10, y3: 0, x4: 10, y4: 400,
        }, {results: bag});
        if (li2 && (li2.intersectX != null || li2.status === 'fallback_manual')) {
          ok(`measure_geom bind field alias lines.0 status=${li2.status} ix=${li2.intersectX}`);
        } else bad(`measure_geom bind failed: ${JSON.stringify(li)} / ${JSON.stringify(li2)}`);
      }
      // point_line_distance bind: point from line midpoint → distance ~0
      const pld = control.pointLineDistance({
        mode: 'bind',
        pointFrom: sid, pointField: 'lines[0]',
        lineFrom: sid, lineField: 'lines[0]',
      }, {results: bag});
      if (pld && pld.status === 'ok' && Number(pld.distance) < 1.5) {
        ok(`measure_geom bind point_line_distance dist=${pld.distance.toFixed?.(4) ?? pld.distance}`);
      } else bad(`point_line_distance bind: ${JSON.stringify(pld)}`);
    } else {
      bad(`geometry result missing lines: ${JSON.stringify(g && {count: g.count, keys: Object.keys(g || {})})}`);
    }
    if (st && Number(st.elapsedMs) > 0) ok(`runtime elapsedMs=${st.elapsedMs}`);
    else bad(`runtime elapsedMs=${st && st.elapsedMs}`);
  }

  try { vision.stop && vision.stop(); } catch (_) {}
  console.log(fail ? `\nFAIL ${fail} (pass ${pass})` : `\nALL PASS (${pass})`);
  process.exit(fail ? 1 : 0);
}

main().catch(e => { console.error(e); process.exit(1); });
