'use strict';
const bcrypt=require('bcryptjs');
const HASH=/^\$2[aby]\$\d{2}\$[./A-Za-z0-9]{53}$/;
function accounts(env=process.env){
 for(const key of ['ADMIN_USER','ADMIN_PASSWORD_HASH','OPERATOR_USER','OPERATOR_PASSWORD_HASH'])if(env[key]!==undefined&&typeof env[key]!=='string')throw Error('登录账户或密码哈希类型无效：'+key);
 const adminUser=env.ADMIN_USER||'admin',adminHash=env.ADMIN_PASSWORD_HASH||'',operatorUser=env.OPERATOR_USER||'operator',operatorHash=env.OPERATOR_PASSWORD_HASH||'';
 for(const [name,hash]of [[adminUser,adminHash],[operatorUser,operatorHash]])if(typeof name!=='string'||!name.trim()||name.length>80||/[:\x00-\x1f\x7f]/.test(name)||typeof hash!=='string'||hash&&!HASH.test(hash))throw Error('登录账户或 bcrypt 密码哈希无效');
 if(operatorHash&&(!adminHash||operatorUser===adminUser))throw Error('操作员账户需要管理员密码，且用户名必须不同');
 return {adminUser,adminHash,operatorUser,operatorHash};
}
async function identify(header,config){
 if(!config.adminHash)return {role:'admin',username:config.adminUser,localDevelopment:true};
 header=header||'';
 if(typeof header!=='string')return null;
 if(header.length<=2048&&/^Basic [A-Za-z0-9+/]+=*$/.test(header)){
  const decoded=Buffer.from(header.slice(6),'base64').toString('utf8'),separator=decoded.indexOf(':'),username=decoded.slice(0,separator),password=decoded.slice(separator+1);
  const role=username===config.adminUser?'admin':config.operatorHash&&username===config.operatorUser?'operator':null;
  let valid=false;try{valid=separator>=0&&role&&await bcrypt.compare(password,role==='admin'?config.adminHash:config.operatorHash);}catch{}
  if(valid)return {role,username};
  if(separator>=0&&!role&&config.userStore&&await config.userStore.authenticate(username,password))return {role:'operator',username};
 }
 return null;
}
function middleware(config){return async(req,res,next)=>{
 const web=config.webSessions,session=web?.read(req.headers.cookie),browser=/\btext\/html\b/.test(req.headers.accept||'')||!!req.headers['sec-fetch-site']||/(?:^|;\s*)sieans_web=1(?:;|$)/.test(req.headers.cookie||'');
 if(session){if(!['GET','HEAD','OPTIONS'].includes(req.method)&&!web.validCsrf(req,session))return res.status(403).json({error:'会话校验失败，请刷新页面'});req.identity=session.identity;res.set('Cache-Control','no-store');return next();}
 const identity=(!config.adminHash||!browser)?await identify(req.headers.authorization,config):null;if(identity){req.identity=identity;res.set('Cache-Control','no-store');return next();}
 res.set('Cache-Control','no-store');if(web&&req.method==='GET'&&/\btext\/html\b/.test(req.headers.accept||''))return res.redirect('/login');
 if(!browser)res.set('WWW-Authenticate','Basic realm="SIEANS Vision", charset="UTF-8"');
 res.status(401).json({error:'登录已失效，请重新登录'});
};}
function restrictApi(req,res,next){if(req.identity.role==='admin'||req.path==='/identity'&&req.method==='GET'||req.path.startsWith('/operator/')&&['GET','POST'].includes(req.method))return next();res.status(403).json({error:'操作员账户不能访问工程、设备或开发配置接口'});}
function dashboard(config){return async(socket,next)=>{
 const headers=socket.request.headers;
 if(headers.origin){try{const origin=new URL(headers.origin),host=new URL(origin.protocol+'//'+headers.host);if(!['http:','https:'].includes(origin.protocol)||origin.host!==host.host)return next(Error('仪表盘仅允许同站点连接'));}catch{return next(Error('仪表盘来源无效'));}}
 const session=config.webSessions?.read(headers.cookie),identity=session?.identity||(!headers['sec-fetch-site']&&!/(?:^|;\s*)sieans_web=1(?:;|$)/.test(headers.cookie||'')?await identify(headers.authorization,config):null);if(identity?.role==='admin'){if(session){const timer=setInterval(()=>{if(!config.webSessions.read(headers.cookie))socket.disconnect(true);},1000);timer.unref?.();socket.once('disconnect',()=>clearInterval(timer));}next();}else next(Error('此 Node-RED 仪表盘连接仅限管理员'));
};}
module.exports={accounts,identify,middleware,restrictApi,dashboard};
