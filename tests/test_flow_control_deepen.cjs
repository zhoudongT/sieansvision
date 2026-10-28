'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const control = require('../lib/flow-control.cjs');

const np = control.ninePoint({
  points: [
    {index:1,enabled:true,pixelX:0,pixelY:0,worldX:10,worldY:20},
    {index:2,enabled:true,pixelX:100,pixelY:0,worldX:110,worldY:20},
    {index:3,enabled:true,pixelX:0,pixelY:100,worldX:10,worldY:120},
  ],
});
assert.equal(np.status, 'ok');
assert.ok(np.rms < 1e-9);
assert.ok(Math.abs(np.transform[2] - 10) < 1e-6);
assert.ok(Math.abs(np.transform[5] - 20) < 1e-6);

const fd = control.formatData({template:'A={0};x={x}', args:'hi,x', targetVar:'out'}, {global:{},flow:{x:2},module:{}});
assert.equal(fd.formatted, 'A=hi;x=2');

const pp = control.protocolParse({protocol:'fixed', pattern:'a:2,b:2', sourceVar:'recvData'}, {global:{},flow:{recvData:'WXYZ'},module:{}});
assert.deepEqual(pp.fields, {a:'WX', b:'YZ'});

const tmp = path.join(os.tmpdir(), 'sieans-deepen-text.txt');
const ts = control.textSave({path:tmp, content:'row1', append:false}, {global:{},flow:{},module:{}});
assert.equal(ts.status, 'ok');
assert.equal(fs.readFileSync(tmp,'utf8').trim(), 'row1');

const png = 'data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==';
const outDir = path.join(os.tmpdir(), 'sieans-deepen-img');
fs.mkdirSync(outDir, {recursive:true});
const oi = control.outputImage({path:outDir + path.sep, format:'png', useTimestamp:false}, {image:png});
assert.equal(oi.status, 'ok');
assert.ok(fs.existsSync(oi.path));

const dc = control.distortCorrect({mode:'file', calibPath:''}, {});
assert.equal(dc.status, 'uncalibrated');

const cs = control.csharpScript({language:'csharp', code:'//'});
assert.equal(cs.status, 'unsupported');


// deepen: format trim / onEmpty
const fd2 = control.formatData({template:'  {0}  ', args:'hi', targetVar:'out', trim:true}, {global:{},flow:{},module:{}});
assert.equal(fd2.formatted, 'hi');
const fd3 = control.formatData({template:'', args:'', targetVar:'out', onEmpty:'default', emptyDefault:'N/A'}, {global:{},flow:{},module:{}});
assert.equal(fd3.formatted, 'N/A');
const fd4 = control.formatData({template:'', args:'', targetVar:'out', onEmpty:'skip'}, {global:{},flow:{},module:{}});
assert.equal(fd4.status, 'skipped_empty');

// deepen: protocol fixedWidths
const pp2 = control.protocolParse({protocol:'fixed', fixedWidths:'2,2', fields:'a,b', sourceVar:'recvData'}, {global:{},flow:{recvData:'WXYZ'},module:{}});
assert.deepEqual(pp2.fields, {a:'WX', b:'YZ'});

// deepen: textSave bom + timestampPrefix
const tmp2 = path.join(os.tmpdir(), 'sieans-deepen-text-bom.txt');
const ts2 = control.textSave({path:tmp2, content:'row', append:false, bom:true, timestampPrefix:true}, {global:{},flow:{},module:{}});
assert.equal(ts2.status, 'ok');
assert.equal(ts2.bom, true);
const body2 = fs.readFileSync(tmp2);
assert.ok(body2[0]===0xEF && body2[1]===0xBB && body2[2]===0xBF);

// deepen: outputImage onlyOnOk + filePrefix
const outDir2 = path.join(os.tmpdir(), 'sieans-deepen-img2');
fs.mkdirSync(outDir2, {recursive:true});
const oiSkip = control.outputImage({path:outDir2 + path.sep, format:'png', useTimestamp:false, onlyOnOk:true, okVar:'passGate', filePrefix:'shot'}, {image:png}, {global:{},flow:{passGate:0},module:{}});
assert.equal(oiSkip.status, 'skipped_ng');
const oiOk = control.outputImage({path:outDir2 + path.sep, format:'png', useTimestamp:false, onlyOnOk:true, okVar:'passGate', filePrefix:'shot'}, {image:png}, {global:{},flow:{passGate:1},module:{}});
assert.equal(oiOk.status, 'ok');
assert.ok(String(oiOk.path).includes('shot'));


console.log('test_flow_control_deepen: ok');
