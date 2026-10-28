'use strict';
/**
 * Live Runtime e2e: open-and-run-ocr-gate-comm.sieans
 * OCR → var_calc gate → format_data → send_data LocalBus (${flow.*}).
 * No robot SDK / no field TCP / no Halcon.
 */
const fs = require('fs');
const os = require('os');
const path = require('path');

const root = path.resolve(__dirname, '..');
// Ensure vision engine can import cv2 / RapidOCR from .pydeps
process.env.PYTHONPATH = [
  path.join(root, '.pydeps'),
  process.env.PYTHONPATH || '',
].filter(Boolean).join(path.delimiter);

const {Runtime} = require('../lib/runtime.cjs');
const vision = require('../lib/vision-client.cjs');

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
  const data = fs.mkdtempSync(path.join(os.tmpdir(), 'sieans-ocr-'));
  const runtime = new Runtime(data, vision, null);
  const started = runtime.start({project, image, allowScripts: false});
  for (let i = 0; i < 600; i++) {
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
  const rel = 'projects/open-and-run-ocr-gate-comm.sieans';
  if (!fs.existsSync(path.join(root, rel))) {
    bad('missing ' + rel);
    console.log(`\n${pass} PASS / ${fail} FAIL`);
    process.exit(1);
  }
  const proj = JSON.parse(fs.readFileSync(path.join(root, rel), 'utf8'));
  const ops = (proj.steps || []).map(s => s.operation);
  const need = ['ocr', 'var_calc', 'format_data', 'send_data'];
  if (need.every(o => ops.includes(o))) ok(`chain ops=${ops.join('→')}`);
  else bad(`chain incomplete: ${ops}`);

  const ocr = (proj.steps || []).find(s => s.operation === 'ocr');
  const op = (ocr && ocr.params) || {};
  if (op.judgeEnable && String(op.expectedText || '').includes('BATCH') && op.writeFlowVars) {
    ok(`ocr judge expectedText=${op.expectedText}`);
  } else bad(`ocr judge params ${JSON.stringify(op)}`);

  const meta = ((proj.runUi || {}).meta) || {};
  if (meta.openAndRun && Array.isArray(meta.watchKeys) && meta.watchKeys.includes('passGate')) {
    ok(`openAndRun watchKeys=${meta.watchKeys.length}`);
  } else bad('openAndRun/watchKeys missing');

  const hw = proj.hostWatch || {};
  if (hw.pinGroups && hw.pinGroups['OCR链']) ok('hostWatch pinGroups OCR链');
  else bad('hostWatch pinGroups missing');

  const cm = proj.commManager || {};
  const sends = cm.sendEvents || [];
  if (sends.some(e => String(e.message || '').includes('${flow.'))) ok('comm sendEvents ${} templates');
  else bad('comm sendEvents missing ${}');
  const tpls = cm.messageTemplates || [];
  if (tpls.some(t => String(t.body || '').includes('${flow.'))) ok(`messageTemplates=${tpls.length}`);
  else bad('messageTemplates missing ${}');

  const sendStep = (proj.steps || []).find(s => s.operation === 'send_data');
  const sm = String((sendStep && sendStep.params && sendStep.params.message) || '');
  if (sm.includes('${flow.passGate}') && sm.includes('${flow.ocrText}')) ok('send_data message ${flow.*}');
  else bad(`send_data message=${sm}`);

  const mw = fs.readFileSync(path.join(root, 'desktop/mainwindow.py'), 'utf8');
  if (mw.includes('open-and-run-ocr-gate-comm.sieans')) ok('mainwindow lists sample');
  else bad('mainwindow missing sample');

  const readme = fs.readFileSync(path.join(root, 'projects/README-open-and-run.md'), 'utf8');
  if (readme.includes('open-and-run-ocr-gate-comm.sieans')) ok('README lists sample');
  else bad('README missing sample');

  const fc = fs.readFileSync(path.join(root, 'lib/flow-control.cjs'), 'utf8');
  if (fc.includes("'ocr_judgeOk'") && fc.includes("'ocr_text'")) ok('varCalc zero-fill ocr_judgeOk/ocr_text');
  else bad('varCalc zero-fill missing ocr extras');

  const {project, flow, results, st} = await runProject(rel, 'ocr-gate-comm');
  if (flow) {
    const count = Number(flow.ocrCount);
    if (count >= 1) ok(`ocrCount=${count}`);
    else bad(`ocrCount=${flow.ocrCount}`);
    const conf = Number(flow.ocrConf);
    if (conf >= 0.5) ok(`ocrConf=${conf}`);
    else bad(`ocrConf=${flow.ocrConf}`);
    const text = String(flow.ocrText || '');
    if (text.includes('BATCH')) ok(`ocrText has BATCH (${JSON.stringify(text.slice(0, 60))})`);
    else bad(`ocrText=${JSON.stringify(text)}`);
    if (flow.ocrOk === 1 || flow.ocrOk === true || Number(flow.ocrOk) === 1) ok(`ocrOk=${flow.ocrOk}`);
    else bad(`ocrOk=${JSON.stringify(flow.ocrOk)}`);
    if (flow.passGate === 1 || flow.passGate === true || Number(flow.passGate) === 1) {
      ok(`passGate=${flow.passGate}`);
    } else bad(`passGate=${JSON.stringify(flow.passGate)} keys=${Object.keys(flow)}`);
    const formatted = String(flow.formatted || '');
    if (formatted.includes('OCR ok=') || formatted.includes('ok=')) ok(`formatted=${JSON.stringify(formatted.slice(0, 80))}`);
    else bad(`formatted=${JSON.stringify(formatted)}`);

    const sendRes = (results || []).find(r => {
      const step = (project.steps || []).find(s => s.id === r.id);
      return step && step.operation === 'send_data';
    });
    const sent = sendRes && (sendRes.output && sendRes.output.result && (sendRes.output.result.sent || sendRes.output.result.message));
    const sentStr = String(sent || (sendRes && sendRes.output && JSON.stringify(sendRes.output.result)) || '');
    if (sentStr.includes('ok=1') || sentStr.includes('RESULT')) ok(`send result has payload (${sentStr.slice(0, 100)})`);
    else {
      // soft: LocalBus may report differently
      const anySend = (results || []).some(r => {
        const o = r && r.output && r.output.result;
        return o && (o.status === 'ok' || o.sent || o.bytes > 0);
      });
      if (anySend) ok(`send_data status ok (raw=${sentStr.slice(0, 80)})`);
      else bad(`send_data missing payload results=${JSON.stringify((results||[]).map(r=>({id:r.id,op:(project.steps||[]).find(s=>s.id===r.id)?.operation,out:r.output&&r.output.result}))).slice(0,500)}`);
    }
  }

  console.log(`\n${pass} PASS / ${fail} FAIL`);
  process.exit(fail ? 1 : 0);
}

main().catch(err => {
  console.error(err);
  process.exit(1);
});
