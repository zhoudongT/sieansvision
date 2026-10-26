'use strict';
const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const {createHash} = require('node:crypto');
const {spawn} = require('node:child_process');
const readline = require('node:readline');
const bcrypt = require('bcryptjs');
const {createDemoService, MANIFESTS} = require('../desktop/demo-service.cjs');
const graph = require('../public/vision/flow-graph.js');
const hmi = require('../public/vision/hmi-layout.js');
const {remapResultReferences} = require('../public/vision/data-presentation.js');
const {frame} = require('../lib/frame.cjs');
const {OperatorPlugins} = require('../lib/operator-plugins.cjs');
const root = path.resolve(__dirname, '..');
const samples = path.join(root, 'public/vision/samples');
const digest = file => createHash('sha256').update(fs.readFileSync(file)).digest('hex');
const catalog = () => MANIFESTS.flatMap(file => JSON.parse(fs.readFileSync(path.join(samples, file), 'utf8')));

async function launch(t, secured = false) {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'native-demos-'));
  const data = path.join(directory, 'data'), models = path.join(directory, 'models');
  fs.mkdirSync(models);
  const env = {...process.env, VISION_MODEL_DIR:models};
  for (const key of ['ADMIN_PASSWORD_HASH', 'ADMIN_USER', 'OPERATOR_PASSWORD_HASH', 'OPERATOR_USER']) delete env[key];
  if (secured) env.ADMIN_PASSWORD_HASH = bcrypt.hashSync('demo-test-password', 4);
  const child = spawn(process.execPath, [path.join(root, 'desktop/engine-host.cjs'), '--data', data], {cwd:root, windowsHide:true, env});
  let sequence = 0, logs = '', resolveReady;
  const ready = new Promise(resolve => { resolveReady = resolve; }), pending = new Map();
  child.stderr.on('data', value => { logs += value.toString(); });
  readline.createInterface({input:child.stdout}).on('line', line => {
    const message = JSON.parse(line);
    if (message.event === 'ready') return resolveReady(true);
    const entry = pending.get(message.id);
    if (!entry) return;
    clearTimeout(entry.timer); pending.delete(message.id);
    if (message.error) entry.reject(Error(message.error)); else entry.resolve(message.result);
  });
  const closed = new Promise(resolve => child.once('close', code => {
    for (const entry of pending.values()) { clearTimeout(entry.timer); entry.reject(Error(logs || 'engine closed')); }
    pending.clear(); resolveReady(false); resolve(code);
  }));
  const request = (method, params = {}) => new Promise((resolve, reject) => {
    const id = String(++sequence);
    const timer = setTimeout(() => { pending.delete(id); reject(Error('RPC timed out: ' + method + ' ' + (params.id || '') + '\n' + logs)); }, 45000);
    pending.set(id, {resolve, reject, timer}); child.stdin.write(JSON.stringify({id, method, params}) + '\n');
  });
  t.after(async () => {
    if (child.exitCode === null && child.signalCode === null) { try { await request('shutdown'); } catch { child.kill(); } }
    await closed;
    fs.rmSync(directory, {recursive:true, force:true});
  });
  const timer = setTimeout(() => resolveReady(false), 10000);
  assert.equal(await ready, true, logs); clearTimeout(timer);
  return {request, data, models};
}

function assertProject(raw, loaded) {
  const project = loaded.project;
  graph.expanded(graph.normalize(project));
  frame(loaded);
  assert.notEqual(project.id, raw.id);
  assert.equal(project.steps.length, raw.steps.length, raw.id);
  const ids = Object.fromEntries(raw.steps.flatMap((step, index) => step.id ? [[step.id, project.steps[index].id]] : []));
  for (const [index, step] of project.steps.entries()) {
    assert.notEqual(step.id, raw.steps[index].id);
    const expected = remapResultReferences(raw.steps[index].params, ids);
    for (const binding of raw.bindings || []) if (binding.step === index) expected[binding.param] = {$ref:'results.' + project.steps[binding.source].id + '.' + binding.field};
    if (raw.cameraSession && step.operation === 'camera_capture' && step.params.driver === 'session') {
      assert.notEqual(step.params.sessionId, 'current-session'); expected.sessionId = step.params.sessionId;
    }
    // JSON transport intentionally canonicalizes the numeric spelling -0 to 0.
    assert.deepEqual(step.params, JSON.parse(JSON.stringify(expected)), raw.id + ' parameters ' + index);
    assert.deepEqual(step.variables, raw.steps[index].variables || {});
    assert.deepEqual(step.variableTypes, raw.steps[index].variableTypes);
    if (raw.steps[index].reference) assert.match(step.reference, /^data:image\//);
  }
  assert.deepEqual(project.variables, raw.variables || {});
  assert.deepEqual(project.variableTypes, raw.variableTypes);
  if (raw.connections) assert.deepEqual(project.edges.map(edge => [edge.from === 'source' ? -1 : project.steps.findIndex(step => step.id === edge.from), project.steps.findIndex(step => step.id === edge.to), ...(edge.when ? [edge.when] : [])]), raw.connections);
  for (const [index, parent] of Object.entries(raw.imageParents || {})) assert.equal(project.steps[index].imageFrom, parent < 0 ? 'source' : project.steps[parent].id);
  if (raw.hmi) {
    const expected = structuredClone(raw.hmi), components = hmi.allComponents(expected);
    for (const component of components) if (component.binding && ids[component.binding.nodeId]) component.binding.nodeId = ids[component.binding.nodeId];
    for (const binding of raw.hmiBindings || []) components[binding.component].binding.nodeId = project.steps[binding.step].id;
    assert.deepEqual(project.hmi, expected, raw.id + ' HMI');
  }
  for (const [index, definition] of (project.subflows || []).entries()) {
    const original = raw.subflows[index];
    assert.equal(definition.id, original.id);
    assert.equal(definition.outputNode, definition.steps[original.steps.findIndex(step => step.id === original.outputNode)].id);
    assert.ok(definition.steps.every((step, i) => step.id !== original.steps[i].id));
  }
  if (raw.depthFile) { assert.equal(loaded.image, ''); assert.equal(loaded.depth.format, 'png16'); assert.ok(loaded.cloud.points.length); }
  else if (raw.cloud) { assert.equal(loaded.image, ''); assert.ok(loaded.cloud.points.length); }
  else if (raw.camera) assert.equal(loaded.image, '');
  else assert.match(loaded.image, /^data:image\//);
}

test('all authored demos load through authenticated native RPC with their assets, graph and bindings intact', {timeout:180000}, async t => {
  const original = catalog(), hashes = MANIFESTS.map(file => digest(path.join(samples, file)));
  const web = fs.readFileSync(path.join(root, 'public/vision/app.js'), 'utf8');
  assert.deepEqual([...web.matchAll(/fetch\('samples\/(demos[^']*\.json)'\)/g)].map(match => match[1]), MANIFESTS);
  const host = await launch(t, true);
  for (const method of ['demos/list', 'demos/load', 'demos/sample']) await assert.rejects(host.request(method, {id:'contours', operation:'geometry'}), /登录/);
  await host.request('auth/login', {username:'admin', password:'demo-test-password'});
  const list = await host.request('demos/list');
  assert.equal(list.items.length, 149);
  assert.deepEqual(list.items.map(item => item.id), original.map(item => item.id));
  assert.ok(list.items.every(item => item.available));
  assert.deepEqual((await host.request('status')).workerPids, []);
  assert.equal(fs.existsSync(path.join(host.data, 'camera-session.json')), false);
  for (const item of list.items) if (item.preview) assert.ok(fs.statSync(path.join(samples, item.preview)).isFile());
  // Load the simulator session last; this keeps the full validation pass free of
  // background acquisition until the explicit session demonstration is chosen.
  for (const raw of [...original.filter(item => !item.cameraSession), ...original.filter(item => item.cameraSession)]) {
    const loaded = await host.request('demos/load', {id:raw.id});
    assertProject(raw, loaded);
    assert.equal((await host.request('project/validate', {project:loaded.project})).valid, true);
    if (raw.id === 'python-vars' || raw.loadOnly || raw.steps.some(step => ['yolo','yolo_segment'].includes(step.operation))) {
      assert.equal(loaded.autoRun, false, raw.id); assert.ok(loaded.requirements.length);
    } else assert.equal(loaded.autoRun, true, raw.id);
    if (!raw.cameraSession) assert.equal(fs.existsSync(path.join(host.data, 'camera-session.json')), false);
  }
  const session = await host.request('camera/session/status');
  assert.equal(session.state, 'running'); assert.equal(session.config.autoStart, false); assert.equal(session.config.params.driver, 'simulator');
  await host.request('camera/session/stop', {id:session.id});
  const a = await host.request('demos/load', {id:'inspection-chain-pass'}), b = await host.request('demos/load', {id:'inspection-chain-pass'});
  assert.notEqual(a.project.id, b.project.id); assert.notEqual(a.project.steps[0].id, b.project.steps[0].id);
  await host.request('plugins/update', {id:'sieans-inspection', enabled:false});
  assert.equal((await host.request('demos/list')).items.find(item => item.id === 'plugin-brightness').available, false);
  await assert.rejects(host.request('demos/load', {id:'plugin-brightness'}), /插件未安装或已停用/);
  await assert.rejects(host.request('demos/load', {id:'../demos.json'}), /案例不存在/);
  assert.equal((await host.request('status')).state, 'idle');
  assert.deepEqual(MANIFESTS.map(file => digest(path.join(samples, file))), hashes);
  assert.deepEqual(fs.readdirSync(path.join(host.data, 'native-projects')), []);
});

test('native demos execute real 2D, 3D, branches, subflows, HMI, plugins, depth and local protocol simulators', {timeout:180000}, async t => {
  const host = await launch(t);
  const execute = async id => {
    const loaded = await host.request('demos/load', {id});
    assert.equal(loaded.autoRun, true);
    const run = await host.request('run', {...loaded, allowScripts:false});
    assert.equal(run.state, 'completed', id + ': ' + run.error);
    assert.equal(run.archive.state, 'saved');
    return {loaded, run, result:run.results.filter(row => !row.skipped).at(-1).output.result};
  };
  assert.equal((await execute('contours')).result.count, 3);
  assert.equal((await execute('cloud-box')).result.sizeX, 20);
  const branch = await execute('conditional-inspection');
  assert.equal(branch.run.variables.flow.inspectionRoute, 'OK'); assert.ok(branch.run.results.some(row => row.skipped));
  assert.equal((await execute('subflow-reuse')).run.variables.flow.count, 3);
  assert.equal((await execute('loop-until')).run.variables.flow.rounds, 3);
  assert.equal((await execute('loop-cloud')).run.variables.flow.width, 20);
  assert.equal((await execute('typed-variables-pass')).run.variables.flow.accepted, true);
  const hmiRun = await execute('hmi-inspection');
  assert.equal(hmiRun.result.passed, true);
  const bound = hmi.allComponents(hmiRun.loaded.project.hmi).filter(component => component.binding?.source === 'result');
  assert.ok(bound.every(component => hmiRun.run.results.some(row => row.id === component.binding.nodeId)));
  assert.equal((await execute('plugin-brightness')).run.variables.flow.brightnessOK, true);
  const depth = await execute('depth-file-top');
  assert.equal(depth.loaded.depth.width, 64); assert.equal(depth.loaded.depth.height, 48);
  assert.ok(Math.abs(depth.run.variables.flow.topWidth - 185.25) < 0.001);
  for (const [id, variable, expected] of [
    ['modbus-vision','plcCount',3], ['s7-vision','s7Count',3], ['serial-text','serialReply','SIEANS-SERIAL-00042'],
    ['tcp-detection','networkReply',3], ['mqtt-count','mqttValue',3], ['opcua-vision','uaCount',3],
  ]) assert.equal((await execute(id)).run.variables.flow[variable], expected, id);
  const udp = await execute('udp-record');
  assert.ok(udp.run.results.some(row => row.output.result.simulated === true));
  const session = await execute('camera-session-2d');
  assert.equal(session.result.count, 3);
  assert.equal((await host.request('camera/session/status')).active, true);
  for (const [operation, filename] of [['geometry','parts.png'],['barcode','codes.png'],['ocr','text.png']]) {
    const sample = await host.request('demos/sample', {operation}); frame(sample);
    assert.deepEqual(Buffer.from(sample.image.split(',')[1], 'base64'), fs.readFileSync(path.join(samples, filename)));
  }
  for (const [operation, name] of [['cloud_plane','cloud-scene.json'],['cloud_cluster','cloud-scene.json'],['cloud_measure','cloud-box.json']]) {
    const sample = await host.request('demos/sample', {operation}); frame(sample);
    const direct = await host.request('cloud/import', {name, content:'data:application/json;base64,' + fs.readFileSync(path.join(samples,name)).toString('base64'), unit:'mm'});
    assert.deepEqual(sample.cloud, direct.cloud);
  }
  const untrusted = await host.request('demos/load', {id:'python-vars'});
  await assert.rejects(host.request('run', {...untrusted, allowScripts:false}), /可信 Python/);
});

test('demo import failures release runtime reservation and concurrent work is rejected', async t => {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'native-demo-service-'));
  t.after(() => fs.rmSync(directory, {recursive:true, force:true}));
  const runtime = {
    owner:null,
    reserve(owner) { if (this.owner) throw Error('执行其他任务'); this.owner = owner; },
    release(owner) { assert.equal(owner, this.owner); this.owner = null; },
    vision:{run:async () => { throw Error('import failed'); }},
  };
  const service = createDemoService({runtime, plugins:new OperatorPlugins(directory), session:() => { throw Error('session must be explicit'); }, modelDirectory:directory});
  await assert.rejects(service.load('cloud-box'), /import failed/); assert.equal(runtime.owner, null);
  await assert.rejects(service.load('depth-file-top'), /import failed/); assert.equal(runtime.owner, null);
  let finish;
  runtime.vision.run = () => new Promise(resolve => { finish = resolve; });
  const loading = service.load('cloud-box');
  await assert.rejects(service.sample('geometry'), /执行其他任务/);
  finish({cloud:{unit:'mm', points:[[0,0,0]]}}); await loading; assert.equal(runtime.owner, null);
  await service.shutdown(); await assert.rejects(service.load('contours'), /关闭/);
});
