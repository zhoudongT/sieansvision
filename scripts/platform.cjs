'use strict';
const fs=require('node:fs'),path=require('node:path'),os=require('node:os'),net=require('node:net'),crypto=require('node:crypto');
const {spawn,spawnSync}=require('node:child_process');
const {supervise,SERVICE_STOP_SECONDS}=require('../lib/process-supervisor.cjs');
const root=path.resolve(__dirname,'..');
const features={ '2d':'vision/requirements.txt','3d':'vision/requirements-3d.txt',industrial:'industrial/requirements.txt',camera:'cameras/requirements.txt',yolo:'vision/requirements-yolo.txt',cuda:'vision/requirements-cuda.txt',depth:'cameras/requirements-depth.txt',orbbec:'cameras/requirements-orbbec.txt'};
function options(args){
 const out={command:args.shift()||'help'};
 for(let i=0;i<args.length;i+=2){const key=args[i];if(!['--data-dir','--python','--features','--host','--port','--admin-user','--models-dir','--format','--output','--archive','--service-user'].includes(key)||!args[i+1]||args[i+1].startsWith('--'))throw Error('未知或缺值的选项：'+key);if(Object.hasOwn(out,key.slice(2)))throw Error('重复选项：'+key);out[key.slice(2)]=args[i+1];}
 return out;
}
function featureList(value='2d,3d,industrial,camera'){
 if(value==='core')return [];
 const list=[...new Set(value.split(',').map(v=>v.trim()))];if(list.some(v=>!Object.hasOwn(features,v)))throw Error('功能可选：core 或 '+Object.keys(features).join(','));
 if(list.some(v=>['3d','camera','yolo','cuda','depth','orbbec'].includes(v))&&!list.includes('2d'))list.unshift('2d');
 if(list.includes('cuda')&&!list.includes('yolo'))list.push('yolo');
 if(list.some(v=>['depth','orbbec'].includes(v))&&!list.includes('camera'))list.push('camera');return list;
}
function inside(parent,child){const rel=path.relative(parent,child);return rel===''||(!rel.startsWith('..'+path.sep)&&rel!=='..'&&!path.isAbsolute(rel));}
function directory(value){
 const dir=path.resolve(value||path.join(process.platform==='win32'?(process.env.LOCALAPPDATA||os.homedir()):(process.env.XDG_DATA_HOME||path.join(os.homedir(),'.local/share')),'SIEANS','Vision'));
 if(inside(root,dir)||inside(dir,root))throw Error('部署数据目录必须与程序目录分离；请选择程序目录之外的位置');
 return dir;
}
function validate(config){
 if(!config||typeof config!=='object'||Array.isArray(config))throw Error('部署配置格式无效');
 if(config.version!==1||typeof config.python!=='string'||!path.isAbsolute(config.python)||typeof config.models!=='string'||!path.isAbsolute(config.models))throw Error('部署路径或配置版本无效，请重新 configure');
 if(typeof config.host!=='string'||(config.host!=='localhost'&&!net.isIP(config.host))||!Number.isInteger(config.port)||config.port<1||config.port>65535)throw Error('监听地址或端口无效');
 if(!Array.isArray(config.features)||config.features.some(v=>!Object.hasOwn(features,v)))throw Error('功能配置无效');
 if(typeof config.adminUser!=='string'||!config.adminUser.trim()||/[\r\n]/.test(config.adminUser))throw Error('管理员用户名无效');
 if(typeof config.passwordHash!=='string'||(config.passwordHash&&!/^\$2[aby]\$\d{2}\$[./A-Za-z0-9]{53}$/.test(config.passwordHash)))throw Error('ADMIN_PASSWORD_HASH 必须为有效的 bcrypt 哈希');
 require('../lib/access-control.cjs').accounts({ADMIN_USER:config.adminUser,ADMIN_PASSWORD_HASH:config.passwordHash,OPERATOR_USER:config.operatorUser,OPERATOR_PASSWORD_HASH:config.operatorPasswordHash});
 if(!['127.0.0.1','localhost','::1'].includes(config.host)&&!config.passwordHash)throw Error('局域网监听需要先通过环境变量 ADMIN_PASSWORD_HASH 设置管理员密码哈希');
 return config;
}
function readDeployment(file){try{return JSON.parse(fs.readFileSync(file,'utf8'));}catch{throw Error('部署配置文件不可读或格式无效，请检查 deployment.json');}}
function load(dir){const file=path.join(dir,'deployment.json');if(!fs.existsSync(file))throw Error('尚未配置部署，请先执行 install 或 configure');return validate(readDeployment(file));}
function pythonInfo(python){
 const r=spawnSync(python,['-I','-c','import sys,json; print(json.dumps(dict(executable=sys.executable,version=list(sys.version_info[:3]))))'],{encoding:'utf8',windowsHide:true,timeout:15000});
 if(r.error||r.status!==0)throw Error('无法运行 Python：'+python+'；请通过 --python 指定 Python 3.12 可执行文件');
 let info;try{info=JSON.parse(r.stdout.trim());}catch{throw Error('Python 版本响应无效');}
 if(info.version[0]!==3||info.version[1]!==12)throw Error('当前发行版要求 Python 3.12，检测到 '+info.version.join('.'));
 return info;
}
function nodeVersion(){if(Number(process.versions.node.split('.')[0])!==24)throw Error('当前发行版要求 Node.js 24 LTS');}
function compatibleAccounts(dir,config){
 const identities=require('../lib/access-control.cjs').accounts({ADMIN_USER:config.adminUser,ADMIN_PASSWORD_HASH:config.passwordHash,OPERATOR_USER:config.operatorUser,OPERATOR_PASSWORD_HASH:config.operatorPasswordHash});
 return new (require('../lib/user-store.cjs').UserStore)(dir,identities).list();
}
function configure(o,pythonOverride,oldOverride){
 const dir=directory(o['data-dir']),file=path.join(dir,'deployment.json');
 const old=oldOverride??(fs.existsSync(file)?load(dir):{});
 const python=pythonInfo(pythonOverride||o.python||old.python||path.join(root,'.venv',process.platform==='win32'?'Scripts/python.exe':'bin/python')).executable;
 const config=validate({version:1,python,features:o.features!==undefined?featureList(o.features):(old.features||featureList()),host:o.host??old.host??'127.0.0.1',port:Number(o.port??old.port??1880),
  models:path.resolve(o['models-dir']||old.models||path.join(dir,'models')),adminUser:o['admin-user']??old.adminUser??'admin',passwordHash:process.env.ADMIN_PASSWORD_HASH??old.passwordHash??'',operatorUser:process.env.OPERATOR_USER??old.operatorUser??'operator',operatorPasswordHash:process.env.OPERATOR_PASSWORD_HASH??old.operatorPasswordHash??''});
 compatibleAccounts(dir,config);
 fs.mkdirSync(dir,{recursive:true});for(const name of ['models','yolo-config','cache','logs'])fs.mkdirSync(path.join(dir,name),{recursive:true});fs.mkdirSync(config.models,{recursive:true});
 const temp=file+'.'+crypto.randomUUID()+'.tmp';fs.writeFileSync(temp,JSON.stringify(config,null,2)+'\n',{mode:0o600});fs.renameSync(temp,file);
 console.log('部署配置已保存：'+dir);return {dir,config};
}
function run(program,args,opts={}){
 return new Promise((resolve,reject)=>{const child=spawn(program,args,{cwd:root,stdio:'inherit',windowsHide:true,...opts});child.once('error',reject);child.once('close',code=>code===0?resolve():reject(Error('命令执行失败（'+code+'）：'+path.basename(program))));});
}
function verifyRelease(){
 const file=path.join(root,'release-manifest.json');if(!fs.existsSync(file)){console.log('源码工作目录：没有发行清单，跳过发行文件校验');return;}
 const manifest=JSON.parse(fs.readFileSync(file,'utf8'));if(manifest.format!==1||!Array.isArray(manifest.files)||manifest.files.length>10000)throw Error('发行清单无效');
 const seen=new Set();for(const entry of manifest.files){
  if(typeof entry.path!=='string'||entry.path.includes('\\')||entry.path.startsWith('/')||entry.path.split('/').some(p=>!p||p==='.'||p==='..')||seen.has(entry.path)||!/^[a-f0-9]{64}$/.test(entry.sha256))throw Error('发行文件路径或摘要无效');
  seen.add(entry.path);const file=path.resolve(root,entry.path);if(!inside(root,file))throw Error('发行文件超出程序目录');
  let current=root;for(const part of entry.path.split('/')){current=path.join(current,part);if(fs.lstatSync(current).isSymbolicLink())throw Error('发行文件不允许符号链接：'+entry.path);}
  const bytes=fs.readFileSync(file);if(bytes.length!==entry.bytes||crypto.createHash('sha256').update(bytes).digest('hex')!==entry.sha256)throw Error('发行文件校验失败：'+entry.path);
 }
 for(const required of ['server.cjs','package.json','package-lock.json','scripts/platform.cjs','deploy/doctor.py'])if(!seen.has(required))throw Error('发行清单缺少关键文件：'+required);
 console.log('发行文件校验通过：'+manifest.files.length+' 项（完整性校验，不代替发布者签名）');
}
async function install(o){
 nodeVersion();verifyRelease();const dir=directory(o['data-dir']);
 if(fs.existsSync(path.join(dir,'.sieans-runtime.lock')))throw Error('运行数据目录存在服务锁，请停止服务后安装');
 const python=pythonInfo(o.python||(process.platform==='win32'?'python':'python3')).executable;
 const list=featureList(o.features);const venv=path.join(root,'.venv'),executable=path.join(venv,process.platform==='win32'?'Scripts/python.exe':'bin/python');
 console.log('安装 Node 依赖（使用 package-lock.json）');
 if(process.platform==='win32')await run(process.env.ComSpec||'cmd.exe',['/d','/s','/c','npm.cmd ci --omit=dev --no-audit --no-fund']);
 else await run('npm',['ci','--omit=dev','--no-audit','--no-fund']);
 if(!fs.existsSync(executable))await run(python,['-m','venv',venv]);else pythonInfo(executable);
 if(list.length){console.log('安装 Python 功能：'+list.join(', '));await run(executable,['-m','pip','install','--disable-pip-version-check',...list.flatMap(f=>['-r',path.join(root,features[f])])]);}
 configure({...o,features:list.length?list.join(','):'core'},executable);
 await doctor({...o,'data-dir':dir});console.log('安装完成。使用 start 启动；设备驱动和模型需单独准备。');
}
async function doctor(o){
 nodeVersion();verifyRelease();const dir=directory(o['data-dir']),config=load(dir);pythonInfo(config.python);
 const rows=[{项目:'Node.js',状态:'通过',详情:process.version},{项目:'Python',状态:'通过',详情:config.python},{项目:'运行数据',状态:'已配置',详情:dir},{项目:'模型目录',状态:'已配置',详情:config.models},{项目:'访问控制',状态:config.passwordHash?'已配置认证':'仅本机',详情:config.host+':'+config.port}];
 let failed=false;for(const [name,expected] of Object.entries(require(path.join(root,'package.json')).dependencies)){try{const installed=JSON.parse(fs.readFileSync(path.join(root,'node_modules',name,'package.json'),'utf8'));if(installed.name!==name||(!expected.startsWith('file:')&&installed.version!==expected))throw Error('版本不一致');rows.push({项目:name,状态:'通过',详情:installed.version});}catch{failed=true;rows.push({项目:name,状态:'缺失或版本不符',详情:'请先安装 Node 依赖'});}}
 try{const a=compatibleAccounts(dir,config);rows.push({项目:'操作员账号',状态:'通过',详情:'平台管理 '+a.users.length+' 个，启用 '+a.users.filter(u=>u.enabled).length+' 个；部署操作员'+(config.operatorPasswordHash?'已启用':'未启用')});}catch(error){failed=true;rows.push({项目:'操作员账号',状态:'失败',详情:error.message});}
 const operationStatus=new (require('../lib/operation-history.cjs').OperationHistory)(dir).status();rows.push({项目:'操作记录文件',状态:operationStatus.available?'通过':'警告',详情:operationStatus.available?'只读检查通过，保留 '+operationStatus.storedCount+' 条':operationStatus.warning});
 const result=spawnSync(config.python,['-I','-X','utf8',path.join(root,'deploy/doctor.py'),...config.features],{encoding:'utf8',windowsHide:true,timeout:60000,env:runtimeEnv(dir,config)});
 if(result.error||result.status!==0){failed=true;rows.push({项目:'Python 功能检测',状态:'失败',详情:String(result.error?.message||result.stderr).slice(-350)});}
 else{const checks=JSON.parse(result.stdout.trim().split('\n').at(-1));for(const c of checks){rows.push({项目:c.name,状态:c.ok?'通过':'失败',详情:c.detail});if(!c.ok)failed=true;}}
 console.table(rows);if(!operationStatus.available)console.warn('操作记录文件存在异常；服务可启动，但记录将暂停追加。请修复存储后再使用需要留痕的操作。');console.log('硬件采集、现场通信及 Linux 验收需在目标机器另行测试。');if(failed)throw Error('部署诊断未通过');return rows;
}
function runtimeEnv(dir,config){return {...process.env,HOST:config.host,PORT:String(config.port),MACHINE_DATA_DIR:dir,VISION_PYTHON:config.python,VISION_MODEL_DIR:config.models,YOLO_CONFIG_DIR:path.join(dir,'yolo-config'),XDG_CACHE_HOME:path.join(dir,'cache'),ADMIN_USER:config.adminUser,ADMIN_PASSWORD_HASH:config.passwordHash,OPERATOR_USER:config.operatorUser||'operator',OPERATOR_PASSWORD_HASH:config.operatorPasswordHash||''};}
async function start(o){
 nodeVersion();const dir=directory(o['data-dir']),config=load(dir);pythonInfo(config.python);
 console.log('启动 SIEANS Vision；运行数据：'+dir);
 const child=spawn(process.execPath,[path.join(root,'server.cjs')],{cwd:root,stdio:['inherit','inherit','inherit','ipc'],windowsHide:true,env:runtimeEnv(dir,config)});
 await supervise(child);
}
function service(o){
 const dir=directory(o['data-dir']);load(dir);const output=o.output;if(!output)throw Error('请指定 --output 服务文件路径');
 const script=path.join(root,'scripts/platform.cjs');let content;
 if(o.format==='systemd'){
  if(process.platform==='win32')throw Error('请在 Linux 目标机器生成 systemd 服务文件');
  const user=o['service-user']||'sieans';if(!/^[a-z_][a-z0-9_-]{0,31}$/.test(user))throw Error('服务账户名称无效');
  const quote=v=>{if(/[\r\n$%]/.test(v))throw Error('服务路径不支持换行、$ 或 %');return JSON.stringify(v);};
  content='[Unit]\nDescription=SIEANS Vision\nAfter=network.target\n\n[Service]\nType=simple\nUser='+user+'\nWorkingDirectory='+quote(root)+'\nExecStart='+[process.execPath,script,'start','--data-dir',dir].map(quote).join(' ')+'\nRestart=on-failure\nRestartSec=5\nKillMode=mixed\nTimeoutStopSec='+SERVICE_STOP_SECONDS+'\nUMask=0077\n\n[Install]\nWantedBy=multi-user.target\n';
 }else if(o.format==='winsw'){
  if(process.platform!=='win32')throw Error('请在 Windows 目标机器生成 WinSW 服务文件');
  const xml=v=>v.replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;');
  for(const v of [script,dir,process.execPath])if(/["\r\n%]/.test(v))throw Error('服务路径不支持引号、换行或 %');
  content='<service>\n  <id>SIEANSVision</id>\n  <name>SIEANS Vision</name>\n  <serviceaccount><domain>NT AUTHORITY</domain><user>LocalService</user></serviceaccount>\n  <description>Visual inspection development and runtime platform</description>\n  <executable>'+xml(process.execPath)+'</executable>\n  <arguments>'+xml('"'+script+'" start --data-dir "'+dir+'"')+'</arguments>\n  <workingdirectory>'+xml(root)+'</workingdirectory>\n  <logpath>'+xml(path.join(dir,'logs'))+'</logpath>\n  <log mode="roll-by-size"><sizeThreshold>10240</sizeThreshold><keepFiles>5</keepFiles></log>\n  <stoptimeout>'+SERVICE_STOP_SECONDS+' sec</stoptimeout>\n  <onfailure action="restart" delay="5 sec"/>\n</service>\n';
 }else throw Error('--format 必须为 systemd 或 winsw');
 fs.writeFileSync(path.resolve(output),content,{flag:'wx',mode:0o600});console.log('服务配置已生成，尚未安装或启动系统服务：'+path.resolve(output));
}
async function main(args=process.argv.slice(2)){
 const maintenanceCommands=['backup','backup-info','restore'];
 if(maintenanceCommands.includes(args[0])){const result=await require('../lib/data-backup.cjs').maintenance(options([...args]),module.exports);console.table([result]);return result;}
 const o=options([...args]);if(o.command==='install')return install(o);if(o.command==='configure'){nodeVersion();return configure(o);}if(o.command==='doctor')return doctor(o);if(o.command==='start')return start(o);if(o.command==='verify')return verifyRelease();if(o.command==='service')return service(o);
 if(o.command!=='help')throw Error('未知命令：'+o.command);
 console.log('运行数据维护（停止服务后执行；恢复不会启动服务）\n  backup --data-dir <外部数据目录> --output <新备份.zip> [--python <路径>] [--models-dir <独立模型目录>]\n  backup-info --archive <备份.zip> [--python <路径>]\n  restore --archive <备份.zip> --data-dir <尚不存在的新目录> [--python <当前解释器>] [--host 127.0.0.1] [--port 1880]\n');
 console.log('SIEANS 部署工具\n  install --python <Python 3.12 路径> --data-dir <外部数据目录> [--features 2d,3d,industrial,camera,yolo,cuda,depth,orbbec]\n  configure --data-dir <目录> [--python <路径>] [--host 127.0.0.1] [--port 1880] [--models-dir <目录>]\n  doctor --data-dir <目录>\n  start --data-dir <目录>\n  verify\n  service --data-dir <目录> --format winsw|systemd --output <新服务文件> [--service-user sieans]\n默认安装 2d,3d,industrial,camera；core 仅安装编辑器和 Python 标准库。局域网需 ADMIN_PASSWORD_HASH。');
}
module.exports={options,featureList,directory,validate,readDeployment,pythonInfo,runtimeEnv,verifyRelease,configure,main};
if(require.main===module)main().catch(error=>{console.error(error.message);process.exitCode=1;});
