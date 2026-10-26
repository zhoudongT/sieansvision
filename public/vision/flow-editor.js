'use strict';
let flowZoom=1,flowLink=null,flowEdge=null,flowRoute='elbow';
const flowLabel=s=>s?.name||stepDefinition(s)?.name||s?.id||'';
const flowName=id=>id==='source'?'数据源1':(project.steps.findIndex(s=>s.id===id)+1)+' · '+flowLabel(project.steps.find(s=>s.id===id));
const flowPoint=event=>{const box=$('pipeline').getBoundingClientRect();return {x:Math.max(12,Math.min(9900,(event.clientX-box.left)/flowZoom)),y:Math.max(12,Math.min(9900,(event.clientY-box.top)/flowZoom))};};
function flowCommit(next,message){project=next;flowLink=null;flowEdge=null;dirty();renderPipeline();renderParams();if(message)status(message,'success');}
function flowConnect(from,to,fromPort='bottom',toPort='top'){
  if(running)return;applyParams();
  flowCommit(FlowGraph.connect(project,{id:uid(),from,to,fromPort,toPort}),'连线已建立，按依赖执行');
}
function flowPort(id,side,output){
  const b=document.createElement('button');b.className='flow-port port-'+side+(output?' output':' input');b.dataset.node=id;b.dataset.side=side;b.dataset.output=String(output);
  b.title=(output?'输出':'输入')+' · '+flowName(id);b.setAttribute('aria-label',flowName(id)+' '+(output?'输出':'输入')+' '+({top:'上',bottom:'下',left:'左',right:'右'})[side]);b.disabled=running;
  b.onclick=safe(event=>{event.stopPropagation();if(output){flowLink={from:id,fromPort:side};flowEdge=null;flowUpdateSelection();status('请选择目标节点的输入端口；Esc 取消');}else if(flowLink)flowConnect(flowLink.from,id,flowLink.fromPort,side);else status('先点击上游的输出端口，再点击此输入端口');});
  if(output){let start=null,moved=false;
    b.onpointerdown=e=>{if(running||e.button!==0)return;e.stopPropagation();start={x:e.clientX,y:e.clientY};moved=false;b.setPointerCapture(e.pointerId);};
    b.onpointermove=e=>{if(!start||Math.hypot(e.clientX-start.x,e.clientY-start.y)<5)return;moved=true;flowLink={from:id,fromPort:side};flowDrawEdges(flowPoint(e));};
    b.onpointerup=safe(e=>{if(!start)return;start=null;if(!moved)return;e.stopPropagation();const hit=document.elementFromPoint(e.clientX,e.clientY)?.closest('.flow-port.input');b.addEventListener('click',ev=>{ev.stopImmediatePropagation();ev.preventDefault();},{capture:true,once:true});if(hit)flowConnect(id,hit.dataset.node,side,hit.dataset.side);else{flowLink=null;flowDrawEdges();}});
    b.onpointercancel=()=>{start=null;flowLink=null;flowDrawEdges();};
  }
  return b;
}
function flowPosition(id){return id==='source'?project.sourcePosition:project.steps.find(s=>s.id===id).position;}
function flowAnchor(id,side){const p=flowPosition(id),w=200,h=id==='source'?40:72;return {x:p.x+(side==='left'?0:side==='right'?w:w/2),y:p.y+(side==='top'?0:side==='bottom'?h:h/2)};}
function flowPath(a,b,fromPort,toPort){
  const av=fromPort==='right'?{x:1,y:0}:{x:0,y:1},bv=toPort==='left'?{x:-1,y:0}:{x:0,y:-1};
  if(flowRoute==='curve'){const d=Math.max(45,Math.min(170,Math.hypot(b.x-a.x,b.y-a.y)/2));return `M${a.x},${a.y} C${a.x+av.x*d},${a.y+av.y*d} ${b.x+bv.x*d},${b.y+bv.y*d} ${b.x},${b.y}`;}
  const s={x:a.x+av.x*24,y:a.y+av.y*24},t={x:b.x+bv.x*24,y:b.y+bv.y*24};
  const mid=fromPort==='right'?`L${(s.x+t.x)/2},${s.y} L${(s.x+t.x)/2},${t.y}`:`L${s.x},${(s.y+t.y)/2} L${t.x},${(s.y+t.y)/2}`;
  return `M${a.x},${a.y} L${s.x},${s.y} ${mid} L${t.x},${t.y} L${b.x},${b.y}`;
}
function flowDrawEdges(pointer){
  const svg=$('flow-edges');if(!svg)return;svg.replaceChildren();
  const ns='http://www.w3.org/2000/svg',make=(tag,attrs)=>{const el=document.createElementNS(ns,tag);for(const [k,v]of Object.entries(attrs))el.setAttribute(k,v);return el;};
  const defs=make('defs',{}),marker=make('marker',{id:'flow-arrow',viewBox:'0 0 10 10',refX:9,refY:5,markerWidth:7,markerHeight:7,orient:'auto-start-reverse'});marker.append(make('path',{d:'M0 1 L9 5 L0 9 z',fill:'#1292c1'}));defs.append(marker);svg.append(defs);
  for(const e of project.edges){
    const target=project.steps.find(s=>s.id===e.to),record=results.find(r=>r.id===e.to);
    const d=flowPath(flowAnchor(e.from,e.fromPort),flowAnchor(e.to,e.toPort),e.fromPort,e.toPort),image=target.operation==='branch_merge'?(!record?.inputFrom||record.inputFrom===e.from):target.imageFrom===e.from;
    const guard=e.when==='true'?'成立':e.when==='false'?'不成立':e.when==='error'?'失败':e.when==='success'?'成功':'';
    const inactive=record?.skipped||results.find(r=>r.id===e.from)?.skipped;
    const group=make('g',{'data-edge-id':e.id,class:'flow-edge'+(flowEdge===e.id?' selected':'')+(inactive?' inactive':'')+(image?' image-edge':' dependency-edge'),tabindex:0,role:'button','aria-label':`${flowName(e.from)} → ${flowName(e.to)}，${image?'数据':'依赖'}连线${guard?'，'+guard+'时执行':''}`});
    group.append(make('path',{d,class:'edge-hit'}),make('path',{d,class:'edge-line','marker-end':'url(#flow-arrow)'}));
    if(guard){const a=flowAnchor(e.from,e.fromPort),b=flowAnchor(e.to,e.toPort),label=make('text',{x:(a.x+b.x)/2+8,y:(a.y+b.y)/2-8,class:'edge-condition'});label.textContent=guard;group.append(label);}
    const pick=()=>{flowEdge=e.id;flowLink=null;flowUpdateSelection();};group.onclick=event=>{event.stopPropagation();pick();};group.onkeydown=safe(event=>{if(event.key==='Enter'||event.key===' '){event.preventDefault();pick();}if(event.key==='Delete'){event.preventDefault();if(!running)flowCommit(FlowGraph.disconnect(project,e.id),'连线已删除');}});svg.append(group);
  }
  if(flowLink&&pointer)svg.append(make('path',{d:flowPath(flowAnchor(flowLink.from,flowLink.fromPort),pointer,flowLink.fromPort,'top'),class:'edge-preview'}));
}
function flowUpdateSelection(){
  document.querySelectorAll('.flow-port.output').forEach(b=>b.classList.toggle('connecting',flowLink?.from===b.dataset.node&&flowLink?.fromPort===b.dataset.side));
  document.querySelectorAll('.flow-edge').forEach(e=>e.classList.toggle('selected',e.dataset.edgeId===flowEdge));
  $('flow-disconnect').disabled=running||!flowEdge;
  $('flow-hint').textContent=flowLink?'点击目标输入端口 · Esc 取消':flowEdge?'已选择连线 · 点击工具箱插入模块 · Delete 断开':'Ctrl 多选 · Shift 框选 · 右键编辑 · 拖动节点自由布局';
  flowEditButtons();
}
function flowResize(){
  const positions=[project.sourcePosition,...project.steps.map(s=>s.position)];
  const w=Math.max(280,...positions.map(p=>p.x+240)),h=Math.max(360,...positions.map(p=>p.y+140));
  $('pipeline').style.width=w+'px';$('pipeline').style.height=h+'px';$('pipeline').style.transform=`scale(${flowZoom})`;
  $('flow-space').style.width=w*flowZoom+'px';$('flow-space').style.height=h*flowZoom+'px';$('flow-zoom-value').textContent=Math.round(flowZoom*100)+'%';
}
function flowFit(){const viewport=document.querySelector('.flow-viewport');flowResize();flowZoom=Math.max(.25,Math.min(1,(viewport.clientWidth-24)/parseFloat($('pipeline').style.width),(viewport.clientHeight-24)/parseFloat($('pipeline').style.height)));flowResize();viewport.scrollTo(0,0);}
function flowDrag(el,id){
  let start=null,moved=false,skip=false;
  el.addEventListener('click',e=>{if(skip){e.stopImmediatePropagation();skip=false;}},true);
  el.onpointerdown=e=>{if(running||e.button!==0||e.target.closest('button')||e.ctrlKey||e.metaKey)return;const ids=id!=='source'&&flowSelection.has(id)?[...flowSelection]:[id];start={x:e.clientX,y:e.clientY,positions:ids.map(key=>({id:key,position:{...flowPosition(key)}}))};moved=false;el.setPointerCapture(e.pointerId);};
  el.onpointermove=e=>{if(!start)return;let dx=Math.round((e.clientX-start.x)/flowZoom/10)*10,dy=Math.round((e.clientY-start.y)/flowZoom/10)*10;if(!moved&&Math.hypot(dx,dy)<4)return;moved=true;
    dx=Math.max(...start.positions.map(item=>12-item.position.x),Math.min(dx,...start.positions.map(item=>9800-item.position.x)));
    dy=Math.max(...start.positions.map(item=>12-item.position.y),Math.min(dy,...start.positions.map(item=>9800-item.position.y)));
    for(const item of start.positions){const p=flowPosition(item.id);p.x=item.position.x+dx;p.y=item.position.y+dy;const element=item.id==='source'?document.querySelector('.flow-source'):[...document.querySelectorAll('#pipeline .step')].find(n=>n.dataset.nodeId===item.id);element.style.left=p.x+'px';element.style.top=p.y+'px';}flowResize();flowDrawEdges();};
  el.onpointerup=()=>{if(!start)return;start=null;if(moved){skip=true;dirty(false);}};
  el.onpointercancel=()=>{if(start&&moved){for(const item of start.positions)Object.assign(flowPosition(item.id),item.position);renderPipeline();}start=null;};
  el.addEventListener('keydown',e=>{if(e.target!==el||running||!['ArrowLeft','ArrowRight','ArrowUp','ArrowDown'].includes(e.key))return;e.preventDefault();const p=flowPosition(id),d=e.shiftKey?50:10;p.x=Math.max(12,Math.min(9800,p.x+(e.key==='ArrowLeft'?-d:e.key==='ArrowRight'?d:0)));p.y=Math.max(12,Math.min(9800,p.y+(e.key==='ArrowUp'?-d:e.key==='ArrowDown'?d:0)));el.style.left=p.x+'px';el.style.top=p.y+'px';dirty(false);flowResize();flowDrawEdges();});
}
function flowRender(){
  for(const id of flowSelection)if(!project.steps.some(s=>s.id===id))flowSelection.delete(id);
  const pipeline=$('pipeline');pipeline.replaceChildren();$('step-count').textContent=project.steps.length+' 个算子';
  const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');svg.id='flow-edges';pipeline.append(svg);
  const sourceNode=document.createElement('div');sourceNode.className='flow-source';sourceNode.tabIndex=0;sourceNode.setAttribute('aria-label','数据源1 节点');sourceNode.style.left=project.sourcePosition.x+'px';sourceNode.style.top=project.sourcePosition.y+'px';
  const sourceLabel=document.createElement('span');sourceLabel.textContent=sourceCloud?'◈  数据源1 · 点云':'▧  数据源1';
  const wantsCloud=!!sourceCloud||project.steps.some(s=>s.operation.startsWith('cloud_'));
  const openSource=()=>{if(!running)$(wantsCloud?'open-cloud':'source-file').click();};
  sourceNode.title='拖动移动 · 双击打开'+(wantsCloud?'点云':'图像');sourceNode.ondblclick=openSource;sourceNode.addEventListener('keydown',e=>{if(e.target===sourceNode&&e.key==='Enter')openSource();});sourceNode.append(sourceLabel,flowPort('source','bottom',true),flowPort('source','right',true));flowDrag(sourceNode,'source');pipeline.append(sourceNode);
  project.steps.forEach((s,index)=>{
    const el=document.createElement('div');el.className='step'+(index===selected?' selected':'');el.dataset.index=index;el.dataset.nodeId=s.id;el.tabIndex=0;el.setAttribute('aria-label',`算子 ${index+1} ${flowLabel(s)}`);el.style.left=s.position.x+'px';el.style.top=s.position.y+'px';
    const result=results.find(item=>item.id===s.id);if(result)el.classList.add(result.error?'failed':result.skipped?'skipped':'done');if(activeStepId===s.id)el.classList.add('executing');
    const heading=document.createElement('div');heading.className='node-heading';
    const icon=document.createElement('span');icon.className='node-icon';icon.textContent=catalog[s.operation].glyph;const number=document.createElement('span');number.className='node-index';number.textContent=String(index+1).padStart(2,'0');const name=document.createElement('strong');name.textContent=flowLabel(s);heading.append(icon,number,name);
    const meta=document.createElement('div');meta.className='node-meta';const state=document.createElement('small');state.textContent=activeStepId===s.id?'正在执行…':result?(result.error?(result.handled?'失败 · 已转入处理分支':'执行失败'):result.skipped?'已跳过':`完成 · ${result.output.elapsedMs} ms`):s.imageFrom?'等待执行':'未连接';meta.append(state);
    const actions=document.createElement('div');actions.className='step-actions';
    for(const [text,label,action] of [['⚙','配置',()=>{flowSelect(s.id);renderPipeline();renderParams();openParameters();}],['×','移除',()=>{const next=FlowGraph.remove(project,s.id);selected=Math.min(selected,next.steps.length-1);flowCommit(next,'节点及关联连线已移除');}]]){const b=document.createElement('button');b.textContent=text;b.setAttribute('aria-label',label+' '+flowLabel(s));b.disabled=running;b.onclick=safe(e=>{e.stopPropagation();applyParams();action();});actions.append(b);}
    meta.append(actions);el.append(heading,meta,flowPort(s.id,'top',false),flowPort(s.id,'left',false),flowPort(s.id,'bottom',true),flowPort(s.id,'right',true));
    flowDrag(el,s.id);el.onclick=safe(event=>{if(running)return;applyParams();flowSelect(s.id,event.ctrlKey||event.metaKey);flowEdge=null;flowLink=null;flowUpdateSelection();document.querySelectorAll('.step').forEach(n=>n.classList.toggle('selected',Number(n.dataset.index)===selected));renderParams();if(result)showResult(result);});el.ondblclick=safe(()=>{if(!running){el.click();openParameters();}});el.addEventListener('keydown',e=>{if(e.target===el&&e.key==='Enter'){el.click();openParameters();}});pipeline.append(el);
  });
  flowResize();flowDrawEdges();flowUpdateSelection();
}
function flowRenderInputs(){
  const holder=$('flow-inputs');holder.replaceChildren();const s=selectedStep();if(!s)return;
  const title=document.createElement('div');title.className='section-caption';title.textContent='连线与数据来源';holder.append(title);
  const row=document.createElement('label');row.className='field';row.textContent='输入数据';const select=document.createElement('select');select.setAttribute('aria-label','输入数据来源');select.disabled=running;
  const parents=project.edges.filter(e=>e.to===s.id);if(!parents.length){const option=document.createElement('option');option.textContent='未连接';select.append(option);}
  for(const e of parents){const option=document.createElement('option');option.value=e.from;option.textContent=flowName(e.from);select.append(option);}select.value=s.imageFrom||'';
  select.onchange=safe(()=>{applyParams();s.imageFrom=select.value;dirty();flowDrawEdges();refreshInputPreview();});row.append(select);holder.append(row);
  if(s.operation==='branch_merge'){select.replaceChildren(new Option('自动选择唯一激活分支',''));select.disabled=true;select.dataset.fixed='true';}
  const hint=document.createElement('p');hint.className='muted';hint.textContent=s.operation==='camera_capture'?'等待所有上游完成后采集新数据帧；2D 清除旧深度/点云，RGB-D 保留原始深度，GenTL 3D 输出毫米点云与预览图。':'等待所有上游完成；选定来源传入图像和点云，其余连线作为执行依赖。实线为数据，虚线为依赖。';holder.append(hint);
  if(s.operation==='branch_merge')hint.textContent='等待上游完成或跳过；只允许一路激活，自动沿用该路的完整数据帧。结果字段 value 包含该路的模块结果。';
  const guards=project.edges.filter(e=>(e.to===s.id||e.from===s.id)&&e.from!=='source');
  if(guards.length){const table=formEl('table',undefined,'form-table branch-table'),head=formEl('tr');head.append(formEl('th','连线'),formEl('th','执行条件'));table.append(head);
    for(const edge of guards){const tr=formEl('tr'),cell=formEl('td'),name=flowName(edge.from)+' → '+flowName(edge.to);const guard=formSelect([['always','成功后执行（默认）'],['success','成功时执行'],['error','失败时执行'],...(project.steps.find(n=>n.id===edge.from)?.operation==='condition'?[['true','判断成立'],['false','判断不成立']]:[])],edge.when||'always',name+' 连线条件');guard.disabled=running;guard.onchange=safe(()=>{applyParams();edge.when=guard.value;dirty();renderPipeline();renderParams();});cell.append(guard);tr.append(formEl('td',name),cell);table.append(tr);}holder.append(table);
  }
}
function flowInit(){
  $('flow-layout').onclick=safe(()=>{if(running)return;applyParams();flowCommit(FlowGraph.layout(project),'已按连接层级排列');flowFit();});
  $('flow-fit').onclick=flowFit;
  $('flow-minus').onclick=()=>{flowZoom=Math.max(.25,flowZoom-.1);flowResize();};$('flow-plus').onclick=()=>{flowZoom=Math.min(2,flowZoom+.1);flowResize();};
  $('flow-routing').onchange=e=>{flowRoute=e.target.value;flowDrawEdges();};
  $('flow-disconnect').onclick=safe(()=>{if(!running&&flowEdge){applyParams();flowCommit(FlowGraph.disconnect(project,flowEdge),'连线已删除');}});
  $('flow-expand').onclick=()=>{const expanded=document.body.classList.toggle('flow-expanded');$('flow-expand').textContent=expanded?'收起':'展开';$('flow-expand').setAttribute('aria-expanded',String(expanded));requestAnimationFrame(flowFit);};
  document.addEventListener('keydown',safe(e=>{if(e.key==='Escape'){flowLink=null;flowEdge=null;flowDrawEdges();flowUpdateSelection();}if(e.key==='Delete'&&flowEdge&&!running&&!e.target.closest('input,textarea,select')){e.preventDefault();flowCommit(FlowGraph.disconnect(project,flowEdge),'连线已删除');}}));
  const viewport=document.querySelector('.flow-viewport');
  viewport.ondragover=e=>e.preventDefault();viewport.ondrop=safe(e=>{e.preventDefault();if(running)return;const payload=JSON.parse(e.dataTransfer.getData('text/plain'));if(catalog[payload.operation])addStep(payload.operation,flowPoint(e),payload.pluginKey);});
  let pan=null;viewport.addEventListener('pointerdown',e=>{if(e.button!==0||e.shiftKey||e.target.closest('.step,.flow-source,.flow-edge'))return;pan={x:e.clientX,y:e.clientY,left:viewport.scrollLeft,top:viewport.scrollTop};viewport.setPointerCapture(e.pointerId);});
  viewport.addEventListener('pointermove',e=>{if(pan){viewport.scrollLeft=pan.left+pan.x-e.clientX;viewport.scrollTop=pan.top+pan.y-e.clientY;}});viewport.addEventListener('pointerup',()=>pan=null);viewport.addEventListener('pointercancel',()=>pan=null);
}
