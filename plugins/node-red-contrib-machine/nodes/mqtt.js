'use strict';
module.exports=function(RED){
 for(const operation of ['mqtt_publish','mqtt_receive']){
  function MqttNode(config){
   RED.nodes.createNode(this,config);const pending=new Set();let closed=false;
   this.on('close',()=>{closed=true;for(const controller of pending)controller.abort();});
   this.on('input',async(msg,send,done)=>{
    const controller=new AbortController();pending.add(controller);this.status({fill:'blue',shape:'dot',text:'MQTT 通信中'});
    try{
     if(!RED.settings.machineIndustrial)throw Error('需要 SIEANS 工业通信运行时');
     const params={...JSON.parse(config.params||'{}'),...(msg.industrialParams||{})};
     if(operation==='mqtt_publish'&&config.valueSource!=='constant')params.value=msg.payload;
     const output=await RED.settings.machineIndustrial.run({operation,params},{signal:controller.signal});
     if(!closed){msg.industrial=output;msg.payload=output.result;send(msg);this.status({fill:'green',shape:'dot',text:output.elapsedMs+' ms'});}done();
    }catch(error){if(!closed)this.status({fill:'red',shape:'ring',text:'MQTT 失败'});done(error);}finally{pending.delete(controller);}
   });
  }
  RED.nodes.registerType('machine-'+operation,MqttNode);
 }
};
