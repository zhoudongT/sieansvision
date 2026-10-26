'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),os=require('node:os'),path=require('node:path'),bcrypt=require('bcryptjs');
const {createManagement}=require('../desktop/management-service.cjs');

function setup(t,secured=false){
 const directory=fs.mkdtempSync(path.join(os.tmpdir(),'native-management-'));
 const keys=['ADMIN_PASSWORD_HASH','ADMIN_USER','OPERATOR_PASSWORD_HASH','OPERATOR_USER'];
 const previous=Object.fromEntries(keys.map(k=>[k,process.env[k]]));
 for(const k of keys)delete process.env[k];
 if(secured)process.env.ADMIN_PASSWORD_HASH=bcrypt.hashSync('test-admin-password',4);
 const service=createManagement({dataDirectory:directory,runtime:{}});
 for(const k of keys){if(previous[k]===undefined)delete process.env[k];else process.env[k]=previous[k];}
 t.after(()=>fs.rmSync(directory,{recursive:true,force:true}));
 return {service,directory};
}

test('native project library upgrades legacy graphs and preserves HMI extension fields',async t=>{
 const {service,directory}=setup(t);
 const project={version:1,id:'compatibility',name:'旧工程',steps:[{operation:'delay',params:{milliseconds:0},vendorExtension:{serial:1}}],
  hmi:{version:1,title:'运行画面',rows:4,rowHeight:40,components:[{id:'label',type:'text',label:'标题',x:0,y:0,w:2,h:1,color:'#0099cc',fontSize:16,futureFlag:true}],futureSettings:{value:2}}};
 const result=await service.dispatch('projects/save',{project});
 assert.equal(result.project.version,2);assert.equal(result.project.steps[0].id,'legacy-0');
 assert.deepEqual(result.project.hmi,project.hmi);
 const loaded=await service.dispatch('projects/get',{id:project.id});
 assert.deepEqual(loaded.project.hmi,project.hmi);assert.deepEqual(loaded.project.steps[0].vendorExtension,{serial:1});
 assert.equal((await service.dispatch('projects/list')).items[0].modules,1);
 await assert.rejects(service.dispatch('projects/get',{id:'../escape'}),/编号无效/);
 const before=fs.readFileSync(path.join(directory,'native-projects','compatibility.json'),'utf8');
 await assert.rejects(service.dispatch('projects/save',{project:{...project,hmi:{...project.hmi,rows:999}}}),/行数/);
 assert.equal(fs.readFileSync(path.join(directory,'native-projects','compatibility.json'),'utf8'),before);
});

test('native managed accounts require admin login, hide hashes and persist audit without submitted secrets',async t=>{
 const {service,directory}=setup(t,true);
 assert.equal((await service.dispatch('auth/status')).identity,null);
 assert.throws(()=>service.authorize('run'),/登录/);
 await assert.rejects(service.dispatch('auth/login',{username:'admin',password:'incorrect'}),/不正确/);
 await service.dispatch('auth/login',{username:'admin',password:'test-admin-password'});
 const account=await service.dispatch('accounts/create',{username:'tester',password:'test-operator-password'});
 assert.equal(account.role,'operator');
 const listing=await service.dispatch('accounts/list');assert.equal(listing.users.length,1);assert.equal(listing.users[0].passwordHash,undefined);
 await service.dispatch('accounts/update',{id:account.id,changes:{enabled:false}});
 assert.equal((await service.dispatch('accounts/list')).users[0].enabled,false);
 service.record('accounts/create',{password:'never-store-this'},true,2);
 service.record('continuous/start',{},true,1);service.record('mqtt/stop',{},true,1);
 const audit=await service.dispatch('audit/list',{limit:'20'});assert.equal(audit.total,3);
 assert.equal(audit.items[0].action,'mqtt_stop');
 assert.equal(fs.readFileSync(path.join(directory,'operation-history.jsonl'),'utf8').includes('never-store-this'),false);
 await service.dispatch('auth/logout');assert.throws(()=>service.authorize('accounts/list'),/登录/);
 await assert.rejects(service.dispatch('auth/login',{username:'tester',password:'test-operator-password'}),/不正确/);
});
