(function(root,factory){const node=typeof module==='object'&&module.exports;const api=factory(node?require('./hmi-layout.js'):root.HmiLayout,node?require('./variable-types.js'):root.VariableTypes);if(node)module.exports=api;else root.FlowGraph=api;})(typeof globalThis!=='undefined'?globalThis:this,function(HmiLayout,VariableTypes){
  'use strict';
  const SOURCE='source';
  const operations=new Set(['preprocess','locate','geometry','measure','barcode','ocr','defects','yolo','yolo_segment','script','variables','cloud_filter','cloud_plane','cloud_cluster','cloud_measure','cloud_height','cloud_register','modbus_read','modbus_write','modbus_wait','s7_read','s7_write','mqtt_publish','mqtt_receive','tcp_exchange','udp_exchange','serial_exchange','opcua_read','opcua_write','opcua_browse','opcua_wait','camera_capture']);
  const copy=value=>JSON.parse(JSON.stringify(value));
  for(const operation of ['condition','branch_merge','branch','delay','plugin','subflow','loop','pose_correct','group','distort_correct','nine_point','var_calc','elapsed_stats','receive_data','send_data','format_data','output_image','protocol_parse','text_save','display','rect_find','line_intersect','point_distance','point_line_distance','line_angle','point_circle_distance','circle_circle_distance','csharp_script','production_task'])operations.add(operation);
  function normalize(value,nested=false){
    if(!value||![1,2].includes(value.version)||typeof value.name!=='string'||!Array.isArray(value.steps)||value.steps.length>50)throw Error('工程格式无效，最多 50 个算子');
    const p=copy(value),legacy=p.version===1;
    p.id=p.id||globalThis.crypto.randomUUID();
    if(typeof p.id!=='string'||!/^[A-Za-z0-9_-]{1,80}$/.test(p.id)||['__proto__','constructor','prototype'].includes(p.id))throw Error('工程 ID 无效');
    p.variables=p.variables||{};dataObject(p.variables);
    if(p.variableTypes!==undefined){p.variableTypes=VariableTypes.definitions(p.variableTypes);VariableTypes.assert(p.variables,p.variableTypes,'流程初始变量');}
    if(p.history!==undefined){if(!p.history||typeof p.history!=='object'||Array.isArray(p.history)||typeof p.history.includeFrames!=='boolean'||Object.keys(p.history).some(k=>k!=='includeFrames'))throw Error('历史图像保留设置无效');}
    if(p.hmi!==undefined)p.hmi=HmiLayout.normalize(p.hmi);
    const ids=new Set([SOURCE]);
    p.steps.forEach((s,i)=>{
      if(!s||!operations.has(s.operation)||!s.params||typeof s.params!=='object'||Array.isArray(s.params)||(s.reference!==undefined&&typeof s.reference!=='string'))throw Error('工程包含无效算子');
      if(legacy&&!s.id)s.id='legacy-'+i;
      if(typeof s.id!=='string'||!s.id||s.id.length>80||ids.has(s.id))throw Error('节点 ID 无效或重复');
      ids.add(s.id);
      if(s.name!==undefined&&(typeof s.name!=='string'||!s.name.trim()||s.name.length>80))throw Error('模块名称应为 1–80 个字符');
      if(['__proto__','constructor','prototype'].includes(s.id))throw Error('节点 ID 保留字不可使用');
      s.variables=s.variables||{};dataObject(s.variables);dataObject(s.params);
      if(s.variableTypes!==undefined){s.variableTypes=VariableTypes.definitions(s.variableTypes);VariableTypes.assert(s.variables,s.variableTypes,'模块 '+s.id+' 初始变量');}
      if(!s.position)s.position={x:70,y:130+i*120};
      validatePosition(s.position);
    });
    p.sourcePosition=p.sourcePosition||{x:70,y:25};validatePosition(p.sourcePosition);
    if(legacy){p.edges=p.steps.map((s,i)=>({id:'edge-'+i,from:i?p.steps[i-1].id:SOURCE,to:s.id,fromPort:'bottom',toPort:'top'}));p.steps.forEach((s,i)=>s.imageFrom=i?p.steps[i-1].id:SOURCE);}
    p.version=2;
    if(!Array.isArray(p.edges)||p.edges.length>250)throw Error('连线格式无效，最多 250 条');
    const pairs=new Set(),edgeIds=new Set();
    for(const e of p.edges){
      if(!e||typeof e.id!=='string'||!e.id||edgeIds.has(e.id)||!ids.has(e.from)||!ids.has(e.to)||e.to===SOURCE||e.from===e.to)throw Error('连线端点无效');
      const pair=JSON.stringify([e.from,e.to]);if(pairs.has(pair))throw Error('存在重复连线');pairs.add(pair);edgeIds.add(e.id);
      e.fromPort=e.fromPort||'bottom';e.toPort=e.toPort||'top';
      if(!['bottom','right'].includes(e.fromPort)||!['top','left'].includes(e.toPort))throw Error('连接端口无效');
      if(e.when!==undefined&&!['always','true','false','success','error'].includes(e.when)){
        const fromStep=p.steps.find(s=>s.id===e.from);
        if(!(fromStep&&fromStep.operation==='branch'&&typeof e.when==='string'&&e.when.length>0&&e.when.length<=80))throw Error('连线条件无效');
      }
      if(['true','false'].includes(e.when)&&p.steps.find(s=>s.id===e.from)?.operation!=='condition')throw Error('条件连线必须从条件判断节点输出');
      if(e.from===SOURCE&&e.when==='error')throw Error('数据源没有算子错误输出');
    }
    for(const s of p.steps){
      const parents=p.edges.filter(e=>e.to===s.id).map(e=>e.from);
      if(s.imageFrom!=null&&!parents.includes(s.imageFrom))throw Error('图像来源必须是已连接的上游节点');
      s.imageFrom=s.imageFrom||parents[0]||null;
    }
    order(p,false);
    if(p.outputNode!==undefined&&p.outputNode!==null&&!p.steps.some(s=>s.id===p.outputNode))throw Error('子流程输出节点不存在');
    if(p.subflows!==undefined){
      if(nested||!Array.isArray(p.subflows)||p.subflows.length>20)throw Error('子流程定义只能存放在主工程中，最多 20 项');
      p.subflows=p.subflows.map(def=>normalize(def,true));
      const names=new Set();for(const def of p.subflows){if(names.has(def.id))throw Error('子流程编号重复');names.add(def.id);}
    }
    if(!nested){
      const library=p.subflows||[],checked=new Map();
      const visit=(definition,stack)=>{if(stack.includes(definition.id))throw Error('子流程不允许递归调用');if(checked.has(definition.id))return checked.get(definition.id);let height=1;
        for(const step of definition.steps.filter(s=>['subflow','loop'].includes(s.operation))){const id=step.params.subflowId;if(id==null||id==='')continue;if(typeof id!=='string')throw Error('子流程必须从定义列表中选择');const child=library.find(d=>d.id===id);if(!child)throw Error('引用的子流程不存在：'+id);height=Math.max(height,1+visit(child,[...stack,definition.id]));}if(height>4)throw Error('子流程最多嵌套 4 层');checked.set(definition.id,height);return height;
      };
      for(const def of library)visit(def,[]);
      for(const step of p.steps.filter(s=>['subflow','loop'].includes(s.operation))){const id=step.params.subflowId;if(id!=null&&id!==''&&(typeof id!=='string'||!library.some(d=>d.id===id)))throw Error('引用的子流程不存在');}
    }
    return p;
  }
  function dataObject(value){
    if(!value||typeof value!=='object'||Array.isArray(value))throw Error('变量与参数必须使用名称与值组成的字段表');
    const visit=(v,depth)=>{if(depth>20)throw Error('嵌套数据超过 20 层');if(typeof v==='number'&&!Number.isFinite(v))throw Error('数据包含无效数值');if(v&&typeof v==='object')for(const [k,item] of Object.entries(v)){if(['__proto__','constructor','prototype'].includes(k))throw Error('数据包含保留名称');visit(item,depth+1);}};visit(value,0);
  }
  function validatePosition(pos){if(!pos||!Number.isFinite(pos.x)||!Number.isFinite(pos.y)||pos.x<0||pos.y<0||pos.x>10000||pos.y>10000)throw Error('节点坐标超出画布范围');}
  function order(p,requireConnected=true){
    const remaining=new Set(p.steps.map(s=>s.id)),done=new Set([SOURCE]),sorted=[];
    while(remaining.size){
      const ready=p.steps.filter(s=>remaining.has(s.id)&&p.edges.filter(e=>e.to===s.id).every(e=>done.has(e.from)));
      if(!ready.length)throw Error('流程包含循环连接，请断开回路');
      for(const s of ready){sorted.push(s);remaining.delete(s.id);done.add(s.id);}
    }
    if(requireConnected)for(const s of sorted){if(!p.edges.some(e=>e.to===s.id)||!s.imageFrom)throw Error('存在未连接图像源的节点：'+s.id+'，请连接后再运行');}
    return sorted;
  }
  function connect(p,edge){
    const next=copy(p);next.edges.push(edge);
    const target=next.steps.find(s=>s.id===edge.to);if(target&&!target.imageFrom)target.imageFrom=edge.from;
    return normalize(next);
  }
  function disconnect(p,id){
    const next=copy(p);next.edges=next.edges.filter(e=>e.id!==id);
    for(const s of next.steps)if(!next.edges.some(e=>e.to===s.id&&e.from===s.imageFrom))s.imageFrom=next.edges.find(e=>e.to===s.id)?.from||null;
    return normalize(next);
  }
  function remove(p,id){let next=copy(p);for(const e of [...next.edges])if(e.from===id||e.to===id)next=disconnect(next,e.id);next.steps=next.steps.filter(s=>s.id!==id);if(next.outputNode===id)next.outputNode=next.steps.at(-1)?.id||null;return normalize(next);}
  function layout(p){
    const next=copy(p),levels=new Map([[SOURCE,0]]),rows=new Map();
    for(const s of order(next,false)){const parents=next.edges.filter(e=>e.to===s.id);const level=parents.length?1+Math.max(...parents.map(e=>levels.get(e.from)||0)):1;levels.set(s.id,level);if(!rows.has(level))rows.set(level,[]);rows.get(level).push(s);}
    const columns=Math.min(8,Math.max(1,...[...rows.values()].map(row=>row.length)));
    next.sourcePosition={x:40+(columns-1)*125,y:30};
    let y=160;
    for(const [,nodes] of [...rows.entries()].sort((a,b)=>a[0]-b[0])){nodes.forEach((s,i)=>s.position={x:40+Math.max(0,columns-nodes.length)*125+(i%8)*250,y:y+Math.floor(i/8)*130});y+=Math.ceil(nodes.length/8)*130;}
    return next;
  }
  function plan(p,target){
    let steps=order(p,false);
    if(target){const needed=new Set([target]);for(let i=steps.length-1;i>=0;i--)if(needed.has(steps[i].id))for(const e of p.edges.filter(e=>e.to===steps[i].id))needed.add(e.from);steps=steps.filter(s=>needed.has(s.id));if(!steps.some(s=>s.id===target))throw Error('请选择算子');}
    for(const s of steps)if(!p.edges.some(e=>e.to===s.id)||!s.imageFrom)throw Error('存在未连接图像源的节点：'+s.id+'，请连接后再运行');
    return steps;
  }
  function activation(p,step,outputs){
    const incoming=p.edges.filter(e=>e.to===step.id);
    const active=incoming.filter(e=>{
      if(e.from===SOURCE)return e.when!=='error';
      if(!outputs.has(e.from))return false;
      const output=outputs.get(e.from);
      if(e.when==='error')return output.flowError===true;
      if(output.flowError===true)return false;
      if(!e.when||['always','success'].includes(e.when))return true;
      if(e.when==='true'||e.when==='false')return output.result&&output.result.passed===(e.when==='true');
      // branch path name / id
      if(output.result&&(e.when===output.result.pathId||e.when===output.result.pathName))return true;
      return false;
    });
    return {active,skip:step.operation==='branch_merge'?active.length===0:active.length!==incoming.length};
  }
  function expanded(p,target){
    const result=[],library=p.subflows||[],visited=new Set();
    const visit=(steps,stack=[])=>{for(const step of steps){result.push(step);if(['subflow','loop'].includes(step.operation)){
      const def=library.find(d=>d.id===step.params.subflowId);if(!def)throw Error('请为调用节点选择子流程');if(stack.includes(def.id)||stack.length>=4)throw Error('子流程递归或嵌套层数超限');if(!def.steps.length||!def.outputNode)throw Error('子流程需要算子及明确的输出节点');if(!visited.has(def.id)){visited.add(def.id);visit(plan(def),[...stack,def.id]);}
    }else if(step.operation==='group'){
      const inner=step.params&&step.params.inner;const kids=inner&&Array.isArray(inner.steps)?inner.steps:[];
      if(kids.length){if(stack.length>=4)throw Error('组合模块嵌套层数超限');visit(kids,[...stack,'group:'+step.id]);}
    }}};visit(plan(p,target));return result;
  }
  // Dependencies determine order; only the chosen image parent supplies pixels.
  // Recognition operators propagate their input, not their painted overlay.
  async function run(p,source,invoke,{target,onStart=()=>{},onResult=()=>{},cancelled=()=>false}={}){
    const steps=plan(p,target);
    if(steps.some(s=>['condition','branch_merge','branch','delay','subflow','loop','pose_correct'].includes(s.operation))||p.edges.some(e=>['success','error'].includes(e.when)))throw Error('含流程控制块的工程请使用服务器运行平台执行');
    const images=new Map([[SOURCE,source]]),outputs=[];
    for(const s of steps){
      if(cancelled())break;
      onStart(s);
      try{const input=images.get(s.imageFrom);if(!input)throw Error('上游图像不可用');const output=await invoke(s,input);if(cancelled())break;images.set(s.id,s.operation==='preprocess'?output.annotatedImage:input);outputs.push({id:s.id,output});onResult(s,output);}
      catch(error){onResult(s,null,error);throw error;}
    }
    return outputs;
  }
  return {SOURCE,normalize,order,plan,connect,disconnect,remove,layout,run,activation,expanded};
});
