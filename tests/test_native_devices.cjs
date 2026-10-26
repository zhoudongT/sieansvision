'use strict';
// Real stdio host + synthetic camera and temporary datasets. Never trains a model.
const {test} = require('node:test');
const assert = require('node:assert/strict');
const {spawn} = require('node:child_process');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const readline = require('node:readline');
const crypto = require('node:crypto');
const {setTimeout:wait} = require('node:timers/promises');
const root = path.resolve(__dirname, '..');

async function launch(t, prepare=()=>{}) {
  const data = fs.mkdtempSync(path.join(os.tmpdir(), 'native-devices-'));
  const models = path.join(data, 'models'); fs.mkdirSync(models);
  prepare(data, models);
  const child = spawn(process.execPath, [path.join(root, 'desktop/engine-host.cjs'), '--data', data], {
    cwd: root, windowsHide: true, env: {...process.env, VISION_MODEL_DIR: models, ADMIN_PASSWORD_HASH: ''},
  });
  let logs = '', seq = 0, readyResolve, readyReject;
  const ready = new Promise((resolve, reject) => { readyResolve = resolve; readyReject = reject; });
  const pending = new Map();
  child.stderr.on('data', b => { logs += b; });
  readline.createInterface({input: child.stdout}).on('line', line => {
    const message = JSON.parse(line);
    if (message.event === 'ready') return readyResolve(message.data);
    const entry = pending.get(message.id);
    if (!entry) return;
    pending.delete(message.id); clearTimeout(entry.timer);
    if (message.error) entry.reject(Error(message.error)); else entry.resolve(message.result);
  });
  const closed = new Promise(resolve => child.once('close', code => {
    readyReject(Error(logs || 'engine closed'));
    for (const p of pending.values()) { clearTimeout(p.timer); p.reject(Error(logs || 'engine closed')); }
    pending.clear(); resolve(code);
  }));
  function call(method, params={}) {
    const id = String(++seq);
    const promise = new Promise((resolve, reject) => {
      const timer = setTimeout(() => {pending.delete(id); reject(Error(method + ' timeout: ' + logs));}, 20000);
      pending.set(id, {resolve, reject, timer});
      child.stdin.write(JSON.stringify({id, method, params}) + '\n');
    });
    promise.requestId = id;
    return promise;
  }
  t.after(async () => {
    if (child.exitCode === null && child.signalCode === null) {
      try { await call('shutdown'); } catch { child.kill(); }
    }
    await closed;
    fs.rmSync(data, {recursive: true, force: true});
  });
  const startup = setTimeout(() => readyReject(Error('startup timeout: ' + logs)), 10000);
  try { await ready; } finally { clearTimeout(startup); }
  return {call, child, closed, data};
}

test('camera RPC enumerates only simulator; persistent session supports frames, cancellation and release', {timeout: 40000}, async t => {
  const host = await launch(t);
  const params = {driver: 'simulator', deviceId: 'synthetic-parts', timeoutMs: 1000};
  const listed = await host.call('camera/list', {driver: 'simulator'});
  assert.equal(listed.result.items[0].deviceId, 'synthetic-parts');
  const inspected = await host.call('camera/inspect', params);
  assert.ok(inspected.result.items.length);
  const captured = await host.call('camera/capture', params);
  assert.match(captured.annotatedImage, /^data:image\//);
  assert.equal(captured.result.simulated, true);
  let state = await host.call('camera/session/start', {params, intervalMs: 1000, autoStart: true});
  assert.equal(state.config.autoStart, false);
  for (let i=0; i<100 && (!state.buffered || state.state!=='running'); i++) {
    await wait(50); state = await host.call('camera/session/status');
  }
  assert.equal(state.state, 'running');
  assert.ok(state.buffered);
  const frame = await host.call('camera/capture', {driver:'session', sessionId:state.bindingId, framePolicy:'latest', maxAgeMs:5000});
  assert.ok(frame.result.frameSequence > 0);
  const workers = (await host.call('status')).workerPids;
  assert.ok(workers.length > 0);
  const next = host.call('camera/capture', {driver:'session', sessionId:state.id, framePolicy:'next', timeoutMs:5000});
  const cancelled = assert.rejects(next, /取消/);
  assert.equal((await host.call('camera/cancel', {requestId:next.requestId})).cancelled, true);
  await cancelled;
  assert.equal((await host.call('camera/session/status')).active, true);
  await host.call('shutdown');
  assert.equal(await host.closed, 0);
  for (const pid of workers) assert.throws(() => process.kill(pid, 0), /ESRCH/);
});

test('training RPC creates and checks synthetic dataset, revision-saves annotations and installs completed artifact', {timeout: 40000}, async t => {
  const host = await launch(t, data => {
    const directory = path.join(data,'training'), jobDir = path.join(directory,'jobs','fixture-job');
    fs.mkdirSync(jobDir, {recursive:true});
    const checkpoint = path.join(jobDir,'best.pt'), bytes = Buffer.from('synthetic checkpoint, never executed');
    fs.writeFileSync(checkpoint, bytes);
    fs.writeFileSync(path.join(directory,'latest.json'), JSON.stringify({id:'fixture-job', state:'completed', checkpoint, sha256:crypto.createHash('sha256').update(bytes).digest('hex'), task:'detect', config:{epochs:1}, metrics:[], epoch:1}));
  });
  assert.equal((await host.call('training/status')).busy, false);
  await assert.rejects(host.call('training/datasets/create', {id:'../escape',task:'detect',names:['part']}), /有效数据集/);
  const dataset = await host.call('training/datasets/create', {id:'demo-parts',task:'detect',names:['part'],demo:true});
  assert.ok(dataset.folder.startsWith(host.data));
  const checked = await host.call('training/datasets/check', {datasetId:dataset.id});
  assert.equal(checked.summary.splits.train.images, 12);
  const annotation = (action,body={}) => host.call('training/annotations', {datasetId:dataset.id,action,body});
  const listed = await annotation('list'); assert.equal(listed.items.length, 16);
  const loaded = await annotation('load', {name:'part-0.png',split:'train'});
  assert.equal(loaded.records.length, 1);
  loaded.records[0].box[0] += .001;
  const saved = await annotation('save', {name:loaded.name,split:loaded.split,revision:loaded.revision,records:loaded.records});
  assert.notEqual(saved.revision, loaded.revision);
  await assert.rejects(annotation('save', {name:loaded.name,split:loaded.split,revision:loaded.revision,records:[]}), /其他页面修改/);
  const history = await annotation('history', {name:loaded.name,split:loaded.split,revision:saved.revision});
  assert.equal(history.entries.length, 1);
  assert.equal((await host.call('training/publish', {id:'fixture-job',name:'trained-fixture.pt'})).name, 'trained-fixture.pt');
  assert.deepEqual((await host.call('models/list')).models, ['trained-fixture.pt']);
  await assert.rejects(host.call('training/publish', {id:'fixture-job',name:'trained-fixture.pt'}), /EEXIST/);
  assert.equal((await host.call('status')).state, 'idle');
});

test('continuous RPC runs a bounded synthetic project and global stop wakes a waiting session', {timeout: 15000}, async t => {
  const host = await launch(t);
  const project = {version:1,id:'native-continuous',name:'持续检测测试',steps:[{id:'count',operation:'variables',params:{scope:'flow',name:'count',mode:'increment',value:1}}]};
  let state = await host.call('continuous/start', {project,intervalMs:100,maxCycles:2});
  for (let i=0; i<80 && state.busy; i++) { await wait(50); state = await host.call('continuous/status'); }
  assert.equal(state.state, 'completed');
  assert.equal(state.completedCycles, 2);
  assert.equal((await host.call('variables/get',{project})).flow.count, 2);
  state = await host.call('continuous/start', {project,intervalMs:60000,maxCycles:0});
  for (let i=0; i<80 && state.state!=='waiting'; i++) { await wait(20); state = await host.call('continuous/status'); }
  assert.equal(state.state, 'waiting');
  const started = Date.now();
  await host.call('stop');
  assert.equal((await host.call('continuous/status')).state, 'stopped');
  assert.ok(Date.now()-started < 2000);
});

test('MQTT RPC uses an explicitly started loopback simulator and shuts down its listener', {timeout: 15000}, async t => {
  const host = await launch(t);
  const project = {version:1,id:'native-mqtt',name:'模拟事件测试',steps:[{id:'count',operation:'variables',params:{scope:'flow',name:'count',mode:'increment',value:1}}]};
  assert.equal((await host.call('mqtt/status')).state, 'idle');
  await assert.rejects(host.call('mqtt/test'), /本机模拟订阅/);
  let state = await host.call('mqtt/start', {project,connection:{connection:'simulator',topic:'native/test',encoding:'structured',acceptRetained:false},keyField:'requestId'});
  for (let i=0; i<100 && state.state!=='subscribed'; i++) { await wait(30); state = await host.call('mqtt/status'); }
  assert.equal(state.state, 'subscribed', state.error);
  await host.call('mqtt/test');
  for (let i=0; i<100 && !state.completed; i++) { await wait(30); state = await host.call('mqtt/status'); }
  assert.equal(state.completed, 1);
  assert.equal((await host.call('variables/get',{project})).flow.count, 1);
  await host.call('shutdown');
  assert.equal(await host.closed, 0);
});
