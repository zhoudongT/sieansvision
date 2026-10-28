'use strict';
/**
 * Open-and-use smoke: default-platform.sieans with relative sample paths.
 * Runs preprocess→geometry(circles)→measure→var_calc; expects passGate=1.
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
  if (fs.existsSync(p)) return p;
  const cand = path.join(root, p);
  if (fs.existsSync(cand)) return cand;
  throw new Error('missing image ' + p);
}

async function main() {
  const rel = 'projects/default-platform.sieans';
  const project = JSON.parse(fs.readFileSync(path.join(root, rel), 'utf8'));
  const imgs = (project.sourceConfig && project.sourceConfig.images) || [];
  if (!imgs.length) { bad('no images'); process.exit(1); }
  const allRel = imgs.every(i => !path.isAbsolute(i) || String(i).includes('public/vision/samples/'));
  if (imgs.every(i => !path.isAbsolute(i))) ok('source images are repo-relative');
  else if (allRel) ok('source images under samples (abs or rel)');
  else bad('images not portable: ' + JSON.stringify(imgs));

  const meta = ((project.runUi || {}).meta) || {};
  if (meta.openAndRun) ok('runUi.meta.openAndRun=true');
  else bad('openAndRun flag missing');

  const imgPath = resolveImage(imgs[0]);
  const buf = fs.readFileSync(imgPath);
  const image = 'data:image/png;base64,' + buf.toString('base64');
  const data = fs.mkdtempSync(path.join(os.tmpdir(), 'sieans-defplat-'));
  const runtime = new Runtime(data, vision, null);
  const started = runtime.start({project, image, allowScripts: false});
  let st = null;
  for (let i = 0; i < 400; i++) {
    await new Promise(r => setTimeout(r, 50));
    st = runtime.poll(started.id);
    if (st.state !== 'running') break;
  }
  if (!st || st.state !== 'completed') {
    bad('run state=' + (st && st.state) + ' err=' + (st && st.error));
  } else {
    ok('default-platform run completed');
  }
  const flow = (st && st.variables && st.variables.flow) || {};
  if (Number(flow.circleCount) > 0) ok('circleCount=' + flow.circleCount);
  else bad('circleCount expected >0 got ' + flow.circleCount);
  if (Number(flow.passGate) === 1) ok('passGate=1');
  else bad('passGate expected 1 got ' + flow.passGate);
  if (Number(flow.firstRadius) > 0) ok('firstRadius=' + flow.firstRadius);
  else bad('firstRadius missing');

  console.log(`\n${pass} PASS / ${fail} FAIL`);
  process.exit(fail ? 1 : 0);
}

main().catch(e => { console.error(e); process.exit(1); });
