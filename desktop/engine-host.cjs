'use strict';

// Private stdio adapter for the native desktop app. It never starts server.cjs,
// Express or Node-RED. Local protocol simulators start only on explicit requests.
const fs = require('node:fs');
const path = require('node:path');
const {StringDecoder} = require('node:string_decoder');
const childProcess = require('node:child_process');

// Register only children created by this dedicated host. Legacy clients capture
// spawn when loaded below; tracking here gives shutdown one owned-child boundary.
const ownedChildren = new Set();
const spawn = childProcess.spawn;
childProcess.spawn = function (...args) {
  const child = spawn.apply(this, args);
  ownedChildren.add(child);
  child.once('close', () => ownedChildren.delete(child));
  return child;
};

const root = path.resolve(__dirname, '..');
const args = process.argv.slice(2);
const dataIndex = args.indexOf('--data');
if (dataIndex >= 0 && !args[dataIndex + 1]) throw Error('--data requires a directory');
const dataDirectory = path.resolve(dataIndex >= 0 ? args[dataIndex + 1] : path.join(root, 'native-data'));
// Do not inherit a web/server data directory or its YOLO configuration.
process.env.MACHINE_DATA_DIR = dataDirectory;
process.env.YOLO_CONFIG_DIR = path.join(dataDirectory, 'yolo-config');

const graph = require('../public/vision/flow-graph.js');
const vision = require('../lib/vision-client.cjs');
const cameras = require('../lib/camera-client.cjs');
const industrial = require('../lib/industrial-client.cjs');
const {Runtime} = require('../lib/runtime.cjs');
const {OperatorPlugins} = require('../lib/operator-plugins.cjs');
const {CameraSession} = require('../lib/camera-session.cjs');
const {Training} = require('../lib/training.cjs');
const {ContinuousRun} = require('../lib/continuous-run.cjs');
const {paths} = require('../lib/platform-paths.cjs');
const {createManagement} = require('./management-service.cjs');
const {createDemoService} = require('./demo-service.cjs');
const {acquire} = require('../lib/data-lock.cjs');
const MAX_REQUEST_BYTES = 80_000_000;
let runtime, plugins, releaseLock, cameraSession, training, continuous, mqttTrigger, management, demos, closing = false, shutdownPromise;
const cameraRequests = new Map();

function write(message) {
  if (!process.stdout.destroyed) process.stdout.write(JSON.stringify(message) + '\n');
}
function killOwned(forceHelpers = false) {
  for (const child of ownedChildren) {
    // Let Training.stop()'s Windows tree-termination helper finish its work.
    if (!forceHelpers && /^taskkill(?:\.exe)?$/i.test(path.basename(child.spawnfile || ''))) continue;
    if (child.exitCode === null && child.signalCode === null) child.kill();
  }
}
function session() {
  if (!cameraSession) {
    // Load prior session metadata. Soft-restore only when the last start
    // asked for autoStart (CameraManager 「自动重连」/ sessionPersist) so
    // force-quit → relaunch can reopen GenTL/UVC without manual 相机管理.
    cameraSession = new CameraSession(dataDirectory, cameras);
    cameras.setSessions(cameraSession);
    try { cameraSession.restore(); } catch (_) { /* leave interrupted/failed for UI */ }
  }
  return cameraSession;
}
function object(value, name = 'params') {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw Error(name + ' 必须为对象');
  return value;
}
function trainer() {
  if (!training) training = new Training(dataDirectory, paths().models, runtime);
  return training;
}
function continuousRun() {
  if (!continuous) continuous = new ContinuousRun(runtime, dataDirectory);
  return continuous;
}
function trigger() {
  if (!mqttTrigger) mqttTrigger = new (require('../lib/mqtt-trigger.cjs').MqttTrigger)(runtime, dataDirectory);
  return mqttTrigger;
}
async function cameraRequest(operation, params, requestId) {
  session(); // Wire CameraSession so freerun GenTL/UVC captures stay open across flow runs.
  const controller = new AbortController();
  cameraRequests.set(requestId, controller);
  try { return await cameras.run({operation, params}, {signal: controller.signal}); }
  finally { cameraRequests.delete(requestId); }
}

async function stopRun() {
  const active = runtime?.active;
  if (continuous?.busy) continuous.stop(continuous.state.id);
  if (mqttTrigger?.busy) mqttTrigger.stop(mqttTrigger.state.id);
  if (active) runtime.cancel(active.id);
  // Runtime's vision adapter predates AbortSignal. This host owns its single
  // vision worker, so cancelling the run also ends that worker immediately.
  if (active) vision.stop();
  await Promise.all([active?.promise, continuous?.promise, mqttTrigger?.finishPromise]);
  return active ? runtime.poll(active.id) : {state: 'idle'};
}

async function shutdown() {
  if (shutdownPromise) return shutdownPromise;
  closing = true;
  shutdownPromise = (async () => {
    const active = runtime?.active;
    if (continuous?.busy) continuous.stop(continuous.state.id);
    const mqttStopped = mqttTrigger?.shutdown();
    if (active) runtime.cancel(active.id);
    for (const controller of cameraRequests.values()) controller.abort();
    // Training.stop() marks an active job cancelled before terminating its tree.
    const trainingStopped = training?.stop();
    const demosStopped = demos?.shutdown();
    vision.stop();
    // Killing only registered children also interrupts long camera reads before
    // awaiting legacy clients' cooperative shutdown and history persistence.
    killOwned();
    const deadline = setTimeout(() => killOwned(true), 3000);
    try {
      await Promise.allSettled([active?.promise, trainingStopped, demosStopped, continuous?.promise, mqttStopped, cameras.stop(), industrial.stop(), management?.shutdown?.()]);
      await Promise.all([...ownedChildren].map(child => new Promise(resolve => {
        if (child.exitCode !== null || child.signalCode !== null) return resolve();
        child.once('close', resolve);
      })));
    } finally {
      clearTimeout(deadline);
      releaseLock?.();
      releaseLock = null;
    }
    return {state: 'stopped'};
  })();
  return shutdownPromise;
}

async function dispatch(method, params, requestId) {
  if (closing && method !== 'shutdown') throw Error('原生运行引擎正在关闭');
  management.authorize(method);
  switch (method) {
    case 'demos/list': return demos.list();
    case 'demos/load': return demos.load(params.id);
    case 'demos/sample': return demos.sample(params.operation);
    case 'plugins/list': return plugins.list();
    case 'project/validate': {
      const project = graph.normalize(params.project);
      // Loading/saving a draft must not require every node to be connected.
      // Runtime.prepare() performs the stricter executable-plan check on run.
      const plan = graph.order(project, false);
      for (const definition of [project, ...(project.subflows || [])]) {
        for (const step of definition.steps) {
          if (step.operation === 'plugin') plugins.get(step.params);
        }
      }
      // Validation still uses the canonical schema, while native editors retain
      // extension fields on HMI pages/components for round-trip compatibility.
      if (Object.hasOwn(params.project, 'hmi')) project.hmi = structuredClone(params.project.hmi);
      // Desktop open-and-run / operator HMI: keep runUi (判定门 gateKey), sourceConfig, Comm, triggers.
      for (const key of ['runUi', 'sourceConfig', 'commManager', 'globalTriggers', 'notes']) {
        if (Object.hasOwn(params.project, key)) project[key] = structuredClone(params.project[key]);
      }
      return {valid: true, project, plan: plan.map(step => step.id)};
    }
    case 'run': {
      const started = runtime.start({...params, allowScripts: params.allowScripts === true});
      const job = runtime.jobs.get(started.id);
      let cursor = 0, lastKey = '';
      const progress = () => {
        const state = runtime.poll(job.id, cursor);
        const key = [state.state, state.activeStep, state.cursor].join(':');
        if (key === lastKey) return;
        lastKey = key;
        cursor = state.cursor;
        write({event: 'progress', data: {requestId, ...state}});
      };
      progress();
      const timer = setInterval(progress, 100);
      try {
        await job.promise;
        progress();
        return runtime.poll(job.id);
      } finally { clearInterval(timer); }
    }
    case 'stop': return stopRun();
    case 'status': return {
      state: closing ? 'stopping' : runtime.busy ? 'running' : 'idle',
      pid: process.pid, dataDirectory,
      workerPids: [...ownedChildren].map(child => child.pid).filter(Number.isInteger),
      job: runtime.active ? runtime.poll(runtime.active.id, runtime.active.results.length) : null,
    };
    case 'variables/get': return runtime.snapshot(params.project);
    case 'runtime/view': return runtime.view(params.project, params.since);
    case 'monitor/ack': return runtime.monitor.acknowledge(params.projectId, params.id, params.comment ?? '');
    case 'variables/set': return runtime.update(params.project, params.state, params.revision);
    case 'camera/list': return cameraRequest('camera_list', params, requestId);
    case 'camera/providers': return cameraRequest('camera_providers', params, requestId);
    case 'camera/inspect': return cameraRequest('camera_inspect', params, requestId);
    case 'camera/capture': return cameraRequest('camera_capture', params, requestId);
    case 'camera/cancel': {
      const controller = cameraRequests.get(params.requestId);
      if (!controller) return {cancelled: false};
      controller.abort();
      return {cancelled: true};
    }
    case 'camera/session/status': return session().status();
    case 'camera/session/start': {
      // Honor client autoStart so sessionPersist / 「自动重连」survive relaunch.
      const body = {...params};
      if (body.autoStart === undefined) body.autoStart = false;
      return session().start(body);
    }
    case 'camera/session/reconnect': {
      // One-click reopen after interrupted/failed/stopped (clear disconnect UX).
      const s = session();
      const st = s.status();
      const cfg = (params && params.config) || st.config;
      if (!cfg || typeof cfg !== 'object') throw Error('无可重连的会话配置；请先在相机管理连接一次');
      if (s.busy) {
        try { s.stop(st.id || cfg.id); } catch (_) {}
        try { await s.closed; } catch (_) {}
      }
      const body = {
        params: cfg.params || params.params,
        intervalMs: cfg.intervalMs ?? 100,
        reconnectAttempts: cfg.reconnectAttempts ?? 2,
        reconnectMs: cfg.reconnectMs ?? 1000,
        autoStart: true,
      };
      if (!body.params) throw Error('会话配置缺少相机参数');
      return s.start(body);
    }
    case 'camera/session/stop': return session().stop(params.id || session().state.id);
    case 'models/list': return {models: trainer().status().models};
    case 'training/status': return trainer().status();
    case 'training/datasets/create': return trainer().create(params);
    case 'training/datasets/check': return trainer().check(params.datasetId);
    case 'training/annotations': return trainer().annotate(params.datasetId, params.action, object(params.body ?? {}, '标注内容'));
    case 'training/start': return trainer().start(params);
    case 'training/cancel': return trainer().cancel(params.id);
    case 'training/publish': return trainer().publish(params.id, params.name);
    case 'continuous/status': return continuousRun().status();
    case 'continuous/start': return continuousRun().start({...params, allowScripts: params.allowScripts === true});
    case 'continuous/stop': {
      const service = continuousRun();
      service.stop(params.id || service.state.id);
      if (runtime.active?.id === service.state.lastJobId) vision.stop();
      await service.promise;
      return service.status();
    }
    case 'mqtt/status': return trigger().status();
    case 'mqtt/start': return trigger().start({...params, allowScripts: params.allowScripts === true});
    case 'mqtt/stop': {
      const service = trigger();
      service.stop(params.id || service.state.id);
      if (runtime.active?.id === service.state.lastJobId) vision.stop();
      await service.finishPromise;
      return service.status();
    }
    case 'mqtt/test': {
      const service = trigger();
      if (!service.ready || service.state.state !== 'subscribed' || !service.cfg.c.simulated) throw Error('请先建立本机模拟订阅');
      const topic = service.cfg.c.topic.split('/').map(part => part === '+' || part === '#' ? 'test' : part).join('/');
      const encoding = service.cfg.c.encoding;
      return require('../lib/mqtt-client.cjs').run({operation:'mqtt_publish', params:{connection:'simulator', topic, encoding,
        value: encoding === 'text' ? 'SIEANS 测试消息' : encoding === 'bytes' ? [83,73,69,65,78,83] : {requestId:require('node:crypto').randomUUID(),count:3,passed:true}, retain:false,qos:1}});
    }
    case 'shutdown': return shutdown();
    default: return management.dispatch(method, params);
  }
}

const inFlight = new Set();
async function receive(line) {
  let request;
  try {
    request = JSON.parse(line);
    object(request, '请求');
    if (typeof request.id !== 'string' || !request.id || request.id.length > 128) throw Error('请求 id 必须为 1–128 字符');
    if (typeof request.method !== 'string') throw Error('请求 method 必须为字符串');
    if (inFlight.has(request.id)) throw Error('请求 id 正在执行');
    if (inFlight.size >= 32) throw Error('未完成请求超过 32 个');
    object(request.params ?? {});
  } catch (error) {
    write({id: typeof request?.id === 'string' ? request.id : null, error: error.message});
    return;
  }
  inFlight.add(request.id);
  const started = Date.now();
  let succeeded = false;
  try {
    const result = await dispatch(request.method, request.params ?? {}, request.id);
    succeeded = true;
    write({id: request.id, result});
  } catch (error) {
    write({id: request.id, error: error.message || String(error)});
  } finally {
    try { management.record(request.method, request.params ?? {}, succeeded, Date.now() - started); } catch {}
    inFlight.delete(request.id);
    if (request.method === 'shutdown') {
      process.stdin.pause();
      process.stdout.end(() => process.exit(0));
    }
  }
}

async function terminate() {
  await shutdown();
  process.stdout.end(() => process.exit(0));
}

try {
  fs.mkdirSync(dataDirectory, {recursive: true});
  releaseLock = acquire(dataDirectory);
  plugins = new OperatorPlugins(dataDirectory);
  runtime = new Runtime(dataDirectory, vision, plugins);
  management = createManagement({dataDirectory, runtime});
  demos = createDemoService({runtime, plugins, session});
  const decoder = new StringDecoder('utf8');
  let buffer = '';
  process.stdin.on('data', chunk => {
    buffer += decoder.write(chunk);
    let newline;
    while ((newline = buffer.indexOf('\n')) >= 0) {
      const line = buffer.slice(0, newline);
      buffer = buffer.slice(newline + 1);
      if (!line.trim()) continue;
      if (Buffer.byteLength(line) > MAX_REQUEST_BYTES) {
        write({id: null, error: '原生请求超过 80 MB'});
        void terminate();
        return;
      }
      void receive(line);
    }
    if (Buffer.byteLength(buffer) > MAX_REQUEST_BYTES) {
      write({id: null, error: '原生请求超过 80 MB 或缺少换行'});
      void terminate();
    }
  });
  process.stdin.on('end', () => { void terminate(); });
  process.stdin.on('error', () => { void terminate(); });
  process.stdout.on('error', () => { void terminate(); });
  process.once('SIGINT', () => { void terminate(); });
  process.once('SIGTERM', () => { void terminate(); });
  process.once('exit', () => { killOwned(true); releaseLock?.(); });
  // t243u: wire CameraSession before any flow run so GenTL capturePersistent
  // is used (avoids one-shot worker rejecting framePolicy/maxAgeMs).
  try { session(); } catch (_) {}
  write({event: 'ready', data: {protocolVersion: 1, pid: process.pid, dataDirectory}});
} catch (error) {
  releaseLock?.();
  process.stderr.write('原生引擎启动失败：' + error.message + '\n');
  process.exitCode = 1;
}
