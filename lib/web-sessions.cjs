'use strict';
const {randomBytes,randomUUID,createHash,timingSafeEqual}=require('node:crypto');
const COOKIE='sieans_session';
const digest=value=>createHash('sha256').update(value).digest('hex');
function cookieToken(header){if(typeof header!=='string'||header.length>8192)return '';const found=header.split(';').map(s=>s.trim()).filter(s=>s.startsWith(COOKIE+'='));return found.length===1&&/^[a-f0-9]{64}$/.test(found[0].slice(COOKIE.length+1))?found[0].slice(COOKIE.length+1):'';}
function sameSite(req){if(req.headers['sec-fetch-site']==='cross-site')return false;if(!req.headers.origin)return true;try{const u=new URL(req.headers.origin);return ['http:','https:'].includes(u.protocol)&&u.host===req.headers.host;}catch{return false;}}
function equal(a,b){return typeof a==='string'&&typeof b==='string'&&/^[a-f0-9]{64}$/.test(a)&&/^[a-f0-9]{64}$/.test(b)&&timingSafeEqual(Buffer.from(a),Buffer.from(b));}
class WebSessions{
 constructor(config,{now=Date.now,idleMs=30*60*1000,absoluteMs=8*60*60*1000,maxSessions=500,secure=false}={}){Object.assign(this,{config,now,idleMs,absoluteMs,maxSessions,secure});this.sessions=new Map();this.attempts=new Map();this.activeLogins=0;}
 credential(username){const c=this.config;if(username===c.adminUser)return c.adminHash?digest('admin:'+c.adminHash):null;if(username===c.operatorUser&&c.operatorHash)return digest('operator:'+c.operatorHash);const u=c.userStore?.users.find(u=>u.username===username&&u.enabled);return u?digest(u.id+':'+u.passwordHash+':'+u.updatedAt):null;}
 prune(){for(const [key,s]of this.sessions)if(this.now()>=s.expiresAt||this.now()-s.touchedAt>=this.idleMs||this.credential(s.identity.username)!==s.credential)this.sessions.delete(key);}
 create(identity){this.prune();if(this.sessions.size>=this.maxSessions)throw Object.assign(Error('登录会话已达上限，请稍后重试'),{status:503});const token=randomBytes(32).toString('hex'),session={id:randomUUID(),createdAt:this.now(),identity:{role:identity.role,username:identity.username},credential:this.credential(identity.username),csrf:randomBytes(32).toString('hex'),touchedAt:this.now(),expiresAt:this.now()+this.absoluteMs};if(!session.credential)throw Error('账号已失效');this.sessions.set(digest(token),session);return {token,session};}
 read(header){this.prune();const token=cookieToken(header);return token?this.sessions.get(digest(token))||null:null;}
 revoke(header){const token=cookieToken(header);if(token)this.sessions.delete(digest(token));}
 revokeUser(username){for(const [key,s]of this.sessions)if(s.identity.username===username)this.sessions.delete(key);}
 list(header){const current=this.read(header);return {canManage:!!this.config.adminHash,limit:this.maxSessions,items:[...this.sessions.values()].sort((a,b)=>b.createdAt-a.createdAt).map(s=>({id:s.id,username:s.identity.username,role:s.identity.role,createdAt:s.createdAt,touchedAt:s.touchedAt,expiresAt:s.expiresAt,idleExpiresAt:Math.min(s.expiresAt,s.touchedAt+this.idleMs),current:s===current}))};}
 revokeId(id){if(typeof id!=='string'||!/^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/.test(id))throw Error('会话编号无效');this.prune();for(const [key,s]of this.sessions)if(s.id===id){this.sessions.delete(key);return true;}return false;}
 validCsrf(req,session){return sameSite(req)&&equal(req.headers['x-sieans-csrf'],session.csrf);}
 setCookie(req,res,token){const secure=this.secure||req.secure?'; Secure':'';const cookie=COOKIE+'='+token+'; Path=/; HttpOnly; SameSite=Strict; Max-Age='+(token?Math.floor(this.absoluteMs/1000):0)+secure;res.setHeader('Set-Cookie',token?[cookie,'sieans_web=1; Path=/; HttpOnly; SameSite=Strict; Max-Age=31536000'+secure]:cookie);}
 public(session){return {mode:'session',...session.identity,csrfToken:session.csrf,expiresAt:session.expiresAt,idleExpiresAt:Math.min(session.expiresAt,session.touchedAt+this.idleMs)};}
 allowLogin(address){const now=this.now();for(const [key,v]of this.attempts)if(now>=v.until)this.attempts.delete(key);let v=this.attempts.get(address);if(!v){if(this.attempts.size>=1024)return false;v={count:0,until:now+10*60*1000};this.attempts.set(address,v);}if(v.count>=10||this.activeLogins>=4)return false;v.count++;return true;}
 install(app,express,root){
  const access=require('./access-control.cjs'),path=require('node:path');
  app.use('/auth',(_req,res,next)=>{res.set('Cache-Control','no-store');next();});
  for(const [route,file,type]of [['/login','login.html','html'],['/auth/login.js','login.js','js'],['/auth/login.css','login.css','css'],['/auth/session-ui.js','session-ui.js','js']])app.get(route,(_req,res)=>{res.set({'Cache-Control':'no-store','X-Content-Type-Options':'nosniff','X-Frame-Options':'DENY',...(route==='/login'?{'Content-Security-Policy':"default-src 'self'; frame-ancestors 'none'; form-action 'self'; base-uri 'none'"}:{})});res.type(type).sendFile(path.join(root,'public/vision',file));});
  app.get('/auth/session',(req,res)=>{if(!this.config.adminHash)return res.json({mode:'development',username:this.config.adminUser,role:'admin'});const s=this.read(req.headers.cookie);if(s)return res.json(this.public(s));res.status(401).json({error:'请登录视觉平台'});});
  app.post('/auth/login',express.json({limit:'4kb'}),async(req,res)=>{
   if(!sameSite(req))return res.status(403).json({error:'登录请求来源无效'});
   if(!this.config.adminHash)return res.status(409).json({error:'当前为本机开发模式，请直接打开工作台'});
   const body=req.body;if(!req.is('application/json')||!body||Object.keys(body).sort().join(',')!=='password,username'||typeof body.username!=='string'||body.username.length>80||/[:\x00-\x1f\x7f]/.test(body.username)||typeof body.password!=='string'||body.password.length>128||Buffer.byteLength(body.password)>72)return res.status(400).json({error:'请填写有效的用户名和密码'});
   const address=req.socket.remoteAddress||'unknown';if(!this.allowLogin(address))return res.status(429).set('Retry-After','600').json({error:'登录尝试过于频繁，请稍后再试'});
   const credential=this.credential(body.username),attempt=this.attempts.get(address);this.activeLogins++;
   try{const identity=await access.identify('Basic '+Buffer.from(body.username+':'+body.password).toString('base64'),this.config);if(!identity||!credential||credential!==this.credential(body.username))return res.status(401).json({error:'用户名或密码错误，或账号已停用'});if(this.attempts.get(address)===attempt)attempt.count=Math.max(0,attempt.count-1);this.revoke(req.headers.cookie);const {token,session}=this.create(identity);this.setCookie(req,res,token);res.json({...this.public(session),redirect:identity.role==='admin'?'/vision/':'/vision/operator.html'});}catch(error){res.status(error.status||503).json({error:'暂时无法创建登录会话，请稍后重试'});}finally{this.activeLogins--;}
  });
  for(const route of ['touch','logout'])app.post('/auth/'+route,(req,res)=>{const s=this.read(req.headers.cookie);if(!s){this.setCookie(req,res,'');return res.status(401).json({error:'登录已失效，请重新登录'});}if(!this.validCsrf(req,s))return res.status(403).json({error:'会话校验失败，请刷新页面'});if(route==='logout'){this.revoke(req.headers.cookie);this.setCookie(req,res,'');return res.json({loggedOut:true});}s.touchedAt=this.now();res.json(this.public(s));});
 }
}
module.exports={WebSessions,cookieToken,sameSite};
