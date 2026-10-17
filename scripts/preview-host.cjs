'use strict';
// A development-only supervisor for its own child. No remote shutdown endpoint or PID attachment.
const {fork}=require('node:child_process'),path=require('node:path'),readline=require('node:readline');
const {PREVIEW_STOP_MS}=require('../lib/process-supervisor.cjs');
const root=path.resolve(__dirname,'..'),port=Number(process.argv[2]||1919),data=path.resolve(process.argv[3]||path.join(root,'artifacts/hmi-pages-preview-data'));
if(!Number.isInteger(port)||port<1024||port>65535)throw Error('Preview port must be 1024–65535');
let child=null,operation=Promise.resolve(),ending=false;
function start(){if(child)throw Error('Preview child still owns the port');const launched=fork(path.join(root,'server.cjs'),[],{cwd:root,windowsHide:true,stdio:['ignore','inherit','inherit','ipc'],env:{...process.env,HOST:'127.0.0.1',PORT:String(port),MACHINE_DATA_DIR:data}});child=launched;launched.once('exit',code=>{if(child===launched)child=null;process.stdout.write('Preview child exited: '+code+'\n');});}
async function stop(){
 const current=child;if(!current)return;
 await new Promise((resolve,reject)=>{const timeout=setTimeout(()=>{current.off('exit',finished);reject(Error('Preview is still stopping; no replacement was started'));},PREVIEW_STOP_MS);const finished=()=>{clearTimeout(timeout);resolve();};current.once('exit',finished);if(current.connected)current.send({type:'sieans-shutdown'});else{clearTimeout(timeout);current.off('exit',finished);reject(Error('Owned preview IPC is unavailable'));}});
}
const input=readline.createInterface({input:process.stdin});
input.on('line',line=>{operation=operation.then(async()=>{const command=line.trim();if(command==='restart'){await stop();if(!ending)start();}else if(command==='stop'){ending=true;await stop();input.close();process.exit(0);}else if(command==='status')process.stdout.write('Owned preview: '+(child?'running PID '+child.pid:'stopped')+'; http://127.0.0.1:'+port+'/vision/\n');else if(command)process.stdout.write('Commands: status, restart, stop\n');}).catch(error=>process.stderr.write(error.message+'\n'));});
process.on('SIGINT',()=>{ending=true;stop().then(()=>process.exit(0)).catch(error=>process.stderr.write(error.message+'\n'));});
process.stdout.write('Managed preview http://127.0.0.1:'+port+'/vision/\nCommands: status, restart, stop\n');start();
