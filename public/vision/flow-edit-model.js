(function(root,factory){const node=typeof module==='object'&&module.exports;const api=factory(node?require('./flow-graph.js'):root.FlowGraph);if(node)module.exports=api;else root.FlowEdit=api;})(globalThis,function(Graph){
  'use strict';
  const clone=value=>JSON.parse(JSON.stringify(value));
  function copy(project,ids){
    const chosen=new Set(ids),steps=project.steps.filter(s=>chosen.has(s.id));
    if(!steps.length)throw Error('请先选择模块');
    return clone({projectId:project.id,steps,edges:project.edges.filter(e=>chosen.has(e.to))});
  }
  function paste(project,clipboard,makeId,offset=40){
    if(!clipboard?.steps?.length)throw Error('请先复制模块');
    if(clipboard.projectId!==project.id)throw Error('请在当前流程重新复制模块');
    if(project.steps.length+clipboard.steps.length>50)throw Error('粘贴后不能超过 50 个算子');
    const next=clone(project),mapping=new Map(clipboard.steps.map(s=>[s.id,makeId()]));
    const existing=new Set(project.steps.map(s=>s.id));existing.add('source');
    const remap=value=>{
      if(Array.isArray(value))return value.map(remap);
      if(!value||typeof value!=='object')return value;
      if(Object.keys(value).length===1&&typeof value.$ref==='string'){
        const match=/^results\.([^.]+)\.(.+)$/.exec(value.$ref);
        if(match&&mapping.has(match[1]))return {$ref:'results.'+mapping.get(match[1])+'.'+match[2]};
        if(match&&!existing.has(match[1]))throw Error('复制的模块引用了已删除的上游，请重新复制');
      }
      return Object.fromEntries(Object.entries(value).map(([k,v])=>[k,remap(v)]));
    };
    for(const original of clipboard.steps){
      const step=remap(clone(original));step.id=mapping.get(original.id);
      if(step.name)step.name=(step.name+' 副本').slice(0,80);
      step.position={x:Math.min(9800,step.position.x+offset),y:Math.min(9800,step.position.y+offset)};
      step.imageFrom=mapping.get(original.imageFrom)||(existing.has(original.imageFrom)?original.imageFrom:null);
      next.steps.push(step);
    }
    for(const edge of clipboard.edges){
      const from=mapping.get(edge.from)||edge.from;
      if(!existing.has(from)&&!Array.from(mapping.values()).includes(from))continue;
      next.edges.push({...clone(edge),id:makeId(),from,to:mapping.get(edge.to)});
    }
    return {project:Graph.normalize(next),ids:Array.from(mapping.values())};
  }
  function remove(project,ids){let next=project;for(const id of ids)next=Graph.remove(next,id);return next;}
  // Keep the original branch condition upstream; only redirect the chosen data input.
  function insert(project,edgeId,nodeId,makeId){
    const next=clone(project),edge=next.edges.find(e=>e.id===edgeId),node=next.steps.find(s=>s.id===nodeId);
    if(!edge||!node)throw Error('插入位置或模块不存在');
    if(next.edges.some(e=>e.to===nodeId||e.from===nodeId))throw Error('只能插入尚未连接的模块');
    const target=next.steps.find(s=>s.id===edge.to);node.imageFrom=edge.from;
    next.edges=next.edges.filter(e=>e.id!==edgeId);
    next.edges.push({...edge,id:makeId(),to:nodeId,toPort:'top'},
      {id:makeId(),from:nodeId,to:edge.to,fromPort:'bottom',toPort:edge.toPort,when:'always'});
    if(target.imageFrom===edge.from)target.imageFrom=nodeId;
    return Graph.normalize(next);
  }
  class History {
    constructor(limit=50,maxBytes=24*1024*1024){this.limit=limit;this.maxBytes=maxBytes;this.reset(null);}
    reset(value){this.entries=[JSON.stringify(value)];this.index=0;}
    record(value){
      const encoded=JSON.stringify(value);if(encoded===this.entries[this.index])return;
      this.entries.splice(this.index+1);this.entries.push(encoded);this.index++;
      while(this.entries.length>1&&(this.entries.length>this.limit+1||this.entries.reduce((n,s)=>n+s.length*2,0)>this.maxBytes)){this.entries.shift();this.index--;}
    }
    get canUndo(){return this.index>0;}
    get canRedo(){return this.index<this.entries.length-1;}
    undo(){if(this.canUndo)this.index--;return JSON.parse(this.entries[this.index]);}
    redo(){if(this.canRedo)this.index++;return JSON.parse(this.entries[this.index]);}
  }
  return {copy,paste,remove,insert,History};
});
