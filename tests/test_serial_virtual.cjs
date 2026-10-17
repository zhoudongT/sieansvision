'use strict';
const assert=require('node:assert/strict'),path=require('node:path'),{spawn}=require('node:child_process'),{once}=require('node:events');
const io=require('../lib/industrial-client.cjs');
const client=process.env.SIEANS_TEST_SERIAL_CLIENT,peer=process.env.SIEANS_TEST_SERIAL_PEER;
if(process.platform!=='win32'||!/^COM[1-9]\d*$/.test(client??'')||!/^COM[1-9]\d*$/.test(peer??'')||client===peer)throw Error('Explicit Windows virtual pair ports required in SIEANS_TEST_SERIAL_CLIENT / PEER');
const root=path.resolve(__dirname,'..'),child=spawn(path.join(root,'.venv/Scripts/python.exe'),['-u','tests/serial_virtual_peer.py',client,peer],{cwd:root,windowsHide:true});
let log='';child.stdout.on('data',b=>log+=b);child.stderr.on('data',b=>log+=b);
const pause=ms=>new Promise(r=>setTimeout(r,ms));
const run=p=>io.run({operation:'serial_exchange',params:{connection:'device',serialPort:client,baudrate:115200,dataBits:8,parity:'N',stopbits:1,flowControl:'none',rts:false,dtr:false,clearInput:true,timeoutMs:1500,...p}});
async function main(){
 for(let i=0;i<100&&!log.includes('READY');i++){if(child.exitCode!==null)throw Error(log);await pause(20);}assert(log.includes('READY'),log);
 assert.equal((await run({value:'SCAN'})).result.value,'SIEANS 虚拟串口 42');
 const measured=await run({value:'MEASURE',responseEncoding:'structured'});assert.deepEqual(measured.result.value,{count:3,width:12.5,passed:true});assert.equal(measured.result.simulated,false);assert.equal(measured.result.sentEncoding,'text');assert.equal(measured.result.encoding,'structured');
 const binary=await run({encoding:'bytes',value:[66,73,78,65,82,89],txFraming:'crlf',rxFraming:'length32le'});assert.deepEqual(binary.result.value,[0,128,255]);
 const controller=new AbortController(),pending=io.run({operation:'serial_exchange',params:{connection:'device',serialPort:client,value:'WAIT',timeoutMs:5000}},{signal:controller.signal});
 await assert.rejects(io.run({operation:'modbus_read',params:{transport:'rtu',serialPort:client,timeoutMs:1000}}),/正在使用/);
 for(let i=0;i<100&&!log.includes('RECEIVED WAIT');i++)await pause(10);assert(log.includes('RECEIVED WAIT'),log);controller.abort();await assert.rejects(pending,/取消/);
 for(let i=0;i<100&&io.activeCount();i++)await pause(10);assert.equal(io.activeCount(),0);assert.equal((await run({value:'SCAN'})).result.value,'SIEANS 虚拟串口 42');
 await assert.rejects(run({value:'WAIT',timeoutMs:100}),/超时/);
 console.log('PASS: Windows ELTIMA '+client+' <-> '+peer+' driver transactions, fragmented UTF-8/length header, binary values, RTU port lock, cancellation/reopen and timeout; no physical device tested');
}
main().catch(e=>{console.error(e,log);process.exitCode=1;}).finally(async()=>{await io.stop();if(child.exitCode===null){const ended=once(child,'exit');child.kill();await ended;}});
