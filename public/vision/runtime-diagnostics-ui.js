(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;else root.RuntimeDiagnostics=api;})(typeof globalThis!=='undefined'?globalThis:this,function(){
 'use strict';
 const states={idle:'空闲',running:'运行中',waiting:'等待中',completed:'已完成',failed:'失败',cancelled:'已取消',stopped:'已停止',stopping:'正在停止',opening:'正在连接',subscribed:'已订阅',connecting:'正在连接',reconnecting:'正在重连',interrupted:'已中断'};
 const mib=n=>(n/1024/1024).toFixed(2)+' MiB',state=s=>states[s]||s;
 function rows(d){return [
  ['采样时间',new Date(d.capturedAt).toLocaleString('zh-CN')],['服务器环境',d.process.node+' / '+d.process.platform+' / '+d.process.arch],['服务器运行时间',Math.floor(d.process.uptimeSeconds)+' 秒'],
  ['Node 进程驻留内存',mib(d.process.rssBytes)],['Node 已用堆内存',mib(d.process.heapUsedBytes)],['Node 已分配堆内存',mib(d.process.heapTotalBytes)],['Node 外部内存',mib(d.process.externalBytes)],['启动以来事件循环活跃比例',(d.process.eventLoopUtilization*100).toFixed(1)+'%'],
  ['流程状态',state(d.runtime.activeJobState)+(d.runtime.reserved?' · 运行资源已保留':'')],['缓存作业数',d.runtime.cachedJobs+' / '+d.runtime.jobCacheLimit],['视觉待处理请求',d.resources.visionPending],['视觉引擎子进程',d.resources.visionChildren],['Python 脚本/插件子进程',d.resources.scriptChildren],['正在执行的插件',d.resources.activePlugins],['工业通信子进程',d.resources.industrialChildren],['相机资源占用',d.resources.cameraReservations],['MQTT 通信任务',d.resources.mqttRequests],['TCP / UDP 通信任务',d.resources.socketRequests],
  ['连续检测',state(d.sessions.continuous)],['MQTT 事件订阅',state(d.sessions.mqttTrigger)],['连续相机',state(d.sessions.camera)+(d.sessions.cameraProcess?' · 进程存在':'')],['模型训练',d.sessions.training?'执行中':'未执行'],['历史记录数',d.history.records+' / '+d.history.recordLimit],['历史数据大小',mib(d.history.bytes)+' / '+mib(d.history.byteLimit)],['历史读取警告数',d.history.warnings]
 ];}
 return {rows};
});
function initDiagnosticsUI(){
 const open=formEl('button','运行诊断');open.id='diagnostics-open';open.type='button';$('help-dialog').append(open);
 const dialog=formEl('dialog'),title=formEl('h2','运行诊断'),description=formEl('p','此页只读取状态。内存仅统计 Node 服务器，不包含 Python、厂商 SDK 或 GPU；计数是当前采样，不能单独证明不存在泄漏。'),close=formEl('button','关闭'),refresh=formEl('button','刷新状态'),message=formEl('p'),table=formEl('table',undefined,'form-table'),body=formEl('tbody');dialog.id='diagnostics-dialog';dialog.setAttribute('aria-label','运行诊断');table.append(body);dialog.append(title,description,refresh,close,message,table);document.body.append(dialog);let pending=false;
 const load=async()=>{if(pending)return;pending=true;refresh.disabled=true;message.textContent='正在读取…';try{const d=await api('diagnostics');body.replaceChildren();for(const [label,value]of RuntimeDiagnostics.rows(d)){const row=formEl('tr');row.append(formEl('th',label),formEl('td',String(value)));body.append(row);}message.textContent='状态已刷新';}catch(error){body.replaceChildren();message.textContent='读取失败：'+error.message;throw error;}finally{pending=false;refresh.disabled=false;}};
 open.onclick=safe(async()=>{dialog.showModal();await load();});refresh.onclick=safe(load);close.onclick=()=>dialog.close();
}
