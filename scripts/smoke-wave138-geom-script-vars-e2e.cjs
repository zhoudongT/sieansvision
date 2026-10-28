#!/usr/bin/env node
/** wave138: line_angle / point_circle / circle_circle + csharp inject/writeback soft. */
'use strict';
const path = require('path');
const ROOT = path.resolve(__dirname, '..');
const fc = require(path.join(ROOT, 'lib/flow-control.cjs'));
let pass = 0, fail = 0;
const ok = (m) => { pass++; console.log('PASS:', m); };
const bad = (m) => { fail++; console.log('FAIL:', m); };

const ctx = { flow: {}, module: {}, global: {}, results: new Map(), steps: [] };

// --- line_angle 90deg ---
ctx.flow = {};
let r = fc.lineAngle({
  mode: 'manual', x1: 0, y1: 0, x2: 100, y2: 0, x3: 0, y3: 0, x4: 0, y4: 100,
  judgeEnable: true, judgeMin: 85, judgeMax: 95,
  resultVar: 'lineAngle', writeFlowVars: true,
}, ctx);
if (Math.abs(r.angleDeg - 90) < 1e-6 && r.perpendicular === true && r.judgeOk === true)
  ok(`line_angle 90deg=${r.angleDeg}`);
else bad(`line_angle ${JSON.stringify(r)}`);
if (ctx.flow.lineAngle === 90 && ctx.flow.lineAngle_angleDeg === 90)
  ok('line_angle flow vars');
else bad(`line_angle flow ${JSON.stringify(ctx.flow)}`);

// parallel
ctx.flow = {};
r = fc.lineAngle({
  mode: 'manual', x1: 0, y1: 0, x2: 10, y2: 0, x3: 0, y3: 5, x4: 10, y4: 5,
  resultVar: 'la2', writeFlowVars: true,
}, ctx);
if (r.parallel === true && Math.abs(r.angleDeg) < 1e-6) ok(`line_angle parallel ${r.angleDeg}`);
else bad(`parallel ${JSON.stringify(r)}`);

// --- point_circle edge ---
ctx.flow = {};
r = fc.pointCircleDistance({
  mode: 'manual', px: 50, py: 50, cx: 0, cy: 0, radius: 30, circleMode: 'edge',
  scale: 1, judgeEnable: true, judgeMin: 40, judgeMax: 50,
  resultVar: 'pointCircle', writeFlowVars: true,
}, ctx);
const expectEdge = Math.hypot(50, 50) - 30;
if (Math.abs(r.distance - expectEdge) < 1e-6 && r.inside === false && r.judgeOk)
  ok(`point_circle edge d=${r.distance.toFixed(4)}`);
else bad(`point_circle edge ${JSON.stringify(r)}`);
if (Number.isFinite(ctx.flow.pointCircle_centerDist) && ctx.flow.pointCircle_ok === 1)
  ok('point_circle flow vars');
else bad(`pc flow ${JSON.stringify(ctx.flow)}`);

// signed inside
r = fc.pointCircleDistance({
  mode: 'manual', px: 0, py: 0, cx: 0, cy: 0, radius: 10, circleMode: 'signed',
}, ctx);
if (r.signed < 0 && r.inside === true) ok(`point_circle signed inside ${r.signed}`);
else bad(`signed ${JSON.stringify(r)}`);

// --- circle_circle gap ---
ctx.flow = {};
r = fc.circleCircleDistance({
  mode: 'manual', cx1: 0, cy1: 0, r1: 10, cx2: 40, cy2: 0, r2: 10, circleMode: 'gap',
  judgeEnable: true, judgeMin: 15, judgeMax: 25,
  resultVar: 'circleGap', writeFlowVars: true,
}, ctx);
if (Math.abs(r.distance - 20) < 1e-6 && r.separate === true && r.judgeOk)
  ok(`circle_circle gap=${r.distance}`);
else bad(`cc gap ${JSON.stringify(r)}`);
if (ctx.flow.circleGap_gap === 20 && ctx.flow.circleGap_centerDist === 40)
  ok('circle_circle flow vars');
else bad(`cc flow ${JSON.stringify(ctx.flow)}`);

// overlapping
r = fc.circleCircleDistance({
  mode: 'manual', cx1: 0, cy1: 0, r1: 20, cx2: 10, cy2: 0, r2: 20, circleMode: 'gap',
}, ctx);
if (r.overlapping === true && r.gap < 0) ok(`circle_circle overlap gap=${r.gap}`);
else bad(`overlap ${JSON.stringify(r)}`);

// --- csharpScript inject + writeback ---
ctx.flow = { myIn: 42 };
ctx.global = { gFlag: 1 };
r = fc.csharpScript({
  language: 'csharp',
  code: 'public class Script { public void Run(){} }',
  entry: 'Script.Run',
  inputs: [{ name: 'recStr', type: 'string', bind: 'flow.myIn' }, { name: 'flag', bind: 'global.gFlag' }],
  outputs: [{ name: 'out0', type: 'string' }, { name: 'out1', type: 'string' }],
  writeOutputVars: true,
}, ctx);
if (r.status === 'unsupported' && r.injected.recStr === 42 && r.injected.flag === 1)
  ok(`csharp inject ${JSON.stringify(r.injected)}`);
else bad(`csharp inject ${JSON.stringify(r)}`);
if (ctx.flow.script_out0 === 42 || 'script_out0' in ctx.flow)
  ok(`csharp written ${JSON.stringify(r.written)}`);
else bad(`csharp written ${JSON.stringify(r.written)} flow=${JSON.stringify(ctx.flow)}`);
if (Number.isFinite(r.bytes) && r.bytes > 10) ok(`csharp bytes=${r.bytes}`);
else bad(`bytes ${r.bytes}`);

console.log(`\n${fail ? 'FAIL' : 'PASS'} ${pass} ok / ${fail} fail`);
process.exit(fail ? 1 : 0);
