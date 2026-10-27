'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const bus = require('../lib/comm-bus.cjs');

test('in-process send then receive on LocalLoop', async () => {
  bus.reset();
  const project = {commManager: {devices: [{name: 'LocalLoop', protocol: 'Local Bus', enabled: true}], recvEvents: [], sendEvents: []}};
  const vars = {global: {}, flow: {}};
  const sent = await bus.send({device: 'LocalLoop', channel: 'ch1', message: 'HELLO'}, null, {project, vars});
  assert.equal(sent.status, 'ok');
  assert.equal(sent.path, 'inprocess');
  assert.equal(sent.sent, 'HELLO');
  const got = await bus.receive({device: 'LocalLoop', channel: 'ch1', timeoutMs: 200}, {project, vars});
  assert.equal(got.status, 'ok');
  assert.equal(got.payload, 'HELLO');
});

test('receive timeout yields empty', async () => {
  bus.reset();
  const project = {commManager: {devices: [{name: 'LocalLoop', protocol: 'Local Bus', enabled: true}]}};
  const got = await bus.receive({device: 'LocalLoop', channel: 'empty', timeoutMs: 50}, {project, vars: {flow: {}, global: {}}});
  assert.equal(got.status, 'timeout');
  assert.equal(got.payload, '');
});

test('recvEvents write flow var', async () => {
  bus.reset();
  const project = {
    commManager: {
      devices: [{name: 'LocalLoop', protocol: 'Local Bus', enabled: true}],
      recvEvents: [{name: 'e1', device: 'LocalLoop', variable: 'flow.lastMsg'}],
    },
  };
  const vars = {flow: {}, global: {}};
  await bus.send({device: 'LocalLoop', message: 'PING'}, null, {project, vars});
  const got = await bus.receive({device: 'LocalLoop', timeoutMs: 100}, {project, vars});
  assert.equal(got.payload, 'PING');
  assert.equal(vars.flow.lastMsg, 'PING');
  assert.ok(got.eventVars.includes('flow.lastMsg'));
});

test('TCP device falls back to simulator when unreachable', async () => {
  bus.reset();
  const project = {
    commManager: {
      devices: [{name: 'TcpDemo', protocol: 'TCP Client', host: '127.0.0.1', port: 59999, enabled: true}],
    },
  };
  const vars = {flow: {}, global: {}};
  const sent = await bus.send({device: 'TcpDemo', message: 'ECHO-ME', timeoutMs: 1500}, null, {project, vars});
  assert.equal(sent.status, 'ok');
  assert.ok(sent.path === 'tcp-simulator' || sent.path === 'inprocess-fallback' || sent.path === 'tcp', sent.path);
});

test('sendEvents fills message from variable', async () => {
  bus.reset();
  const project = {
    commManager: {
      devices: [{name: 'LocalLoop', protocol: 'Local Bus', enabled: true}],
      sendEvents: [{device: 'LocalLoop', variable: 'outMsg'}],
    },
  };
  const vars = {flow: {outMsg: 'FROM_VAR'}, global: {}};
  const sent = await bus.send({device: 'LocalLoop', message: ''}, null, {project, vars});
  assert.equal(sent.sent, 'FROM_VAR');
});
