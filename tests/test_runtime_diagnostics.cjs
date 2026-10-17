'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const {snapshot}=require('../lib/runtime-diagnostics.cjs'),ui=require('../public/vision/runtime-diagnostics-ui.js'),scripts=require('../lib/script-runner.cjs');
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
function services(){return {runtime:{busy:false,jobs:new Map(),active:null,owner:null,history:{records:[{bytes:1234}],maxRecords:200,maxBytes:268435456,warnings:[]},variables:{secret:'must not leak'}},continuous:{state:{state:'idle'}},mqttTrigger:{state:{state:'stopped',config:{password:'must not leak'}}},cameraSession:{state:{state:'idle',config:{privateKey:'must not leak'}},child:null},plugins:{activeCount:0},vision:{status:()=>({pending:0,children:0,pids:[]})},industrial:{activeCount:()=>0},cameras:{activeCount:()=>0},scripts:{activeCount:()=>0},mqtt:{activeCount:()=>0},socket:{activeCount:()=>0},training:{working:false,job:{secret:'must not leak'}}};}
test('diagnostics reports bounded counts and Node memory without serializing service configuration or user data',()=>{
 const d=snapshot(services());assert(d.process.rssBytes>0);assert(d.process.heapUsedBytes>0);assert.equal(d.runtime.cachedJobs,0);assert.equal(d.history.bytes,1234);assert.equal(d.resources.scriptChildren,0);assert.equal(d.history.recordLimit,200);assert(!JSON.stringify(d).includes('must not leak'));
 const rows=ui.rows(d);assert(rows.some(([k,v])=>k==='Node 进程驻留内存'&&v.endsWith(' MiB')));assert(rows.some(([k,v])=>k==='历史记录数'&&v==='1 / 200'));assert(rows.every(row=>row.length===2));
});
test('actual Python process count includes cancellation cleanup until child close',async()=>{
 const controller=new AbortController(),pending=scripts.run('import time\ndef run(ctx):\n    time.sleep(5)\n    return dict(result={})',{}, {signal:controller.signal,timeoutMs:10000});
 assert.equal(scripts.activeCount(),1);controller.abort();await assert.rejects(pending,/取消/);for(let i=0;i<100&&scripts.activeCount();i++)await sleep(10);assert.equal(scripts.activeCount(),0);
 const out=await scripts.run('def run(ctx):\n    return dict(result=dict(ok=True))',{});assert.equal(out.data.result.ok,true);assert.equal(scripts.activeCount(),0);
});
test('diagnostics dialog only reads status, renders rows and clears stale values on failure',async()=>{
 class Element{constructor(tag,text){this.tagName=tag;this.textContent=text??'';this.children=[];}append(...children){this.children.push(...children);}replaceChildren(...children){this.children=[...children];}setAttribute(){}showModal(){this.open=true;}close(){this.open=false;}}
 const help=new Element('dialog'),body=new Element('body'),calls=[];let failing=false;
 const find=(root,id)=>root.id===id?root:root.children.map(c=>find(c,id)).find(Boolean);
 const ctx=vm.createContext({document:{body},formEl:(tag,text)=>new Element(tag,text),$:id=>id==='help-dialog'?help:find(body,id)||find(help,id),safe:fn=>fn,api:async route=>{calls.push(route);if(failing)throw Error('connection lost');return snapshot(services());}});
 vm.runInContext(fs.readFileSync(path.join(__dirname,'../public/vision/runtime-diagnostics-ui.js'),'utf8'),ctx);vm.runInContext('initDiagnosticsUI()',ctx);
 const open=find(help,'diagnostics-open');await open.onclick();const dialog=find(body,'diagnostics-dialog'),table=dialog.children.find(e=>e.tagName==='table'),rows=table.children[0];assert(dialog.open);assert(rows.children.length>20);assert.deepEqual(calls,['diagnostics']);
 const refresh=dialog.children.find(e=>e.textContent==='刷新状态');failing=true;await assert.rejects(refresh.onclick(),/connection lost/);assert.equal(rows.children.length,0);assert.equal(refresh.disabled,false);assert(dialog.children.some(e=>e.textContent==='读取失败：connection lost'));dialog.children.find(e=>e.textContent==='关闭').onclick();assert.equal(dialog.open,false);
});
test('soak configuration validates limits and projects keep simulated devices and bounded history inputs',()=>{
 const soak=require('../scripts/soak-runtime.cjs'),graph=require('../public/vision/flow-graph.js');
 for(const args of [['--cycles','4'],['--cycles','20','--warmup','20'],['--unknown','1'],['--max-rss-growth-mib','1']])assert.throws(()=>soak.options(args));
 for(const mode of ['completed','failed','cancelled']){const p=graph.normalize(soak.project('owned-session',mode));assert.equal(p.steps[0].params.driver,'session');assert.equal(p.steps.find(s=>s.id==='write').params.transport,'simulator');assert.equal(p.hmi.components[0].capacity,20);}
});
