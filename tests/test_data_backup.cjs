'use strict';
const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),os=require('node:os');
const {maintenance}=require('../lib/data-backup.cjs'),platform=require('../scripts/platform.cjs'),{acquire}=require('../lib/data-lock.cjs');
const root=path.resolve(__dirname,'..'),python=process.env.VISION_PYTHON||path.join(root,'.venv',process.platform==='win32'?'Scripts/python.exe':'bin/python');
function fixture(){const temp=fs.mkdtempSync(path.join(os.tmpdir(),'sieans-backup-node-'));const data=path.join(temp,'source');fs.mkdirSync(data);fs.writeFileSync(path.join(data,'project.txt'),'retained');return {temp,data,output:path.join(temp,'snapshot.zip')};}
test('backup refuses live directory and does not alter its lock',async()=>{
 const f=fixture(),release=acquire(f.data),before=fs.readFileSync(path.join(f.data,'.sieans-runtime.lock'),'utf8');
 try{await assert.rejects(maintenance({command:'backup',...f,python,'data-dir':f.data},platform),/占用/);assert.equal(fs.existsSync(f.output),false);assert.equal(fs.readFileSync(path.join(f.data,'.sieans-runtime.lock'),'utf8'),before);}finally{release();}
});
test('restore adapts foreign paths, retains authentication, keeps original config and rejects existing targets',async()=>{
 const f=fixture(),hash=require('bcryptjs').hashSync('test-password',4);
 // This backup is created without a deployment config; emulate a migrated
 // config inside its data through the low-level worker, never execute it.
 const foreign={version:1,python:'/foreign/python',models:'/foreign/models',host:'0.0.0.0',port:1999,features:[],adminUser:'operator',passwordHash:hash,operatorUser:'worker',operatorPasswordHash:hash};
 fs.writeFileSync(path.join(f.data,'deployment.json'),JSON.stringify(foreign));
 const accountConfig={adminUser:'operator',adminHash:hash,operatorUser:'worker',operatorHash:hash};const users=new (require('../lib/user-store.cjs').UserStore)(f.data,accountConfig);await users.change(null,{username:'backup-worker',password:'backup-password-123'});const history=new (require('../lib/operation-history.cjs').OperationHistory)(f.data);history.append({actor:'operator',role:'admin',action:'account_create',outcome:'succeeded',statusCode:201,elapsedMs:2});
 const {worker}=require('../lib/data-backup.cjs');await worker(python,{action:'backup',data:f.data,output:f.output,programVersion:'test'});
 const target=path.join(f.temp,'new'),out=await maintenance({command:'restore',archive:f.output,'data-dir':target,python},platform);
 const config=JSON.parse(fs.readFileSync(path.join(target,'deployment.json'),'utf8'));
 assert.equal(config.python,platform.pythonInfo(python).executable);assert.equal(config.models,path.join(target,'models'));assert.equal(config.passwordHash,hash);assert.equal(config.adminUser,'operator');assert.equal(config.host,'127.0.0.1');assert.equal(config.port,1999);assert.deepEqual(config.features,[]);
 assert.equal(out.serviceStarted,false);assert.equal(fs.existsSync(path.join(target,'.sieans-restore-incomplete')),false);
 const restoredUsers=new (require('../lib/user-store.cjs').UserStore)(target,accountConfig);assert(await restoredUsers.authenticate('backup-worker','backup-password-123'));assert.equal(new (require('../lib/operation-history.cjs').OperationHistory)(target).list().items[0].action,'account_create');
 assert.equal(config.operatorUser,'worker');assert.equal(config.operatorPasswordHash,hash);assert.equal(platform.runtimeEnv(target,config).OPERATOR_PASSWORD_HASH,hash);
 const receipt=fs.readdirSync(target).find(n=>n.startsWith('.sieans-restore-'));assert.deepEqual(JSON.parse(fs.readFileSync(path.join(target,receipt,'deployment-original.json'),'utf8')),foreign);
 await assert.rejects(maintenance({command:'restore',archive:f.output,'data-dir':target,python},platform),/不存在/);
 const release=acquire(target);release();assert.equal(fs.readFileSync(path.join(f.data,'project.txt'),'utf8'),'retained');
});
test('configuration failure preserves incomplete marker and blocks runtime acquisition',async()=>{
 const f=fixture();await maintenance({command:'backup',...f,python,'data-dir':f.data},platform);const target=path.join(f.temp,'failed');
 await assert.rejects(maintenance({command:'restore',archive:f.output,'data-dir':target,python,port:'invalid'},platform),/恢复未完成/);
 assert.equal(fs.existsSync(path.join(target,'.sieans-restore-incomplete')),true);assert.equal(fs.existsSync(path.join(target,'.sieans-runtime.lock')),false);
 assert.throws(()=>acquire(target),/恢复尚未完成/);assert.equal(fs.readFileSync(path.join(target,'project.txt'),'utf8'),'retained');
});
test('invalid archives never create restore target',async()=>{
 const f=fixture();fs.writeFileSync(f.output,'invalid ZIP');const target=path.join(f.temp,'never-created');
 await assert.rejects(maintenance({command:'restore',archive:f.output,'data-dir':target,python},platform));assert.equal(fs.existsSync(target),false);
});
test('public maintenance CLI creates, inspects and restores a snapshot',()=>{
 const f=fixture(),{spawnSync}=require('node:child_process'),launcher=path.join(root,'scripts/platform.cjs');
 const command=(...args)=>spawnSync(process.execPath,[launcher,...args,'--python',python],{encoding:'utf8',windowsHide:true,timeout:30000});
 for(const args of [['backup','--data-dir',f.data,'--output',f.output],['backup-info','--archive',f.output],['restore','--archive',f.output,'--data-dir',path.join(f.temp,'cli-restored')]]){const r=command(...args);assert.equal(r.status,0,r.stdout+r.stderr);}
 assert.equal(fs.readFileSync(path.join(f.temp,'cli-restored','project.txt'),'utf8'),'retained');
 assert.equal(command('backup','--data-dir',f.data,'--output',f.output).status,1);
});
