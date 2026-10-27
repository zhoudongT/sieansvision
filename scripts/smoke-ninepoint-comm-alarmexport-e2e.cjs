'use strict';
/**
 * Ninepoint OK/NG + Comm multiproto (LocalBus/TCP/UDP) + Alarm history export structural.
 * Exit 0 on PASS. No robot SDK / no push.
 */
const fs = require('fs');
const os = require('os');
const path = require('path');
const {Runtime} = require('../lib/runtime.cjs');

const root = path.resolve(__dirname, '..');
let pass = 0, fail = 0;
const ok = (m) => { pass++; console.log('PASS:', m); };
const bad = (m) => { fail++; console.log('FAIL:', m); };

async function runProject(rel, label, opts = {}) {
  const project = JSON.parse(fs.readFileSync(path.join(root, rel), 'utf8'));
  const data = fs.mkdtempSync(path.join(os.tmpdir(), 'sieans-nca-'));
  try { require('../lib/comm-bus.cjs').reset(); } catch (_) {}
  const vision = {
    async run() { throw new Error('vision unused in this smoke'); },
  };
  const runtime = new Runtime(data, vision, null);
  const started = runtime.start({project, allowScripts: false, ...opts});
  for (let i = 0; i < 400; i++) {
    await new Promise(r => setTimeout(r, 40));
    const st = runtime.poll(started.id);
    if (st.state !== 'running') {
      const flow = (st.variables && st.variables.flow) || {};
      if (st.state !== 'completed') {
        bad(`${label} state=${st.state} err=${st.error || ''}`);
        return {flow: null, results: [], st};
      }
      return {flow, results: st.results || [], st};
    }
  }
  bad(`${label} timeout`);
  return {flow: null, results: [], st: null};
}

async function main() {
  // --- Structure: ninepoint sample ---
  const npPath = 'projects/open-and-run-ninepoint.sieans';
  const np = JSON.parse(fs.readFileSync(path.join(root, npPath), 'utf8'));
  const nops = (np.steps || []).map(s => s.operation);
  if (nops.includes('nine_point') && nops.includes('var_calc')) ok(`ninepoint ops=${nops.join('→')}`);
  else bad(`ninepoint ops incomplete: ${nops}`);
  const placements = ((np.runUi || {}).placements || []).map(p => p.name);
  if (placements.includes('OK/NG')) ok('ninepoint runUi has OK/NG');
  else bad(`ninepoint runUi missing OK/NG: ${placements}`);
  const pts = (((np.steps || []).find(s => s.operation === 'nine_point') || {}).params || {}).points || [];
  if (pts.length >= 9) ok(`ninepoint seeded points=${pts.length}`);
  else bad(`ninepoint points=${pts.length}`);

  // --- Run ninepoint ---
  const {flow: nf} = await runProject(npPath, 'ninepoint');
  if (nf) {
    const rms = Number(nf.calibRms);
    const count = Number(nf.calibPoints);
    const gate = nf.passGate;
    if (Number.isFinite(rms) && rms < 0.5) ok(`ninepoint calibRms=${rms}`);
    else bad(`ninepoint calibRms=${nf.calibRms}`);
    if (count >= 9) ok(`ninepoint calibPoints=${count}`);
    else bad(`ninepoint calibPoints=${nf.calibPoints}`);
    if (gate === 1 || gate === true) ok(`ninepoint passGate=${gate}`);
    else bad(`ninepoint passGate=${JSON.stringify(gate)} keys=${Object.keys(nf)}`);
  }

  // --- Structure: comm multiproto ---
  const cmPath = 'projects/open-and-run-comm-multiproto.sieans';
  if (!fs.existsSync(path.join(root, cmPath))) bad('missing open-and-run-comm-multiproto.sieans');
  else {
    const cm = JSON.parse(fs.readFileSync(path.join(root, cmPath), 'utf8'));
    const devices = ((cm.commManager || {}).devices || []).map(d => d.protocol);
    const need = ['Local Bus', 'TCP Client', 'UDP'];
    const missing = need.filter(p => !devices.some(d => String(d).includes(p.split(' ')[0])));
    if (!missing.length) ok(`comm devices protocols=${devices.join('|')}`);
    else bad(`comm missing protocols ${missing} have=${devices}`);
    const sends = (cm.steps || []).filter(s => s.operation === 'send_data').map(s => (s.params || {}).device);
    if (sends.includes('LocalLoop') && sends.includes('TcpClient') && sends.includes('UdpPeer')) {
      ok(`comm send devices=${sends.join(',')}`);
    } else bad(`comm send devices=${sends}`);
  }

  // --- Run LocalBus primary path (TCP/UDP side sends may use simulator) ---
  const {flow: cf} = await runProject(cmPath, 'comm-multiproto');
  if (cf) {
    if (cf.recvData) ok(`comm recvData=${cf.recvData}`);
    else bad(`comm recvData missing keys=${Object.keys(cf)}`);
    if (cf.passGate === 1 || cf.passGate === true) ok(`comm passGate=${cf.passGate}`);
    else bad(`comm passGate=${JSON.stringify(cf.passGate)}`);
    if (typeof cf.formatted === 'string' && cf.formatted.length) ok(`comm formatted=${cf.formatted}`);
    else bad(`comm formatted=${JSON.stringify(cf.formatted)}`);
  }

  // --- Alarm export structural (source contains buttons + methods) ---
  const hsm = fs.readFileSync(path.join(root, 'desktop/host_state_machine.py'), 'utf8');
  for (const needle of [
    'hostAlarmHistoryCopyBtn',
    'hostAlarmHistoryExportBtn',
    'def alarm_history_csv',
    'def export_alarm_history_clipboard',
    'def export_alarm_history_file',
  ]) {
    if (hsm.includes(needle)) ok(`alarm export has ${needle}`);
    else bad(`alarm export missing ${needle}`);
  }

  // --- README lists new samples ---
  const readme = fs.readFileSync(path.join(root, 'projects/README-open-and-run.md'), 'utf8');
  for (const f of ['open-and-run-ninepoint.sieans', 'open-and-run-comm-multiproto.sieans']) {
    if (readme.includes(f)) ok(`README lists ${f}`);
    else bad(`README missing ${f}`);
  }

  console.log('---');
  console.log(`${pass} PASS / ${fail} FAIL`);
  process.exit(fail ? 1 : 0);
}
main().catch(e => { console.error(e); process.exit(1); });
