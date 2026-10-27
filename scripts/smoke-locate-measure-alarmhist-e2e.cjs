'use strict';
/**
 * Locate path depth + measure open-and-run + pose bind.
 * Runs projects with real vision client. Exit 0 on PASS. No robot SDK / no push.
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
  const data = fs.mkdtempSync(path.join(os.tmpdir(), 'sieans-loc-'));
  const runtime = new Runtime(data, vision, null);
  const started = runtime.start({project, image, allowScripts: false});
  for (let i = 0; i < 400; i++) {
    await new Promise(r => setTimeout(r, 50));
    const st = runtime.poll(started.id);
    if (st.state !== 'running') {
      if (st.state !== 'completed') {
        bad(`${label} state=${st.state} err=${st.error || ''}`);
        return {flow: null, results: [], st};
      }
      const flow = (st.variables && st.variables.flow) || {};
      return {flow, results: st.results || [], st};
    }
  }
  bad(`${label} timeout`);
  return {flow: null, results: [], st: null};
}

async function main() {
  // Structure checks (no vision)
  const locPath = 'projects/open-and-run-locate.sieans';
  const loc = JSON.parse(fs.readFileSync(path.join(root, locPath), 'utf8'));
  const ops = (loc.steps || []).map(s => s.operation);
  if (ops.includes('locate') && ops.includes('pose_correct') && ops.includes('var_calc')) {
    ok(`locate chain ops=${ops.join('→')}`);
  } else bad(`locate chain incomplete: ${ops}`);
  const placements = ((loc.runUi || {}).placements || []).map(p => p.name);
  if (placements.includes('OK/NG')) ok('locate runUi has OK/NG');
  else bad(`locate runUi missing OK/NG: ${placements}`);

  const meaPath = 'projects/open-and-run-measure.sieans';
  if (!fs.existsSync(path.join(root, meaPath))) bad('missing open-and-run-measure.sieans');
  else {
    const mea = JSON.parse(fs.readFileSync(path.join(root, meaPath), 'utf8'));
    const mops = (mea.steps || []).map(s => s.operation);
    if (mops.includes('measure') && mops.includes('var_calc')) ok(`measure chain ops=${mops.join('→')}`);
    else bad(`measure chain incomplete: ${mops}`);
  }

  const readme = fs.readFileSync(path.join(root, 'projects/README-open-and-run.md'), 'utf8');
  const samples = fs.readdirSync(path.join(root, 'projects'))
    .filter(f => f.startsWith('open-and-run') && f.endsWith('.sieans'));
  let missing = [];
  for (const f of samples) {
    if (!readme.includes(f)) missing.push(f);
  }
  if (!missing.length) ok(`README lists all ${samples.length} open-and-run samples`);
  else bad(`README missing: ${missing.join(', ')}`);

  // Live runs
  const {flow: locFlow, results: locRes} = await runProject(locPath, 'locate');
  if (locFlow) {
    if (locFlow.passGate === 1 || locFlow.passGate === true) ok(`locate passGate=${locFlow.passGate}`);
    else bad(`locate passGate=${JSON.stringify(locFlow.passGate)} keys=${Object.keys(locFlow)}`);
    if (Number(locFlow.matchScore) > 0.5) ok(`locate matchScore=${locFlow.matchScore}`);
    else bad(`locate matchScore=${locFlow.matchScore}`);
    const pose = (locRes || []).find(r => r && !r.skipped && r.id && (loc.steps.find(s => s.id === r.id) || {}).operation === 'pose_correct');
    // results may nest output.result
    let poseOut = null;
    for (const r of locRes || []) {
      const step = (loc.steps || []).find(s => s.id === r.id);
      if (step && step.operation === 'pose_correct') {
        poseOut = (r.output && r.output.result) || r.result || null;
      }
    }
    if (poseOut && poseOut.boundOk) ok(`pose boundOk fixture=(${poseOut.fixtureX?.toFixed?.(1)},${poseOut.fixtureY?.toFixed?.(1)})`);
    else bad(`pose bind failed: ${JSON.stringify(poseOut)}`);
  }

  const {flow: meaFlow} = await runProject(meaPath, 'measure');
  if (meaFlow) {
    if (meaFlow.passGate === 1 || meaFlow.passGate === true) ok(`measure passGate=${meaFlow.passGate}`);
    else bad(`measure passGate=${JSON.stringify(meaFlow.passGate)} keys=${Object.keys(meaFlow)}`);
    if (Number(meaFlow.circleCount) > 0) ok(`measure circleCount=${meaFlow.circleCount}`);
    else bad(`measure circleCount=${meaFlow.circleCount}`);
  }

  try { vision.stop && vision.stop(); } catch (_) {}
  console.log(fail ? `\nFAIL ${fail} (pass ${pass})` : `\nALL PASS (${pass})`);
  process.exit(fail ? 1 : 0);
}

main().catch(e => { console.error(e); process.exit(1); });
