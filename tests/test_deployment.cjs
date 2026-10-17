'use strict';
const test=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),os=require('node:os'),{spawnSync,fork}=require('node:child_process');
const platform=require('../scripts/platform.cjs'),{paths}=require('../lib/platform-paths.cjs'),{acquire}=require('../lib/data-lock.cjs');
const root=path.resolve(__dirname,'..'),temp=()=>fs.mkdtempSync(path.join(os.tmpdir(),'sieans-deploy-'));
test('deployment options, features and authentication enforce typed configuration',()=>{
 assert.deepEqual(platform.featureList('depth'),['2d','depth','camera']);assert.deepEqual(platform.featureList('core'),[]);assert.deepEqual(platform.featureList('cuda'),['2d','cuda','yolo']);
 assert.deepEqual(platform.featureList('orbbec'),['2d','orbbec','camera']);
 for(const value of ['foo','2d,','core,3d'])assert.throws(()=>platform.featureList(value));
 assert.throws(()=>platform.options(['start','--unknown','x']));assert.throws(()=>platform.options(['start','--port','2','--port','3']));
 assert.throws(()=>platform.directory(root));assert.throws(()=>platform.directory(path.dirname(root)));assert.throws(()=>platform.directory(path.join(root,'data')));
 const config={version:1,python:process.execPath,models:temp(),features:[],host:'127.0.0.1',port:1880,adminUser:'admin',passwordHash:''};
 assert.deepEqual(platform.validate(config),config);
 assert.throws(()=>platform.validate({...config,host:'0.0.0.0'}),/密码/);assert.throws(()=>platform.validate({...config,port:NaN}));
 assert.throws(()=>platform.validate({...config,passwordHash:'plain-password'}));
 assert.throws(()=>platform.validate({...config,passwordHash:false}));
 assert.equal(platform.validate({...config,host:'::1'}).host,'::1');
});
test('external model/cache locations propagate without changing legacy source defaults',()=>{
 const data=temp(),models=temp(),custom=paths({MACHINE_DATA_DIR:data,VISION_MODEL_DIR:models});
 assert.equal(custom.models,models);assert.equal(custom.yoloConfig,path.join(data,'yolo-config'));assert.equal(paths({}).models,path.join(root,'models'));
 const env=platform.runtimeEnv(data,{host:'127.0.0.1',port:1880,python:'python3',models,adminUser:'admin',passwordHash:''});
 assert.equal(env.MACHINE_DATA_DIR,data);assert.equal(env.VISION_MODEL_DIR,models);assert.equal(env.YOLO_CONFIG_DIR,path.join(data,'yolo-config'));
});
test('data directory rejects concurrent ownership and preserves live lock',()=>{
 const dir=temp(),release=acquire(dir),file=path.join(dir,'.sieans-runtime.lock'),before=fs.readFileSync(file,'utf8');
 assert.throws(()=>acquire(dir),/占用/);assert.equal(fs.readFileSync(file,'utf8'),before);
 release();assert.equal(fs.existsSync(file),false);const again=acquire(dir);again();
 fs.writeFileSync(file,'bad');assert.throws(()=>acquire(dir),/损坏/);assert.equal(fs.readFileSync(file,'utf8'),'bad');
});
test('abandoned process lock is recovered once and competing processes cannot steal ownership',async()=>{
 const dir=temp(),helper=path.join(dir,'lock.cjs'),library=path.join(root,'lib/data-lock.cjs');
 fs.writeFileSync(helper,`const {acquire}=require(${JSON.stringify(library)});try{const release=acquire(process.argv[2]);process.send({ready:true});process.on('message',()=>{release();process.exit(0);});}catch(e){process.send({error:e.message});process.exit(2);}`);
 const make=()=>{const child=fork(helper,[dir],{stdio:['ignore','ignore','ignore','ipc']});const done=new Promise(resolve=>child.once('exit',code=>resolve(code)));const ready=new Promise(resolve=>child.once('message',message=>resolve(message)));return {child,done,ready};};
 const abandoned=make();assert.equal((await abandoned.ready).ready,true);abandoned.child.kill();await abandoned.done;
 const competitors=Array.from({length:5},make);const messages=await Promise.all(competitors.map(p=>p.ready));
 const winners=messages.map((m,i)=>m.ready?i:-1).filter(i=>i>=0);
 try{assert.equal(winners.length,1);assert.equal(fs.readdirSync(dir).filter(n=>n.includes('.stale-')).length,1);}
 finally{for(const i of winners)competitors[i].child.send('stop');await Promise.all(competitors.map(p=>p.done));}
 assert.equal(fs.existsSync(path.join(dir,'.sieans-runtime.lock')),false);
});
test('configure and doctor work from CLI and service generation refuses overwrites',()=>{
 const dir=temp(),python=process.env.VISION_PYTHON||path.join(root,'.venv',process.platform==='win32'?'Scripts/python.exe':'bin/python');
 const command=(...args)=>spawnSync(process.execPath,[path.join(root,'scripts/platform.cjs'),...args],{encoding:'utf8',windowsHide:true,timeout:90000,env:{...process.env,ADMIN_PASSWORD_HASH:''}});
 let out=command('configure','--data-dir',dir,'--python',python,'--features','core');assert.equal(out.status,0,out.stderr);
 const saved=JSON.parse(fs.readFileSync(path.join(dir,'deployment.json'),'utf8'));assert.equal(saved.python,platform.pythonInfo(python).executable);assert.deepEqual(saved.features,[]);
 out=command('doctor','--data-dir',dir);assert.equal(out.status,0,out.stderr);assert.match(out.stdout,/仅本机/);
 const hash=require('bcryptjs').hashSync('deployment-test-only',4);
 const authEnv={...process.env,ADMIN_PASSWORD_HASH:hash};
 for(const args of [['configure','--data-dir',dir,'--host','0.0.0.0'],['doctor','--data-dir',dir]]){
  const checked=spawnSync(process.execPath,[path.join(root,'scripts/platform.cjs'),...args],{encoding:'utf8',windowsHide:true,timeout:90000,env:authEnv});
  assert.equal(checked.status,0,checked.stderr);assert.equal((checked.stdout+checked.stderr).includes(hash),false);
 }
 assert.equal(JSON.parse(fs.readFileSync(path.join(dir,'deployment.json'),'utf8')).passwordHash,hash);
 if(process.platform==='win32'){const output=path.join(dir,'service.xml');out=command('service','--data-dir',dir,'--format','winsw','--output',output);assert.equal(out.status,0,out.stderr);const xml=fs.readFileSync(output,'utf8');assert.match(xml,/<user>LocalService<\/user>/);assert.match(xml,/<stoptimeout>60 sec<\/stoptimeout>/);assert.equal(command('service','--data-dir',dir,'--format','winsw','--output',output).status,1);}
});
