'use strict';
const {test,after}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),os=require('node:os'),path=require('node:path');
const io=require('../lib/industrial-client.cjs'),serial=require('../lib/serial-client.cjs');
const {Runtime}=require('../lib/runtime.cjs'),graph=require('../public/vision/flow-graph.js');
const run=(p={},signal)=>io.run({operation:'serial_exchange',params:{connection:'simulator',timeoutMs:1000,value:'扫码测试',...p}},{signal});
after(()=>io.stop());
test('actual Python pySerial round trips all frame formats and payload types; send-only delivery',async()=>{
 for(const framing of ['lf','crlf','nul','length16be','length16le','length32be','length32le']){
  const value={count:3,passed:true,label:'工件 A'},out=await run({encoding:'structured',value,txFraming:framing,rxFraming:framing});assert.deepEqual(out.result.value,value);assert.equal(out.result.protocol,'Serial');assert.equal(out.result.simulated,true);assert.equal(out.result.acknowledged,false);
 }
 assert.deepEqual((await run({encoding:'bytes',value:[0,128,255],txFraming:'raw',rxFraming:'fixed',responseBytes:3})).result.value,[0,128,255]);
 assert.equal((await run({value:'',txFraming:'length16be',rxFraming:'length16be'})).result.value,'');
 const sent=await run({mode:'send',encoding:'structured',value:{ok:true}});assert.equal(sent.result.delivery,'sent');assert.deepEqual(sent.result.value,{ok:true});assert.equal(sent.result.byteLength,11);
 const mixed=await run({encoding:'text',responseEncoding:'structured',value:'{"count":42}'});assert.deepEqual(mixed.result.value,{count:42});assert.equal(mixed.result.sentEncoding,'text');assert.equal(mixed.result.encoding,'structured');
 await assert.rejects(run({value:'not structured',responseEncoding:'structured'}),/结构化/);
});
test('bad configuration rejected before device access, binary range validation, inactive settings ignored',async()=>{
 for(const p of [{rxFraming:'eof'},{mode:'receive'},{timeoutMs:10001},{encoding:'bytes',value:[-1]},{value:'x'.repeat(4096)},{connection:'device',serialPort:'socket://127.0.0.1:9000'},{connection:'device',serialPort:'COM3',dataBits:9},{connection:'device',serialPort:'COM3',dataBits:7,value:'中文'},{connection:'device',serialPort:'COM3',parity:'bad'},{connection:'device',serialPort:'COM3',rts:1}])await assert.rejects(run(p));
 const prepared=serial.prepare({connection:'simulator',serialPort:{bad:true},mode:'send',maxBytes:{bad:true},rxFraming:{bad:true},value:'A'});assert.equal(prepared.serialPort,'loop://');assert.equal(prepared.maxBytes,65536);
 if(process.platform==='win32'){assert.equal(serial.prepare({connection:'device',serialPort:'COM3',mode:'receive',responseEncoding:'bytes',encoding:{$ref:'flow.missing'}}).responseEncoding,'bytes');assert.equal(serial.portKey('COM7'),serial.portKey('com7'));assert.equal(serial.portKey('COM7'),serial.portKey('\\\\.\\COM7'));assert.equal(serial.portKey('COM7'),serial.portKey('COM007'));}
});
test('serial and Modbus RTU share an endpoint lock; cancellation releases it after worker exit',async()=>{
 const controller=new AbortController(),pending=run({value:'INCOMPLETE',txFraming:'raw',rxFraming:'crlf',timeoutMs:5000},controller.signal);
 await assert.rejects(run(),/正在使用/);
 await assert.rejects(io.run({operation:'modbus_read',params:{transport:'rtu',serialPort:'loop://',timeoutMs:500}}),/正在使用/);
 controller.abort();await assert.rejects(pending,/取消/);
 for(let i=0;i<100&&io.activeCount();i++)await new Promise(r=>setTimeout(r,10));assert.equal(io.activeCount(),0);
 assert.equal((await run({value:'NEXT'})).result.value,'NEXT');
 await assert.rejects(run({value:'PART',txFraming:'raw',rxFraming:'crlf',timeoutMs:100}),/超时.*不能回滚/);
 await assert.rejects(run({},AbortSignal.abort()),/取消/);
});
test('runtime binds serial output to all three scopes, keeps frames, and rolls back on timeout',async()=>{
 const runtime=new Runtime(fs.mkdtempSync(path.join(os.tmpdir(),'sieans-serial-')),{});
 const steps=[{id:'serial',operation:'serial_exchange',params:{connection:'simulator',encoding:'structured',value:{count:3}}},...['global','flow','module'].map((scope,i)=>({id:'var'+i,operation:'variables',params:{scope,name:'serialCount',value:{$ref:'results.serial.value.count'}}}))];
 const project=graph.normalize({version:1,id:'serial-vars',name:'Serial',steps}),cloud={points:[[1,2,3]],unit:'mm'},start=runtime.start({project,cloud});await runtime.jobs.get(start.id).promise;const done=runtime.poll(start.id);assert.equal(done.state,'completed',done.error);assert.equal(done.variables.global.serialCount,3);assert.equal(done.variables.flow.serialCount,3);assert.equal(done.variables.modules.var2.serialCount,3);assert.deepEqual(done.results[3].output.cloud,cloud);
 const bad=graph.normalize({...project,version:1,steps:[{id:'before',operation:'variables',params:{scope:'flow',name:'serialCount',value:7}},{id:'timeout',operation:'serial_exchange',params:{connection:'simulator',value:'WAIT',txFraming:'raw',rxFraming:'crlf',timeoutMs:100}}]});
 const startBad=runtime.start({project:bad});await runtime.jobs.get(startBad.id).promise;assert.equal(runtime.poll(startBad.id).state,'failed');assert.equal(runtime.variables.snapshot(project).flow.serialCount,3);
 project.steps[0].params={connection:'simulator',mode:'send',value:'OK',serialPort:{$ref:'flow.missing'},rxFraming:{$ref:'flow.missing'},maxBytes:{$ref:'flow.missing'}};project.steps=project.steps.slice(0,1);project.edges=project.edges.slice(0,1);const hidden=runtime.start({project});await runtime.jobs.get(hidden.id).promise;assert.equal(runtime.poll(hidden.id).state,'completed',runtime.poll(hidden.id).error);
});
