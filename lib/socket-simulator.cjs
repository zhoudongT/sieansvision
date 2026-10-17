'use strict';
const net=require('node:net'),dgram=require('node:dgram');
let tcp=null,udp=null,starting=null,stopping=null,receivedBytes=0;
const clients=new Set();
function status(){let udpPort=null;try{udpPort=udp?.address().port??null;}catch{}return {running:!!tcp?.listening&&udpPort!==null,host:'127.0.0.1',tcpPort:tcp?.listening?tcp.address().port:null,udpPort,receivedBytes};}
async function start(){
 if(stopping)await stopping;if(status().running)return status();if(starting)return starting;
 starting=(async()=>{
  try{
   tcp=net.createServer(socket=>{clients.add(socket);socket.on('close',()=>clients.delete(socket));socket.on('error',()=>{});socket.on('data',data=>{receivedBytes+=data.length;});socket.pipe(socket);});
   await new Promise((resolve,reject)=>{tcp.once('error',reject);tcp.listen(0,'127.0.0.1',resolve);});
   udp=dgram.createSocket('udp4');udp.on('error',()=>{});udp.on('message',(data,peer)=>{receivedBytes+=data.length;try{udp?.send(data,peer.port,peer.address,()=>{});}catch{}});
   await new Promise((resolve,reject)=>{udp.once('error',reject);udp.bind(0,'127.0.0.1',resolve);});
   return status();
  }catch(error){for(const s of clients)s.destroy();if(tcp){try{tcp.close();}catch{}}if(udp){try{udp.close();}catch{}}tcp=null;udp=null;throw error;}
 })();try{return await starting;}finally{starting=null;}
}
async function stop(){
 if(stopping)return stopping;
 stopping=(async()=>{if(starting)await starting.catch(()=>{});for(const s of clients)s.destroy();await Promise.all([tcp?new Promise(r=>tcp.close(r)):null,udp?new Promise(r=>udp.close(r)):null]);tcp=null;udp=null;receivedBytes=0;return status();})();
 try{return await stopping;}finally{stopping=null;}
}
module.exports={start,stop,status};
