'use strict';
const crypto=require('node:crypto');
const graph=require('../public/vision/flow-graph.js');
const {VariableStore,object,resolve}=require('./variable-store.cjs');
const scripts=require('./script-runner.cjs');
const industrial=require('./industrial-client.cjs');
const cameras=require('./camera-client.cjs');
const control=require('./flow-control.cjs');
const {RunHistory,archiveRecord}=require('./run-history.cjs');
const {setImmediate:yieldExecution}=require('node:timers/promises');
const {frame,cloud:validateCloud,depth:validateDepth,CLOUD_OPERATIONS}=require('./frame.cjs');
class Runtime{
  constructor(directory,vision,plugins=null){this.variables=new VariableStore(directory);this.history=new RunHistory(directory);this.monitor=new (require('./runtime-monitor.cjs').RuntimeMonitor)(directory);this.monitorError='';this.vision=vision;this.plugins=plugins;this.jobs=new Map();this.active=null;this.owner=null;}
  get busy(){return !!(this.active||this.owner);}
  reserve(owner){if(!owner||this.busy)throw Error('运行平台正在执行其他任务，请稍后再试');this.owner=owner;}
  release(owner){if(this.owner===owner)this.owner=null;}
  prepare(request){
    const project=graph.normalize(request.project),steps=graph.plan(project,request.target);
    const expanded=graph.expanded(project,request.target);
    if(expanded.some(s=>s.operation==='script')&&request.allowScripts!==true)throw Error('请先启用本次可信 Python 脚本执行');
    // Fail before any device writes if a pinned server plugin is unavailable.
    for(const step of expanded.filter(s=>s.operation==='plugin')){if(!this.plugins)throw Error('服务器未配置算子插件');this.plugins.get(step.params);}
    this.variables.assertTypes(project,this.variables.snapshot(project));
    const input=frame(request);return {project,steps,input};
  }
  start(request,owner=null,trigger=null){
    if(this.active||(this.owner&&owner!==this.owner))throw Error('运行平台正在执行其他任务，请稍后再试');
    const {project,steps,input}=this.prepare(request);
    if(trigger){if(!owner||trigger.kind!=='mqtt'||typeof trigger.variable!=='string'||!/^[A-Za-z_][A-Za-z0-9_]{0,63}$/.test(trigger.variable)||['__proto__','constructor','prototype'].includes(trigger.variable))throw Error('事件输入变量无效');trigger=object(trigger,'事件输入');}
    const job={id:crypto.randomUUID(),projectId:project.id,origin:owner?'continuous':'manual',state:'running',activeStep:null,results:[],startedAt:Date.now(),cancelled:false,controller:new AbortController()};
    if(trigger){job.origin='mqtt';job.trigger=trigger;}
    this.active=job;this.jobs.set(job.id,job);
    // Preserve a small bounded history, not unlimited image payloads.
    while(this.jobs.size>3)this.jobs.delete(this.jobs.keys().next().value);
    job.promise=this.execute(job,project,steps,input);
    return this.poll(job.id);
  }
  poll(id,after=0){const job=this.jobs.get(id);if(!job)throw Error('运行记录不存在或已过期');if(!Number.isInteger(after)||after<0)throw Error('结果游标无效');return {id:job.id,state:job.archive?.state==='writing'?'running':job.state,archive:job.archive,activeStep:job.activeStep,activePath:job.activePath,results:job.results.slice(after),cursor:job.results.length,error:job.error,elapsedMs:(job.endedAt||Date.now())-job.startedAt,variables:job.variables,monitorWarning:job.monitorWarning||'',monitor:{...this.monitor.view(job.projectId),error:this.monitorError}};}
  cancel(id){const job=this.jobs.get(id);if(!job)throw Error('运行记录不存在');if(job.state==='running'){job.cancelled=true;job.controller.abort();}return this.poll(id,job.results.length);}
  view(project,since){
    const p=graph.normalize(project),job=[...this.jobs.values()].reverse().find(j=>j.projectId===p.id),variables=this.variables.snapshot(p);
    const monitor={...this.monitor.view(p.id),error:this.monitorError};
    if(!job)return {projectId:p.id,variables,version:'none:'+monitor.revision,status:{state:'idle'},results:[],monitor};
    const state=job.archive?.state==='writing'?'running':job.state,version=[job.id,state,job.archive?.state||'',job.results.length,job.activeStep||'',monitor.revision].join(':');
    return {projectId:p.id,variables,version,monitor,status:{id:job.id,state,archive:job.archive,error:job.error,startedAt:job.startedAt,elapsedMs:(job.endedAt||Date.now())-job.startedAt,activeStep:job.activeStep,monitorWarning:job.monitorWarning||''},...(since===version?{}:{results:job.results})};
  }
  async execute(job,project,steps,sourceFrame){
    const previousGlobal=JSON.stringify(this.variables.state.global);
    try{
      const initial=this.variables.snapshot(project);
      if(job.trigger){initial.flow[job.trigger.variable]=structuredClone(job.trigger.message);this.variables.assertTypes(project,initial);}
      const response=await this.executeGraph(job,project,steps,sourceFrame,initial,project.subflows||[],{count:0,bytes:0},[],job.results);
      if(job.cancelled){job.state='cancelled';}else{this.variables.commit(project,response.vars,response.vars.revision);job.state='completed';job.variables=this.variables.snapshot(project);}
    }catch(error){job.state=job.cancelled?'cancelled':'failed';job.error=error.message;}
    finally{
      job.activeStep=null;job.endedAt=Date.now();job.archive={state:'writing'};
      this.recordMonitor(project,{variables:this.variables.snapshot(project),results:job.results,status:{state:job.state,error:job.error||'',elapsedMs:job.endedAt-job.startedAt}},{kind:'job',jobId:job.id,time:job.endedAt},previousGlobal);job.monitorWarning=this.monitorError;
      try{await this.history.store(archiveRecord(job,project,steps,sourceFrame,this.variables.snapshot(project)));job.archive={state:'saved'};}
      catch(error){job.archive={state:'failed',error:'运行结果归档失败：'+error.message};}
      this.active=null;
    }
  }
  async executeGraph(job,project,steps,sourceFrame,initial,library,budget,path,records){
    let vars=initial;const frames=new Map([['source',sourceFrame]]),outputs=new Map(),planned=new Set(steps.map(s=>s.id));
      for(const step of steps){
        if(job.cancelled)break;
        if(++budget.count>1000){const error=Error('本轮执行超过 1000 个节点访问上限');error.executionLimit=true;throw error;}
        if(budget.count%25===0)await yieldExecution();if(job.cancelled)break;
        job.activeStep=path[0]||step.id;job.activePath=[...path,step.id];
        const activation=graph.activation(project,step,outputs);
        if(activation.skip){
          const reason=step.operation==='branch_merge'?'没有激活的输入分支':'上游分支未激活';
          records.push({id:step.id,skipped:true,reason,output:{result:{status:'已跳过',reason},elapsedMs:0}});continue;
        }
        const parents=new Set();const collect=id=>{for(const edge of project.edges.filter(e=>e.to===id)){if(parents.has(edge.from))continue;parents.add(edge.from);collect(edge.from);}};collect(step.id);
        const context={global:vars.global,flow:vars.flow,module:vars.modules[step.id],results:Object.fromEntries([...outputs].filter(([id])=>parents.has(id)).map(([id,out])=>[id,out.result]))};
        const inputFrom=step.operation==='branch_merge'?activation.active[0]?.from:step.imageFrom;
        const input=frames.get(inputFrom)||{image:'',cloud:null};let output,nextScriptImage,nextFrame;
        const handlesError=project.edges.some(e=>e.from===step.id&&e.when==='error'&&planned.has(e.to));
        const before=handlesError?structuredClone(vars):null,previousBytes=budget.bytes;
        try{
          // Unary conditions do not resolve a hidden, unused right-hand binding.
          let raw=step.params;
          if(['subflow','loop'].includes(step.operation)){
            raw={...raw};
            if(step.operation==='subflow')for(const key of ['iterations','mode','frameMode','stopField','stopValue'])delete raw[key];
            else{raw.mode=resolve(raw.mode??'count',context);if(raw.mode==='count'){delete raw.stopField;delete raw.stopValue;}}
          }
          if(step.operation==='yolo_segment'){
            raw={...raw,output:resolve(raw.output??'overlay',context)};
            if(raw.output==='mask')delete raw.overlayAlpha;
          }
          if(step.operation==='serial_exchange')raw=require('./serial-client.cjs').activeParams(raw,value=>resolve(value,context));
          if(['tcp_exchange','udp_exchange'].includes(step.operation))raw=require('./socket-client.cjs').activeParams(step.operation,raw,value=>resolve(value,context));
          if(step.operation==='condition'){
            raw={...raw,comparison:resolve(raw.comparison??'eq',context)};
            if(['is_true','is_false'].includes(raw.comparison))delete raw.right;
            if(Array.isArray(raw.rules)){
              raw.rules=raw.rules.map(rule=>{
                const r={...rule,comparison:resolve(rule.comparison??'eq',context),left:resolve(rule.left,context),right:resolve(rule.right,context)};
                if(['is_true','is_false'].includes(r.comparison))delete r.right;
                return r;
              });
            }
          }
          if(step.operation==='branch'&&Array.isArray(raw.paths)){
            raw={...raw,paths:raw.paths.map(path=>({
              ...path,
              left:resolve(path.left,context),
              right:resolve(path.right,context),
              comparison:resolve(path.comparison??'eq',context),
            }))};
          }
          if(['modbus_wait','opcua_wait'].includes(step.operation)){
            raw={...raw,comparison:resolve(raw.comparison??'eq',context)};
            if(['is_true','is_false'].includes(raw.comparison))delete raw.expectedValue;
          }
          if(step.operation==='cloud_register'){
            raw={...raw,method:resolve(raw.method??'icp',context)};
            if(raw.method==='global')delete raw.initialTransform;
            else if(raw.method==='icp')for(const key of ['voxelSize','ransacIterations','ransacConfidence','minFitness','minTargetFitness','maxRmsError'])delete raw[key];
          }
          let runOp=step.operation;
          if(runOp==='rect_find'){runOp='geometry';raw={...raw,feature:raw.feature||'rects'};}
          const params=resolve(raw,context);
          if(['subflow','loop'].includes(step.operation)){
            const began=Date.now(),nested=await this.invokeSubflow(job,step,params,input,vars,library,budget,[...path,step.id]);
            vars=nested.vars;nextFrame=nested.frame;output={result:nested.result,elapsedMs:Date.now()-began,image:nextFrame.image,annotatedImage:nested.displayImage,cloud:nextFrame.cloud,depth:nextFrame.depth};
          }else if(step.operation==='group'){
            const began=Date.now(),nested=await this.invokeGroup(job,step,params,input,vars,library,budget,[...path,step.id]);
            vars=nested.vars;nextFrame=nested.frame;output={result:nested.result,elapsedMs:Date.now()-began,image:nextFrame?.image,annotatedImage:nested.displayImage,cloud:nextFrame?.cloud,depth:nextFrame?.depth};
          }else if(step.operation==='condition'){
            output={result:control.condition(params),elapsedMs:0,annotatedImage:input.image,cloud:input.cloud};
          }else if(step.operation==='branch'){
            output={result:control.branch(params),elapsedMs:0,annotatedImage:input.image,cloud:input.cloud};
          }else if(step.operation==='pose_correct'){
            output={result:control.poseCorrect(params,input),elapsedMs:0,annotatedImage:input.image,cloud:input.cloud,image:input.image};
          }else if(step.operation==='distort_correct'){
            const began=Date.now();
            const gate=control.distortCorrect(params,input);
            if(gate.status==='disabled'||gate.status==='uncalibrated'){
              output={result:gate,elapsedMs:Date.now()-began,annotatedImage:input.image,cloud:input.cloud,image:input.image};
            }else if(!input.image){
              output={result:{...gate,status:'no_image',note:'上游无图像'},elapsedMs:Date.now()-began,annotatedImage:input.image,cloud:input.cloud,image:input.image};
            }else{
              const vis=await this.vision.run({operation:'distort_correct',image:input.image,params});
              nextFrame={image:vis.annotatedImage||input.image,cloud:input.cloud,depth:input.depth??null};
              output={result:{...(vis.result||{}),status:'ok',mode:params.mode||'file'},elapsedMs:vis.elapsedMs??(Date.now()-began),annotatedImage:vis.annotatedImage||input.image,cloud:input.cloud,image:vis.annotatedImage||input.image};
            }
          }else if(step.operation==='nine_point'){
            output={result:control.ninePoint(params),elapsedMs:0,annotatedImage:input.image,cloud:input.cloud,image:input.image};
          }else if(step.operation==='var_calc'){
            const began=Date.now();
            const priorResults=Object.fromEntries(outputs.entries());
            const result=control.varCalc(params,{global:vars.global,flow:vars.flow,module:vars.modules[step.id]||(vars.modules[step.id]={}),results:priorResults,steps});
            output={result,elapsedMs:Date.now()-began,annotatedImage:input.image,cloud:input.cloud};
          }else if(step.operation==='elapsed_stats'){
            const began=Date.now();
            const prior=[];
            for(const [id,out] of outputs.entries())prior.push({id,output:out});
            output={result:control.elapsedStats(params,prior,steps),elapsedMs:Date.now()-began,annotatedImage:input.image,cloud:input.cloud};
          }else if(step.operation==='receive_data'){
            const began=Date.now();
            const bus=require('./comm-bus.cjs');
            const result=await bus.receive(params,{project,vars,signal:job.controller.signal});
            const scope=params.targetScope||'flow',name=params.targetVar||'recvData';
            if(['global','flow','module'].includes(scope)&&typeof name==='string'&&/^[A-Za-z_][A-Za-z0-9_]{0,63}$/.test(name)){
              (scope==='module'?vars.modules[step.id]:vars[scope])[name]=result.payload;
            }
            output={result,elapsedMs:Date.now()-began,annotatedImage:input.image,cloud:input.cloud};
          }else if(step.operation==='send_data'){
            const began=Date.now();
            const bus=require('./comm-bus.cjs');
            let message=params.message;
            if((params.sourceMode||'text')==='variable'&&params.sourceVar){
              const scope=params.sourceScope||'flow';
              message=(scope==='module'?vars.modules[step.id]:vars[scope])?.[params.sourceVar];
            }
            const result=await bus.send(params,message,{project,vars,signal:job.controller.signal});
            output={result,elapsedMs:Date.now()-began,annotatedImage:input.image,cloud:input.cloud};
          }else if(step.operation==='format_data'){
            const began=Date.now();
            output={result:control.formatData(params,{global:vars.global,flow:vars.flow,module:vars.modules[step.id]||{}}),elapsedMs:Date.now()-began,annotatedImage:input.image,cloud:input.cloud};
          }else if(step.operation==='protocol_parse'){
            const began=Date.now();
            output={result:control.protocolParse(params,{global:vars.global,flow:vars.flow,module:vars.modules[step.id]||{}}),elapsedMs:Date.now()-began,annotatedImage:input.image,cloud:input.cloud};
          }else if(step.operation==='text_save'){
            const began=Date.now();
            output={result:control.textSave(params,{global:vars.global,flow:vars.flow,module:vars.modules[step.id]||{}}),elapsedMs:Date.now()-began,annotatedImage:input.image,cloud:input.cloud};
          }else if(step.operation==='output_image'){
            const began=Date.now();
            output={result:control.outputImage(params,input),elapsedMs:Date.now()-began,annotatedImage:input.image,cloud:input.cloud,image:input.image};
          }else if(step.operation==='line_intersect'){
            const began=Date.now();
            const ctxResults={};
            for(const [id,out] of outputs.entries())ctxResults[id]=out;
            output={result:control.lineIntersect(params,{results:ctxResults}),elapsedMs:Date.now()-began,annotatedImage:input.image,cloud:input.cloud,image:input.image};
          }else if(step.operation==='point_distance'){
            const began=Date.now();
            const ctxResults={};
            for(const [id,out] of outputs.entries())ctxResults[id]=out;
            output={result:control.pointDistance(params,{results:ctxResults}),elapsedMs:Date.now()-began,annotatedImage:input.image,cloud:input.cloud,image:input.image};
          }else if(step.operation==='point_line_distance'){
            const began=Date.now();
            const ctxResults={};
            for(const [id,out] of outputs.entries())ctxResults[id]=out;
            output={result:control.pointLineDistance(params,{results:ctxResults}),elapsedMs:Date.now()-began,annotatedImage:input.image,cloud:input.cloud,image:input.image};
          }else if(step.operation==='csharp_script'){
            const began=Date.now();
            const lang=params.language||'csharp';
            if(lang==='python'&&params.code&&request.allowScripts===true){
              const scriptContext={vars:structuredClone({global:context.global,flow:context.flow,module:context.module}),results:context.results,image:input.image,cloud:input.cloud,depth:input.depth??null,params:params.arguments||{}};
              const response=await scripts.run(params.code,scriptContext,{timeoutMs:params.timeoutMs??5000,signal:job.controller.signal});
              const data=response.data;object(data.result??{},'脚本结果');
              nextScriptImage=data.image??input.image;
              output={result:{...(data.result||{}),language:'python',status:'ok',via:'csharp_script→script'},elapsedMs:response.elapsedMs,logs:response.logs,annotatedImage:data.annotatedImage??nextScriptImage,cloud:data.cloud===undefined?input.cloud:data.cloud===null?null:validateCloud(data.cloud),depth:data.depth===undefined?(input.depth??null):data.depth===null?null:validateDepth(data.depth),image:nextScriptImage};
            }else{
              output={result:control.csharpScript(params),elapsedMs:Date.now()-began,annotatedImage:input.image,cloud:input.cloud,image:input.image};
            }
          }else if(step.operation==='production_task'){
            const began=Date.now();
            output={result:control.productionTask(params,{global:vars.global,flow:vars.flow,module:vars.modules[step.id]||{}}),elapsedMs:Date.now()-began,annotatedImage:input.image,cloud:input.cloud,image:input.image};
          }else if(step.operation==='branch_merge'){
            if(activation.active.length!==1)throw Error('分支汇合要求恰好一路激活；并行汇合请使用普通节点并选择数据来源');
            output={result:{inputFrom,value:outputs.get(inputFrom)?.result??null},elapsedMs:0,annotatedImage:input.image,cloud:input.cloud};
          }else if(step.operation==='delay'){
            const began=Date.now(),result=await control.delay(params,job.controller.signal);
            output={result,elapsedMs:Date.now()-began,annotatedImage:input.image,cloud:input.cloud};
          }else if(step.operation==='variables'){
            const scope=params.scope||'flow',name=params.name;
            if(!['global','flow','module'].includes(scope)||typeof name!=='string'||!/^[A-Za-z_][A-Za-z0-9_]{0,63}$/.test(name)||['__proto__','constructor','prototype'].includes(name))throw Error('变量作用域或名称无效');
            const values=context[scope];const mode=params.mode||'set';let value=params.value;
            if(mode==='increment'){if(typeof value!=='number'||(values[name]!==undefined&&typeof values[name]!=='number'))throw Error('累加操作只接受数字');value=(values[name]||0)+value;}
            else if(mode!=='set')throw Error('未知变量操作');
            values[name]=value;object(values,'变量');output={result:{scope,name,value},elapsedMs:0,annotatedImage:input.image,cloud:input.cloud};
          }else if(step.operation==='camera_capture'){
            output=await cameras.run({operation:step.operation,params},{signal:job.controller.signal});
          }else if(industrial.operations.has(step.operation)){
            output=await industrial.run({operation:step.operation,params},{signal:job.controller.signal});
          }else if(step.operation==='script'||step.operation==='plugin'){
            const scriptContext={vars:structuredClone({global:context.global,flow:context.flow,module:context.module}),results:context.results,image:input.image,cloud:input.cloud,depth:input.depth??null,params:params.arguments||{}};
            const response=step.operation==='plugin'?await this.plugins.run(params,scriptContext,{signal:job.controller.signal}):await scripts.run(params.code,scriptContext,{timeoutMs:params.timeoutMs??5000,signal:job.controller.signal});
            const data=response.data;object(data.result??{},'脚本结果');
            if(data.variables!==undefined){object(data.variables,'脚本变量');for(const [scope,values] of Object.entries(data.variables)){if(!['global','flow','module'].includes(scope))throw Error('未知脚本变量作用域：'+scope);const next=object(values,'脚本变量');if(scope==='module')vars.modules[step.id]=next;else vars[scope]=next;}}
            if(params.outputBindings!==undefined){
              if(!Array.isArray(params.outputBindings)||params.outputBindings.length>100)throw Error('脚本输出绑定最多 100 项');
              const targets=new Set();
              for(const binding of params.outputBindings){
                if(!binding||!['global','flow','module'].includes(binding.scope)||typeof binding.name!=='string'||!/^[A-Za-z_][A-Za-z0-9_]{0,63}$/.test(binding.name)||['__proto__','constructor','prototype'].includes(binding.name)||typeof binding.field!=='string'||!binding.field)throw Error('脚本输出绑定的范围、变量名或结果字段无效');
                const target=binding.scope+'.'+binding.name;if(targets.has(target))throw Error('脚本输出重复写入同一变量：'+binding.name);targets.add(target);
                const value=resolve({$ref:'results.output.'+binding.field},{results:{output:data.result||{}}});
                (binding.scope==='module'?vars.modules[step.id]:vars[binding.scope])[binding.name]=value;
              }
            }
            if(data.image!==undefined&&(typeof data.image!=='string'||data.image.length>17_000_000))throw Error('脚本输出图像无效');
            if(data.annotatedImage!==undefined&&(typeof data.annotatedImage!=='string'||data.annotatedImage.length>17_000_000))throw Error('脚本显示图像无效');
            nextScriptImage=data.image??input.image;
            output={result:data.result||{},elapsedMs:response.elapsedMs,logs:response.logs,annotatedImage:data.annotatedImage??nextScriptImage,cloud:data.cloud===undefined?input.cloud:data.cloud===null?null:validateCloud(data.cloud),depth:data.depth===undefined?(input.depth??null):data.depth===null?null:validateDepth(data.depth)};
            if(data.annotatedImage!==undefined)output.image=nextScriptImage;
          }else{
            if(CLOUD_OPERATIONS.has(runOp)){if(!input.cloud)throw Error('3D 算子需要输入点云，请打开点云文件');}
            else if(!input.image)throw Error('2D 算子需要输入图像');
            output=await this.vision.run({operation:runOp,image:input.image,cloud:input.cloud,reference:step.reference,params});
          }
          if(job.cancelled)break;
          this.variables.assertTypes(project,vars);
          budget.bytes+=Buffer.byteLength(JSON.stringify(output));if(budget.bytes>40_000_000){const error=Error('本次运行结果超过 40 MB，请减少图像尺寸或节点数量');error.executionLimit=true;throw error;}
          frames.set(step.id,nextFrame||{image:step.operation==='yolo_segment'&&params.output==='mask'?output.maskImage:['script','plugin'].includes(step.operation)?nextScriptImage:['preprocess','camera_capture','distort_correct'].includes(step.operation)?output.annotatedImage:input.image,cloud:step.operation==='camera_capture'?(output.cloud??null):(CLOUD_OPERATIONS.has(step.operation)||['script','plugin'].includes(step.operation))?(output.cloud??null):input.cloud,depth:['camera_capture','script','plugin'].includes(step.operation)?(output.depth??null):(input.depth??null)});outputs.set(step.id,output);records.push({id:step.id,inputFrom,output});
        }catch(error){
          if(job.cancelled||error.executionLimit)throw error;
          if(!handlesError){records.push({id:step.id,error:error.message,...(error.subflowTrace?{output:{result:{trace:error.subflowTrace},elapsedMs:0}}:{})});throw error;}
          // Restore only this failed step's variable writes. Prior successful steps remain pending.
          // Hardware writes and external script side effects cannot be undone here.
          vars=before;budget.bytes=previousBytes;
          const failure={flowError:true,result:{failed:true,error:String(error.message||error),operation:step.operation,...(error.subflowTrace?{trace:error.subflowTrace}:{})},elapsedMs:0};
          budget.bytes+=Buffer.byteLength(JSON.stringify(failure));if(budget.bytes>40_000_000){const error=Error('本次运行结果超过 40 MB');error.executionLimit=true;throw error;}
          frames.set(step.id,input);outputs.set(step.id,failure);records.push({id:step.id,inputFrom,error:failure.result.error,handled:true,output:failure});
        }
      }
    return {vars,frames,outputs};
  }

  async invokeGroup(job,step,params,input,parent,library,budget,path){
    if(path.length>4)throw Error('组合模块嵌套超过 4 层');
    const inner=params.inner&&typeof params.inner==='object'&&!Array.isArray(params.inner)?params.inner:{};
    const stepsIn=Array.isArray(inner.steps)?inner.steps:[];
    if(!stepsIn.length)throw Error('组合模块内部为空，请进入组合模块添加算子');
    const edgesIn=Array.isArray(inner.edges)?inner.edges:[];
    const localVars=(inner.localVariables&&typeof inner.localVariables==='object'&&!Array.isArray(inner.localVariables))?inner.localVariables:{};
    const outputNode=inner.outputNode||stepsIn[stepsIn.length-1]?.id||null;
    const safeId=('g'+String(step.id||'group')).replace(/[^A-Za-z0-9_-]/g,'').slice(0,80)||'group';
    const definition=graph.normalize({
      version:2,
      id:safeId,
      name:String(step.name||'组合模块').slice(0,80)||'组合模块',
      steps:structuredClone(stepsIn),
      edges:structuredClone(edgesIn),
      sourcePosition:inner.sourcePosition||{x:300,y:40},
      variables:{...structuredClone(localVars)},
      outputNode,
    },true);
    if(!definition.outputNode)definition.outputNode=definition.steps.at(-1)?.id||null;
    if(!definition.outputNode)throw Error('组合模块缺少输出节点');
    const count=params.loopEnabled?Math.max(1,Math.min(100,Number(params.loopCount)||1)):1;
    const intervalMs=Math.max(0,Math.min(60_000,Number(params.loopIntervalMs)||0));
    let local={revision:parent.revision,global:structuredClone(parent.global),flow:{...structuredClone(parent.flow),...structuredClone(definition.variables)},modules:{}};
    const priorGroup=parent.modules?.[step.id]?._group;
    for(const child of definition.steps){
      local.modules[child.id]={...structuredClone(child.variables||{}),...object(priorGroup?.modules?.[child.id]??{},'组内模块状态')};
    }
    let current=input,displayImage=input.image,value=null,completed=0;
    const trace=[],iterations=[],planned=graph.plan(definition);
    for(let iteration=1;iteration<=count;iteration++){
      await yieldExecution();
      if(job.cancelled)throw Error('组合模块已取消');
      if(iteration>1&&intervalMs>0){
        await new Promise((resolve,reject)=>{
          const timer=setTimeout(resolve,intervalMs);
          const onAbort=()=>{clearTimeout(timer);reject(Error('组合模块已取消'));};
          if(job.controller?.signal?.aborted)return onAbort();
          job.controller?.signal?.addEventListener('abort',onAbort,{once:true});
        });
      }
      local.flow._iteration=iteration;local.flow._iterations=count;
      this.variables.assertTypes(definition,local);
      const records=[];
      const collect=()=>{for(const row of records)trace.push({iteration,nodeId:row.id,operation:definition.steps.find(s=>s.id===row.id)?.operation,skipped:!!row.skipped,handled:!!row.handled,error:row.error||'',elapsedMs:row.output?.elapsedMs??0,result:row.output?.result??{}});};
      try{
        const response=await this.executeGraph(job,definition,planned,current,local,library,budget,[...path,step.id],records);
        local=response.vars;if(job.cancelled)throw Error('组合模块已取消');
        const output=response.outputs.get(definition.outputNode);
        if(!output||output.flowError)throw Error('组合模块输出节点未激活或执行失败');
        current=response.frames.get(definition.outputNode)||current;
        displayImage=output.annotatedImage??current?.image??input.image;
        value=output.result;completed=iteration;
        iterations.push({iteration,value:structuredClone(value)});
        collect();
      }catch(error){
        collect();
        error.subflowTrace=trace;
        error.message=(step.name||'组合模块')+' · 第 '+iteration+' 轮：'+(error.message||error);
        throw error;
      }
    }
    const vars=structuredClone(parent);
    vars.global=local.global;
    const mergedFlow={...parent.flow,...local.flow};
    delete mergedFlow._iteration;delete mergedFlow._iterations;
    vars.flow=mergedFlow;
    if(!vars.modules[step.id]||typeof vars.modules[step.id]!=='object')vars.modules[step.id]={};
    vars.modules[step.id]._group={flow:local.flow,modules:local.modules};
    vars.modules[step.id].status='ok';
    vars.modules[step.id].completedIterations=completed;
    return {
      vars,
      frame:current||input,
      displayImage,
      result:{
        status:'ok',
        groupId:step.id,
        completedIterations:completed,
        loopEnabled:!!params.loopEnabled,
        value,
        variables:mergedFlow,
        iterations,
        trace,
        imageData:String(params.imageData||''),
        inputRoi:String(params.inputRoi||''),
      },
    };
  }

  async invokeSubflow(job,step,params,input,parent,library,budget,path){
    const definition=library.find(d=>d.id===params.subflowId);
    if(!definition||path.length>4)throw Error('子流程不存在或嵌套超过 4 层');
    const count=step.operation==='loop'?params.iterations??1:1,mode=step.operation==='loop'?params.mode??'count':'count';
    if(!Number.isInteger(count)||count<1||count>100)throw Error('循环次数须为 1–100 的整数');
    if(!['count','until'].includes(mode)||!['reset','preserve'].includes(params.stateMode??'reset')||!['original','previous'].includes(params.frameMode??'previous'))throw Error('子流程状态、图像或循环模式无效');
    const stopField=params.stopField??'passed',stopValue=params.stopValue??true;
    if(mode==='until'&&(typeof stopField!=='string'||!stopField||stopField.length>200||typeof stopValue!=='boolean'))throw Error('停止条件需要结果字段路径和开关值');
    const args=object(params.arguments??{},'子流程输入变量'),saved=parent.modules[step.id]._subflow;
    if(Object.keys(args).some(k=>! /^[A-Za-z_][A-Za-z0-9_]{0,63}$/.test(k)||['_iteration','_iterations'].includes(k)))throw Error('子流程输入变量名称无效或占用了只读轮次变量');
    const previous=params.stateMode==='preserve'&&saved?.definitionId===definition.id?saved:null;
    let local={revision:parent.revision,global:structuredClone(parent.global),flow:{...structuredClone(definition.variables),...object(previous?.flow??{},'子流程状态'),...args},modules:{}};
    for(const child of definition.steps)local.modules[child.id]={...structuredClone(child.variables),...object(previous?.modules?.[child.id]??{},'子模块状态')};
    let current=input,displayImage=input.image,value=null,completed=0,stopped=false;const trace=[],iterations=[],steps=graph.plan(definition);
    for(let iteration=1;iteration<=count;iteration++){
      await yieldExecution();if(job.cancelled)throw Error('子流程已取消');
      local.flow._iteration=iteration;local.flow._iterations=count;this.variables.assertTypes(definition,local);
      const records=[];
      const collect=()=>{for(const row of records)trace.push({iteration,nodeId:row.id,operation:definition.steps.find(s=>s.id===row.id)?.operation,skipped:!!row.skipped,handled:!!row.handled,error:row.error||'',elapsedMs:row.output?.elapsedMs??0,result:row.output?.result??{}});};
      try{
        const response=await this.executeGraph(job,definition,steps,params.frameMode==='original'?input:current,local,library,budget,path,records);
        local=response.vars;if(job.cancelled)throw Error('子流程已取消');
        const output=response.outputs.get(definition.outputNode);if(!output||output.flowError)throw Error('子流程输出节点未激活或执行失败');
        current=response.frames.get(definition.outputNode);displayImage=output.annotatedImage??current.image;value=output.result;completed=iteration;
        iterations.push({iteration,value:structuredClone(value)});
        if(mode==='until'){
          const predicate=resolve({$ref:'results.output.'+stopField},{results:{output:value}});
          if(typeof predicate!=='boolean')throw Error('循环停止字段必须为开关，不能自动转换类型');
          stopped=predicate===stopValue;
        }
        collect();if(stopped)break;
      }catch(error){collect();error.subflowTrace=trace;error.message=definition.name+' · 第 '+iteration+' 轮：'+error.message;throw error;}
    }
    if(mode==='until'&&!stopped){const error=Error('循环达到最大轮数，仍未满足停止条件');error.subflowTrace=trace;throw error;}
    const vars=structuredClone(parent);vars.global=local.global;
    vars.modules[step.id]._subflow={definitionId:definition.id,flow:local.flow,modules:local.modules};
    try{object(vars.modules[step.id],'子流程调用状态');}catch(error){error.subflowTrace=trace;throw error;}
    return {vars,frame:current,displayImage,result:{subflowId:definition.id,completedIterations:completed,stoppedEarly:stopped&&completed<count,value,variables:local.flow,iterations,trace}};
  }

  snapshot(project){return this.variables.snapshot(graph.normalize(project));}
  recordMonitor(project,state,event,previousGlobal){
    try{const revision=this.monitor.state.revision;this.monitor.batch(()=>{this.monitor.observe(project,state,event);if(previousGlobal!==JSON.stringify(this.variables.state.global))this.monitor.observeGlobals(this.variables.state.global,project.id,event.time);});if(this.monitor.state.revision!==revision)this.monitorError='';}
    catch(error){this.monitorError='监控记录写入失败：'+error.message;}
  }
  update(project,state,revision){
    if(this.busy)throw Error('执行期间不可修改变量');const p=graph.normalize(project),known=new Set(p.steps.map(s=>s.id));
    for(const id of Object.keys(state.modules||{}))if(!known.has(id))throw Error('模块变量引用未知节点');
    const next={global:object(state.global,'全局变量'),flow:{...p.variables,...object(state.flow,'流程变量')},modules:{}};
    const modules=object(state.modules,'模块变量');for(const step of p.steps)next.modules[step.id]={...step.variables,...object(modules[step.id]||{},'模块变量')};
    const previousGlobal=JSON.stringify(this.variables.state.global);
    this.variables.commit(p,next,revision,state.globalTypes===undefined?this.variables.state.globalTypes:state.globalTypes);const snapshot=this.snapshot(p);this.recordMonitor(p,{variables:snapshot,results:[],status:{state:'idle'}},{kind:'variables',time:Date.now()},previousGlobal);return {...snapshot,...(this.monitorError?{monitorWarning:this.monitorError}:{})};
  }
}
module.exports={Runtime};
