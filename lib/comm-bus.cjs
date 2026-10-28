'use strict';
/**
 * Lightweight Comm event bus for receive_data / send_data.
 * - In-process queues (Local Bus / missing device / Serial demo)
 * - TCP/UDP devices → socket-client (device first, simulator fallback)
 * CommManager devices / sendEvents / recvEvents drive routing + var hints.
 * No robot SDK; practical for desktop demo.
 */
const socketClient = require('./socket-client.cjs');

const queues = new Map(); // key -> {items:[], waiters:[]}

function queueKey(device, channel) {
  return String(device || 'LocalLoop') + '\0' + String(channel || 'default');
}

function ensureQueue(key) {
  if (!queues.has(key)) queues.set(key, {items: [], waiters: []});
  return queues.get(key);
}

const TRANSCRIPT_MAX = 48;
const transcript = []; // denser LocalBus TX/RX soft history (no field TCP)

function pushTranscript(entry) {
  const row = Object.assign({at: Date.now()}, entry || {});
  transcript.push(row);
  while (transcript.length > TRANSCRIPT_MAX) transcript.shift();
  return row;
}

function getTranscript(limit) {
  const n = Math.max(1, Math.min(TRANSCRIPT_MAX, Number(limit) || TRANSCRIPT_MAX));
  return transcript.slice(-n).map((e) => Object.assign({}, e));
}

function clearTranscript() {
  transcript.length = 0;
}

function formatTranscriptLine(e) {
  const ts = new Date(e.at || Date.now()).toISOString().replace('T', ' ').replace('Z', '');
  const dir = e.dir || (e.meta && e.meta.from === 'send' ? 'TX' : 'RX');
  const device = e.device || 'LocalLoop';
  const channel = e.channel || 'default';
  const path = e.path || (e.meta && e.meta.protocol) || 'inprocess';
  const bytes = e.bytes != null ? e.bytes : Buffer.byteLength(String(e.payload || ''), 'utf8');
  const body = String(e.payload == null ? '' : e.payload).replace(/\r/g, '\\r').replace(/\n/g, '\\n');
  const clip = body.length > 160 ? body.slice(0, 157) + '…' : body;
  return `[${ts}] ${dir} ${device}/${channel} path=${path} bytes=${bytes} │ ${clip}`;
}

function formatTranscript(limit) {
  return getTranscript(limit).map(formatTranscriptLine).join('\n');
}

function pushInbox(device, channel, payload, meta) {
  const key = queueKey(device, channel);
  const q = ensureQueue(key);
  const item = {payload: payload == null ? '' : String(payload), meta: meta || {}, at: Date.now()};
  pushTranscript({
    dir: (meta && meta.from === 'send') ? 'TX' : 'RX',
    device, channel,
    payload: item.payload,
    bytes: Buffer.byteLength(item.payload, 'utf8'),
    path: (meta && meta.from) || 'inprocess',
    meta: meta || {},
    at: item.at,
  });
  if (q.waiters.length) {
    const w = q.waiters.shift();
    clearTimeout(w.timer);
    try { w.signal?.removeEventListener('abort', w.onAbort); } catch { /* ignore */ }
    w.resolve(item);
  } else {
    q.items.push(item);
    while (q.items.length > 64) q.items.shift();
  }
  return item;
}

function popInbox(device, channel, timeoutMs, signal) {
  const key = queueKey(device, channel);
  const q = ensureQueue(key);
  if (q.items.length) return Promise.resolve(q.items.shift());
  const wait = Math.max(0, Number(timeoutMs) || 0);
  if (wait === 0) return Promise.resolve(null);
  return new Promise((resolve, reject) => {
    const waiter = {resolve, reject, timer: null, signal, onAbort: null};
    waiter.onAbort = () => {
      const i = q.waiters.indexOf(waiter);
      if (i >= 0) q.waiters.splice(i, 1);
      clearTimeout(waiter.timer);
      reject(Error('通信已取消'));
    };
    if (signal?.aborted) return waiter.onAbort();
    signal?.addEventListener('abort', waiter.onAbort, {once: true});
    waiter.timer = setTimeout(() => {
      const i = q.waiters.indexOf(waiter);
      if (i >= 0) q.waiters.splice(i, 1);
      try { signal?.removeEventListener('abort', waiter.onAbort); } catch { /* ignore */ }
      resolve(null);
    }, wait);
    q.waiters.push(waiter);
  });
}

function findDevice(project, name) {
  const n = String(name || '').trim();
  if (!n) return null;
  const cm = (project && project.commManager) || {};
  const devices = Array.isArray(cm.devices) ? cm.devices : [];
  for (const d of devices) {
    if (!d || typeof d !== 'object') continue;
    if (String(d.name || '') === n || String(d.id || '') === n) return d;
  }
  return null;
}

function protocolKind(proto) {
  const p = String(proto || '').toLowerCase();
  if (p.includes('udp')) return 'udp';
  if (p.includes('serial') || p.includes('串口')) return 'serial';
  if (p.includes('local') || p.includes('bus') || p.includes('内存') || p.includes('loop')) return 'local';
  if (p.includes('tcp')) return 'tcp';
  // MQTT / Modbus / OPC / S7 → in-process for desktop demo (no vendor stack here)
  return 'local';
}

function parseVarRef(raw) {
  const text = String(raw || '').trim();
  if (!text) return {scope: 'flow', name: ''};
  const lower = text.toLowerCase();
  for (const [prefix, scope] of [['flow.', 'flow'], ['global.', 'global'], ['g.', 'global']]) {
    if (lower.startsWith(prefix)) return {scope, name: text.slice(prefix.length).trim()};
  }
  return {scope: 'flow', name: text};
}

function writeVar(vars, scope, name, value) {
  if (!vars || !name || !/^[A-Za-z_][A-Za-z0-9_]{0,63}$/.test(name)) return false;
  if (scope === 'global') {
    if (!vars.global || typeof vars.global !== 'object') vars.global = {};
    vars.global[name] = value;
    return true;
  }
  if (!vars.flow || typeof vars.flow !== 'object') vars.flow = {};
  vars.flow[name] = value;
  return true;
}

function applyRecvEvents(project, deviceName, payload, vars) {
  const cm = (project && project.commManager) || {};
  const events = Array.isArray(cm.recvEvents) ? cm.recvEvents : [];
  const written = [];
  for (const ev of events) {
    if (!ev || typeof ev !== 'object') continue;
    const bound = String(ev.device || ev.deviceName || '').trim();
    if (bound && bound !== deviceName) continue;
    const ref = ev.variable || ev.var || ev.targetVar || '';
    const {scope, name} = parseVarRef(ref);
    if (!name) continue;
    if (writeVar(vars, scope, name, payload)) written.push(scope + '.' + name);
  }
  return written;
}

function readVar(vars, scope, name) {
  if (!vars || !name) return undefined;
  const bag = scope === 'global' ? vars.global : vars.flow;
  if (bag && Object.prototype.hasOwnProperty.call(bag, name)) return bag[name];
  return undefined;
}

function expandPlaceholders(text, vars) {
  const raw = text == null ? '' : String(text);
  if (!raw.includes('${')) return raw;
  return raw.replace(/\$\{([^}]+)\}/g, (all, inner) => {
    const {scope, name} = parseVarRef(String(inner || '').trim());
    if (!name) return all;
    const v = readVar(vars, scope, name);
    return v === undefined || v === null ? all : String(v);
  });
}

function resolveSendMessage(params, message, project, vars) {
  // Prefer explicit non-empty message (with ${} expand), then sourceVar, then sendEvents
  if (message != null && String(message).length) {
    return expandPlaceholders(String(message), vars);
  }
  if ((params.sourceMode || 'text') === 'variable' && params.sourceVar) {
    const scope = params.sourceScope || 'flow';
    const v = readVar(vars, scope, params.sourceVar);
    if (v !== undefined) return String(v ?? '');
  }
  // CommManager sendEvents: fill from bound variable when node message empty
  const cm = (project && project.commManager) || {};
  const deviceName = String(params.device || '').trim();
  for (const ev of (Array.isArray(cm.sendEvents) ? cm.sendEvents : [])) {
    if (!ev || typeof ev !== 'object') continue;
    const bound = String(ev.device || ev.deviceName || '').trim();
    if (bound && deviceName && bound !== deviceName) continue;
    const ref = ev.variable || ev.var || '';
    const {scope, name} = parseVarRef(ref);
    if (name) {
      const v = readVar(vars, scope, name);
      if (v !== undefined) return String(v ?? '');
    }
    if (ev.message != null && String(ev.message).length) {
      return expandPlaceholders(String(ev.message), vars);
    }
  }
  return expandPlaceholders(String(params.message || ''), vars);
}

async function socketSend(kind, device, text, timeoutMs, signal) {
  const host = String(device.host || '127.0.0.1');
  const port = Number(device.port) || (kind === 'udp' ? 9001 : 9000);
  const op = kind === 'udp' ? 'udp_exchange' : 'tcp_exchange';
  try {
    const data = await socketClient.run({
      operation: op,
      params: {
        connection: 'device',
        mode: 'send',
        host,
        port,
        value: text,
        encoding: 'text',
        timeoutMs: Math.min(Math.max(Number(timeoutMs) || 3000, 100), 60000),
        txFraming: kind === 'udp' ? undefined : 'crlf',
      },
    }, {signal});
    return {ok: true, path: kind, host, port, result: data.result, elapsedMs: data.elapsedMs};
  } catch (err) {
    // Desktop demo: fall back to built-in echo simulator
    try {
      const data = await socketClient.run({
        operation: op,
        params: {
          connection: 'simulator',
          mode: 'exchange',
          value: text,
          encoding: 'text',
          timeoutMs: Math.min(Math.max(Number(timeoutMs) || 3000, 100), 60000),
          txFraming: kind === 'udp' ? undefined : 'crlf',
          rxFraming: kind === 'udp' ? undefined : 'crlf',
        },
      }, {signal});
      return {
        ok: true,
        path: kind + '-simulator',
        host,
        port,
        result: data.result,
        elapsedMs: data.elapsedMs,
        note: '设备不可达，已走回显模拟：' + (err.message || err),
        echo: data.result?.value,
      };
    } catch (err2) {
      return {ok: false, path: 'inprocess-fallback', host, port, error: err.message || String(err), note: err2.message};
    }
  }
}

async function send(params, message, ctx = {}) {
  const {project, vars, signal} = ctx;
  const p = params || {};
  const deviceName = String(p.device || '').trim() || 'LocalLoop';
  const channel = String(p.channel || '').trim() || 'default';
  let text = resolveSendMessage(p, message, project, vars);
  if (p.appendCrLf) text += '\r\n';
  const bytes = Buffer.byteLength(text, 'utf8');
  const device = findDevice(project, deviceName);
  const kind = device ? protocolKind(device.protocol) : 'local';
  const timeoutMs = Number(p.timeoutMs) || 3000;

  // Always mirror into in-process bus so same-run receive_data can pick it up
  pushInbox(deviceName, channel, text, {from: 'send', protocol: kind});

  if (!device || device.enabled === false || kind === 'local' || kind === 'serial') {
    return {
      device: deviceName,
      channel,
      sent: text,
      bytes,
      status: 'ok',
      path: kind === 'serial' ? 'inprocess-serial' : 'inprocess',
      note: kind === 'serial'
        ? '串口演示走进程内总线（无硬件/SDK）'
        : (device ? '本地事件总线' : '未找到设备，已用 LocalLoop 进程内总线'),
    };
  }

  if (kind === 'tcp' || kind === 'udp') {
    // TCP Server listening is out of scope for a single step; treat like client send + bus
    if (String(device.protocol || '').toLowerCase().includes('server')) {
      return {
        device: deviceName, channel, sent: text, bytes, status: 'ok', path: 'inprocess-server',
        note: 'TCP Server 步骤侧仅投递本地总线；请用对端 Client 或另一流程 receive',
      };
    }
    const sock = await socketSend(kind, device, text, timeoutMs, signal);
    if (sock.echo != null) {
      const echoText = typeof sock.echo === 'string' ? sock.echo : JSON.stringify(sock.echo);
      pushInbox(deviceName, channel, echoText, {from: 'echo', protocol: kind});
    }
    return {
      device: deviceName,
      channel,
      sent: text,
      bytes,
      status: 'ok',
      path: sock.path,
      host: sock.host,
      port: sock.port,
      note: sock.note || '',
      echo: sock.echo,
      socket: sock.result || null,
    };
  }

  return {device: deviceName, channel, sent: text, bytes, status: 'ok', path: 'inprocess', note: '未知协议，已投递本地总线'};
}

async function receive(params, ctx = {}) {
  const {project, vars, signal} = ctx;
  const p = params || {};
  const deviceName = String(p.device || '').trim() || 'LocalLoop';
  const channel = String(p.channel || '').trim() || 'default';
  const timeoutMs = Number(p.timeoutMs) || 1000;
  const device = findDevice(project, deviceName);
  const kind = device ? protocolKind(device.protocol) : 'local';

  const item = await popInbox(deviceName, channel, timeoutMs, signal);
  if (item) {
    const payload = item.payload;
    const eventVars = applyRecvEvents(project, deviceName, payload, vars);
    const path = item.meta?.from === 'echo' ? 'echo' : (item.meta?.from || 'inprocess');
    const bytes = Buffer.byteLength(payload, 'utf8');
    pushTranscript({
      dir: 'RX',
      device: deviceName,
      channel,
      path,
      bytes,
      payload,
      note: 'receive',
    });
    return {
      device: deviceName,
      channel,
      payload,
      bytes,
      status: 'ok',
      path,
      eventVars,
    };
  }

  // Optional demo inject from recvEvent.demoPayload / message when inbox empty
  const cm = (project && project.commManager) || {};
  for (const ev of (Array.isArray(cm.recvEvents) ? cm.recvEvents : [])) {
    if (!ev || typeof ev !== 'object') continue;
    const bound = String(ev.device || ev.deviceName || '').trim();
    if (bound && bound !== deviceName) continue;
    const demo = ev.demoPayload != null ? ev.demoPayload : (ev.inject != null ? ev.inject : null);
    if (demo == null || demo === '') continue;
    const payload = String(demo);
    const eventVars = applyRecvEvents(project, deviceName, payload, vars);
    const bytes = Buffer.byteLength(payload, 'utf8');
    pushTranscript({
      dir: 'RX',
      device: deviceName,
      channel,
      path: 'recvEvent',
      bytes,
      payload,
      note: 'recvEvent demo',
    });
    return {
      device: deviceName, channel, payload,
      bytes,
      status: 'ok', path: 'recvEvent', eventVars,
      note: '来自通信管理接收事件演示载荷',
    };
  }

  return {
    device: deviceName,
    channel,
    payload: '',
    bytes: 0,
    status: 'timeout',
    path: kind,
    note: '等待超时，无数据（进程内总线 / 对端未发）',
    eventVars: [],
  };
}

function reset() {
  for (const q of queues.values()) {
    for (const w of q.waiters) {
      clearTimeout(w.timer);
      try { w.signal?.removeEventListener('abort', w.onAbort); } catch { /* ignore */ }
      try { w.resolve(null); } catch { /* ignore */ }
    }
  }
  queues.clear();
  clearTranscript();
}

module.exports = {
  send, receive, pushInbox, popInbox, reset, findDevice, protocolKind, queueKey, applyRecvEvents,
  resolveSendMessage, expandPlaceholders, parseVarRef,
  getTranscript, clearTranscript, formatTranscript, formatTranscriptLine, pushTranscript, TRANSCRIPT_MAX,
};
