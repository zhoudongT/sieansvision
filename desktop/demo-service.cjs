'use strict';

// The web and native workbenches share these authored manifests and assets.
// Discovery is read-only; importing data or opening a simulator requires load().
const fs = require('node:fs');
const path = require('node:path');
const {randomUUID} = require('node:crypto');
const {setTimeout:wait} = require('node:timers/promises');
const graph = require('../public/vision/flow-graph.js');
const hmi = require('../public/vision/hmi-layout.js');
const {remapResultReferences} = require('../public/vision/data-presentation.js');
const {frame} = require('../lib/frame.cjs');
const {paths} = require('../lib/platform-paths.cjs');

// Keep the catalog/category order identical to public/vision/app.js.
const MANIFESTS = [
  'demos.json', 'demos-inspection-chain.json', 'demos-image-quality.json',
  'demos-deviation.json', 'demos-relations.json', 'demos-segmentation.json',
  'demos-3d.json', 'demos-industrial.json', 'demos-s7.json', 'demos-serial.json',
  'demos-socket.json', 'demos-mqtt.json', 'demos-opcua-wait.json', 'demos-opcua.json',
  'demos-cameras.json', 'demos-control.json', 'demos-cylinder.json', 'demos-sphere.json',
  'demos-records.json', 'demos-handeye.json', 'demos-rigid.json', 'demos-intrinsics.json',
  'demos-heightfield.json', 'demos-fixture.json', 'demos-box.json', 'demos-depth-file.json',
  'demos-shape.json', 'demos-circle.json', 'demos-caliper.json', 'demos-plugins.json',
  'demos-hmi.json',
];
const allSteps = item => [...item.steps, ...(item.subflows || []).flatMap(def => def.steps)];
const simulatedCamera = params => ['simulator', 'rgbd_simulator'].includes(params?.driver);

function createDemoService({runtime, plugins, session, samplesDirectory = path.join(__dirname, '../public/vision/samples'), modelDirectory = paths().models}) {
  const directory = fs.realpathSync(samplesDirectory);
  let catalog, closing = false;
  const pending = new Set();
  function asset(name) {
    if (typeof name !== 'string' || !name || path.basename(name) !== name || /[\\/]/.test(name)) throw Error('演示素材名称无效');
    const file = fs.realpathSync(path.join(directory, name));
    if (path.dirname(file) !== directory || !fs.statSync(file).isFile() || fs.statSync(file).size > 12_000_000) throw Error('演示素材无效或超过 12 MB：' + name);
    return fs.readFileSync(file);
  }
  function data(name) {
    const mime = {'.png':'image/png', '.jpg':'image/jpeg', '.jpeg':'image/jpeg', '.json':'application/json'}[path.extname(name).toLowerCase()] || 'application/octet-stream';
    return 'data:' + mime + ';base64,' + asset(name).toString('base64');
  }
  function entries() {
    if (!catalog) {
      const ids = new Set();
      catalog = MANIFESTS.flatMap(name => {
        const items = JSON.parse(asset(name).toString('utf8'));
        if (!Array.isArray(items)) throw Error('演示清单格式无效：' + name);
        for (const item of items) {
          if (!item || typeof item.id !== 'string' || ids.has(item.id) || !Array.isArray(item.steps)) throw Error('演示编号重复或格式无效：' + name);
          ids.add(item.id);
        }
        return items;
      });
    }
    return catalog;
  }
  function metadata(item) {
    const steps = allSteps(item), requirements = [];
    const hasScripts = steps.some(step => step.operation === 'script');
    if (hasScripts) requirements.push('包含 Python 脚本：请检查代码并启用本次可信脚本执行后手动运行。');
    if (item.loadOnly) requirements.push('仅载入：请打开事件触发，启动本机模拟订阅后发送测试消息。');
    const missingModels = new Set();
    for (const step of steps.filter(step => ['yolo', 'yolo_segment'].includes(step.operation))) {
      const model = step.params.model || (step.operation === 'yolo_segment' ? 'yolo11n-seg.pt' : 'yolo11n.pt');
      let installed = false;
      if (typeof model === 'string' && path.basename(model) === model) {
        try {
          const file = fs.realpathSync(path.join(modelDirectory, model));
          installed = path.dirname(file) === fs.realpathSync(modelDirectory) && fs.statSync(file).isFile();
        } catch {}
      }
      if (!installed) missingModels.add(String(model));
    }
    for (const model of missingModels) requirements.push('缺少本地模型 ' + model + '：安装可信权重后手动运行，不会自动下载。');
    // A future authored case must never automatically contact real equipment.
    const external = steps.some(step => {
      const p = step.params;
      if (step.operation === 'camera_capture') return !simulatedCamera(p) && !(p.driver === 'session' && simulatedCamera(item.cameraSession));
      if (step.operation.startsWith('modbus_')) return p.transport !== 'simulator';
      if (/^(s7_|opcua_|mqtt_|tcp_exchange$|udp_exchange$|serial_exchange$)/.test(step.operation)) return p.connection !== 'simulator';
      return false;
    });
    if (external) requirements.push('包含非模拟设备连接：请检查连接参数并手动运行。');
    let unavailableReason = '';
    try { for (const step of steps.filter(step => step.operation === 'plugin')) plugins.get(step.params); }
    catch (error) { unavailableReason = error.message; }
    return {
      id:item.id, name:item.name, category:item.category, description:item.description, expected:item.expected,
      ...(item.image ? {image:item.image, preview:item.image} : {}),
      loadOnly:!!item.loadOnly, hasScripts, requirements,
      available:!unavailableReason, unavailableReason,
      autoRun:!hasScripts && !item.loadOnly && !missingModels.size && !external && !unavailableReason,
    };
  }
  function cloneDefinition(value) {
    const definition = structuredClone(value), ids = Object.create(null);
    for (const step of definition.steps) {
      const id = randomUUID();
      if (step.id) ids[step.id] = id;
      step.id = id;
      step.reference = step.reference ? data(step.reference) : '';
    }
    for (const step of definition.steps) {
      step.params = remapResultReferences(step.params, ids);
      if (step.imageFrom && ids[step.imageFrom]) step.imageFrom = ids[step.imageFrom];
    }
    if (definition.edges) definition.edges = definition.edges.map(edge => ({...edge, id:randomUUID(), from:ids[edge.from] || edge.from, to:ids[edge.to] || edge.to}));
    if (ids[definition.outputNode]) definition.outputNode = ids[definition.outputNode];
    if (definition.hmi) for (const component of hmi.allComponents(definition.hmi)) {
      if (component.binding && ids[component.binding.nodeId]) component.binding.nodeId = ids[component.binding.nodeId];
    }
    return definition;
  }
  function projectFor(item) {
    const main = cloneDefinition({steps:item.steps, ...(item.hmi ? {hmi:item.hmi} : {})});
    const steps = main.steps;
    for (const binding of item.bindings || []) {
      if (!steps[binding.step] || !steps[binding.source] || typeof binding.param !== 'string' || typeof binding.field !== 'string') throw Error('演示结果绑定无效');
      steps[binding.step].params[binding.param] = {$ref:'results.' + steps[binding.source].id + '.' + binding.field};
    }
    const project = {
      version:1, id:randomUUID(), name:'演示 · ' + item.name, variables:structuredClone(item.variables || {}), steps,
      ...(item.variableTypes ? {variableTypes:structuredClone(item.variableTypes)} : {}),
      ...(item.subflows ? {subflows:item.subflows.map(cloneDefinition)} : {}),
      ...(main.hmi ? {hmi:main.hmi} : {}),
    };
    if (item.connections) {
      project.version = 2;
      project.edges = item.connections.map(([from, to, when]) => {
        if ((from >= 0 && !steps[from]) || !steps[to]) throw Error('演示连线无效');
        return {id:randomUUID(), from:from < 0 ? 'source' : steps[from].id, to:steps[to].id, fromPort:'bottom', toPort:'top', ...(when ? {when} : {})};
      });
      for (let index = 0; index < steps.length; index++) if (item.imageParents?.[index] !== undefined) {
        const parent = item.imageParents[index];
        if (parent >= 0 && !steps[parent]) throw Error('演示图像来源无效');
        steps[index].imageFrom = parent < 0 ? 'source' : steps[parent].id;
      }
    }
    if (project.hmi) {
      const components = hmi.allComponents(project.hmi);
      for (const binding of item.hmiBindings || []) {
        if (!steps[binding.step] || !components[binding.component]?.binding) throw Error('画面演示绑定无效');
        components[binding.component].binding.nodeId = steps[binding.step].id;
      }
    }
    const normalized = graph.normalize(project);
    graph.expanded(normalized);
    // Keep native HMI extension fields, as project/validate and projects/save do.
    if (project.hmi) normalized.hmi = project.hmi;
    return item.connections ? graph.layout(normalized) : normalized;
  }
  async function importCloud(name) {
    return (await runtime.vision.run({operation:'cloud_import', name, content:data(name), unit:'mm'}, {timeoutMs:15000})).cloud;
  }
  async function prepareSession(project, params) {
    if (!simulatedCamera(params)) throw Error('演示加载只能建立模拟相机会话');
    const service = session();
    let status = service.status(), started = false;
    if (status.active && (status.config?.params.driver !== params.driver || status.config?.params.deviceId !== params.deviceId)) throw Error('已有其他设备的连续会话，请先在相机管理中停止，再载入此演示');
    try {
      if (!status.active) {
        status = service.start({params:structuredClone(params), intervalMs:100, reconnectAttempts:0, autoStart:false});
        started = true;
      }
      for (let attempt = 0; attempt < 150 && status.state !== 'running'; attempt++) {
        if (closing) throw Error('原生运行引擎正在关闭');
        if (['failed', 'stopped', 'interrupted'].includes(status.state)) throw Error(status.error || '连续相机未运行');
        await wait(100);
        status = service.status();
      }
      if (closing || status.state !== 'running') throw Error(closing ? '原生运行引擎正在关闭' : '模拟连续相机打开超时');
      for (const step of allSteps(project)) if (step.operation === 'camera_capture' && step.params.driver === 'session') step.params.sessionId = status.id;
    } catch (error) {
      if (started) await service.stop(status.id);
      throw error;
    }
  }
  function reserved(action) {
    if (closing) return Promise.reject(Error('原生运行引擎正在关闭'));
    const owner = {kind:'native-demo'};
    runtime.reserve(owner);
    const promise = (async () => { try { return await action(); } finally { runtime.release(owner); } })();
    pending.add(promise);
    promise.then(() => pending.delete(promise), () => pending.delete(promise));
    return promise;
  }
  async function load(id) {
    return reserved(async () => {
      const item = entries().find(entry => entry.id === id);
      if (!item) throw Error('演示案例不存在：' + String(id));
      const info = metadata(item);
      if (!info.available) throw Error(info.unavailableReason);
      const project = projectFor(item);
      let image = '', cloud = null, depth = null;
      if (item.depthFile) {
        const imported = await runtime.vision.run({operation:'depth_import', name:item.depthFile, content:data(item.depthFile), params:structuredClone(item.depthParams)}, {timeoutMs:15000});
        cloud = imported.cloud; depth = imported.depth;
      } else if (item.cloud) cloud = await importCloud(item.cloud);
      else if (!item.camera) image = data(item.image);
      const input = frame({image, cloud, depth});
      if (closing) throw Error('原生运行引擎正在关闭');
      if (item.cameraSession) await prepareSession(project, item.cameraSession);
      return {item:info, project, ...input, autoRun:info.autoRun, requirements:info.requirements};
    });
  }
  async function sample(operation) {
    return reserved(async () => {
      if (typeof operation === 'string' && operation.startsWith('cloud_')) {
        const name = ['cloud_plane', 'cloud_cluster'].includes(operation) ? 'cloud-scene.json' : 'cloud-box.json';
        return frame({cloud:await importCloud(name)});
      }
      return frame({image:data((operation === 'barcode' ? 'codes' : operation === 'ocr' ? 'text' : 'parts') + '.png')});
    });
  }
  return {
    list:() => ({items:entries().map(metadata)}), load, sample,
    shutdown:async () => { closing = true; await Promise.allSettled([...pending]); },
  };
}

module.exports = {createDemoService, MANIFESTS};
