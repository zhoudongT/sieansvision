'use strict';
const {test,after}=require('node:test'),assert=require('node:assert/strict'),net=require('node:net'),dgram=require('node:dgram');
const fs=require('node:fs'),os=require('node:os'),path=require('node:path'),{once}=require('node:events');
const io=require('../lib/socket-client.cjs'),sim=require('../lib/socket-simulator.cjs'),industrial=require('../lib/industrial-client.cjs');
const {Runtime}=require('../lib/runtime.cjs'),graph=require('../public/vision/flow-graph.js');
const run=(params={},signal,udp=false)=>io.run({operation:udp?'udp_exchange':'tcp_exchange',params:{connection:'simulator',encoding:'text',value:'工件 OK',timeoutMs:1500,...params}},{signal});
async function tcp(handler){const sockets=new Set(),server=net.createServer(socket=>{sockets.add(socket);socket.on('error',()=>{});socket.on('close',()=>sockets.delete(socket));handler(socket);});server.listen(0,'127.0.0.1');await once(server,'listening');return {connection:'device',host:'127.0.0.1',port:server.address().port,close:async()=>{const done=new Promise(r=>server.close(r));sockets.forEach(s=>s.destroy());await done;}};}
async function udp(){const s=dgram.createSocket('udp4');s.bind(0,'127.0.0.1');await once(s,'listening');return s;}
after(()=>io.stop());
test('real echo TCP framing and UDP round trip preserve text, structured values, bytes and empty payloads',async()=>{
 const [a,b]=await Promise.all([sim.start(),sim.start()]);assert.equal(a.tcpPort,b.tcpPort);assert.equal(a.udpPort,b.udpPort);
 for(const framing of ['lf','crlf','nul','length16be','length16le','length32be','length32le'])for(const [encoding,value] of [['text','中文✓'],['structured',{count:3,passed:true,items:[{x:1.2}]}],['bytes',[128,255,1]],['text','']]){
  const out=await run({txFraming:framing,rxFraming:framing,encoding,value});assert.deepEqual(out.result.value,value);assert.equal(out.result.simulated,true);assert.equal(out.result.delivery,'received');assert.equal(out.result.acknowledged,false);
 }
 for(const [encoding,value] of [['text','中文\n'],['structured',null],['bytes',[0,255,128]],['text','']])assert.deepEqual((await run({encoding,value},null,true)).result.value,value);
 assert.equal((await run({txFraming:'raw',rxFraming:'eof',value:'end'})).result.value,'end');assert.equal((await run({txFraming:'raw',rxFraming:'fixed',responseBytes:4,value:'ABCD'})).result.value,'ABCD');
 assert(sim.status().receivedBytes>0);
});
test('TCP fragmented UTF-8, delimiters and length headers; coalesced frames never merged',async()=>{
 for(const framing of ['crlf','length16be','length32le']){
  const payload=Buffer.from('定位成功'),wire=io.framePayload(payload,framing);const server=await tcp(s=>s.once('data',()=>{s.write(wire.subarray(0,1));setTimeout(()=>{if(!s.destroyed)s.write(wire.subarray(1,4));},10);setTimeout(()=>{if(!s.destroyed)s.end(Buffer.concat([wire.subarray(4),wire]));},20);}));
  try{const out=await run({...server,txFraming:'raw',rxFraming:framing});assert.equal(out.result.value,'定位成功');assert.equal(out.result.trailingBytes,wire.length);}finally{await server.close();}
 }
});
test('partial frames, oversize headers, invalid encoding and limits reject without hanging or leaking slots',async()=>{
 for(const [bytes,p,expected] of [[Buffer.from('ABC'),{rxFraming:'crlf'},/完整报文/],[Buffer.from([0,10,1]),{rxFraming:'length16be',maxBytes:3},/上限/],[Buffer.from([255,10]),{rxFraming:'lf'},/UTF-8/],[Buffer.from('bad\n'),{rxFraming:'lf',encoding:'structured',value:1},/结构化/],[Buffer.from('ABCD'),{rxFraming:'eof',maxBytes:3},/上限/]]){
  const server=await tcp(s=>s.once('data',()=>s.end(bytes)));try{await assert.rejects(run({...server,...p}),expected);assert.equal(io.activeCount(),0);}finally{await server.close();}
 }
 await assert.rejects(run({value:'a\r\nb'}),/结束符/);
 for(const params of [{mode:'bad'},{timeoutMs:99},{maxBytes:0},{encoding:'hex'},{connection:'device',host:'http://localhost'},{rxFraming:'fixed',responseBytes:5,maxBytes:4},{mode:'receive'},{value:'\ud800'},{encoding:'bytes',value:[256]},{txFraming:'length16be',rxFraming:'length16be',value:'x'.repeat(65536)}])await assert.rejects(run(params));
 await assert.rejects(run({value:'x'.repeat(65508)},null,true),/65507/);await assert.rejects(run({maxBytes:1,value:'AB'},null,true),/上限/);
});
test('send only reports sent, TCP receive connects without writing; cancellation, deadline and endpoint lock',async()=>{
 let accepted;const connected=new Promise(r=>accepted=r),server=await tcp(s=>accepted(s));
 try{
  const controller=new AbortController(),pending=run({...server,mode:'receive',timeoutMs:3000},controller.signal);const socket=await connected;let bytes=0;socket.on('data',b=>bytes+=b.length);
  await assert.rejects(run({...server,mode:'receive'}),/正在使用/);controller.abort();await assert.rejects(pending,/取消/);assert.equal(bytes,0);assert.equal(io.activeCount(),0);
  await assert.rejects(run({...server,timeoutMs:100}),/超时.*不能回滚/);assert.equal(io.activeCount(),0);
 }finally{await server.close();}
 const push=await tcp(s=>s.end('SCAN-123\r\n'));try{assert.equal((await run({...push,mode:'receive'})).result.value,'SCAN-123');}finally{await push.close();}
 for(const isUdp of [false,true]){const out=await run({mode:'send',value:'ABC'},null,isUdp);assert.equal(out.result.delivery,'sent');assert.equal(out.result.acknowledged,false);}
 const cancelled=new AbortController();cancelled.abort();await assert.rejects(run({},cancelled.signal),/取消/);
});
test('UDP receive binds a local port and ignores datagrams from the wrong source; deadlines and bind conflicts',async()=>{
 const peer=await udp(),other=await udp(),reservation=await udp(),port=reservation.address().port;reservation.close();await once(reservation,'close');
 const p={connection:'device',mode:'receive',host:'127.0.0.1',port:peer.address().port,localAddress:'127.0.0.1',localPort:port,timeoutMs:1500};
 const pending=run(p,null,true);const sender=setInterval(()=>{other.send('WRONG',port,'127.0.0.1');peer.send('RIGHT',port,'127.0.0.1');},20);
 try{assert.equal((await pending).result.value,'RIGHT');}finally{clearInterval(sender);}
 await assert.rejects(run({...p,timeoutMs:100},null,true),/超时/);
 await assert.rejects(run({...p,localPort:other.address().port},null,true),/UDP/);
 await assert.rejects(run({...p,localPort:0},null,true),/本地 UDP/);
 peer.close();other.close();assert.equal(io.activeCount(),0);
});
test('runtime preserves image and point cloud, typed bindings commit and failed communication rolls back',async()=>{
 const directory=fs.mkdtempSync(path.join(os.tmpdir(),'sieans-socket-test-')),runtime=new Runtime(directory,{});
 const project=graph.normalize({version:1,id:'socket-vars',name:'Socket',variables:{reply:0},variableTypes:{reply:'integer'},steps:[{id:'io',operation:'tcp_exchange',params:{connection:'simulator',encoding:'structured',value:3}},{id:'save',operation:'variables',params:{scope:'flow',name:'reply',value:{$ref:'results.io.value'}}}]});
 const cloud={points:[[1,2,3]],unit:'mm'},job=runtime.start({project,cloud});await runtime.jobs.get(job.id).promise;const result=runtime.poll(job.id);assert.equal(result.state,'completed',result.error);assert.equal(result.variables.flow.reply,3);assert.deepEqual(result.results[1].output.cloud,cloud);
 project.steps[0].params.value='bad';const bad=runtime.start({project,cloud});await runtime.jobs.get(bad.id).promise;assert.equal(runtime.poll(bad.id).state,'failed');assert.equal(runtime.variables.snapshot(project).flow.reply,3);
 assert(industrial.operations.has('tcp_exchange'));assert(industrial.operations.has('udp_exchange'));
});
test('inactive settings and missing bindings are ignored after changing communication mode',async()=>{
 const runtime=new Runtime(fs.mkdtempSync(path.join(os.tmpdir(),'sieans-socket-modes-')),{}),server=await tcp(s=>s.end('READY\r\n'));
 const missing={$ref:'flow.missing'};
 try{
  const project=graph.normalize({version:1,id:'socket-hidden',name:'Mode switch',steps:[{id:'io',operation:'tcp_exchange',params:{...server,close:undefined,mode:'receive',value:missing,txFraming:missing,responseBytes:missing,localPort:missing}}]});
  const start=runtime.start({project});await runtime.jobs.get(start.id).promise;const job=runtime.poll(start.id);assert.equal(job.state,'completed',job.error);assert.equal(job.results[0].output.result.value,'READY');
  project.steps[0].params={connection:'simulator',mode:'send',encoding:'structured',value:{ok:true},host:missing,port:missing,maxBytes:missing,rxFraming:missing,responseBytes:missing};
  const send=runtime.start({project});await runtime.jobs.get(send.id).promise;assert.equal(runtime.poll(send.id).state,'completed',runtime.poll(send.id).error);
 }finally{await server.close();}
});
