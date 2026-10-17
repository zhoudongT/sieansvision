const { spawn } = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');
const readline = require('node:readline');
const root = path.resolve(__dirname, '..');
let worker;
let serial = 0;
const pending = new Map();
const children = new Set();

function start() {
  const configDir = require('./platform-paths.cjs').paths().yoloConfig;
  fs.mkdirSync(configDir, { recursive: true });
  const local = path.join(root, '.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python');
  const python = process.env.VISION_PYTHON || (fs.existsSync(local) ? local : 'python3');
  const child = spawn(python, ['-u', path.join(root, 'vision/engine.py')], {
    cwd: root, windowsHide: true, env: { ...process.env, PYTHONIOENCODING: 'utf-8', YOLO_CONFIG_DIR: configDir, YOLO_AUTOINSTALL: 'false' }
  });
  worker = child;
  children.add(child);child.once('close',()=>children.delete(child));
  let logs = '';
  child.stderr.on('data', data => { logs = (logs + data.toString()).slice(-4000); });
  const fail = error => {
    if (worker === child) worker = undefined;
    for (const [id, job] of pending) {
      if (job.child !== child) continue;
      clearTimeout(job.timer); pending.delete(id); job.reject(error);
    }
  };
  child.on('error', error => fail(new Error(`视觉引擎启动失败，请安装 Python 依赖：${error.message}`)));
  child.on('exit', code => fail(new Error(`视觉引擎退出 (${code})：${logs}`)));
  child.stdin.on('error', error => fail(error));
  readline.createInterface({ input: child.stdout }).on('line', line => {
    let response;
    try { response = JSON.parse(line); } catch { return; }
    const job = pending.get(response.id);
    if (!job || job.child !== child) return;
    clearTimeout(job.timer); pending.delete(response.id);
    if (response.ok) job.resolve(response.data); else job.reject(new Error(response.error));
  });
  return child;
}

function run(request,options={}) {
  if (!request) return Promise.reject(new Error('缺少视觉请求'));
  const timeoutMs=options.timeoutMs??120000;
  if(!Number.isInteger(timeoutMs)||timeoutMs<100||timeoutMs>120000)return Promise.reject(new Error('视觉任务超时设置无效'));
  const {CLOUD_OPERATIONS,cloud}=require('./frame.cjs');
  try {
    if(CLOUD_OPERATIONS.has(request.operation))cloud(request.cloud);
    else if(['cloud_import','depth_import'].includes(request.operation)){
      if(typeof request.content!=='string'||request.content.length>17_000_000||typeof request.name!=='string'||request.name.length>255)throw Error('点云文件格式无效或超过 12 MB');
    }else if(request.operation!=='compute_devices'&&typeof request.image!=='string')throw Error('需要 image 图像字符串');
  }catch(error){return Promise.reject(error);}
  if ((request.image || '').length > 17_000_000 || (request.reference || '').length > 17_000_000) {
    return Promise.reject(new Error('图像超过允许大小'));
  }
  if (pending.size >= 8) return Promise.reject(new Error('视觉任务队列已满，请稍后重试'));
  const child = worker || start();
  const id = ++serial;
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      // Kill the stalled engine; invalidate the entire queue rather than return stale results.
      child.kill();
      for (const [key, job] of pending) {
        if (job.child !== child) continue;
        clearTimeout(job.timer); pending.delete(key); job.reject(new Error('视觉任务超时，引擎已重置'));
      }
      if (worker === child) worker = undefined;
    }, timeoutMs);
    pending.set(id, { resolve, reject, timer, child });
    child.stdin.write(JSON.stringify({ ...request, id })+'\n');
  });
}

function stop() {
  if (worker) worker.kill();
  worker = undefined;
}
module.exports = { run, stop, status:()=>({pending:pending.size,children:children.size,pids:[...children].map(c=>c.pid).filter(Number.isInteger)}) };
