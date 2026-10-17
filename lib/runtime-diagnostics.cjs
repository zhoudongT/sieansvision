'use strict';
const {performance}=require('node:perf_hooks');
function snapshot({runtime,continuous,mqttTrigger,cameraSession,plugins,vision,industrial,cameras,scripts,mqtt,socket,training}){
 const memory=process.memoryUsage(),cpu=process.cpuUsage(),engine=vision.status(),history=runtime.history;
 return {version:1,capturedAt:new Date().toISOString(),process:{pid:process.pid,node:process.version,platform:process.platform,arch:process.arch,uptimeSeconds:process.uptime(),rssBytes:memory.rss,heapUsedBytes:memory.heapUsed,heapTotalBytes:memory.heapTotal,externalBytes:memory.external,cpuUserMs:cpu.user/1000,cpuSystemMs:cpu.system/1000,eventLoopUtilization:performance.eventLoopUtilization().utilization},
  runtime:{busy:runtime.busy,activeJobState:runtime.active?.state||'idle',reserved:!!runtime.owner,cachedJobs:runtime.jobs.size,jobCacheLimit:3},
  resources:{visionPending:engine.pending,visionChildren:engine.children,scriptChildren:scripts.activeCount(),industrialChildren:industrial.activeCount(),cameraReservations:cameras.activeCount(),activePlugins:plugins.activeCount,mqttRequests:mqtt.activeCount(),socketRequests:socket.activeCount()},
  sessions:{continuous:continuous.state.state,mqttTrigger:mqttTrigger.state.state,camera:cameraSession.state.state,cameraProcess:!!cameraSession.child,training:!!training.working},
  processes:{visionPids:engine.pids,cameraPid:cameraSession.child?.pid??null},
  history:{records:history.records.length,bytes:history.records.reduce((n,r)=>n+r.bytes,0),recordLimit:history.maxRecords,byteLimit:history.maxBytes,warnings:history.warnings.length}};
}
module.exports={snapshot};
