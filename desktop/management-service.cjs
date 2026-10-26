'use strict';
const fs=require('node:fs'),path=require('node:path');
const graph=require('../public/vision/flow-graph.js');
const access=require('../lib/access-control.cjs');
const {UserStore}=require('../lib/user-store.cjs');
const {OperationHistory}=require('../lib/operation-history.cjs');
const actions={'projects/save':'project_save','accounts/create':'account_create','accounts/update':'account_update',
 'variables/set':'variables_write',run:'job_start',stop:'job_cancel','camera/session/start':'camera_start','camera/session/stop':'camera_stop',
 'training/start':'training_start','training/cancel':'training_cancel','plugins/update':'plugin_update',
 'continuous/start':'continuous_start','continuous/stop':'continuous_stop','mqtt/start':'mqtt_start','mqtt/stop':'mqtt_stop','monitor/ack':'operator_ack'};

function editableProject(value){
 const result=graph.normalize(value);
 // Validation uses the canonical schema; storage keeps future HMI extensions.
 if(value.hmi!==undefined)result.hmi=JSON.parse(JSON.stringify(value.hmi));
 return result;
}

function createManagement({dataDirectory,runtime}){
 const config=access.accounts(),users=new UserStore(dataDirectory,config),audit=new OperationHistory(dataDirectory);
 config.userStore=users;
 let identity=config.adminHash?null:{role:'admin',username:config.adminUser,localDevelopment:true};
 const directory=path.join(dataDirectory,'native-projects');fs.mkdirSync(directory,{recursive:true});
 const filename=id=>{if(typeof id!=='string'||!(/^[A-Za-z0-9_-]{1,80}$/).test(id))throw Error('工程编号无效');return path.join(directory,id+'.json');};
 function authorize(method){
   if(['auth/status','auth/login','auth/logout','shutdown'].includes(method))return;
   if(!identity)throw Error('请先使用管理员账号登录桌面工作台');
   if(identity.role!=='admin')throw Error('工程开发和设备配置需要管理员账号');
 }
 function record(method,params,ok,elapsedMs=0){
   if(!actions[method])return;
   try{audit.append({actor:identity?.username||'anonymous',role:identity?.role||'admin',localDevelopment:!!identity?.localDevelopment,
    action:actions[method],resourceId:'',outcome:ok?'succeeded':'failed',statusCode:ok?200:400,elapsedMs:Math.max(0,Math.round(elapsedMs))});}catch{}
 }
 async function dispatch(method,params={}){
   authorize(method);
   switch(method){
    case 'auth/status':return {identity,configured:!!config.adminHash};
    case 'auth/logout':identity=config.adminHash?null:{role:'admin',username:config.adminUser,localDevelopment:true};return {identity};
    case 'auth/login':{
     if(typeof params.username!=='string'||typeof params.password!=='string'||params.username.length>80||params.password.length>128)throw Error('账号或密码无效');
     const next=await access.identify('Basic '+Buffer.from(params.username+':'+params.password).toString('base64'),config);
     if(!next||next.role!=='admin'){await new Promise(r=>setTimeout(r,350));throw Error('管理员账号或密码不正确');}
     identity=next;return {identity};
    }
    case 'accounts/list':return users.list();
    case 'accounts/create':return users.change(null,params);
    case 'accounts/update':return users.change(params.id,params.changes);
    case 'audit/list':return audit.list(params);
    case 'history/list':return runtime.history.list(params);
    case 'history/get':return runtime.history.get(params.id);
    case 'projects/list':{
      const items=[];for(const file of fs.readdirSync(directory).filter(f=>f.endsWith('.json'))){
       try{const full=path.join(directory,file),stat=fs.statSync(full);if(stat.size>32_000_000)continue;
        const p=JSON.parse(fs.readFileSync(full,'utf8'));items.push({id:p.id,name:p.name,modules:p.steps?.length||0,updatedAt:stat.mtimeMs});}catch{}
      }return {items:items.sort((a,b)=>b.updatedAt-a.updatedAt)};
    }
    case 'projects/get':{const file=filename(params.id);if(fs.statSync(file).size>32_000_000)throw Error('工程文件过大');return {project:editableProject(JSON.parse(fs.readFileSync(file,'utf8')))};}
    case 'projects/save':{
      const project=editableProject(params.project);graph.order(project,false);const file=filename(project.id),body=JSON.stringify(project);
      if(Buffer.byteLength(body)>32_000_000)throw Error('工程不能超过 32 MB');
      fs.writeFileSync(file+'.tmp',body,{mode:0o600});fs.renameSync(file+'.tmp',file);return {project};
    }
    case 'cloud/import':case 'depth/import':{
      const owner={kind:'native-import'};runtime.reserve(owner);
      try{return await runtime.vision.run({...params,operation:method==='cloud/import'?'cloud_import':'depth_import'},{timeoutMs:15000});}
      finally{runtime.release(owner);}
    }
    case 'plugins/reload':if(runtime.busy)throw Error('运行期间不能扫描插件');runtime.plugins.reload();return runtime.plugins.list();
    case 'plugins/update':if(runtime.busy)throw Error('运行期间不能修改插件');return runtime.plugins.setEnabled(params.id,params.enabled);
    default:throw Error('未知原生管理方法：'+method);
   }
 }
 return {dispatch,authorize,record};
}
module.exports={createManagement};
