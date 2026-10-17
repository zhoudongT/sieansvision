'use strict';
const opcuaTypes=['Boolean','SByte','Byte','Int16','UInt16','Int32','UInt32','Int64','UInt64','Float','Double','String','DateTime','Guid','ByteString'];
const opcuaFields=[['connection','连接目标',['simulator','server']],['endpoint','服务器端点','text'],['security','安全策略',['None','Basic256Sha256']],['applicationUri','客户端应用 URI','text'],['clientCertificate','客户端证书路径','text'],['privateKey','客户端私钥路径','text'],['serverCertificate','已信任服务器证书路径','text'],['username','用户名（留空为匿名）','text'],['passwordEnv','密码环境变量名（SIEANS_OPCUA_ 前缀）','text'],['namespaceUri','命名空间 URI（可选）','text'],['nodeId','节点地址','text'],['timeoutMs','总操作超时 (ms)',100,10000,100]];
const opcuaDefaults={connection:'simulator',endpoint:'opc.tcp://127.0.0.1:4840/',security:'None',applicationUri:'urn:sieans:vision:client',nodeId:'ns=2;s=SIEANS.Count',timeoutMs:3000};
const opcuaCatalog={
 opcua_wait:{name:'等待 OPC UA 信号',glyph:'UA',tag:'订阅 · 条件 / 边沿触发',defaults:{...opcuaDefaults,comparison:'eq',expectedValue:0,triggerMode:'level',publishingIntervalMs:100,waitTimeoutMs:10000,onTimeout:'error'},fields:[...opcuaFields.map(f=>f[0]==='timeoutMs'?[f[0],'单次通信超时 (ms)',...f.slice(2)]:f),['comparison','信号条件',['eq','ne','gt','gte','lt','lte','is_true','is_false']],['expectedValue','比较值',-1e15,1e15,'any'],['triggerMode','触发方式',['level','rising','falling']],['publishingIntervalMs','请求发布/采样间隔 (ms)',20,10000],['waitTimeoutMs','等待超时 (ms)',100,600000],['onTimeout','超时处理',['error','continue']]],description:'单次有界订阅一个数值或开关节点，收到满足条件的通知后执行下游。初始值仅在条件成立模式立即触发，边沿模式先建立基线。',hint:'每次调用重新建立基线，不缓存跨轮事件。服务端可能修订采样/发布间隔，不能保证捕获短脉冲。只接受良好质量；通知溢出、断线、类型或协议错误停止，不作为条件超时继续。等待占用本平台同一端点。'},
 opcua_browse:{name:'OPC UA 浏览',glyph:'UA',tag:'设备 · 地址空间',defaults:{...opcuaDefaults,nodeId:'ns=2;s=SIEANS',browseLimit:100},fields:[...opcuaFields,['browseLimit','单层浏览上限',1,500]],description:'浏览节点下的层级引用，输出名称、节点地址、类型及命名空间。',hint:'节点浏览器可逐层进入并选用节点。每次建立独立会话；结果超过上限会标记截断，不代表已列出全部节点。'},
 opcua_read:{name:'OPC UA 读取',glyph:'UA',tag:'状态码 · 时间戳 · 变量',defaults:{...opcuaDefaults,requireGood:true},fields:[...opcuaFields,['requireGood','仅接受良好数据质量','boolean']],description:'读取节点值、类型、质量和源端/服务器时间戳。结果可绑定三级变量。',hint:'64 位整数以十进制文本返回，避免精度丢失；数组最多 1000 项。当前按流程单次读取，不是持续订阅。'},
 opcua_write:{name:'OPC UA 写入',glyph:'UA',tag:'带类型写入 · 检测结果',defaults:{...opcuaDefaults,dataType:'UInt32',value:0},fields:[...opcuaFields,['dataType','节点值类型',opcuaTypes]],description:'按指定 OPC UA 类型写入标量或一维数组。请选择与服务端节点一致的类型。',hint:'Boolean 使用开关；Int64/UInt64 大整数使用十进制文本；DateTime 使用带时区日期文本，ByteString 使用 Base64 文本。写入不重试，外部动作不会回滚。'}
};
function opcuaParamDefault(step,key){return step.operation.startsWith('opcua_')?({...(step.operation==='opcua_wait'?opcuaCatalog.opcua_wait.defaults:{}),connection:'server',security:'None',applicationUri:'urn:sieans:vision:client',nodeId:step.operation==='opcua_browse'?'i=85':'',timeoutMs:3000,requireGood:true,browseLimit:100,dataType:'Double'})[key]:undefined;}
function opcuaFieldVisible(step,key){
 if(!step.operation.startsWith('opcua_'))return true;
 if(step.operation==='opcua_wait'&&key==='expectedValue')return typeof step.params.comparison==='object'||!['is_true','is_false'].includes(step.params.comparison);
 const simulator=step.params.connection==='simulator',secure=step.params.security==='Basic256Sha256';
 if(['endpoint','security','namespaceUri'].includes(key))return !simulator;
 if(['applicationUri','clientCertificate','privateKey','serverCertificate','username'].includes(key))return !simulator&&secure;
 if(key==='passwordEnv')return !simulator&&secure&&!!step.params.username;
 return true;
}
let opcuaBrowseStep=null,opcuaBrowseParams=null,opcuaBrowsePath=[],opcuaBrowsing=false;
async function opcuaBrowseNode(nodeId,namespaceUri='',push=true){
 if(opcuaBrowsing)return;opcuaBrowsing=true;$('opcua-browse-status').textContent='正在连接并浏览…';
 try{
  const result=await api('industrial/run',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({operation:'opcua_browse',params:{...opcuaBrowseParams,nodeId,namespaceUri}})});
  if(push)opcuaBrowsePath.push({nodeId,namespaceUri});$('opcua-browse-node').value=nodeId;
  const body=$('opcua-browse-rows');body.replaceChildren();
  for(const item of result.result.items){const row=formEl('tr');for(const value of [item.displayName,item.nodeClass==='Variable'?'变量':item.nodeClass==='Object'?'对象':item.nodeClass,item.nodeId])row.append(formEl('td',value));
   const cell=formEl('td'),enter=formEl('button','进入'),choose=formEl('button','选用');
   enter.disabled=item.remote;choose.disabled=item.remote;
   enter.onclick=safe(()=>opcuaBrowseNode(item.nodeId,item.namespaceUri));
   choose.onclick=safe(async()=>{if(opcuaBrowsing||running)return;const step=project.steps.find(s=>s.id===opcuaBrowseStep);if(!step)throw Error('模块已移除');if(step.operation!=='opcua_browse'&&item.nodeClass!=='Variable')throw Error('读写模块请选择变量节点');
    if(step.operation==='opcua_write'){const out=await opcuaPreview(item);if(!opcuaTypes.includes(out.dataType))throw Error('此节点类型尚不支持写入');step.params.dataType=out.dataType;}
    step.params.nodeId=item.nodeId;step.params.namespaceUri=item.namespaceUri;dirty();renderParams();$('opcua-browser').close();status('已选择节点：'+item.displayName);
   });cell.append(enter,choose);
   if(item.nodeClass==='Variable'&&!item.remote){const read=formEl('button','读取');read.onclick=safe(()=>opcuaPreview(item));cell.append(read);}row.append(cell);body.append(row);
  }
  $('opcua-browse-status').textContent=`${result.result.simulated?'本机模拟 · ':''}${result.result.count} 个子节点${result.result.truncated?' · 达到上限，结果已截断':''}`;$('opcua-browse-up').disabled=opcuaBrowsePath.length<2;
 }catch(error){renderDataMessage($('opcua-browse-status'),error.message);throw error;}finally{opcuaBrowsing=false;}
}
async function opcuaPreview(item){
 try{
 const out=await api('industrial/run',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({operation:'opcua_read',params:{...opcuaBrowseParams,nodeId:item.nodeId,namespaceUri:item.namespaceUri,requireGood:false}})});
 const holder=$('opcua-preview');holder.replaceChildren();holder.append(formEl('h3',item.displayName||item.nodeId));const table=formEl('table',undefined,'form-table');
 for(const key of ['dataType','quality','status','value','sourceTimestamp','serverTimestamp']){const row=formEl('tr'),cell=formEl('td');cell.append(resultValueView(out.result[key]));row.append(formEl('td',resultLabel(key)),cell);table.append(row);}holder.append(table);return out.result;
 }catch(error){renderDataMessage($('opcua-browse-status'),error.message);throw error;}
}
function initOpcuaUI(){
 $('opcua-open-browser').onclick=safe(async()=>{if(running)return;applyParams();const step=selectedStep();if(!step?.operation.startsWith('opcua_'))return;opcuaBrowseStep=step.id;opcuaBrowseParams=structuredClone(step.params);opcuaBrowsePath=[];$('opcua-preview').replaceChildren();$('opcua-browse-rows').replaceChildren();$('opcua-browser').showModal();await opcuaBrowseNode('i=85');});
 $('opcua-browse-go').onclick=safe(()=>opcuaBrowseNode($('opcua-browse-node').value.trim()));
 $('opcua-browse-up').onclick=safe(()=>{if(opcuaBrowsing||opcuaBrowsePath.length<2)return;const parent=opcuaBrowsePath.at(-2);opcuaBrowsePath.pop();return opcuaBrowseNode(parent.nodeId,parent.namespaceUri,false);});
 $('opcua-simulator-start').onclick=safe(async()=>{if(running)return;showOpcuaSimulator(await api('industrial/opcua/simulator/start',{method:'POST'}));});
 $('opcua-simulator-stop').onclick=safe(async()=>{if(running)return;showOpcuaSimulator(await api('industrial/opcua/simulator/stop',{method:'POST'}));});
}
function showOpcuaSimulator(value){$('opcua-simulator-status').textContent=value.running?'运行中 · '+value.endpoint:'本机模拟设备未启动';$('opcua-simulator-start').disabled=value.running;$('opcua-simulator-stop').disabled=!value.running||running;}
