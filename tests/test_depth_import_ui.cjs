'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs'),path=require('node:path');
const script=fs.readFileSync(path.join(__dirname,'../public/vision/depth-ui.js'),'utf8');
function harness(){
 const elements=new Map(),get=id=>{if(!elements.has(id))elements.set(id,{value:'',checked:false,disabled:false,files:[],textContent:'',hidden:false,checkValidity(){return this.value!=='';},getAttribute(){return id;},removeAttribute(){this.src='';},close(){this.closed=true;}});return elements.get(id);};
 const context=vm.createContext({$:get,source:'old-image',sourceCloud:{old:true},project:{id:'project'},originalImage:{old:true},inputPreviewEpoch:0,inputPreviewData:'old',inputPreviewImage:{old:true},framePreviews:new Map([['old','old']]),ctx:{clearRect(){}},canvas:{width:100,height:100},results:[],displayedResultId:'',running:false,refreshInputPreview(){},setImageView(){},setBusy(){},status(){},readFile:async()=>'data:application/octet-stream;base64,AAAA',safe:fn=>fn,Number,Error});
 vm.runInContext(script,context);context.setSourceCloud=(cloud,depth)=>{context.sourceCloud=cloud;context.nextDepth=depth;vm.runInContext('sourceDepth=nextDepth',context);};
 return {context,get};
}
function fields(h){for(const [key,value]of Object.entries({fx:100,fy:200,cx:31.5,cy:23.5,scale:.1,min:100,max:2000,stride:2,invalid:65535,frame:'optical'}))h.get('depth-import-'+key).value=String(value);h.get('depth-import-confirm').checked=true;}

test('depth form converts visible millimeters to meters and keeps explicit calibration',()=>{
 const h=harness();fields(h);const p=vm.runInContext('depthImportParams()',h.context);assert.equal(p.scaleMeters,.0001);assert.equal(p.minDepth,.1);assert.equal(p.maxDepth,2);assert.equal(p.fx,100);assert.equal(p.projection,'rectified-z');
 h.get('depth-import-fx').value='';assert.throws(()=>vm.runInContext('depthImportParams()',h.context),/有效的深度参数/);fields(h);h.get('depth-import-confirm').checked=false;assert.throws(()=>vm.runInContext('depthImportParams()',h.context),/确认/);
});

test('successful import changes all source channels together and failed import preserves original input',async()=>{
 const h=harness();fields(h);const result={cloud:{points:[[0,0,1000]],unit:'mm'},depth:{width:4,height:3,preview:'preview',scaleMeters:.001,minMeters:.1,maxMeters:2}};
 h.get('depth-import-file').files=[{name:'raw.png',size:100}];h.context.api=async(route,options)=>{assert.equal(JSON.parse(options.body).content,'data:image/png;base64,AAAA');return result;};vm.runInContext('initDepthImportUI()',h.context);await h.get('depth-import-form').onsubmit({preventDefault(){}});
 assert.equal(h.context.source,'');assert.equal(h.context.originalImage,null);assert.equal(h.context.sourceCloud,result.cloud);assert.equal(h.context.nextDepth,result.depth);assert.equal(h.get('cloud-dialog').closed,true);assert.equal(h.context.framePreviews.size,0);
 const old=h.context.sourceCloud;h.context.api=async()=>{throw Error('invalid PNG');};await assert.rejects(h.get('depth-import-form').onsubmit({preventDefault(){}}),/invalid PNG/);assert.equal(h.context.sourceCloud,old);assert.equal(h.get('depth-import-fields').disabled,false);
});

test('in-flight file import cannot overwrite changed input or an active run',async()=>{
 for(const mode of ['input','running']){const h=harness();fields(h);h.get('depth-import-file').files=[{name:'raw.png',size:100}];h.context.api=async()=>{if(mode==='input')h.context.source='new-image';else h.context.running=true;return {cloud:{},depth:{}};};vm.runInContext('initDepthImportUI()',h.context);await assert.rejects(h.get('depth-import-form').onsubmit({preventDefault(){}}),/输入已变化/);assert.equal(h.context.sourceCloud.old,true);assert.equal(h.context.source,mode==='input'?'new-image':'old-image');}
});

test('depth preview walks frame origin and clears explicitly empty, failed or uncaptured channels',()=>{
 const h=harness();h.context.nextDepth={preview:'raw'};vm.runInContext('sourceDepth=nextDepth',h.context);assert.equal(vm.runInContext('resultDepth().preview',h.context),'raw');
 h.context.project.steps=[{id:'measure',operation:'cloud_measure',imageFrom:'source'}];h.context.results=[{id:'measure',output:{}}];h.context.displayedResultId='measure';assert.equal(vm.runInContext('resultDepth().preview',h.context),'raw');
 h.context.results[0].output.depth=null;assert.equal(vm.runInContext('resultDepth()',h.context),null);delete h.context.results[0].output.depth;h.context.results[0].error='failed';assert.equal(vm.runInContext('resultDepth()',h.context),null);
 h.context.results=[];h.context.project.steps[0].operation='camera_capture';assert.equal(vm.runInContext('resultDepth()',h.context),null);
});
