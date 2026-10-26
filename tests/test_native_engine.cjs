'use strict';
const {test} = require('node:test');
const assert = require('node:assert/strict');
const {spawn} = require('node:child_process');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const readline = require('node:readline');
const {setTimeout:wait} = require('node:timers/promises');
const root = path.resolve(__dirname, '..');

function fixture() {
  const width = 160, height = 100, pixels = Buffer.alloc(width * height * 3);
  for (let y = 0; y < height; y++) for (let x = 0; x < width; x++) {
    if ((x > 15 && x < 55 && y > 15 && y < 65) || (x - 110) ** 2 + (y - 50) ** 2 < 20 ** 2) {
      pixels.fill(255, (y * width + x) * 3, (y * width + x) * 3 + 3);
    }
  }
  return 'data:image/x-portable-pixmap;base64,' + Buffer.concat([Buffer.from(`P6\n${width} ${height}\n255\n`), pixels]).toString('base64');
}
const project = (steps, id = 'native-test') => ({version: 1, id, name: '原生桥接测试', steps});
const geometry = {id: 'contours', operation: 'geometry', params: {feature: 'contours', minArea: 100}};
const delayed = () => project([{id: 'wait', operation: 'delay', params: {milliseconds: 30000}}]);

async function launch(t) {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'native-engine-test-'));
  const oldDirectory = path.join(directory, 'old-server-data');
  fs.mkdirSync(oldDirectory);
  fs.writeFileSync(path.join(oldDirectory, 'camera-session.json'), '{malformed legacy camera state');
  const data = path.join(directory, 'native-data');
  const child = spawn(process.execPath, [path.join(root, 'desktop/engine-host.cjs'), '--data', data], {
    cwd: root, windowsHide: true, env: {...process.env, MACHINE_DATA_DIR: oldDirectory},
  });
  let sequence = 0, logs = '', resolveReady;
  const ready = new Promise(resolve => { resolveReady = resolve; });
  const pending = new Map(), events = [];
  child.stderr.on('data', bytes => { logs += bytes.toString(); });
  readline.createInterface({input: child.stdout}).on('line', line => {
    const message = JSON.parse(line);
    if (message.event) {
      events.push(message);
      if (message.event === 'ready') resolveReady(message.data);
      return;
    }
    const entry = pending.get(message.id);
    if (entry) {
      pending.delete(message.id);
      clearTimeout(entry.timer);
      if (message.error) entry.reject(Error(message.error)); else entry.resolve(message.result);
    }
  });
  const closed = new Promise(resolve => child.once('close', (code, signal) => {
    for (const entry of pending.values()) { clearTimeout(entry.timer); entry.reject(Error(logs || 'engine closed')); }
    pending.clear();
    resolve({code, signal});
  }));
  const request = (method, params = {}) => {
    const id = String(++sequence);
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => { pending.delete(id); reject(Error('RPC timed out: ' + method + '\n' + logs)); }, 20000);
      pending.set(id, {resolve, reject, timer});
      child.stdin.write(JSON.stringify({id, method, params}) + '\n');
    });
  };
  t.after(async () => {
    if (child.exitCode === null && child.signalCode === null) {
      try { await request('shutdown'); } catch { child.kill(); }
    }
    await closed;
    fs.rmSync(directory, {recursive: true, force: true});
  });
  const startupTimeout = setTimeout(() => { resolveReady(null); }, 10000);
  const info = await ready;
  clearTimeout(startupTimeout);
  assert.ok(info, 'host did not become ready: ' + logs);
  assert.equal(info.dataDirectory, data);
  return {request, child, closed, data, events};
}

function alive(pid) {
  try { process.kill(pid, 0); return true; } catch (error) { if (error.code === 'ESRCH') return false; throw error; }
}
async function assertExited(pids) {
  for (let attempt = 0; attempt < 40 && pids.some(alive); attempt++) await wait(50);
  assert.deepEqual(pids.filter(alive), [], 'owned worker process remained alive');
}

test('native stdio validates projects, discovers plugins, and runs real image algorithms', {timeout: 30000}, async t => {
  const host = await launch(t);
  const plugins = await host.request('plugins/list');
  assert.ok(Array.isArray(plugins));
  assert.ok(plugins.some(plugin => plugin.operators.length));
  const p = project([geometry]);
  const validated = await host.request('project/validate', {project: p});
  assert.deepEqual(validated.plan, ['contours']);
  assert.equal(validated.project.version, 2);
  const run = await host.request('run', {project: p, image: fixture(), allowScripts: false});
  assert.equal(run.state, 'completed', run.error);
  assert.equal(run.results[0].output.result.count, 2);
  assert.match(run.results[0].output.annotatedImage, /^data:image\/(png|jpeg);base64,/);
  assert.equal(run.archive.state, 'saved');
  assert.ok(host.events.some(event => event.event === 'progress' && event.data.state === 'completed'));
  const status = await host.request('status');
  assert.equal(status.state, 'idle');
  assert.ok(status.workerPids.length > 0);
  assert.equal((await host.request('camera/session/status')).state, 'idle');
  await host.request('shutdown');
  assert.deepEqual(await host.closed, {code: 0, signal: null});
  await assertExited(status.workerPids);
  assert.equal(fs.existsSync(path.join(host.data, '.sieans-runtime.lock')), false);
});

test('stop cancels an in-flight run without blocking stdio and the next run succeeds', {timeout: 30000}, async t => {
  const host = await launch(t);
  await host.request('run', {project: project([geometry]), image: fixture()});
  const workers = (await host.request('status')).workerPids;
  const running = host.request('run', {project: delayed()});
  assert.equal((await host.request('status')).state, 'running');
  await assert.rejects(host.request('run', {project: project([])}), /执行其他任务/);
  const started = Date.now();
  assert.equal((await host.request('stop')).state, 'cancelled');
  assert.equal((await running).state, 'cancelled');
  assert.ok(Date.now() - started < 5000, 'cancellation waited for the 30 second delay');
  await assertExited(workers);
  const result = await host.request('run', {project: project([geometry]), image: fixture()});
  assert.equal(result.state, 'completed', result.error);
});

test('shutdown cancels work and removes owned workers; unrelated processes remain alive', {timeout: 30000}, async t => {
  const unrelated = spawn(process.execPath, ['-e', 'setInterval(()=>{},1000)'], {windowsHide: true, stdio: 'ignore'});
  t.after(() => unrelated.kill());
  const host = await launch(t);
  await host.request('run', {project: project([geometry]), image: fixture()});
  const pids = (await host.request('status')).workerPids;
  const running = host.request('run', {project: delayed()});
  await host.request('shutdown');
  assert.equal((await running).state, 'cancelled');
  assert.equal((await host.closed).code, 0);
  await assertExited(pids);
  assert.equal(alive(unrelated.pid), true);
});

test('parent stdin closing also cleans up the native engine and its image worker', {timeout: 30000}, async t => {
  const host = await launch(t);
  await host.request('run', {project: project([geometry]), image: fixture()});
  const pids = (await host.request('status')).workerPids;
  host.child.stdin.end();
  assert.equal((await host.closed).code, 0);
  await assertExited(pids);
});

test('invalid methods, graph errors, and unapproved scripts return useful RPC errors', async t => {
  const host = await launch(t);
  await assert.rejects(host.request('missing/method'), /未知/);
  await assert.rejects(host.request('project/validate', {project: {}}), /工程格式无效/);
  await assert.rejects(host.request('run', {project: project([{id: 'code', operation: 'script', params: {code: 'print(1)'}}])}), /可信 Python/);
  const script = project([{id:'code',operation:'script',params:{code:'def run(ctx):\n    return {"result": {"answer": 42}}\n',timeoutMs:1000}}]);
  const trusted = await host.request('run', {project:script, allowScripts:true});
  assert.equal(trusted.state, 'completed', trusted.error);
  assert.equal(trusted.results[0].output.result.answer, 42);
  const failed = await host.request('run', {project: project([geometry]), image: ''});
  assert.equal(failed.state, 'failed');
  assert.match(failed.error, /图像/);
  assert.equal((await host.request('status')).state, 'idle');
});

test('draft validation permits disconnected nodes but execution still rejects them', async t => {
  const host = await launch(t);
  const draft = {version: 2, id: 'draft', name: '尚未连线的草稿', edges: [], steps: [geometry]};
  const checked = await host.request('project/validate', {project: draft});
  assert.equal(checked.valid, true);
  assert.deepEqual(checked.plan, ['contours']);
  assert.deepEqual(checked.project.edges, []);
  assert.equal(checked.project.steps[0].imageFrom, null);
  await assert.rejects(host.request('run', {project: checked.project, image: fixture()}), /未连接图像源/);
});

test('project validation retains unknown HMI extension fields after schema checks', async t => {
  const host = await launch(t);
  const p = project([{id:'delay',operation:'delay',params:{milliseconds:0}}]);
  p.hmi = {version:1,title:'运行画面',rows:4,rowHeight:40,components:[{id:'label',type:'text',label:'标题',x:0,y:0,w:2,h:1,color:'#0099cc',fontSize:16,futureFlag:true}],futureSettings:{value:2}};
  const result = await host.request('project/validate', {project:p});
  assert.deepEqual(result.project.hmi, p.hmi);
  await assert.rejects(host.request('project/validate', {project:{...p,hmi:{...p.hmi,rows:999}}}), /行数/);
});
