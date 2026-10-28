#!/usr/bin/env node
/** wave139: poseCorrect affine/fixture flow vars + preprocess catalog density. */
'use strict';
const path = require('path');
const fs = require('fs');
const ROOT = path.resolve(__dirname, '..');
const fc = require(path.join(ROOT, 'lib/flow-control.cjs'));
let pass = 0, fail = 0;
const ok = (m) => { pass++; console.log('PASS:', m); };
const bad = (m) => { fail++; console.log('FAIL:', m); };

// --- manual pose + rotation matrix ---
let ctx = { flow: {}, module: {}, global: {}, results: {}, steps: [] };
let r = fc.poseCorrect({
  fixtureSource: 'manual', baseX: 100, baseY: 50, baseAngle: 90, baseScale: 2,
  axisLength: 40, writeFlowVars: true, resultVar: 'fixture',
}, null, ctx);
const c = Math.cos(Math.PI / 2) * 2, s = Math.sin(Math.PI / 2) * 2;
if (Math.abs(r.matrix[0] - c) < 1e-9 && Math.abs(r.matrix[1] - (-s)) < 1e-9 &&
    Math.abs(r.matrix[2] - 100) < 1e-9 && Math.abs(r.matrix[3] - s) < 1e-9 &&
    Math.abs(r.matrix[5] - 50) < 1e-9 && r.status === 'ok')
  ok(`manual matrix angle90 scale2 tx=${r.matrix[2]}`);
else bad(`manual matrix ${JSON.stringify(r.matrix)}`);
if (ctx.flow.fixture_x === 100 && ctx.flow.fixture_y === 50 &&
    ctx.flow.fixture_angle === 90 && ctx.flow.fixture_scale === 2 &&
    ctx.flow.fixture_ok === 1 && ctx.flow.fixture_status === 'ok')
  ok('manual flow vars');
else bad(`manual flow ${JSON.stringify(ctx.flow)}`);
if (Math.abs(r.axisX.x) < 1e-6 && Math.abs(r.axisX.y - 40) < 1e-6)
  ok(`axisX @90deg ${JSON.stringify(r.axisX)}`);
else bad(`axisX ${JSON.stringify(r.axisX)}`);

// --- bind from locate match ---
ctx = {
  flow: {},
  results: {
    loc1: { result: { matches: [{ x: 12.5, y: 34, angleDeg: 15, score: 0.92, scale: 1.1 }] } },
  },
  steps: [{ id: 'loc1', operation: 'locate' }, { id: 'pose1', operation: 'pose_correct' }],
};
r = fc.poseCorrect({
  fixtureSource: 'auto', bindStepId: '', bindField: 'matches[0]',
  writeFlowVars: true, resultVar: 'fx', autoBindLocate: true, axisLength: 20,
}, null, ctx);
if (r.boundOk && r.fixtureX === 12.5 && r.fixtureY === 34 && r.fixtureAngle === 15 &&
    Math.abs(r.fixtureScale - 1.1) < 1e-9 && r.boundFrom === 'loc1' && r.status === 'ok')
  ok(`auto-bind locate score=${r.score}`);
else bad(`auto-bind ${JSON.stringify(r)}`);
if (ctx.flow.fx_ok === 1 && ctx.flow.fx_angle === 15 && ctx.flow.fx_score === 0.92)
  ok('bound flow vars');
else bad(`bound flow ${JSON.stringify(ctx.flow)}`);

// --- unbound ---
ctx = { flow: {}, results: {}, steps: [{ id: 'pose1', operation: 'pose_correct' }] };
r = fc.poseCorrect({ fixtureSource: 'auto', writeFlowVars: true, resultVar: 'u' }, null, ctx);
if (r.status === 'unbound' && r.boundOk === false && ctx.flow.u_ok === 0)
  ok('unbound status');
else bad(`unbound ${JSON.stringify(r)} flow=${JSON.stringify(ctx.flow)}`);

// --- project file ---
const projPath = path.join(ROOT, 'projects/open-and-run-fixture-preprocess.sieans');
const proj = JSON.parse(fs.readFileSync(projPath, 'utf8'));
const ops = proj.steps.map((s) => s.operation);
if (ops.join(',') === 'locate,pose_correct,preprocess,var_calc') ok('project ops chain');
else bad(`project ops ${ops}`);
const pose = proj.steps.find((s) => s.operation === 'pose_correct');
const pp = proj.steps.find((s) => s.operation === 'preprocess');
if (pose && pose.params && pose.params.writeFlowVars && pose.params.resultVar === 'fixture' &&
    pose.params.bindStepId) ok('project pose fixture bind');
else bad(`pose params ${JSON.stringify(pose && pose.params)}`);
if (pp && pp.params.method === 'median' && pp.params.roiMode === 'draw' &&
    Array.isArray(pp.params.roi) && pp.params.roi.length === 4) ok('project preprocess ROI');
else bad(`pp params ${JSON.stringify(pp && pp.params)}`);

console.log(`\n${fail ? 'FAIL' : 'PASS'} ${pass} ok / ${fail} fail`);
process.exit(fail ? 1 : 0);
