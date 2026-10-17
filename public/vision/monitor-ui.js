'use strict';
const monitorSeverity={info:'提示',warning:'警告',critical:'严重'};
const monitorTime=value=>value?new Date(value).toLocaleString('zh-CN',{hour12:false}):'—';
function monitorSignature(c){return JSON.stringify(Object.fromEntries(Object.entries(c).filter(([key])=>!['x','y','w','h','fontSize','color'].includes(key))));}
async function monitorAcknowledge(event,comment=''){
 const id=project.id,monitor=await api('runtime/monitor/ack',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({projectId:id,id:event.id,comment})});
 if(id!==project.id)return;const updated=monitor.events.find(e=>e.id===event.id);if(updated)Object.assign(event,updated);hmiState.monitor=monitor;hmiUpdateWidgets();status('报警已确认；确认不会消除仍然存在的报警条件','success');
}
function monitorAlarmTable(events,{editing=false,comment=()=>''}={}){
 const table=formEl('table',undefined,'form-table monitor-event-table'),head=formEl('tr');for(const title of ['报警','级别','触发值','发生时间','恢复时间','确认时间','状态','结束说明','确认备注','操作'])head.append(formEl('th',title));table.append(head);
 for(const event of events){const row=formEl('tr'),action=formEl('td'),ack=formEl('button','确认');ack.setAttribute('aria-label','确认报警 '+event.label+' '+event.id);ack.disabled=editing||!!event.acknowledgedAt;ack.onclick=safe(async()=>{ack.disabled=true;try{await monitorAcknowledge(event,comment());}finally{ack.disabled=editing||!!event.acknowledgedAt;}});action.append(ack);
  for(const value of [event.label,monitorSeverity[event.severity]||event.severity,event.value,monitorTime(event.startedAt),monitorTime(event.returnedAt),monitorTime(event.acknowledgedAt),event.returnedAt?(event.endReason?(event.acknowledgedAt?'配置停用 · 已确认':'配置停用 · 待确认'):(event.acknowledgedAt?'已恢复并确认':'已恢复 · 待确认')):(event.acknowledgedAt?'仍在报警 · 已确认':'报警中 · 待确认'),event.endReason||'',event.comment||'']){const cell=formEl('td');cell.append(resultValueView(value));row.append(cell);}row.append(action);table.append(row);
 }return table;
}
function monitorSampleRows(samples,precision){return samples.slice().reverse().map(s=>({采样时间:monitorTime(s.time),数值:s.quality==='good'?Number(s.value.toFixed(precision)):null,数据质量:s.quality==='good'?'有效':'缺口',说明:s.reason||''}));}
function monitorTrendChart(samples,c){
 const ns='http://www.w3.org/2000/svg',make=(tag,attrs,text)=>{const el=document.createElementNS(ns,tag);for(const [key,value] of Object.entries(attrs))el.setAttribute(key,String(value));if(text!==undefined)el.textContent=text;return el;},svg=make('svg',{viewBox:'0 0 520 180',role:'img','aria-label':c.label+' 趋势曲线，缺失样本处断开'}),plot=MonitorChart.plot(samples);
 if(!plot.validCount){svg.append(make('text',{x:80,y:90,fill:'#60798e'},'暂无有效数值样本'));return svg;}
 for(const [fraction,value] of [[0,plot.high],[.5,plot.middle],[1,plot.low]]){const y=12+fraction*138;svg.append(make('line',{x1:52,y1:y,x2:504,y2:y,stroke:'#d9e5ee'}),make('text',{x:2,y:y+4,fill:'#46647c','font-size':10},value.toFixed(c.precision)));}
 for(const d of plot.paths)svg.append(make('path',{d,fill:'none',stroke:c.color,'stroke-width':2,'stroke-linecap':'round'}));
 for(const point of plot.dots)svg.append(make('circle',{cx:point.x,cy:point.y,r:3,fill:c.color}));
 svg.append(make('text',{x:52,y:174,fill:'#46647c','font-size':10},new Date(plot.start).toLocaleTimeString('zh-CN',{hour12:false})),make('text',{x:440,y:174,fill:'#46647c','font-size':10},new Date(plot.end).toLocaleTimeString('zh-CN',{hour12:false})));return svg;
}
function hmiMonitorUpdate(view){
 const {c,content}=view,monitor=hmiState.monitor,widget=monitor?.widgets?.[c.id],events=(monitor?.events||[]).filter(e=>e.componentId===c.id),signature=JSON.stringify([widget,events,hmiError,monitor?.error]);
 if(view.paused||view.monitorSignature===signature)return;view.monitorSignature=signature;const expanded=content.querySelector('details')?.open;content.replaceChildren();content.classList.add('monitor-widget');
 if(hmiError||monitor?.error){content.append(formEl('p',hmiError||monitor.error,'error'));return;}
 if(!widget||widget.signature!==monitorSignature(c)){content.append(formEl('p','配置将在下一轮作业或变量写入后启用；尚无当前配置样本。','muted'));return;}
 if(c.type==='alarm'){
  content.append(formEl('strong',widget.quality==='invalid'?'数据未知 · 保留原报警状态':widget.active?'报警中':'当前未报警',widget.active?'error':'monitor-normal'));
  if(widget.reason)content.append(formEl('p',widget.reason));if(widget.pending)content.append(formEl('small','状态变化确认中：'+widget.pending+' / '+c.stableSamples));
  if(events.length)content.append(monitorAlarmTable(events.slice(0,30),{editing:view.editing}));else content.append(formEl('p','暂无报警记录','muted'));
 }else{
  const samples=widget.samples||[],last=samples.at(-1);content.append(formEl('p',samples.length+' 个保留样本 · '+(last?.quality==='good'?last.value.toFixed(c.precision)+' '+c.unit:'最新值无效 / 未采样')));content.append(monitorTrendChart(samples,c));
  const details=formEl('details');details.open=!!expanded;details.append(formEl('summary','采样明细 · '+samples.length+' 行'));let built=false;details.ontoggle=()=>{if(details.open&&!built){built=true;details.append(resultValueView(monitorSampleRows(samples,c.precision)));}};content.append(details);
 }
}
function hmiMonitorProperties(c,field){
 if(c.type==='trend')field('趋势保留样本数',c.capacity,'number',value=>c.capacity=value,{min:20,max:1000});
 if(c.type!=='alarm')return;
 field('报警判断',c.comparison,[['gte','大于等于'],['gt','大于'],['lte','小于等于'],['lt','小于'],['eq','等于'],['ne','不等于'],['is_true','开关为是'],['is_false','开关为否']],value=>{c.comparison=value;if(['is_true','is_false'].includes(value)){delete c.threshold;c.hysteresis=0;}else if(['gt','gte','lt','lte'].includes(value)){if(typeof c.threshold!=='number')c.threshold=0;}else if(c.threshold===undefined)c.threshold=true;if(!['gt','gte','lt','lte'].includes(value))c.hysteresis=0;hmiProperties();});
 if(!['is_true','is_false'].includes(c.comparison)){
  if(['eq','ne'].includes(c.comparison))field('阈值类型',c.threshold===null?'null':typeof c.threshold,[['number','数值'],['string','文本'],['boolean','开关'],['null','空值']],value=>{c.threshold={number:0,string:'',boolean:true,null:null}[value];hmiProperties();});
  if(typeof c.threshold==='boolean')field('报警阈值',String(c.threshold),[['true','是'],['false','否']],value=>c.threshold=value==='true');
  else if(c.threshold!==null)field('报警阈值',c.threshold,typeof c.threshold==='number'?'number':'text',value=>c.threshold=value,{step:'any',maxLength:200});
 }
 if(['gt','gte','lt','lte'].includes(c.comparison))field('恢复回差',c.hysteresis,'number',value=>c.hysteresis=value,{min:0,max:1e12,step:'any'});
 field('连续确认样本数',c.stableSamples,'number',value=>c.stableSamples=value,{min:1,max:100});field('报警级别',c.severity,[['info','提示'],['warning','警告'],['critical','严重']],value=>c.severity=value);
}
function monitorDialogUpdate(){
 const dialog=$('monitor-dialog');if(!dialog?.open)return;if(dialog.paused)return;const monitor=hmiState.monitor||{widgets:{},events:[]},signature=JSON.stringify(monitor);if(dialog.signature===signature)return;dialog.signature=signature;dialog.snapshot=structuredClone(monitor);
 $('monitor-dialog-message').textContent=hmiError||monitor.error||'保留最近 20 个工程；每工程最多 200 条报警、5000 个趋势样本。样本在服务器生成，浏览器刷新不增加采样。';
 $('monitor-alarm-events').replaceChildren(monitorAlarmTable(monitor.events||[],{comment:()=>$('monitor-ack-comment').value}));
 $('monitor-retention').textContent='按保留策略移除：报警 '+(monitor.discardedEvents||0)+' 条，趋势 '+(monitor.discardedSamples||0)+' 点。';
 const select=$('monitor-series'),selected=select.value;select.replaceChildren(...Object.entries(monitor.widgets||{}).filter(([,w])=>w.type==='trend').map(([id,w])=>new Option(w.label,id)));if(Array.from(select.options).some(o=>o.value===selected))select.value=selected;
 monitorDialogSeries();
}
function monitorDialogSeries(){const holder=$('monitor-series-view'),widget=$('monitor-dialog').snapshot?.widgets?.[$('monitor-series').value];holder.replaceChildren();if(!widget){holder.append(formEl('p','暂无趋势样本'));return;}const config=JSON.parse(widget.signature);holder.append(monitorTrendChart(widget.samples,config),resultValueView(monitorSampleRows(widget.samples,config.precision)));}
function initMonitorUI(){
 const button=formEl('button','报警与趋势记录');button.id='monitor-open';$('history-open').after(button);
 const dialog=formEl('dialog');dialog.id='monitor-dialog';dialog.setAttribute('aria-label','报警与趋势记录');dialog.innerHTML='<header><h2>报警与趋势记录</h2><button id="monitor-pause">暂停显示</button><button id="monitor-close" aria-label="关闭报警与趋势记录">×</button></header><p id="monitor-dialog-message"></p><h3>当前工程报警</h3><label>确认备注<input id="monitor-ack-comment" aria-label="报警确认备注" maxlength="200"></label><div id="monitor-alarm-events"></div><h3>趋势与采样表</h3><label>趋势系列<select id="monitor-series" aria-label="监控趋势系列"></select></label><div id="monitor-series-view"></div><p id="monitor-retention"></p>';document.body.append(dialog);
 button.onclick=safe(async()=>{dialog.signature=null;dialog.paused=false;$('monitor-pause').textContent='暂停显示';dialog.showModal();await hmiRefresh();monitorDialogUpdate();});$('monitor-pause').onclick=()=>{dialog.paused=!dialog.paused;$('monitor-pause').textContent=dialog.paused?'继续显示':'暂停显示';if(!dialog.paused){dialog.signature=null;monitorDialogUpdate();}};$('monitor-close').onclick=()=>dialog.close();$('monitor-series').onchange=monitorDialogSeries;
}
