'use strict';
const forbidden=new Set(['__proto__','constructor','prototype']);
function map(value,label){if(!value||typeof value!=='object'||Array.isArray(value))throw Error(label+' 必须为字段映射');return value;}
function read(msg,path){
  if(typeof path!=='string'||path.length>300||!path||path.split('.').some(k=>!k||forbidden.has(k)))throw Error('消息字段路径无效');
  let value=msg;for(const key of path.split('.')){if(!value||typeof value!=='object'||!Object.hasOwn(value,key))throw Error('消息字段不存在：'+path);value=value[key];}return value;
}
module.exports=function(RED){
  RED.httpAdmin.get('/machine/operators',RED.auth.needsPermission('flows.read'),(_req,res)=>{
    if(!RED.settings.machineOperators)return res.status(503).json({error:'需要 SIEANS 算子运行时'});
    res.json({plugins:RED.settings.machineOperators.list()});
  });
  function Operator(config){
    RED.nodes.createNode(this,config);let closed=false,active=null;
    this.on('close',()=>{closed=true;active?.abort();});
    this.on('input',async(msg,send,done)=>{
      if(closed)return done();
      if(active)return done(Error('扩展算子节点正在处理上一条消息，请限制输入频率'));
      const controller=new AbortController();active=controller;this.status({fill:'blue',shape:'dot',text:'执行插件'});
      try{
        if(!RED.settings.machineOperators)throw Error('需要 SIEANS 算子运行时');
        const args={...map(JSON.parse(config.arguments||'{}'),'参数'),...map(msg.operatorArgs??{},'消息参数')};
        const bindings=map(JSON.parse(config.parameterBindings||'{}'),'参数绑定');
        if(Object.keys(bindings).length>100)throw Error('参数绑定最多 100 项');
        for(const [key,path] of Object.entries(bindings)){if(forbidden.has(key))throw Error('参数名称无效');args[key]=read(msg,path);}
        const image=Object.hasOwn(msg,'image')?msg.image:typeof msg.payload==='string'?msg.payload:msg.payload?.image;
        const output=await RED.settings.machineOperators.run({pluginId:config.pluginId,pluginVersion:config.pluginVersion,operatorId:config.operatorId,arguments:args,
          image:image??'',cloud:Object.hasOwn(msg,'cloud')?msg.cloud:msg.payload?.cloud,depth:Object.hasOwn(msg,'depth')?msg.depth:msg.payload?.depth,variables:msg.operatorVariables},{signal:controller.signal});
        if(closed)return done();
        msg.image=output.image??output.annotatedImage;
        for(const channel of ['cloud','depth']){if(output[channel]===null||output[channel]===undefined)delete msg[channel];else msg[channel]=output[channel];}
        msg.operatorVariables=output.variables;msg.vision=output;msg.payload=output.result;
        const display=output.cloud??output.annotatedImage;
        send([msg,display?{...msg,payload:display}:null]);
        this.status({fill:'green',shape:'dot',text:Math.round(output.elapsedMs)+' ms'});done();
      }catch(error){if(!closed){this.status({fill:'red',shape:'ring',text:'插件失败'});done(error);}else done();}
      finally{active=null;}
    });
  }
  RED.nodes.registerType('machine-operator',Operator);
};
