'use strict';
const fs=require('node:fs'),path=require('node:path');
const {readPackage,OperatorPlugins}=require('../lib/operator-plugins.cjs');
const data=path.resolve(process.env.MACHINE_DATA_DIR||path.join(__dirname,'..','data'));
function install(source){
  const folder=fs.realpathSync(path.resolve(source)),{manifest}=readPackage(folder);
  const registry=new OperatorPlugins(data);if(registry.registry.has(manifest.id))throw Error('插件 ID 已安装；请使用新版本备份升级流程，不覆盖现有插件');
  const root=path.join(data,'operator-plugins'),destination=path.join(root,manifest.id);
  if(fs.existsSync(destination))throw Error('目标插件目录已存在');
  // Copy only the contract and executable entry files; no install scripts run.
  const names=new Set(['operator-plugin.json',...manifest.operators.map(op=>op.entry)]);
  for(const name of ['README.md','LICENSE'])if(fs.existsSync(path.join(folder,name)))names.add(name);
  for(const name of names){const f=path.join(folder,name),s=fs.lstatSync(f);if(!s.isFile()||s.isSymbolicLink()||s.size>128000)throw Error('插件文件无效：'+name);}
  fs.mkdirSync(root,{recursive:true});fs.mkdirSync(destination);
  for(const name of names)fs.copyFileSync(path.join(folder,name),path.join(destination,name),fs.constants.COPYFILE_EXCL);
  console.log('已安装 '+manifest.name+' '+manifest.version+'；重启服务器后加载。');
}
try{
  const [command,arg]=process.argv.slice(2);
  if(command==='validate'){const {manifest}=readPackage(path.resolve(arg));console.log('通过：'+manifest.name+' '+manifest.version+'，'+manifest.operators.length+' 个算子');}
  else if(command==='install'){if(!arg)throw Error('请提供可信本地插件目录');install(arg);}
  else if(command==='list')console.table(new OperatorPlugins(data).list().map(p=>({插件:p.name,版本:p.version,状态:p.status,错误:p.error||''})));
  else throw Error('用法：node scripts/operator-plugin.cjs validate <目录> | install <可信目录> | list');
}catch(error){console.error(error.message);process.exitCode=1;}
