module.exports=function(RED){
 function Camera(config){
  RED.nodes.createNode(this,config);const pending=new Set();let closed=false;
  this.on('close',()=>{closed=true;for(const c of pending)c.abort();});
  this.on('input',async(msg,send,done)=>{
   const controller=new AbortController();pending.add(controller);this.status({fill:'blue',shape:'dot',text:'采集中'});
   try{
    if(!RED.settings.machineCameras)throw Error('需要 Machine Visual Studio 相机运行时');
    const params={...JSON.parse(config.params||'{}'),...(msg.cameraParams||{})};
    const output=await RED.settings.machineCameras.run({operation:'camera_capture',params},{signal:controller.signal});
    if(!closed){msg.image=output.annotatedImage;if(output.cloud)msg.cloud=output.cloud;else delete msg.cloud;if(output.depth)msg.depth=output.depth;else delete msg.depth;msg.camera=output.result;msg.payload=output.result;send(msg);this.status({fill:'green',shape:'dot',text:output.result.simulated?'模拟采集完成':'采集完成'});}done();
   }catch(error){if(!closed)this.status({fill:'red',shape:'ring',text:'采集失败'});done(error);}finally{pending.delete(controller);}
  });
 }
 RED.nodes.registerType('machine-camera_capture',Camera);
};
