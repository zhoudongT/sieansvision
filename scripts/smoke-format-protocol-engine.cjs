'use strict';
/**
 * Headless engine smoke: format-protocol RUN once → flow.recvData/formatted/passGate.
 * Also: no-send demoPayload variant; optional TCP RUN to live :19777.
 * Exit 0 on PASS. No robot SDK.
 */
const fs = require('fs');
const os = require('os');
const path = require('path');
const net = require('net');
const {Runtime} = require('../lib/runtime.cjs');

const root = path.resolve(__dirname, '..');
let pass = 0, fail = 0;
const ok = (m) => { pass++; console.log('PASS:', m); };
const bad = (m) => { fail++; console.log('FAIL:', m); };

async function runProject(rel, label) {
  const project = JSON.parse(fs.readFileSync(path.join(root, rel), 'utf8'));
  const data = fs.mkdtempSync(path.join(os.tmpdir(), 'sieans-fmt-'));
  const runtime = new Runtime(data, {async run() { throw new Error('vision unused'); }}, null);
  // Reset LocalBus between runs
  try { require('../lib/comm-bus.cjs').reset(); } catch (_) {}
  const started = runtime.start({project, allowScripts: false});
  for (let i = 0; i < 200; i++) {
    await new Promise(r => setTimeout(r, 25));
    const st = runtime.poll(started.id);
    if (st.state !== 'running') {
      const flow = (st.variables && st.variables.flow) || {};
      if (st.state !== 'completed') {
        bad(`${label} state=${st.state} err=${st.error || ''}`);
        return null;
      }
      return flow;
    }
  }
  bad(`${label} timeout`);
  return null;
}

async function main() {
  // 1) Full chain with send→recv
  const flow = await runProject('projects/open-and-run-format-protocol.sieans', 'full-send');
  if (flow) {
    if (flow.recvData === 'OK,12.5,PASS') ok(`full recvData=${flow.recvData}`);
    else bad(`full recvData=${JSON.stringify(flow.recvData)}`);
    if (typeof flow.formatted === 'string' && flow.formatted.includes('OK') && flow.formatted.includes('12.5')) {
      ok(`full formatted=${flow.formatted}`);
    } else {
      bad(`full formatted=${JSON.stringify(flow.formatted)}`);
    }
    if (flow.passGate === 1 || flow.passGate === true) ok(`full passGate=${flow.passGate}`);
    else bad(`full passGate=${JSON.stringify(flow.passGate)}`);
    if (flow.parsed_status === 'OK' || flow.status === 'OK') {
      ok(`full parsed fields status=${flow.parsed_status || flow.status}`);
    } else {
      bad(`full missing parsed status keys=${Object.keys(flow)}`);
    }
  }

  // 2) No-send demoPayload inject
  const demo = await runProject('projects/open-and-run-format-protocol-demo.sieans', 'demoPayload');
  if (demo) {
    if (demo.recvData === 'OK,12.5,PASS') ok(`demo recvData=${demo.recvData}`);
    else bad(`demo recvData=${JSON.stringify(demo.recvData)}`);
    if (typeof demo.formatted === 'string' && demo.formatted.includes('OK')) {
      ok(`demo formatted=${demo.formatted}`);
    } else {
      bad(`demo formatted=${JSON.stringify(demo.formatted)}`);
    }
    if (demo.passGate === 1 || demo.passGate === true) ok(`demo passGate=${demo.passGate}`);
    else bad(`demo passGate=${JSON.stringify(demo.passGate)}`);
  }

  // 3) Optional TCP TriggerListen RUN on live App :19777
  await new Promise((resolve) => {
    const sock = net.connect({host: '127.0.0.1', port: 19777}, () => {
      sock.write('RUN\n');
      setTimeout(() => {
        try { sock.end(); } catch (_) {}
        ok('TCP TriggerListen :19777 accepted RUN');
        resolve();
      }, 200);
    });
    sock.setTimeout(1500);
    sock.on('timeout', () => {
      try { sock.destroy(); } catch (_) {}
      bad('TCP :19777 timeout (App listen?)');
      resolve();
    });
    sock.on('error', (e) => {
      // optional — report but do not fail whole smoke if App down
      console.log('SKIP: TCP :19777', e.message);
      resolve();
    });
  });

  console.log('---');
  console.log(`${pass} PASS / ${fail} FAIL`);
  process.exit(fail ? 1 : 0);
}

main().catch((e) => { console.error(e); process.exit(1); });
