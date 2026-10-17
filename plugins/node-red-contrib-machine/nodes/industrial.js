module.exports=function(RED){
 for(const operation of ['modbus_read','modbus_write','modbus_wait','s7_read','s7_write','opcua_browse','opcua_read','opcua_write','opcua_wait']){
  function IndustrialNode(config){
   RED.nodes.createNode(this,config);const pending=new Set();let closed=false;
   this.on('close',()=>{closed=true;for(const controller of pending)controller.abort();});
   this.on('input',async(msg,send,done)=>{
    const controller=new AbortController();pending.add(controller);
    this.status({fill:'blue',shape:'dot',text:['modbus_wait','opcua_wait'].includes(operation)?'等待信号':'通信中'});
    try{
     if(!RED.settings.machineIndustrial)throw Error('需要 Machine Visual Studio 工业通信运行时');
     const params={...JSON.parse(config.params||'{}'),...(msg.industrialParams||{})};
     const output=await RED.settings.machineIndustrial.run({operation,params},{signal:controller.signal});
     if(!closed){msg.industrial=output;msg.payload=output.result;send(msg);this.status({fill:'green',shape:'dot',text:`${output.result.simulated?'模拟 · ':''}${output.elapsedMs} ms`});}
     done();
    }catch(error){if(!closed)this.status({fill:'red',shape:'ring',text:'通信失败'});done(error);}
    finally{pending.delete(controller);}
   });
  }
  RED.nodes.registerType('machine-'+operation,IndustrialNode);
 }
};
