'use strict';
const $=id=>document.getElementById(id);
let project={id:'operator-empty',name:'',steps:[],hmi:HmiLayout.empty()},source='',running=false,continuousState={busy:false},publicationVersion='',operatorFetching=false,operatorCommandPending=false,operatorCloudInput=null,operatorImageEpoch=0,operatorImagePending=false,operatorImageNeedsRead=false;
const operatorLabels={count:'数量',passed:'通过',found:'找到目标',height:'高度',diameter:'直径',areaPixels:'像素面积',centerX:'中心 X',centerY:'中心 Y',value:'值',reason:'说明',valid:'有效',coverage:'覆盖率',positiveVolume:'正向观测体积',sampleCount:'独立点数'};
Object.assign(operatorLabels,{check:'检查项目',measured:'实测值',limit:'判定阈值',rule:'判定规则',measurement:'测量项目',unit:'单位',angleDegrees:'夹角 (°)',sharpness:'清晰度方差',darkPercent:'过暗比例 (%)',brightPercent:'过曝比例 (%)'});
function resultLabel(key){return key.split('.').map(k=>operatorLabels[k]||k).join(' · ');}
Object.assign(operatorLabels,{boxCenterX:'包围盒中心 X',boxCenterY:'包围盒中心 Y',boxCenterZ:'包围盒中心 Z',cornerX:'角点 X',cornerY:'角点 Y',cornerZ:'角点 Z',dimension:'尺寸方向',measured:'测量值',minimum:'公差下限',maximum:'公差上限',unit:'单位',directionX:'单位轴 X',directionY:'单位轴 Y',directionZ:'单位轴 Z',axis:'方向',nearEqualDimensions:'存在近等长边'});
Object.assign(operatorLabels,{index:'序号',huDifference:'Hu 差异（越低越相似）',areaScale:'面积等效线性比例',outerAreaPixels:'外轮廓面积 (px²)',longSidePixels:'旋转包围框长边 (px)',shortSidePixels:'旋转包围框短边 (px)',holeCount:'孔洞数量',matched:'是否匹配',candidateCount:'完整候选数量',boundaryRejectedCount:'边界排除数量',x:'X (px)',y:'Y (px)',width:'宽度 (px)'});
function resultText(value){if(value==null)return '—';if(typeof value==='boolean')return value?'是':'否';return typeof value==='number'?String(Number(value.toFixed(6))):String(value);}
function status(message,type){renderDataMessage($('status'),message);$('status').classList.toggle('error',type==='error');}
const safe=fn=>async(...args)=>{try{return await fn(...args);}catch(error){status(error.message,'error');}};
const currentProject=()=>project;
async function operatorRequest(route,body){const response=await fetch('/api/vision/'+route,{method:body===undefined?'GET':'POST',headers:{'Content-Type':'application/json'},body:body===undefined?undefined:JSON.stringify(body),signal:AbortSignal.timeout(route==='operator/import-cloud'?20000:15000)});let value;try{value=await response.json();}catch{throw Error(response.status===401?'登录凭据已失效，请重新打开运行页面登录':'服务未返回有效响应，请刷新重试');}if(!response.ok)throw Error(value.error||'操作失败');return value;}
async function api(route,options={}){if(route==='runtime/monitor/ack'){const b=JSON.parse(options.body);return operatorRequest('operator/ack',{version:publicationVersion,id:b.id,comment:b.comment});}if(/^runtime\/jobs\/[^/]+\/cancel$/.test(route))return operatorStopRuntime();throw Error('此运行入口未开放该操作');}
function operatorUpdateControls(){const busy=!!hmiState.busy,locked=busy||operatorCommandPending||!!operatorCloudInput?.pending(),blocked=locked||!!hmiError||!publicationVersion,unready=operatorImagePending||operatorImageNeedsRead;$('operator-run').disabled=blocked||unready;$('operator-continuous').disabled=blocked||unready||!hmiState.publication?.continuous?.enabled;$('stop').disabled=!busy||operatorCommandPending||!!operatorCloudInput?.pending();$('operator-image').disabled=blocked||operatorImagePending;$('operator-clear').disabled=locked;operatorCloudInput?.updateControls(blocked||operatorImagePending);}
function operatorResetImage(){operatorImageEpoch++;operatorImagePending=false;operatorImageNeedsRead=false;source='';$('operator-image').value='';}
function operatorContinuousDetails(fresh){
 const policy=fresh.publication.continuous||{enabled:false},s=fresh.continuous||{};continuousState={...s,busy:fresh.busy};$('operator-continuous').hidden=!policy.enabled;$('operator-continuous-panel').hidden=!policy.enabled&&!s.matchesPublication;const body=$('operator-continuous-stats');body.replaceChildren();if(!policy.enabled&&!s.matchesPublication)return;
 $('operator-continuous-policy').textContent='管理员发布设置：每轮完成后间隔 '+policy.intervalMs+' 毫秒 · '+(policy.maxCycles===0?'直到停止':policy.maxCycles+' 轮')+'。';
 const labels={idle:'尚未启动',running:'正在执行',waiting:'等待下一轮',stopping:'正在停止',stopped:'已停止',completed:'已完成设定轮次',failed:'执行失败，请联系管理员查看运行历史',interrupted:'服务重启中断，未自动恢复'};
 const rows=[['状态',s.matchesPublication?(labels[s.state]||s.state):fresh.busy?'运行资源正在使用':'尚未启动'],['启动用户',s.startedBy||'—'],['完成 / 已启动轮次',(s.completedCycles??0)+' / '+(s.startedCycles??0)],['失败 / 取消轮次',(s.failedCycles??0)+' / '+(s.cancelledCycles??0)],['最近一轮耗时',s.lastElapsedMs===undefined?'—':s.lastElapsedMs+' ms'],['下一轮时间',s.nextAt?new Date(s.nextAt).toLocaleString('zh-CN'):'—']];for(const [key,value]of rows){const row=formEl('tr');row.append(formEl('th',key),formEl('td',String(value)));body.append(row);}
}
function operatorReady(){if(operatorImagePending)throw Error('正在读取图像，请等待完成或清除文件输入');if(operatorImageNeedsRead)throw Error('图像选择尚未读取成功，请重选或清除文件输入');operatorCloudInput?.assertReady();if(operatorCommandPending)throw Error('运行请求正在处理，请稍候');if(hmiError)throw Error(hmiError);if(!publicationVersion)throw Error('尚无可运行方案');if([...hmiViews.values()].some(views=>views.some(v=>v.pending||v.saving)))throw Error('存在未写入或正在写入的设定值，请先写入或放弃');}
async function operatorRefresh(){
 if(operatorFetching)return;operatorFetching=true;
 try{const fresh=await operatorRequest('operator/view');const changed=publicationVersion&&publicationVersion!==fresh.publication.version;
  if(changed){operatorCloudInput?.clear();operatorResetImage();hmiRuntimeRenderedSignature='';for(const views of hmiViews.values())for(const view of views)view.cloudViewer?.destroy();hmiViews.clear();status('已发布新方案，运行画面已刷新；请核对本次输入。');}
  project=fresh.project;publicationVersion=fresh.publication.version;hmiState=fresh;hmiError='';hmiProjectId=project.id;operatorContinuousDetails(fresh);hmiRuntimePagesRender();hmiUpdateWidgets();
  $('operator-project').textContent=project.name;$('operator-version').textContent='发布于 '+new Date(fresh.publication.publishedAt).toLocaleString('zh-CN');operatorUpdateControls();$('operator-empty').hidden=HmiLayout.allComponents(project.hmi).length>0;
 }catch(error){hmiError=error.message;operatorUpdateControls();hmiUpdateWidgets();status(error.message,'error');}finally{operatorFetching=false;}
}
hmiRefresh=operatorRefresh;
async function operatorStart(route){operatorReady();operatorCommandPending=true;operatorUpdateControls();try{const result=await operatorRequest('operator/'+route,{version:publicationVersion,image:source,...(operatorCloudInput?.getCloud()?{cloud:operatorCloudInput.getCloud()}:{})});status(route==='continuous'?'连续检测请求已受理；服务器按已发布设置执行':'已启动发布方案');return result;}finally{operatorCommandPending=false;await operatorRefresh();operatorUpdateControls();}}
async function executeRuntime(){return operatorStart('run');}
async function operatorStartContinuous(){return operatorStart('continuous');}
async function operatorStopRuntime(){if(operatorCommandPending)throw Error('运行请求正在处理，请稍候');operatorCommandPending=true;operatorUpdateControls();try{const result=await operatorRequest('operator/stop',{});status('已请求停止；等待当前任务取消与归档');return result;}finally{operatorCommandPending=false;await operatorRefresh();operatorUpdateControls();}}
async function operatorWriteInput(c,value,revision){return operatorRequest('operator/input',{version:publicationVersion,componentId:c.id,value,revision});}
$('operator-run').onclick=safe(executeRuntime);$('operator-continuous').onclick=safe(operatorStartContinuous);$('stop').onclick=safe(operatorStopRuntime);$('operator-refresh').onclick=safe(operatorRefresh);$('operator-clear').onclick=()=>{if(hmiState.busy||operatorCommandPending||operatorCloudInput?.pending())return;operatorCloudInput?.clear();operatorResetImage();status('已清除本次文件输入');operatorUpdateControls();hmiUpdateWidgets();};
$('operator-image').onchange=safe(async event=>{
 const file=event.target.files?.[0],token=++operatorImageEpoch,version=publicationVersion;operatorImagePending=false;operatorImageNeedsRead=!!file;
 if(!file){source='';operatorUpdateControls();hmiUpdateWidgets();return;}
 if(!version||hmiState.busy||operatorCommandPending||operatorCloudInput?.pending()){operatorUpdateControls();throw Error('请在方案加载完成且运行空闲时选择图像');}
 if(!Number.isFinite(file.size)||file.size<1||file.size>12000000){operatorUpdateControls();throw Error('图像文件为空或超过 12 MB');}
 operatorImagePending=true;operatorUpdateControls();status('正在读取本次图像…');
 try{const reader=new FileReader(),value=await new Promise((resolve,reject)=>{reader.onload=()=>resolve(reader.result);reader.onerror=()=>reject(Error('图像读取失败'));reader.readAsDataURL(file);});if(token!==operatorImageEpoch||version!==publicationVersion)return;if(hmiState.busy)throw Error('运行状态已变化，请在空闲后重新选择图像');if(typeof value!=='string'||value.length>17000000)throw Error('图像读取结果无效');source=value;operatorImageNeedsRead=false;status('本次输入：'+file.name);}catch(error){if(token===operatorImageEpoch&&version===publicationVersion)throw error;}finally{if(token===operatorImageEpoch)operatorImagePending=false;operatorUpdateControls();hmiUpdateWidgets();}
});
operatorCloudInput=initOperatorCloudInput({request:operatorRequest,version:()=>publicationVersion,isBusy:()=>hmiState.busy||operatorCommandPending||operatorImagePending,status,changed:operatorUpdateControls,refresh:operatorRefresh});
operatorRequest('identity').then(identity=>{$('operator-identity').textContent=identity.username+' · '+(identity.role==='admin'?'管理员预览':'操作员');}).catch(error=>status(error.message,'error'));
operatorRefresh();setInterval(()=>{if(!document.hidden)operatorRefresh();},1000);
