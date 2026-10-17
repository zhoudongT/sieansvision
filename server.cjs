const http = require('node:http');
const path = require('node:path');
const fs = require('node:fs');
const express = require('express');
const RED = require('node-red');
const vision = require('./lib/vision-client.cjs');
const industrial = require('./lib/industrial-client.cjs');
const cameras = require('./lib/camera-client.cjs');
const modbusSimulator = require('./lib/modbus-simulator.cjs');
const opcuaSimulator = require('./lib/opcua-simulator.cjs');
const s7Simulator = require('./lib/s7-simulator.cjs');
const mqttSimulator = require('./lib/mqtt-simulator.cjs'),mqttClient=require('./lib/mqtt-client.cjs');
const socketClient=require('./lib/socket-client.cjs'),socketSimulator=require('./lib/socket-simulator.cjs');
const access = require('./lib/access-control.cjs');
const loginAccounts=access.accounts();
const FlowGraph = require('./public/vision/flow-graph.js');
const {Runtime} = require('./lib/runtime.cjs');
const {ContinuousRun} = require('./lib/continuous-run.cjs');
const {OperatorPlugins} = require('./lib/operator-plugins.cjs');

const app = express();
const server = http.createServer(app);
let shuttingDown=false;
app.use((_req,res,next)=>shuttingDown?res.status(503).json({error:'服务正在停止，请稍后重试'}):next());
const platformPaths = require('./lib/platform-paths.cjs').paths();
const userDir = platformPaths.data;
fs.mkdirSync(userDir, { recursive: true });
const releaseDataLock = require('./lib/data-lock.cjs').acquire(userDir);
const operationHistory=new (require('./lib/operation-history.cjs').OperationHistory)(userDir);
const userStore=new (require('./lib/user-store.cjs').UserStore)(userDir,loginAccounts);
loginAccounts.userStore=userStore;
const webSessions=new (require('./lib/web-sessions.cjs').WebSessions)(loginAccounts,{secure:process.env.SIEANS_SESSION_SECURE==='1'});loginAccounts.webSessions=webSessions;webSessions.install(app,express,__dirname);
process.once('exit',releaseDataLock);
fs.mkdirSync(platformPaths.models,{recursive:true});
const operatorPlugins = new OperatorPlugins(userDir);
const runtime = new Runtime(userDir,vision,operatorPlugins);
const continuous = new ContinuousRun(runtime,userDir);
const mqttTrigger = new (require('./lib/mqtt-trigger.cjs').MqttTrigger)(runtime,userDir);
const cameraSession = new (require('./lib/camera-session.cjs').CameraSession)(userDir,cameras);
const operatorRuntime=new (require('./lib/operator-runtime.cjs').OperatorRuntime)(userDir,runtime,continuous,mqttTrigger);
cameras.setSessions(cameraSession);
const training = new (require('./lib/training.cjs').Training)(userDir,platformPaths.models,runtime);
const flowFile = path.join(userDir, 'flows.json');
if (!fs.existsSync(flowFile)) fs.copyFileSync(path.join(__dirname, 'examples', 'flows.json'), flowFile);
const host = process.env.HOST || '127.0.0.1';
const port = Number(process.env.PORT || 1880);
// LAN editor access requires a configured password hash.
if (!['127.0.0.1','localhost','::1'].includes(host) && !process.env.ADMIN_PASSWORD_HASH) {
  throw new Error('LAN mode requires ADMIN_PASSWORD_HASH. Generate it with npx node-red admin hash-pw.');
}
const settings = {
  httpAdminRoot: '/editor',
  httpNodeRoot: '/',
  userDir,
  flowFile: 'flows.json',
  nodesDir: path.join(__dirname, 'plugins'),
  editorTheme: { page: { title: 'Machine Visual Studio' }, header: { title: 'Machine Visual Studio' } },
  functionGlobalContext: {},
  machineVision: vision,
  machineIndustrial: industrial,
  machineCameras: cameras,
  machineOperators: require('./lib/operator-bridge.cjs').createOperatorBridge(operatorPlugins),
  ...(loginAccounts.adminHash?{dashboard:{ioMiddleware:access.dashboard(loginAccounts)}}:{}),
  ...(process.env.ADMIN_PASSWORD_HASH ? { adminAuth: {
    type: 'credentials', users: [{ username: process.env.ADMIN_USER || 'admin', password: process.env.ADMIN_PASSWORD_HASH, permissions: '*' }]
  } } : {})
};
RED.init(server, settings);
app.get('/', (_req, res) => res.redirect('/vision/'));
app.get('/health', (_req, res) => res.json({ status: 'ok' }));
// Use the configured administrator credentials for the integrated workbench and API.
const workbenchAuth=access.middleware(loginAccounts);
app.use('/vision', workbenchAuth);
app.use('/api/vision', workbenchAuth);
app.use('/api/vision',operationHistory.middleware());
app.use('/api/vision',access.restrictApi);
app.use('/vision',(req,res,next)=>req.identity.role==='operator'&&['/','/index.html'].includes(req.path)?res.redirect('/vision/operator.html'):next());
app.use('/vision', express.static(path.join(__dirname, 'public/vision')));
app.get('/api/vision/identity',(req,res)=>res.json({...req.identity,capabilities:{sessionManagement:req.identity.role==='admin'}}));
app.get('/api/vision/sessions',(req,res)=>{if(Object.keys(req.query).length)return res.status(400).json({error:'会话列表不接受额外查询字段'});res.json(webSessions.list(req.headers.cookie));});
app.post('/api/vision/sessions/:id/revoke',(req,res)=>{try{const current=webSessions.read(req.headers.cookie),currentSessionRevoked=current?.id===req.params.id,revoked=webSessions.revokeId(req.params.id);if(currentSessionRevoked)webSessions.setCookie(req,res,'');res.json({revoked,currentSessionRevoked});}catch(error){res.status(400).json({error:error.message});}});
app.get('/api/vision/accounts',(_req,res)=>res.json(userStore.list()));
app.post('/api/vision/accounts',express.json({limit:'4kb'}),async(req,res)=>{try{res.status(201).json(await userStore.change(null,req.body));}catch(error){res.status(error.status||400).json({error:error.message});}});
app.put('/api/vision/accounts/:id',express.json({limit:'4kb'}),async(req,res)=>{try{const changed=await userStore.change(req.params.id,req.body);webSessions.revokeUser(changed.username);res.json(changed);}catch(error){res.status(error.status||400).json({error:error.message});}});
app.get('/api/vision/operations/export',(req,res)=>{try{const csv=operationHistory.exportCsv(req.query);res.set({'Content-Type':'text/csv; charset=utf-8','Content-Disposition':'attachment; filename="sieans-operation-records.csv"','Cache-Control':'no-store'}).send(csv);}catch(error){res.status(error.status||400).json({error:error.message});}});
app.get('/api/vision/operations', (req,res)=>{try{res.json(operationHistory.list(req.query));}catch(error){res.status(400).json({error:error.message});}});
app.get('/api/vision/diagnostics',(_req,res)=>res.json(require('./lib/runtime-diagnostics.cjs').snapshot({runtime,continuous,mqttTrigger,cameraSession,plugins:operatorPlugins,vision,industrial,cameras,scripts:require('./lib/script-runner.cjs'),mqtt:mqttClient,socket:socketClient,training})));
app.get('/api/vision/operator/view',(_req,res)=>{try{res.json(operatorRuntime.publicState());}catch(error){res.status(error.status||400).json({error:error.message});}});
app.get('/api/vision/operator/publication',(req,res)=>{if(req.identity.role!=='admin')return res.status(403).json({error:'需要管理员权限'});try{res.json(operatorRuntime.summary());}catch(error){res.status(400).json({error:error.message});}});
app.post('/api/vision/operator/publish',express.json({limit:'2kb'}),(req,res)=>{if(req.identity.role!=='admin')return res.status(403).json({error:'需要管理员权限'});try{res.json(operatorRuntime.publish(req.body,req.identity.username));}catch(error){res.status(error.status||400).json({error:error.message});}});
app.post('/api/vision/operator/import-cloud',express.json({limit:'17mb'}),async(req,res)=>{try{res.json(await operatorRuntime.importCloud(req.body));}catch(error){if(!res.destroyed)res.status(error.status||(runtime.busy?409:400)).json({error:error.message});}});
for(const [route,method]of [['run','run'],['continuous','startContinuous'],['stop','stop'],['input','write'],['ack','acknowledge']])app.post('/api/vision/operator/'+route,express.json({limit:['run','continuous'].includes(route)?'35mb':'20kb'}),(req,res)=>{try{res.status(['run','continuous'].includes(route)?202:200).json(operatorRuntime[method](req.body,req.identity.username));}catch(error){res.status(error.status||(runtime.busy?409:400)).json({error:error.message});}});
app.get('/api/vision/version',(_req,res)=>res.json({product:'SIEANS Vision',version:require('./package.json').version}));
app.get('/api/vision/plugins',(_req,res)=>res.json({plugins:operatorPlugins.list(),canReload:true}));
app.post('/api/vision/plugins/reload',(_req,res)=>{
  try{
    if(runtime.busy||continuous.busy||mqttTrigger.busy||operatorPlugins.activeCount)throw Error('流程、连续运行或事件会话正在执行，暂不可重新扫描插件');
    operatorPlugins.reload();res.json({plugins:operatorPlugins.list(),canReload:true});
  }catch(error){res.status(409).json({error:error.message});}
});
app.get('/api/vision/training',(_req,res)=>res.json(training.status()));
app.post('/api/vision/training/datasets',express.json({limit:'20kb'}),async(req,res)=>{
  try{res.status(201).json(await training.create(req.body));}catch(error){res.status(400).json({error:error.message});}
});
app.post('/api/vision/training/datasets/:id/check',async(req,res)=>{
  try{res.json(await training.check(req.params.id));}catch(error){res.status(400).json({error:error.message});}
});
app.post('/api/vision/training/datasets/:id/annotations/:action',express.json({limit:'18mb'}),async(req,res)=>{
  try{res.json(await training.annotate(req.params.id,req.params.action,req.body));}catch(error){res.status(/其他页面修改/.test(error.message)?409:400).json({error:error.message});}
});
app.post('/api/vision/training/jobs',express.json({limit:'10kb'}),(req,res)=>{
  try{res.status(202).json(training.start(req.body));}catch(error){res.status(runtime.busy?409:400).json({error:error.message});}
});
app.post('/api/vision/training/jobs/:id/cancel',(req,res)=>{
  try{res.status(202).json(training.cancel(req.params.id));}catch(error){res.status(409).json({error:error.message});}
});
app.post('/api/vision/training/jobs/:id/publish',express.json({limit:'1kb'}),(req,res)=>{
  try{res.json(training.publish(req.params.id,req.body.name));}catch(error){res.status(400).json({error:error.message});}
});
app.put('/api/vision/plugins/:id',express.json({limit:'1kb'}),(req,res)=>{
  try{if(runtime.busy)throw Error('流程运行期间不可改变插件状态');res.json({plugins:operatorPlugins.setEnabled(req.params.id,req.body.enabled)});}catch(error){res.status(409).json({error:error.message});}
});
app.get('/api/vision/cameras/session',(_req,res)=>res.json(cameraSession.status()));
app.post('/api/vision/cameras/session',express.json({limit:'100kb'}),(req,res)=>{
 try{if(runtime.busy)throw Error('流程运行期间不可打开连续相机');res.status(202).json(cameraSession.start(req.body));}catch(error){res.status(runtime.busy||cameraSession.busy?409:400).json({error:error.message});}
});
app.post('/api/vision/cameras/session/:id/stop',async(req,res)=>{
 try{if(runtime.busy)throw Error('流程运行期间不可停止连续相机，请先停止流程');res.json(await cameraSession.stop(req.params.id));}catch(error){res.status(409).json({error:error.message});}
});
app.post('/api/vision/cameras/run',express.json({limit:'100kb'}),async(req,res)=>{
  if(runtime.busy)return res.status(409).json({error:'流程运行期间不可手动访问相机'});
  const controller=new AbortController();const cancel=()=>{if(!res.writableEnded)controller.abort();};res.on('close',cancel);
  try{res.json(await cameras.run(req.body,{signal:controller.signal}));}catch(error){if(!res.destroyed)res.status(400).json({error:error.message});}finally{res.off('close',cancel);}
});
app.post('/api/vision/industrial/run',express.json({limit:'100kb'}),async(req,res)=>{if(runtime.busy)return res.status(409).json({error:'流程运行期间不可手动访问工业设备'});try{res.json(await industrial.run(req.body));}catch(error){res.status(400).json({error:error.message});}});
app.get('/api/vision/industrial/socket/simulator',(_req,res)=>res.json(socketSimulator.status()));
app.post('/api/vision/industrial/socket/simulator/start',async(_req,res)=>{try{res.json(await socketSimulator.start());}catch(error){res.status(400).json({error:error.message});}});
app.post('/api/vision/industrial/socket/simulator/stop',async(_req,res)=>{try{if(runtime.busy||socketClient.activeCount())throw Error('流程或网络通信期间不可停止回显设备');res.json(await socketSimulator.stop());}catch(error){res.status(409).json({error:error.message});}});
app.get('/api/vision/industrial/mqtt/simulator',(_req,res)=>res.json(mqttSimulator.status()));
app.post('/api/vision/industrial/mqtt/simulator/start',async(_req,res)=>{try{res.json(await mqttSimulator.start());}catch(error){res.status(400).json({error:error.message});}});
app.post('/api/vision/industrial/mqtt/simulator/stop',async(_req,res)=>{try{if(runtime.busy||mqttClient.activeCount())throw Error('流程或 MQTT 通信期间不可停止消息服务器');res.json(await mqttSimulator.stop());}catch(error){res.status(409).json({error:error.message});}});
app.get('/api/vision/industrial/ports',async(_req,res)=>{try{res.json(await industrial.run({operation:'serial_ports',params:{}}));}catch(error){res.status(400).json({error:error.message});}});
app.get('/api/vision/industrial/simulator',(_req,res)=>res.json(modbusSimulator.status()));
app.get('/api/vision/industrial/s7/simulator',(_req,res)=>res.json(s7Simulator.status()));
app.post('/api/vision/industrial/s7/simulator/start',async(_req,res)=>{try{res.json(await s7Simulator.start());}catch(error){res.status(400).json({error:error.message});}});
app.post('/api/vision/industrial/s7/simulator/stop',async(_req,res)=>{try{if(runtime.busy)throw Error('流程执行期间不可停止模拟设备');res.json(await s7Simulator.stop());}catch(error){res.status(409).json({error:error.message});}});
app.get('/api/vision/industrial/opcua/simulator',(_req,res)=>res.json(opcuaSimulator.status()));
app.post('/api/vision/industrial/opcua/simulator/start',async(_req,res)=>{try{res.json(await opcuaSimulator.start());}catch(error){res.status(400).json({error:error.message});}});
app.post('/api/vision/industrial/opcua/simulator/stop',async(_req,res)=>{try{if(runtime.busy)throw Error('流程执行期间不可停止模拟设备');res.json(await opcuaSimulator.stop());}catch(error){res.status(409).json({error:error.message});}});
app.post('/api/vision/industrial/simulator/start',async(_req,res)=>{try{res.json(await modbusSimulator.start());}catch(error){res.status(400).json({error:error.message});}});
app.post('/api/vision/industrial/simulator/stop',async(_req,res)=>{try{if(runtime.busy)throw Error('流程执行期间不可停止模拟设备');res.json(await modbusSimulator.stop());}catch(error){res.status(409).json({error:error.message});}});
app.post('/api/vision/run', express.json({ limit: '35mb' }), async (req, res) => {
  try { res.json(await vision.run(req.body)); }
  catch (error) { res.status(400).json({ error: error.message }); }
});
app.get('/api/vision/runtime/continuous',(_req,res)=>res.json(continuous.status()));
app.get('/api/vision/runtime/mqtt-trigger',(_req,res)=>res.json(mqttTrigger.status()));
app.get('/api/vision/runtime/mqtt-trigger/project',(_req,res)=>res.json({project:mqttTrigger.project}));
app.post('/api/vision/runtime/mqtt-trigger/test-message',async(_req,res)=>{try{
  if(!mqttTrigger.ready||mqttTrigger.state.state!=='subscribed'||!mqttTrigger.cfg.c.simulated)throw Error('请等待本机模拟订阅连接完成后再发送测试消息');
  const topic=mqttTrigger.cfg.c.topic.split('/').map(p=>p==='+'||p==='#'?'test':p).join('/');
  const sent=await mqttClient.run({operation:'mqtt_publish',params:{connection:'simulator',topic,encoding:mqttTrigger.cfg.c.encoding,value:mqttTrigger.cfg.c.encoding==='text'?'SIEANS 测试消息':mqttTrigger.cfg.c.encoding==='bytes'?[83,73,69,65,78,83]:{requestId:require('node:crypto').randomUUID(),count:3,passed:true},retain:false,qos:1}});res.json(sent);
 }catch(error){res.status(400).json({error:error.message});}});
app.post('/api/vision/runtime/mqtt-trigger',express.json({limit:'35mb'}),(req,res)=>{try{res.status(202).json(mqttTrigger.start(req.body));}catch(error){res.status(runtime.busy?409:400).json({error:error.message});}});
app.post('/api/vision/runtime/mqtt-trigger/:id/stop',(req,res)=>{try{res.status(202).json(mqttTrigger.stop(req.params.id));}catch(error){res.status(409).json({error:error.message});}});
app.get('/api/vision/history',(req,res)=>{try{res.json(runtime.history.list(req.query));}catch(error){res.status(400).json({error:error.message});}});
app.get('/api/vision/history/:id',async(req,res)=>{try{res.json(await runtime.history.get(req.params.id));}catch(error){res.status(error.status||500).json({error:error.message});}});
app.get('/api/vision/runtime/continuous/project',(_req,res)=>res.json({project:continuous.project}));
app.post('/api/vision/runtime/continuous',express.json({limit:'35mb'}),(req,res)=>{
  try{res.status(202).json(continuous.start(req.body));}catch(error){res.status(runtime.busy?409:400).json({error:error.message});}
});
app.post('/api/vision/runtime/continuous/:id/stop',(req,res)=>{try{res.status(202).json(continuous.stop(req.params.id));}catch(error){res.status(409).json({error:error.message});}});
app.post('/api/vision/runtime/jobs',express.json({limit:'35mb'}),(req,res)=>{
  try{res.status(202).json(runtime.start(req.body));}catch(error){res.status(runtime.busy?409:400).json({error:error.message});}
});
app.get('/api/vision/runtime/jobs/:id',(req,res)=>{try{res.json(runtime.poll(req.params.id,Number(req.query.after||0)));}catch(error){res.status(404).json({error:error.message});}});
app.post('/api/vision/runtime/jobs/:id/cancel',(req,res)=>{try{res.json(runtime.cancel(req.params.id));}catch(error){res.status(404).json({error:error.message});}});
app.post('/api/vision/runtime/variables/read',express.json({limit:'35mb'}),(req,res)=>{try{res.json(runtime.snapshot(req.body.project));}catch(error){res.status(400).json({error:error.message});}});
app.post('/api/vision/runtime/view',express.json({limit:'35mb'}),(req,res)=>{try{res.json({...runtime.view(req.body.project,req.body.since),continuous:continuous.status()});}catch(error){res.status(400).json({error:error.message});}});
app.post('/api/vision/runtime/monitor/ack',express.json({limit:'2kb'}),(req,res)=>{try{res.json(runtime.monitor.acknowledge(req.body.projectId,req.body.id,req.body.comment??''));}catch(error){res.status(400).json({error:error.message});}});
app.put('/api/vision/runtime/variables',express.json({limit:'35mb'}),(req,res)=>{try{res.json(runtime.update(req.body.project,req.body.values,req.body.revision));}catch(error){res.status(409).json({error:error.message});}});
app.get('/api/vision/models', (_req, res) => {
  res.json({ models: fs.readdirSync(platformPaths.models).filter(name => /\.(pt|onnx)$/.test(name)) });
});
let computeCache=null,computePending=null;
app.get('/api/vision/compute',async(req,res)=>{
  try{
    if(!computeCache||req.query.refresh==='1'||Date.now()-computeCache.at>60000){
      if(!computePending)computePending=vision.run({operation:'compute_devices'}).then(value=>computeCache={at:Date.now(),value:value.result}).finally(()=>computePending=null);
      await computePending;
    }res.json(computeCache.value);
  }catch(error){res.status(400).json({error:'计算设备检查失败：'+error.message});}
});
app.get('/api/vision/dashboard', (_req, res) => {
  const bases = [];
  RED.nodes.eachNode(node => { if (node.type === 'ui-base') bases.push({ id: node.id, name: node.name, path: node.path }); });
  res.json({ bases });
});
const projectPath = path.join(userDir, 'vision-project.json');
app.get('/api/vision/project', (_req, res) => {
  if (!fs.existsSync(projectPath)) return res.json(null);
  res.type('json').send(fs.readFileSync(projectPath, 'utf8'));
});
app.put('/api/vision/project', express.json({ limit: '35mb' }), (req, res) => {
  if(continuous.busy||mqttTrigger.busy)return res.status(409).json({error:'连续检测或事件订阅期间不可保存工程，请先停止'});
  let project;
  try { project = FlowGraph.normalize(req.body); }
  catch(error) { return res.status(400).json({ error:error.message }); }
  const saved = { version: 2, id:project.id, name: project.name.slice(0, 120), ...(project.subflows?{subflows:project.subflows}:{}), ...(project.outputNode?{outputNode:project.outputNode}:{}), steps: project.steps, edges:project.edges, variables:project.variables, ...(project.variableTypes?{variableTypes:project.variableTypes}:{}), sourcePosition:project.sourcePosition, ...(project.hmi?{hmi:project.hmi}:{}), ...(project.history?{history:project.history}:{}), savedAt: new Date().toISOString() };
  fs.writeFileSync(projectPath+'.tmp', JSON.stringify(saved, null, 2));
  fs.renameSync(projectPath+'.tmp', projectPath);
  res.json({ savedAt: saved.savedAt });
});
app.use((error, _req, res, next) => {
  if (!error) return next();
  res.status(error.status || 400).json({ error: error.type === 'entity.too.large' ? (_req.path.startsWith('/auth/')?'登录数据超过 4 KiB':'上传数据超过 35 MB') : '请求格式无效' });
});
app.use(settings.httpAdminRoot, RED.httpAdmin);
if(loginAccounts.adminHash)app.use(settings.httpNodeRoot,workbenchAuth,(req,res,next)=>req.identity.role==='admin'?next():res.status(403).send('此 Node-RED 运行接口仅限管理员'));
app.use(settings.httpNodeRoot, RED.httpNode);
async function main() {
  await RED.start();
  server.listen(port, host, () => console.log(`Machine Visual Studio: http://${host}:${port}`));
}
async function shutdown() {
  if(shuttingDown)return;shuttingDown=true;
  if(continuous.busy)continuous.stop(continuous.state.id);
  const triggerStopping=mqttTrigger.shutdown();
  await training.stop();
  const active=runtime.active;
  if(active)runtime.cancel(active.id);
  await cameras.stop();
  vision.stop();
  await industrial.stop();
  await active?.promise;
  await continuous.promise;
  await triggerStopping;
  await RED.stop();
  server.close(() => process.exit(0));
}
process.on('SIGINT', shutdown);
process.on('SIGTERM', shutdown);
// Private parent IPC is used by the cross-platform launcher, never by an HTTP endpoint.
if(process.send){
  const stopFromParent=()=>shutdown().catch(error=>{console.error(error);process.exit(1);});
  process.on('message',message=>{if(message?.type==='sieans-shutdown')stopFromParent();});
  process.once('disconnect',stopFromParent);
}
main().catch(error => { console.error(error); process.exit(1); });
