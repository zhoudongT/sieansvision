#!/usr/bin/env node
/** Measure geom judge + resultVar flow write + inject scalars. */
'use strict';
const path = require('path');
const ROOT = path.resolve(__dirname, '..');
const fc = require(path.join(ROOT, 'lib/flow-control.cjs'));
let pass = 0, fail = 0;
const ok = (m) => { pass++; console.log('PASS:', m); };
const bad = (m) => { fail++; console.log('FAIL:', m); };

const ctx = { flow: {}, module: {}, global: {}, results: new Map(), steps: [] };

// point distance in range
let r = fc.pointDistance({
  mode: 'manual', x1: 0, y1: 0, x2: 30, y2: 40, scale: 1, unit: 'px',
  judgeEnable: true, judgeMin: 40, judgeMax: 60,
  resultVar: 'pdLive', writeFlowVars: true,
}, ctx);
if (r.distance === 50 && r.judgeOk === true && r.judgeStatus === 'OK') ok(`pd in-range d=${r.distance}`);
else bad(`pd in-range ${JSON.stringify(r)}`);
if (ctx.flow.pdLive === 50 && ctx.flow.pdLive_distance === 50 && ctx.flow.pdLive_judgeOk === 1)
  ok('pd flow vars written');
else bad(`pd flow ${JSON.stringify(ctx.flow)}`);

// out of range → NG
ctx.flow = {};
r = fc.pointDistance({
  mode: 'manual', x1: 0, y1: 0, x2: 10, y2: 0, scale: 1,
  judgeEnable: true, judgeMin: 40, judgeMax: 60,
  resultVar: 'pd2', writeFlowVars: true,
}, ctx);
if (r.judgeOk === false && r.judgeStatus === 'NG') ok(`pd NG d=${r.distance}`);
else bad(`pd NG ${JSON.stringify(r)}`);

// line intersect
ctx.flow = {};
r = fc.lineIntersect({
  mode: 'manual', x1: 0, y1: 0, x2: 100, y2: 0, x3: 50, y3: -50, x4: 50, y4: 50,
  scale: 1, judgeEnable: true, resultVar: 'ix', writeFlowVars: true,
}, ctx);
if (r.status === 'ok' && r.intersectX === 50 && r.judgeOk === true) ok(`li ix=${r.intersectX}`);
else bad(`li ${JSON.stringify(r)}`);
if (ctx.flow.ix_x === 50 && ctx.flow.ix_y === 0) ok('li flow vars');
else bad(`li flow ${JSON.stringify(ctx.flow)}`);

// point-line
ctx.flow = {};
r = fc.pointLineDistance({
  mode: 'manual', x1: 0, y1: 0, x2: 100, y2: 0, px: 50, py: 30, scale: 1,
  judgeEnable: true, judgeMin: 20, judgeMax: 40, resultVar: 'pld', writeFlowVars: true,
}, ctx);
if (Math.abs(r.distance - 30) < 1e-6 && r.judgeOk) ok(`pld d=${r.distance}`);
else bad(`pld ${JSON.stringify(r)}`);
if (ctx.flow.pld_footY === 0 || ctx.flow.pld_footX === 50) ok('pld foot vars');
else bad(`pld flow ${JSON.stringify(ctx.flow)}`);

// inject resultVar alias for defects-like bag
const steps = [{ id: 'd1', operation: 'defects', params: { resultVar: 'defLive', writeFlowVars: true } }];
const results = new Map([['d1', { result: { count: 3, defectRatio: 0.02, passed: false, judgeOk: false, status: 'ok' } }]]);
// call via varCalc side effect — use internal by running varCalc with empty exprs after stuffing
// Access inject through varCalc env by evaluating expressions that read inject keys
const vc = fc.varCalc({
  scope: 'flow',
  expressions: [
    { name: 'c', expression: 'defects_count' },
    { name: 'r', expression: 'defects_ratio' },
    { name: 'j', expression: 'defects_judgeOk' },
    { name: 'alias', expression: 'defLive_count' },
  ],
}, { flow: {}, module: {}, global: {}, results, steps });
if (vc.values.c === 3 && vc.values.r === 0.02 && vc.values.j === 0 && vc.values.alias === 3)
  ok(`inject+alias ${JSON.stringify(vc.values)}`);
else bad(`inject ${JSON.stringify(vc)}`);

console.log(`\n${fail ? 'FAIL' : 'PASS'} ${pass} ok / ${fail} fail`);
process.exit(fail ? 1 : 0);
