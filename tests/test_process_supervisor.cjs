const {test}=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),os=require('node:os'),{fork}=require('node:child_process'),{once,EventEmitter}=require('node:events');
const {supervise,SHUTDOWN_GRACE_MS,SERVICE_STOP_SECONDS}=require('../lib/process-supervisor.cjs');
async function fixture(code){
 const dir=fs.mkdtempSync(path.join(os.tmpdir(),'sieans-supervisor-')),script=path.join(dir,'worker.cjs');fs.writeFileSync(script,code);
 const child=fork(script,[dir],{windowsHide:true,stdio:['ignore','ignore','ignore','ipc']}),ready=once(child,'message'),closed=once(child,'exit');
 await ready;const control=new EventEmitter();control.send=()=>{};return {child,dir,control,closed};
}
test('graceful shutdown allows a real child to finish cleanup beyond the previous ten-second deadline',async()=>{
 assert(SHUTDOWN_GRACE_MS>32000);assert(SERVICE_STOP_SECONDS*1000>SHUTDOWN_GRACE_MS);
 const f=await fixture("const fs=require('node:fs'),path=require('node:path');process.on('message',m=>{if(m.type==='sieans-shutdown')setTimeout(()=>{fs.writeFileSync(path.join(process.argv[2],'released'),'done');process.exit(0)},11000)});process.send('ready');");
 try{
  const done=supervise(f.child,{control:f.control});f.control.emit('message',{type:'sieans-shutdown'});await done;
  assert.equal(fs.readFileSync(path.join(f.dir,'released'),'utf8'),'done');assert.equal(f.child.exitCode,0);
  assert.equal(f.control.listenerCount('message'),0);assert.equal(f.control.listenerCount('SIGTERM'),0);
 }finally{if(f.child.exitCode===null&&f.child.signalCode===null)f.child.kill('SIGKILL');await f.closed;}
});
test('an unresponsive owned child is force-ended at its deadline even if it handles SIGTERM',async()=>{
 const f=await fixture("process.on('SIGTERM',()=>{});process.on('message',()=>{});setInterval(()=>{},1000);process.send('ready');");
 try{
  const done=supervise(f.child,{control:f.control,graceMs:100});const rejected=assert.rejects(done,/服务退出/);
  f.control.emit('SIGTERM');await rejected;await f.closed;assert(f.child.signalCode||f.child.exitCode!==0);
  assert.equal(f.control.listenerCount('disconnect'),0);
 }finally{if(f.child.exitCode===null&&f.child.signalCode===null)f.child.kill('SIGKILL');await f.closed;}
});
