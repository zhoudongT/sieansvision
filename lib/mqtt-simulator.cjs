'use strict';
const net=require('node:net');
let instance=null,queue=Promise.resolve();
function serial(fn){const next=queue.then(fn);queue=next.catch(()=>{});return next;}
function status(){return instance?{running:true,host:'127.0.0.1',port:instance.server.address()?.port,clients:instance.sockets.size,retainedTopics:instance.retained.size}:{running:false};}
function start(){return serial(async()=>{
 if(instance)return status();
 const {Aedes}=await import('aedes'),sockets=new Set(),retained=new Map();let retainedBytes=0;
 const broker=await Aedes.createBroker({maxClientsIdLength:128,maxInflightInbound:16,queueLimit:64,connectTimeout:3000,
  authorizePublish(client,packet,done){
   if(packet.topic.startsWith('$SYS/')||packet.payload.length>65536)return done(Error('模拟器消息超出范围'));
   if(packet.retain){const previous=retained.get(packet.topic)||0,next=retainedBytes-previous+packet.payload.length;
    if(next>4*1024*1024||(!retained.has(packet.topic)&&packet.payload.length&&retained.size>=100))return done(Error('模拟器保留消息容量已满'));
    retainedBytes=next;if(packet.payload.length)retained.set(packet.topic,packet.payload.length);else retained.delete(packet.topic);
   }done(null);
  }
 });
 broker.on('error',()=>{});broker.on('clientError',()=>{});
 const server=net.createServer(socket=>{if(sockets.size>=32){socket.destroy();return;}sockets.add(socket);socket.on('error',()=>{});socket.on('close',()=>sockets.delete(socket));broker.handle(socket);});
 try{await new Promise((resolve,reject)=>{server.once('error',reject);server.listen(0,'127.0.0.1',()=>{server.removeListener('error',reject);resolve();});});}
 catch(error){await new Promise(resolve=>broker.close(resolve));throw error;}
 instance={broker,server,sockets,retained};return status();
});}
function stop(){return serial(async()=>{const current=instance;if(!current)return status();
 const closed=new Promise(resolve=>current.server.close(resolve));for(const socket of current.sockets)socket.destroy();
 await new Promise(resolve=>current.broker.close(resolve));await closed;instance=null;return status();
});}
module.exports={start,stop,status};
