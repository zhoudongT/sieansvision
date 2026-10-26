'use strict';
const $ = id => document.getElementById(id);
const catalog = {
  subflow:{name:'子流程调用',tag:'复用 · 独立作用域',glyph:'▣',defaults:{subflowId:'',arguments:{},stateMode:'reset'},description:'调用工程内可复用子流程，返回所选输出节点的数据帧和结果。',fields:[],hint:'在子流程管理中定义流程。局部变量按调用点隔离，全局变量随主流程统一提交；失败可接错误分支。'},
  loop:{name:'循环子流程',tag:'固定次数 · 条件停止',glyph:'↻',defaults:{subflowId:'',arguments:{},iterations:1,mode:'count',frameMode:'previous',stateMode:'reset',stopField:'passed',stopValue:true},description:'重复执行子流程，固定次数或输出满足开关条件后停止。',fields:[],hint:'最多 100 轮、4 层调用，整轮共 1000 次节点访问；达到上限未满足停止条件时报错。取消传递给内部节点。'},
  plugin:{name:'算子插件',tag:'扩展 · Python',glyph:'▧',defaults:{},description:'使用服务器已安装的算子插件。参数和结果按插件定义显示。',fields:[],hint:'插件使用服务器账户执行；工程固定插件版本。输出可绑定全局、流程或模块变量。'},
  yolo_segment:{name:'YOLO 实例分割',tag:'YOLOv8 / YOLO11 · 轮廓与面积',glyph:'AI',defaults:{device:'cpu',model:'yolo11n-seg.pt',confidence:.25,iou:.45,imageSize:640,maxDetections:50,minArea:1,contourTolerance:.5,overlayAlpha:.35,output:'overlay'},description:'使用本地分割模型逐个提取目标掩膜，返回类别、置信度、轮廓、像素面积和中心。可输出二值掩膜继续进行几何检测。',fields:[['device','计算设备',['cpu','auto','cuda:0']],['model','分割模型文件名','text'],['confidence','最低置信度',0,1,'any'],['iou','NMS IoU 阈值',0,1,'any'],['imageSize','推理尺寸',32,1280,32],['maxDetections','最大目标数',1,100],['minArea','最小掩膜面积 (px²)',1,16000000],['contourTolerance','轮廓简化容差 (px)',0,10,'any'],['output','输出图像',['overlay','mask']],['overlayAlpha','叠加透明度',0,1,'any']],hint:'仅使用本地可信的分割 .pt 权重，不自动下载。计算设备可选择 CPU、自动或可用 GPU。面积保留空洞，重叠实例的面积和可能大于并集面积；轮廓简化不改变掩膜面积。通过类别编号表筛选，通用 COCO 模型不能代替工业缺陷模型。'},
  ...cloudCatalog,...industrialCatalog,...s7Catalog,...mqttCatalog,...socketCatalog,...serialCatalog,...opcuaCatalog,...cameraCatalog,
  condition:{name:'条件判断',tag:'数值 · 文本 · 开关分支',glyph:'?',defaults:{comparison:'eq',left:0,right:0},description:'比较输入值，输出成立或不成立。在连线表中为后续节点选择触发条件。支持变量及上游结果绑定，不执行表达式代码。',fields:[['comparison','判断方式',['eq','ne','gt','gte','lt','lte','contains','is_true','is_false']]],hint:'相等比较保留类型：数值 1 与文本 1 不相等；大小比较只接受数值。未选中的分支及其下游会显示已跳过。'},
  branch_merge:{name:'分支汇合',tag:'互斥分支 · 数据合并',glyph:'⋈',defaults:{},description:'等待所有上游完成或跳过，再接收唯一激活分支的图像、深度、点云及结果。用于条件分支重新合并。',fields:[],hint:'没有激活分支时跳过；同时激活多路时失败，避免混用数据。多个并行上游需全部执行时，使用普通节点汇合。'},
  delay:{name:'延时等待',tag:'可取消 · 毫秒等待',glyph:'◷',defaults:{milliseconds:100},description:'延时后继续流程，保留输入图像、深度及点云。点击停止可立即取消等待。',fields:[['milliseconds','等待时间 (ms)',0,30000]],hint:'范围 0–30000 ms。不用于硬实时触发或精确曝光同步。'},
  script:{name:'Python 自定义脚本',tag:'脚本 · 变量 · 结果处理',glyph:'Py',defaults:{code:"def run(ctx):\n    count = ctx[\"params\"].get(\"count\", 0)\n    return dict(result=dict(count=count, passed=count > 0))\n",timeoutMs:5000,arguments:{count:0},outputBindings:[{field:"passed",scope:"flow",name:"passed"}]},description:'定义 run(ctx)，可读取上游结果、输入图像和三级变量。脚本使用服务器账户权限执行，仅运行可信代码。',fields:[['timeoutMs','超时 (ms)',100,30000,100]],hint:'ctx.vars 含 global / flow / module；ctx.results 以上游节点 ID 为键。返回 result、variables，可选 image。'},
  variables:{name:'变量赋值',tag:'全局 · 流程 · 模块',glyph:'V',defaults:{scope:'flow',name:'counter',mode:'increment',value:1},description:'写入或累加变量。通过表单输入值或选择变量及上游结果，流程成功结束后统一保存。',fields:[['scope','作用域',['global','flow','module']],['name','变量名','text'],['mode','写入方式',['set','increment']]],hint:'赋值内容可选择数值、文本、开关、数组、结构体或变量 / 结果绑定。'},
  preprocess:{name:'图像预处理',tag:'OpenCV · 灰度 / 滤波',glyph:'◐',defaults:{method:'grayscale'},description:'预处理输出成为下一步的输入图像。支持灰度、模糊、二值化、边缘及形态学。',fields:[['method','处理方法',['grayscale','blur','threshold','canny','open','close','erode','dilate']],['threshold','二值阈值',0,255],['kernel','卷积核大小',1,51]],hint:'按处理方法显示参数。高斯模糊的卷积核大小须为奇数；边缘提取使用低、高两个阈值。'},
  locate:{name:'模板与定位',tag:'多目标 · 旋转 · 定位跟随',glyph:'⌖',defaults:{minScore:.85,angleStart:0,angleEnd:0,angleStep:10,maxMatches:1,overlapThreshold:.3},description:'上传或框选模板，搜索平移/旋转/均匀缩放目标，去除重复匹配并返回目标表及定位跟随位姿。',fields:[['minScore','最低匹配分数',0,1,.01],['angleStart','起始角度',-180,180],['angleEnd','终止角度',-180,180],['angleStep','角度步长',1,180],['maxMatches','最多目标数',1,50,1],['overlapThreshold','去重重叠比例',.01,.9,.01]],hint:'搜索比例和坐标原点按表格设置。OpenCV 正角为逆时针；对称模板不能区分方向。多目标时应按目标表选择位姿；唯一目标可绑定 pose 接定位跟随。搜索范围和组合数有上限。'},
  geometry:{name:'几何特征查找',tag:'直线 · 圆 · 轮廓',glyph:'◇',defaults:{feature:'contours',threshold:127,minArea:50},description:'查找直线、圆、边缘与轮廓，返回原图像素坐标及标记结果。',fields:[['feature','特征类型',['contours','lines','circles','edges']],['threshold','轮廓二值阈值',0,255],['minArea','最小轮廓面积',1,16000000],['invert','反色提取深色目标','boolean']],hint:'按所选特征显示圆半径、圆心间距或直线长度等参数。输出最多 100 个特征。'},
  measure:{name:'尺寸测量与标定',tag:'尺寸 · 距离 · 偏移',glyph:'↔',defaults:{feature:'contours',threshold:127,minArea:50},description:'测量轮廓外接矩形或圆直径，也可指定两点测距。未标定时使用 px。',fields:[['feature','测量对象',['contours','circles']],['threshold','轮廓二值阈值',0,255],['minArea','最小轮廓面积',1,16000000],['invert','深色目标','boolean']],hint:'添加平面标定，填写两个像素点及实际距离、单位；添加坐标点可进行两点测距。仅支持等比例平面标定。'},
  barcode:{name:'条码 / 二维码',tag:'ZXing · 多码识别',glyph:'▥',defaults:{},description:'使用 ZXing-C++ 读取一维码、QR、Data Matrix 等。输出内容、码制和角点。',fields:[],hint:'可框选 ROI 缩小搜索范围。无识别结果时 count 为 0。'},
  ocr:{name:'文字识别 OCR',tag:'中英文 · 置信度',glyph:'文',defaults:{minConfidence:.5},description:'本地中英文文字检测与识别，输出文字、置信度和文本框。首次运行需加载模型。',fields:[['minConfidence','最低置信度',0,1,.01]],hint:'适用于批次号、标签、日期等文字。使用清晰且方向正常的图片，实际准确率需要样本验证。'},
  defects:{name:'参考图缺陷检测',tag:'差异 · 区域 · 判定',glyph:'⊙',defaults:{differenceThreshold:30,minArea:20,maxDefectRatio:0},description:'上传同尺寸良品参考图，提取灰度差异区域并按面积比例判定。',fields:[['differenceThreshold','灰度差异阈值',1,255],['minArea','最小差异区域面积',1,16000000],['maxDefectRatio','允许差异比例',0,1,.001]],hint:'要求拍摄位置和光照一致。输出疑似缺陷，不自动区分划痕、污点或错装。'},
  yolo:{name:'YOLO 目标检测',tag:'YOLOv8 / YOLO11',glyph:'AI',defaults:{device:'cpu',model:'yolo11n.pt',confidence:.25,iou:.45,imageSize:640},description:'加载本地 YOLOv8 / YOLO11 检测权重，输出类别、置信度、边界框和标记图。',fields:[['device','计算设备',['cpu','auto','cuda:0']],['model','模型文件名','text'],['confidence','最低置信度',0,1,.01],['iou','NMS IoU 阈值',0,1,.01],['imageSize','推理尺寸',32,1920,32]],hint:'权重放入 models 目录，支持 .pt 或 Ultralytics 导出的 .onnx。默认 CPU，可在设备表单中选择自动或可用 GPU。通过类别筛选表设置类别编号。'}
};
let project = FlowGraph.normalize({version:1,name:'我的视觉工程',steps:[]});
let selected = -1, source = '', originalImage, results = [], running = false, cancelled = false, dragging;
let activeStepId = '', imageZoom = 1, displayedResultId = '';
let demoCases=null, demoCategory='全部', demoBackup=null, demoLoading=false;
const canvas = $('source-canvas'), ctx = canvas.getContext('2d');
const uid = () => crypto.randomUUID().replaceAll('-','').slice(0,16);
const clone = value => JSON.parse(JSON.stringify(value));
function status(message, state='') {
  $('status').textContent=DataPresentation.messageSummary(message); $('status').className=state;
  const entry=document.createElement('div');entry.className='log-entry '+state;
  const time=document.createElement('time');time.textContent=new Date().toLocaleTimeString('zh-CN',{hour12:false});
  const text=document.createElement('div');text.append(resultValueView(message));entry.append(time,text);
  $('run-log').prepend(entry);while($('run-log').children.length>150)$('run-log').lastChild.remove();
  $('log-count').textContent=$('run-log').children.length;
}
function scriptLog(name,logs){
  if(!logs)return;
  status(name+'：脚本输出');
  const holder=$('run-log').firstElementChild.lastElementChild;
  holder.replaceChildren(formEl('strong',name+' · 脚本输出'));
  holder.append(scriptLogView(logs));
}
function setImageView(view) {
  document.body.classList.toggle('cloud-view',view==='cloud');document.body.classList.toggle('depth-view',view==='depth');if(view==='depth')renderDepthPreview();
  $('view-title').textContent=view==='cloud'?'3D 点云':view==='depth'?'深度图':document.body.classList.contains('runtime')?'视觉运行平台':'图像';
  if(view==='cloud')requestAnimationFrame(drawCloud);
  document.querySelector('.views').dataset.view=view;
  document.querySelectorAll('button[data-view]').forEach(button=>button.classList.toggle('active',button.dataset.view===view));imageSizeStatus();
}
function setZoom(value) {
  imageZoom=Math.max(.5,Math.min(3,value));
  document.querySelector('.views').style.setProperty('--image-zoom',imageZoom);
  $('zoom-level').textContent=imageZoom===1?'适应':Math.round(imageZoom*100)+'%';
}
const resultLabels={receivedAt:'接收时间 (Unix 毫秒)',requestId:'业务消息编号',requestedDevice:'请求计算设备',deviceName:'实际设备名称',deviceReason:'设备选择说明',task:'任务类型',instance:'实例序号',rawCount:'模型目标数',filteredCount:'面积过滤数',maxDetections:'最大目标数',limitReached:'已达到目标上限',unionAreaPixels:'掩膜并集面积 (px²)',summedAreaPixels:'实例面积之和 (px²)',maskWidth:'掩膜宽度',maskHeight:'掩膜高度',maskBbox:'掩膜外接框',contours:'轮廓明细',isHole:'空洞边界',parent:'父轮廓索引',contourTolerance:'轮廓简化容差 (px)',sourceFrame:'输入坐标系',targetFrame:'参考坐标系',found:'是否找到',sourceFeaturePoints:'输入特征点数',targetFeaturePoints:'参考特征点数',featureMatches:'双向特征对应数',sourceUniquePoints:'输入独立点数',targetUniquePoints:'参考独立点数',coarseFitness:'粗配准覆盖比例',coarseRmsError:'粗配准均方根误差',targetFitness:'参考覆盖比例',matchedPoints:'有效对应点数',minFitness:'输入最低覆盖比例',minTargetFitness:'参考最低覆盖比例',maxRmsError:'最大均方根误差',sdkVersion:'SDK 版本',colorAlignment:'彩色对齐方式',alignedColorSamples:'对齐彩色采样点数',colorCoverageKnown:'彩色有效覆盖已知',pointPositionScaleMeters:'点坐标比例 (m/原始单位)',depthDeviceTimeUs:'深度设备时间 (µs)',depthSystemTimeUs:'深度系统时间 (µs)',colorDeviceTimeUs:'彩色设备时间 (µs)',colorSystemTimeUs:'彩色系统时间 (µs)',probeCenterX:'卡尺中心 X (px)',probeCenterY:'卡尺中心 Y (px)',probe:'卡尺序号',valid:'有效测量',inlier:'拟合采用',reason:'说明',edgeX:'边缘 X (px)',edgeY:'边缘 Y (px)',gradient:'边缘梯度',residualPixels:'直线残差 (px)',firstX:'第一边缘 X (px)',firstY:'第一边缘 Y (px)',secondX:'第二边缘 X (px)',secondY:'第二边缘 Y (px)',firstGradient:'第一边缘梯度',secondGradient:'第二边缘梯度',widthPixels:'宽度 (px)',directionX:'方向 X',directionY:'方向 Y',rmsPixels:'均方根误差 (px)',inlierCount:'拟合有效点数',items:'检测明细',depthWidth:'深度宽度',depthHeight:'深度高度',depthScaleMeters:'深度比例 (m/原始值)',validDepthPixels:'有效深度像素',invalidDepthPixels:'无效深度像素',inRangePixels:'距离范围内像素',pointStride:'点云采样步长',mappedColorPoints:'映射彩色点数',calibration:'采集标定信息',minDepthMeters:'最近深度 (m)',maxDepthMeters:'最远深度 (m)',depthPreviewRangeMeters:'深度色标范围 (m)',colorAligned:'彩色与深度栅格已对齐',depthFrameNumber:'深度帧号',depthDeviceTimeMs:'深度设备时间 (ms)',depthClockDomain:'深度时钟域',colorFrameNumber:'彩色帧号',colorDeviceTimeMs:'彩色设备时间 (ms)',colorClockDomain:'彩色时钟域',imageKind:'图像来源',depthBits:'原始深度位数',driver:'采集驱动',serial:'序列号',vendor:'厂商',transport:'设备接口',pixelFormat:'像素格式',sourceBits:'源位深',outputBits:'输出位深',conversion:'像素转换',trigger:'触发模式',applied:'参数设置与回读',timestampSource:'时间戳来源',deviceTimestampNs:'设备时间戳 (ns)',nodeId:'节点地址',displayName:'显示名称',browseName:'浏览名称',nodeClass:'节点类型',namespaceUri:'命名空间',remote:'跨服务器节点',truncated:'结果已截断',statusCode:'状态码',status:'状态',sourceTimestamp:'源端时间',serverTimestamp:'服务器时间',isArray:'数组',dimensions:'维度',requestedValue:'请求值',feature:'特征类型',count:'目标数量',method:'处理方法',bbox:'包围框',areaPixels:'面积 (px²)',perimeterPixels:'周长 (px)',center:'中心',centerPixels:'中心 (px)',radiusPixels:'半径 (px)',diameterPixels:'直径 (px)',width:'宽度',height:'高度',diameter:'直径',angleDeg:'角度 (°)',confidence:'置信度',score:'匹配分数',text:'识别内容',format:'码制',classId:'类别编号',label:'类别',polygon:'顶点坐标',points:'轮廓点',value:'值',offset:'偏移',offsetPixels:'偏移 (px)',found:'是否找到',passed:'是否通过',calibrated:'是否标定',unit:'单位',unitsPerPixel:'单位/像素',model:'模型',device:'设备',lengthPixels:'长度 (px)',start:'起点',end:'终点',scale:'缩放',defectRatio:'缺陷比例',edgePixels:'边缘像素数'};
function resultLabel(key,usePlugin=true) {
  const pluginResult=usePlugin&&pluginInfo(project.steps.find(s=>s.id===displayedResultId)).op?.outputs.find(f=>f.key===key);if(pluginResult)return pluginResult.label;
  if(key.startsWith('bbox.'))return ({'bbox.x':'X (px)','bbox.y':'Y (px)','bbox.width':'宽度 (px)','bbox.height':'高度 (px)'})[key];
  return key.split('.').map(part=>resultLabels[part]||part).join(' · ');
}
Object.assign(resultLabels,{notificationCount:'已处理订阅通知数',timeoutConnectionVerified:'条件超时后连接与质量已确认',requestedPublishingIntervalMs:'请求发布/采样间隔 (ms)',condition:'当前条件状态',firstValue:'首次通知值',timedOut:'条件等待已超时'});
Object.assign(resultLabels,{boxCenterX:'包围盒中心 X（输入单位）',boxCenterY:'包围盒中心 Y（输入单位）',boxCenterZ:'包围盒中心 Z（输入单位）',cornerX:'角点 X（输入单位）',cornerY:'角点 Y（输入单位）',cornerZ:'角点 Z（输入单位）',dimension:'尺寸方向',measured:'测量值',nearEqualDimensions:'存在近等长边',hullTriangles:'凸包三角面数',uniquePointCount:'独立点数',axisAlignedVolume:'坐标轴包围盒体积',axisAlignedDimensions:'坐标轴尺寸对照'});
Object.assign(resultLabels,{huDifference:'Hu 差异（越低越相似）',areaScale:'面积等效线性比例',outerAreaPixels:'外轮廓面积 (px²)',longSidePixels:'旋转包围框长边 (px)',shortSidePixels:'旋转包围框短边 (px)',holeCount:'孔洞数量',matched:'是否匹配',candidateCount:'完整候选数量',boundaryRejectedCount:'边界排除数量',contour:'外轮廓点表',holes:'孔洞轮廓点表',sourceSha256:'建模来源标识'});
Object.assign(resultLabels,{axisU:'网格 U 轴',axisV:'网格 V 轴',normal:'高度正法向',totalCells:'网格总数',occupiedCells:'已采样格数',validCells:'有效格数',missingCells:'未采样格数',insufficientCells:'独立采样不足格数',spreadRejectedCells:'高度跨度超限格数',outsideHeightCells:'高度超差格数',roiPointCount:'ROI 内独立点数',outsideRoiPointCount:'ROI 外独立点数',coverage:'有效网格覆盖率',roiArea:'定义 ROI 面积',observedArea:'有效观测面积',positiveVolume:'已观测正向体积估计',negativeVolume:'已观测负向体积估计（绝对值）',netVolume:'已观测净体积估计',sampleCount:'独立点数',heightSpread:'同格高度跨度',signedVolume:'该格有符号体积',cellStatistic:'网格高度代表值',u:'网格 U 中心',v:'网格 V 中心'});
Object.assign(resultLabels,{circle:'拟合圆模型',imageSha256:'原图校验标识',coverageDeg:'有效点角度覆盖 (°)',maximumDeviationPixels:'拟合采用点最大偏差 (px)',radialRangePixels:'拟合采用点径向残差范围 (px)',radialResidualPixels:'径向残差 (px)',centerDistancePixels:'中心距离 (px)',centerDistance:'中心距离',nested:'内圆完全包含于外圆',minimumWall:'理想圆最小壁厚',maximumWall:'理想圆最大壁厚',nominalWall:'半径差',role:'圆类型',centerX:'中心 X (px)',centerY:'中心 Y (px)'});
Object.assign(resultLabels,{unique:'唯一目标且结果完整',bestScore:'最佳候选分数',candidateLimitReached:'候选数量受限',searchedVariants:'旋转与缩放组合数',sourcePixelSha256:'原图校验标识',templatePixelSha256:'模板校验标识',templateWidth:'模板宽度 (px)',templateHeight:'模板高度 (px)',sourceWidth:'原图宽度 (px)',sourceHeight:'原图高度 (px)',matrix:'模板到原图变换',inverse:'原图到模板变换',outsideCount:'超出目标范围点数',inside:'位于目标范围内',rectified:'已校正到模板坐标',templateOriginX:'检测区模板 X (px)',templateOriginY:'检测区模板 Y (px)',sourcePolygon:'原图检测区顶点'});
Object.assign(resultLabels,{record:'记录字段',records:'记录表',fieldCount:'字段数',accepted:'接收记录',replaced:'替换已有行',discarded:'满表丢弃行数',matchedCount:'符合条件行数',missingCount:'缺失字段或空值数',skippedCount:'跳过行数',valueCount:'有效数值数',hasValues:'存在有效数值',summary:'统计结果',sum:'总和',mean:'均值',median:'中位数',populationStddev:'总体标准差',sequence:'采样序号',sampleId:'样本编号'});
Object.assign(resultLabels,{pose:'定位位姿',rotationConvention:'旋转角约定',reference:'固定标定板参考',sampleCount:'采样数量',rmsTranslationError:'平移 RMS',maximumTranslationError:'最大平移误差',maximumAngleErrorDegrees:'最大角度误差 (°)',translationError:'平移误差',angleErrorDegrees:'角度误差 (°)',originX:'原点图像 X (px)',originY:'原点图像 Y (px)',rx:'旋转向量 X (rad)',ry:'旋转向量 Y (rad)',rz:'旋转向量 Z (rad)',boardRotation:'标定板基座旋转',boardTranslation:'标定板基座平移',robotRotation:'机器人角度约定',robotUnit:'机器人长度单位',cameraUnit:'相机位姿长度单位',cameraFrame:'相机坐标系',toolFrame:'工具坐标系',baseFrame:'基座坐标系',boardFrame:'标定板坐标系'});
Object.assign(resultLabels,{sourceUnit:'输入长度单位',targetUnit:'输出长度单位',sourceX:'输入 X',sourceY:'输入 Y',sourceZ:'输入 Z',targetX:'输出 X',targetY:'输出 Y',targetZ:'输出 Z',rmsError:'均方根误差',maximumError:'最大单点误差',rejectedCount:'排除点数',rotation:'旋转矩阵',translation:'平移向量'});
Object.assign(resultLabels,{sessionId:'相机会话编号',frameSequence:'会话帧序号',frameAgeMs:'缓存帧龄 (ms)',framePolicy:'取帧策略',reusedFrame:'本帧曾被读取'});
Object.assign(resultLabels,{view:'视图编号',viewCount:'有效视图数',cornerCount:'棋盘内角点数',column:'角点列',row:'角点行',fx:'水平焦距 (px)',fy:'垂直焦距 (px)',cx:'主点 X (px)',cy:'主点 Y (px)',k1:'径向畸变 k1',k2:'径向畸变 k2',k3:'径向畸变 k3',p1:'切向畸变 p1',p2:'切向畸变 p2'});
Object.assign(resultLabels,{axisPoint:'轴线上基准点',axisDirection:'轴线单位方向',axialPosition:'轴向坐标',angularCoverageDeg:'周向覆盖角（°）',sampledAxialSpan:'采样轴向跨度（非零件长度）',axialSpanRatio:'采样轴向跨度 / 半径',cylinder:'圆柱基准模型'});
Object.assign(resultLabels,{sentEncoding:'发送内容格式',serialPort:'串口路径',baudrate:'波特率',dataBits:'数据位',parity:'校验位',stopbits:'停止位',flowControl:'流量控制',discardedInputBytes:'已丢弃输入字节数'});
Object.assign(resultLabels,{mode:'通信方式',localPort:'本地端口',sentBytes:'已发送字节数',trailingBytes:'已收到的尾随字节数'});
Object.assign(resultLabels,{topic:'实际消息主题',encoding:'消息格式',qos:'QoS 等级',clientId:'客户端标识',retained:'保留消息',duplicate:'重复投递标记',byteLength:'消息字节数',delivery:'交付状态'});
Object.assign(resultLabels,{dbNumber:'数据块编号',byteOffset:'字节偏移',bitOffset:'位偏移',rawBytes:'原始字节'});
Object.assign(resultLabels,{uniquePointCount:'独立坐标点数',validCount:'有效点数',invalidCount:'无效点数',invalidPercent:'无效点比例 (%)',hasValidNormals:'存在有效法向',referenceDirection:'参考方向',meanSlopeDegrees:'平均坡度 (°)',maxSlopeDegrees:'最大坡度 (°)',maxLocalResidual:'最大局部拟合残差',normalX:'法向 X',normalY:'法向 Y',normalZ:'法向 Z',slopeDegrees:'坡度 (°)',localResidual:'局部拟合残差',surfaceVariation:'表面变化率',neighborCount:'邻域点数',valid:'有效',outside:'超差'});
Object.assign(resultLabels,{scope:'变量作用域',name:'变量名称',protocol:'协议',action:'操作',area:'数据区域',deviceId:'设备站号',address:'协议地址',dataType:'数据类型',values:'数值',quality:'数据质量',timestamp:'采集时间',registers:'原始寄存器',simulated:'本机模拟',acknowledged:'设备已应答',requestedValues:'请求写入值'});
Object.assign(resultLabels,{comparison:'判断方式',left:'输入值',right:'比较值',reason:'原因',inputFrom:'实际输入模块',milliseconds:'等待时间 (ms)'});
Object.assign(resultLabels,{pointCount:'点数',inputCount:'输入点数',sizeX:'X 尺寸',sizeY:'Y 尺寸',sizeZ:'Z 尺寸',minimum:'最小坐标',maximum:'最大坐标',boundingBoxVolume:'包围盒体积',note:'说明',normal:'平面法向',plane:'平面方程',inlierCount:'平面内点数',inlierRatio:'平面内点比例',rmsError:'均方根误差',output:'输出方式',noiseCount:'噪声点数',cluster:'聚类编号',minHeight:'最低高度',maxHeight:'最高高度',meanHeight:'平均高度',baselineZ:'基准 Z',cellSize:'网格边长',occupiedCells:'有效网格数',sampledArea:'网格覆盖面积',estimatedVolume:'网格估计体积',volumeUnit:'体积单位',fitness:'对应点比例',transformation:'刚体变换矩阵'});
Object.assign(resultLabels,{check:'检查项目',measured:'实测值',limit:'判定阈值',rule:'判定规则',measurement:'测量项目',value:'值',angleDegrees:'无向锐夹角 (°)',parallel:'阈值内平行',index:'编号',x:'X',y:'Y',z:'Z',centerX:'质心 X (px)',centerY:'质心 Y (px)',fillRatio:'包围框填充率',pointIndex:'点索引（从 0 起）',distance:'有符号偏差',detailsTruncated:'明细超过显示上限',coveragePercent:'区域覆盖率 (%)',largestArea:'最大目标面积 (px²)',roi:'检测区域',outsideCount:'超差点数',outsidePercent:'超差点比例 (%)',minimumDistance:'最小有符号偏差',maximumDistance:'最大有符号偏差',peakToValley:'偏差峰谷差',rmsDistance:'偏差均方根'});
Object.assign(resultLabels,{pixelX:'图像 X (px)',pixelY:'图像 Y (px)',worldX:'实际 X',worldY:'实际 Y',errorPixels:'重投影误差 (px)',inlier:'有效点',insideCalibration:'标定区域内',startPoint:'起点序号',endPoint:'终点序号',startX:'起点 X',startY:'起点 Y',endX:'终点 X',endY:'终点 Y',segmentLength:'线段长度',angleDegrees:'方向角 (°)',pixelHull:'有效图像区域',matrix:'像素到实际坐标矩阵',model:'模型'});
Object.assign(resultLabels,{rangeComponent:'XYZ 分量索引',intensityComponent:'亮度分量索引',confidenceComponent:'置信度分量索引',components:'接收分量表',componentAlignment:'分量对应依据',validCoordinatePoints:'有效坐标点数',invalidCoordinatePoints:'无效坐标点数',confidenceAcceptedPoints:'置信度筛选后点数',zPreviewRangeMm:'Z 预览范围 (mm)',millimetersPerUnit:'每单位对应毫米',axes:'各轴换算',axis:'坐标轴',offset:'偏移',invalidEnabled:'无效标记启用',invalidValue:'无效标记值',reference:'坐标参考系'});
function resultText(value) {
  if(value===null||value===undefined)return '—';
  if(typeof value==='boolean')return value?'是':'否';
  if(typeof value==='number')return Number.isInteger(value)?String(value):String(Number(value.toFixed(6)));
  if(Array.isArray(value))return value.map(item=>Array.isArray(item)?'('+item.map(resultText).join(', ')+')':resultText(item)).join('; ');
  if(typeof value==='object')return Object.entries(value).map(([key,item])=>resultLabel(key)+': '+resultText(item)).join('; ');
  return String(value);
}
function flattenResult(value,prefix='',out={}) {
  if(value!==null&&typeof value==='object'&&!Array.isArray(value)) {
    for(const [key,item] of Object.entries(value))flattenResult(item,prefix?prefix+'.'+key:key,out);
  } else if(Array.isArray(value)&&((prefix==='bbox'&&value.length===4)||(['center','centerPixels','offset','offsetPixels','start','end'].includes(prefix)&&value.length===2))) {
    const axes=prefix==='bbox'?['x','y','width','height']:['x','y'];
    axes.forEach((axis,index)=>out[prefix+'.'+axis]=value[index]);
  } else out[prefix||'value']=value;
  return out;
}
function renderResultTable(value) {
  const panel=$('result-table-panel');panel.replaceChildren();
  const records=Array.isArray(value.items)?value.items:null;
  const metadata=Object.fromEntries(Object.entries(value).filter(([key])=>key!=='items'||records===null));
  const table=document.createElement('table');table.className='result-table'+(records?' detection-table':'');
  const head=document.createElement('thead'),header=document.createElement('tr'),body=document.createElement('tbody');body.id='result-table';
  const heading=(label,key)=>{const th=document.createElement('th');th.scope='col';th.textContent=label;if(key)th.title=key;header.append(th);};
  const cell=(row,item)=>{
    const td=document.createElement('td');
    if(Array.isArray(item)&&item.length&&item.every(point=>Array.isArray(point)&&point.length===2)) {
      const details=document.createElement('details'),summary=document.createElement('summary'),points=document.createElement('table');
      points.className='point-table';summary.textContent=item.length+' 个点';
      const pointHead=document.createElement('thead'),pointHeader=document.createElement('tr'),pointBody=document.createElement('tbody');
      for(const name of ['点序号','X','Y']){const th=document.createElement('th');th.scope='col';th.textContent=name;pointHeader.append(th);}
      item.forEach((point,index)=>{const pointRow=document.createElement('tr');for(const number of [index+1,...point]){const pointCell=document.createElement('td');pointCell.textContent=resultText(number);pointRow.append(pointCell);}pointBody.append(pointRow);});
      pointHead.append(pointHeader);points.append(pointHead,pointBody);details.append(summary,points);td.append(details);
    } else td.append(resultValueView(item));
    row.append(td);
  };
  if(records!==null) {
    const calipers=Object.hasOwn(value,'probeCount')&&records.every(item=>item&&Number.isInteger(item.probe));
    const summary=document.createElement('div');summary.className='result-overview';
    for(const [key,item] of Object.entries(metadata)) {const entry=document.createElement('span');entry.append(document.createTextNode(resultLabel(key)+'：'),resultValueView(value.task==='segment'?({task:{segment:'实例分割'},output:{mask:'二值掩膜',overlay:'彩色叠加'}}[key]?.[item]??item):item));entry.title=key;summary.append(entry);}
    panel.append(summary);
    const rows=records.map(item=>flattenResult(item));
    const columns=[...new Set(rows.flatMap(row=>Object.keys(row)))].filter(key=>!calipers||key!=='probe');
    if(value.task==='segment'){const primary=['instance','label','classId','confidence','areaPixels','center.x','center.y'];const rank=key=>primary.includes(key)?primary.indexOf(key):key==='contours'?100:50;columns.sort((a,b)=>rank(a)-rank(b));}
    if(calipers){const primary=['valid','width','passed','edgeX','edgeY','inlier','residualPixels','widthPixels','reason'];const rank=key=>primary.includes(key)?primary.indexOf(key):primary.length;columns.sort((a,b)=>rank(a)-rank(b));}
    heading(calipers?'卡尺序号':'序号');columns.forEach(key=>heading(calipers&&key==='width'?'宽度 ('+value.unit+')':DataPresentation.recordFieldLabel(rows,key,resultLabel(key,false)),key));
    if(!rows.length){heading('检测结果');const row=document.createElement('tr');cell(row,Object.hasOwn(value,'outsideCount')&&value.outsideCount===0?'无超差点':'暂无检测明细');row.firstChild.colSpan=2;row.firstChild.className='empty-cell';body.append(row);}
    rows.forEach((item,index)=>{const row=document.createElement('tr');cell(row,calipers?item.probe:index+1);columns.forEach(key=>cell(row,item[key]));body.append(row);});
  } else {
    heading('结果字段');heading('当前值');
    const fields=Object.entries(flattenResult(value));
    if(value.method==='global'&&Object.hasOwn(value,'sourceFeaturePoints')){
      const order=['found','passed','fitness','targetFitness','rmsError','reason','transformation','unit','sourceFrame','targetFrame'];
      const rank=key=>order.includes(key)?order.indexOf(key):order.length;
      fields.sort((a,b)=>rank(a[0])-rank(b[0]));
    }else if(Object.hasOwn(value,'sizeX')){
      const order=['unit','sizeX','sizeY','sizeZ','pointCount','inputCount','boundingBoxVolume'];
      const rank=key=>order.includes(key)?order.indexOf(key):order.length;
      fields.sort((a,b)=>rank(a[0])-rank(b[0]));
    }
    for(const [key,item] of fields) {
      const row=document.createElement('tr');cell(row,resultLabel(key));row.firstChild.title=key;
      const display=key==='inputFrom'&&(item==='source'||project.steps.some(s=>s.id===item))?flowName(item):key==='comparison'?({eq:'等于',ne:'不等于',gt:'大于',gte:'大于等于',lt:'小于',lte:'小于等于',contains:'文本包含',is_true:'开关为是',is_false:'开关为否'})[item]||item:key==='delivery'?({sent:'已发送（无服务器应答）',broker_acknowledged:'服务器已应答',received:'已接收'})[item]||item:key==='encoding'?({text:'UTF-8 文本',structured:'结构化数据',bytes:'字节数组'})[item]||item:item;
      cell(row,display);body.append(row);
    }
  }
  head.append(header);table.append(head,body);panel.append(table);
}
function dirty(clearResults=true) {
  flowEditRecord();
  $('saved-state').textContent='有未保存修改';
  if(clearResults&&results.length){rememberBindingFields(results);results=[];renderResults();renderPipeline();$('run-timing').textContent='总耗时 —';}
}
function selectedStep() { return project.steps[selected]; }
// Pointer-based dragging also works on embedded browsers and touch displays.
function enablePointerDrag(element,payload) {
  let start=null,ghost=null,moved=false,suppressClick=false;
  const clear=()=>{ghost?.remove();ghost=null;document.querySelectorAll('.drop-target').forEach(item=>item.classList.remove('drop-target'));};
  element.addEventListener('click',event=>{if(suppressClick){event.preventDefault();event.stopImmediatePropagation();suppressClick=false;}},true);
  element.onpointerdown=event=>{
    suppressClick=false;
    if(running||event.button!==0||event.target.closest('.step-actions'))return;
    start=[event.clientX,event.clientY];moved=false;element.setPointerCapture(event.pointerId);
  };
  element.onpointermove=event=>{
    if(!start)return;
    if(!moved&&Math.hypot(event.clientX-start[0],event.clientY-start[1])<7)return;
    moved=true;
    if(!ghost){ghost=document.createElement('div');ghost.className='drag-ghost';ghost.textContent=payload.operation?catalog[payload.operation].name:catalog[project.steps[payload.index].operation].name;document.body.append(ghost);}
    ghost.style.left=(event.clientX+12)+'px';ghost.style.top=(event.clientY+12)+'px';
    document.querySelectorAll('.drop-target').forEach(item=>item.classList.remove('drop-target'));
    const hit=document.elementFromPoint(event.clientX,event.clientY);
    const target=hit?.closest('.step')||hit?.closest('.flow-viewport');target?.classList.add('drop-target');
  };
  element.onpointerup=safe(event=>{
    if(!start)return;start=null;clear();
    if(!moved)return;suppressClick=true;
    const hit=document.elementFromPoint(event.clientX,event.clientY),viewport=hit?.closest('.flow-viewport');
    if(!viewport||running)return;
    if(payload.operation)addStep(payload.operation,flowPoint(event),payload.pluginKey);
  });
  element.onpointercancel=()=>{start=null;clear();};
}
function getParams() { return structuredClone(selectedStep()?.params||{}); }
function applyParams() {
  if(!selectedStep())return;
  const invalid=$('parameter-dialog').querySelector('input:invalid,select:invalid');
  if(invalid){invalid.reportValidity();throw Error('请修正参数表单中的无效输入');}
  paintSource();
}
function safe(action) { return async (...args) => { try { await action(...args); } catch(error) {status(error.message,'error');} }; }
async function api(url, options) {
  const response = await fetch('/api/vision/'+url,options);
  const body = await response.json();
  if (!response.ok) throw Error(body.error || '请求失败');
  return body;
}
function renderLibrary() {
  $('operators').replaceChildren();
  const query=$('operator-search').value.trim().toLowerCase();let visible=0;
  const groups=[['相机采集',['camera_capture']],['图像处理',['preprocess']],['定位与测量',['locate','geometry','measure']],['识别工具',['barcode','ocr']],['缺陷与 AI',['defects','yolo','yolo_segment']],['3D 点云',['cloud_filter','cloud_plane','cloud_cluster','cloud_measure','cloud_height','cloud_register']],['工业通信',['modbus_read','modbus_write','opcua_browse','opcua_read','opcua_write','s7_read','s7_write','mqtt_publish','mqtt_receive','tcp_exchange','udp_exchange','serial_exchange']],['流程控制',['condition','branch_merge','delay','modbus_wait','opcua_wait','subflow','loop']],['脚本与变量',['script','variables']]];
  for(const [label,operations] of groups) {
    const matches=operations.filter(op=>(catalog[op].name+' '+catalog[op].tag+' '+op).toLowerCase().includes(query));
    if(!matches.length)continue;
    const group=document.createElement('details');group.className='operator-group';group.open=Boolean(query)||label==='图像处理';
    const heading=document.createElement('summary');heading.textContent=label;
    const count=document.createElement('span');count.textContent=matches.length;heading.append(count);group.append(heading);
  for (const operation of matches) {
    const definition=catalog[operation];visible++;
    const button=document.createElement('button'); button.className='operator';button.draggable=false;
    enablePointerDrag(button,{operation});
    button.title='添加 '+definition.name;button.dataset.operation=operation;
    const glyph=document.createElement('span'); glyph.className='glyph';glyph.textContent=definition.glyph;
    const text=document.createElement('span');text.textContent=definition.name;
    const detail=document.createElement('small');detail.textContent=definition.tag;text.append(detail);button.append(glyph,text);
    button.onclick=safe(()=>addStep(operation));
    button.ondragstart=event=>event.dataTransfer.setData('text/plain',JSON.stringify({operation}));
    group.append(button);
  }
    $('operators').append(group);
  }
  visible+=renderPluginLibrary(query);$('no-operators').hidden=visible>0;
}
function addStep(operation,position,pluginKey) {
  if(running)return;if(project.steps.length>=50)throw Error('一个工程最多 50 个算子');applyParams();
  const insertEdge=flowEdge&&project.edges.find(e=>e.id===flowEdge);
  const parent=insertEdge?.from||selectedStep()?.id||'source';
  const step={id:uid(),operation,params:operation==='plugin'?pluginDefaults(pluginKey):clone(catalog[operation].defaults),reference:'',position:position||{x:flowPosition(parent).x,y:Math.min(9800,flowPosition(parent).y+130)},imageFrom:position?null:parent};
  if(insertEdge&&!position){step.position={x:Math.min(9600,flowPosition(parent).x+240),y:Math.min(9800,flowPosition(parent).y+100)};while(project.steps.some(s=>Math.abs(s.position.x-step.position.x)<210&&Math.abs(s.position.y-step.position.y)<90)&&step.position.y<9700)step.position.y+=100;}
  const next=clone(project);next.steps.push(step);
  // Palette click extends the selected branch; a canvas drop creates an unconnected node.
  if(insertEdge){step.imageFrom=null;project=FlowEdit.insert(next,insertEdge.id,step.id,uid);flowEdge=null;}
  else{if(!position)next.edges.push({id:uid(),from:parent,to:step.id,fromPort:'bottom',toPort:'top'});project=next;}
  flowSelection.clear();flowSelection.add(step.id);
  selected=project.steps.length-1;dirty();renderPipeline();renderParams();
}
function renderPipeline(){flowRender();subflowWorkspaceRender();}
function renderParams() {
  runtimeFields();cloudFields();industrialFields();
  flowRenderInputs();
  const step=selectedStep();$('form-fields').replaceChildren();
  $('selected-name').textContent=step?flowLabel(step):'尚未选择算子';
  $('selected-glyph').textContent=step?catalog[step.operation].glyph:'◇';
  $('selected-type').textContent=step?`模块 ${String(selected+1).padStart(2,'0')} / ${step.operation}`:'从工具箱添加模块';
  $('operator-description').textContent=step?stepDefinition(step).description:'';
  $('parameter-hint').textContent=step?catalog[step.operation].hint:'';

  $('camera-config-open').hidden=step?.operation!=='camera_capture';
  $('opcua-open-browser').hidden=!step?.operation.startsWith('opcua_');
  $('reference-tools').hidden=!step||!['locate','defects'].includes(step.operation);
  $('reference-status').textContent=step?.reference?'已设置参考图（随工程保存）':'未设置参考图';
  if(step)for(const [key,label,type,max,increment] of catalog[step.operation].fields) {
    if(!functionalFieldVisible(step,key)||!industrialFieldVisible(step,key)||!opcuaFieldVisible(step,key)||!cameraFieldVisible(step,key)||!s7FieldVisible(step,key)||!mqttFieldVisible(step,key)||!socketFieldVisible(step,key)||!serialFieldVisible(step,key))continue;
    const method=step.params.method||'grayscale';
    if(type==='text'&&DataPresentation.structuredParts(step.params[key])){
      const section=formEl('section',undefined,'parameter-value');section.append(formEl('label',label,'section-caption'),structuredTextEditor(step.params[key],v=>{step.params[key]=v;dirty();},label));$('form-fields').append(section);continue;
    }
    if(step.params[key]&&typeof step.params[key]==='object'){
      const section=formEl('section',undefined,'parameter-value');section.append(formEl('label',label,'section-caption'),valueEditor(step.params[key],v=>{step.params[key]=v;dirty();},{label}));$('form-fields').append(section);continue;
    }
    const row=document.createElement('label');row.className='field';row.textContent=label;
    const input=document.createElement(Array.isArray(type)?'select':'input');input.setAttribute('aria-label',label);
    if(Array.isArray(type)){for(const value of computeChoices(type,step,key)){if(step.operation==='modbus_wait'&&key==='comparison'&&typeof step.params.area!=='object'&&(['coils','discrete'].includes(step.params.area)!==['is_true','is_false'].includes(value)))continue;if(step.operation==='s7_write'&&key==='area'&&value==='pe')continue;if(step.operation==='modbus_write'&&key==='area'&&['input','discrete'].includes(value))continue;const option=document.createElement('option');option.value=value;option.textContent=key==='device'?computeLabel(value):step.operation==='cloud_register'&&value==='global'?'全局定位 · 粗配准与精配准':isSerialStep(step)&&value==='device'?'实际串口设备':isSerialStep(step)&&value==='simulator'?'软件回环模拟':({...socketLabels,...serialLabels,overlay:'彩色叠加 · 下游保留原图',mask:'二值掩膜 · 传给下游',icp:'局部 ICP · 已知近似姿态',global:'全局',level:'条件成立',rising:'条件由不成立变为成立',falling:'条件由成立变为不成立',error:'报错并停止',continue:'输出未触发并继续',image:'2D 图像',pointcloud:'3D 标定点云',broker:'外部 MQTT 服务器',plain:'TCP · 不加密',tls:'TLS · 验证证书',structured:'结构化数据',text:'UTF-8 文本',bytes:'字节数组',plc:'西门子 PLC',db:'数据块 DB',mk:'中间存储 M',pe:'输入区 I',pa:'输出区 Q',bool:'开关 BOOL',eq:'等于',ne:'不等于',gt:'大于',gte:'大于等于',lt:'小于',lte:'小于等于',contains:'文本包含',is_true:'开关为是',is_false:'开关为否',orbbec:'奥比中光 Orbbec 深度相机',realsense:'RealSense 深度相机',rgbd_simulator:'模拟深度相机',session:'已连接连续相机',next:'等待下一帧',latest:'最新未过期缓存帧',uvc:'USB UVC 相机',gentl:'GenTL 工业相机',freerun:'自由采集',software:'软件触发',external:'外部线路触发',simulator:'本机模拟设备',server:'OPC UA 服务器',None:'匿名 · 无加密',Basic256Sha256:'签名并加密 · Basic256Sha256',tcp:'Modbus TCP',rtu:'Modbus RTU',holding:'保持寄存器',input:'输入寄存器',coils:'线圈',discrete:'离散输入',big:'大端',little:'小端',N:'无校验',E:'偶校验',O:'奇校验',grayscale:'灰度化',blur:'高斯模糊',threshold:'二值化',canny:'边缘提取',open:'开运算',close:'闭运算',erode:'腐蚀',dilate:'膨胀',contours:'轮廓',lines:'直线',circles:'圆',edges:'边缘'})[value]||value;input.append(option);}input.value=step.params[key]??functionalDefaults(step)[key]??cloudParamDefault(step,key)??industrialParamDefault(step,key)??opcuaParamDefault(step,key)??serialParamDefault(step,key)??socketParamDefault(step,key)??mqttParamDefault(step,key)??cameraDefault(step,key)??s7ParamDefault(step,key)??type[0];}
    else if(type==='boolean'){input.type='checkbox';input.checked=Boolean(step.params[key]??opcuaParamDefault(step,key)??serialParamDefault(step,key)??socketParamDefault(step,key)??mqttParamDefault(step,key)??cameraDefault(step,key));}
    else {input.type=type==='text'?'text':'number';if(input.type==='number'){input.min=type;input.max=max;input.step=increment||1;}input.value=step.params[key]??functionalDefaults(step)[key]??cloudParamDefault(step,key)??industrialParamDefault(step,key)??opcuaParamDefault(step,key)??serialParamDefault(step,key)??socketParamDefault(step,key)??mqttParamDefault(step,key)??cameraDefault(step,key)??s7ParamDefault(step,key)??'';}
    if(step.operation==='preprocess'&&['kernel','threshold'].includes(key))input.placeholder='默认 '+(key==='threshold'?127:method==='blur'?5:3);
    if(step.operation==='camera_capture'&&['realsense','orbbec'].includes(step.params.driver)&&key==='fps')input.step=1;
    // Commit text/number edits while typing; toolbar actions can run before blur.
    // Keep invalid intermediate input visible so applyParams can report it.
    if(input.type==='number'||input.type==='text')input.oninput=()=>{
      if(running||!input.checkValidity())return;
      if(input.value==='')delete step.params[key];
      else step.params[key]=input.type==='number'?Number(input.value):input.value;
      cloudRefreshDefaults(step,key);dirty();
    };
    input.onchange=safe(()=>{applyParams();if(input.type==='checkbox')step.params[key]=input.checked;else if(input.value==='')delete step.params[key];else step.params[key]=input.type==='number'?Number(input.value):input.value;if(step.operation==='modbus_wait'&&key==='area')step.params.comparison=['coils','discrete'].includes(input.value)?'is_true':'eq';if(step.operation.startsWith('s7_')&&key==='dataType'&&input.value==='bool')step.params.count=1;if(step.operation.startsWith('opcua_')&&key==='security'&&input.value==='None'){delete step.params.username;delete step.params.passwordEnv;}if(step.operation==='camera_capture'&&key==='driver'){for(const k of ['sessionId','framePolicy','maxAgeMs','dataMode','configure3d','coordinateFormat','rangeComponent','intensityComponent','confidenceComponent','confidenceThreshold','alignedComponents','deviceId','providerId','fps','warmupFrames','exposureTime','gain','pixelFormat','triggerSource','width','height','enableColor','colorWidth','colorHeight','colorFormat','discoverNetwork','pointStride','minDepth','maxDepth'])delete step.params[k];if(input.value==='session')delete step.params.trigger;else step.params.trigger='freerun';if(input.value==='simulator')step.params.deviceId='synthetic-parts';if(input.value==='rgbd_simulator')step.params.deviceId='synthetic-rgbd';}if(step.operation==='camera_capture'&&key==='dataMode'&&input.value==='pointcloud')delete step.params.pixelFormat;dirty();if(['output','dataMode','configure3d','intensityComponent','confidenceComponent','flowControl','mode','rxFraming','comparison','method','feature','transport','area','connection','encoding','security','username','driver','trigger','framePolicy','enableColor','dataType'].includes(key))renderParams();});row.append(input);$('form-fields').append(row);
    const bind=formEl('button','绑定变量或结果');bind.className='binding-button';bind.onclick=()=>{step.params[key]={$ref:'flow.'};dirty();renderParams();};$('form-fields').append(bind);
  }
  if(step?.operation==='plugin')renderPluginParams(step);else if(['subflow','loop'].includes(step?.operation))renderSubflowParams(step);else renderStructuredParams();
  renderModuleVariables();renderComputeParamTools(step);
  refreshInputPreview();
}
function paintSource(rect) {
  const roi=rect||selectedStep()?.params?.roi;
  $('roi-info').textContent=Array.isArray(roi)?`ROI: X ${roi[0]} · Y ${roi[1]} · 宽 ${roi[2]} · 高 ${roi[3]}`:roi?'ROI: 运行时读取绑定值':'ROI: 全图';
  ctx.clearRect(0,0,canvas.width,canvas.height);
  if(!inputPreviewImage)return;
  ctx.drawImage(inputPreviewImage,0,0);
  const box=rect||selectedStep()?.params?.roi;
  if(Array.isArray(box)&&box.length===4&&box.every(Number.isFinite)){ctx.strokeStyle=getComputedStyle(document.documentElement).getPropertyValue('--accent').trim()||'#1292c1';ctx.lineWidth=Math.max(2,canvas.width/500);ctx.setLineDash([8,5]);ctx.strokeRect(...box);ctx.setLineDash([]);}
}
async function readFile(file) {
  if(!file)throw Error('请选择文件');
  if(file.size>12_000_000)throw Error('单张图像不能超过 12 MB');
  return new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result);reader.onerror=()=>reject(Error('文件读取失败'));reader.readAsDataURL(file);});
}
async function loadImage(data) {
  const image=new Image();image.src=data;await image.decode();
  if(image.naturalWidth*image.naturalHeight>16_000_000)throw Error('图像超过 1600 万像素');
  framePreviews.clear();inputPreviewEpoch++;inputPreviewImage=image;inputPreviewData=data;source=data;sourceDepth=null;originalImage=image;canvas.width=image.naturalWidth;canvas.height=image.naturalHeight;
  $('empty-image').hidden=true;$('image-size').textContent=`${canvas.width} × ${canvas.height}`;
  setImageView('input');setZoom(1);
  results=[];renderResults();renderPipeline();refreshInputPreview();$('run-timing').textContent='总耗时 —';status('图像已载入');
}
function pointerPosition(event) {
  const box=canvas.getBoundingClientRect();return [Math.max(0,Math.min(canvas.width,Math.round((event.clientX-box.left)*canvas.width/box.width))),Math.max(0,Math.min(canvas.height,Math.round((event.clientY-box.top)*canvas.height/box.height)))];
}
canvas.onpointerdown=event=>{if(!inputPreviewImage||!['preprocess','locate','geometry','measure','barcode','ocr','defects','yolo','yolo_segment'].includes(selectedStep()?.operation)||running||document.body.classList.contains('runtime'))return;dragging=pointerPosition(event);canvas.setPointerCapture(event.pointerId);};
canvas.onpointermove=event=>{const point=pointerPosition(event);$('pointer-position').textContent=`X: ${point[0]}   Y: ${point[1]}`;if(!dragging)return;paintSource([Math.min(dragging[0],point[0]),Math.min(dragging[1],point[1]),Math.abs(point[0]-dragging[0]),Math.abs(point[1]-dragging[1])]);};
canvas.onpointerup=safe(event=>{if(!dragging)return;const start=dragging;dragging=null;const point=pointerPosition(event);const rect=[Math.min(start[0],point[0]),Math.min(start[1],point[1]),Math.abs(start[0]-point[0]),Math.abs(start[1]-point[1])];if(rect[2]<2||rect[3]<2){paintSource();return;}applyParams();if($('draw-mode').value==='template'){if(selectedStep().operation!=='locate')throw Error('请先选择模板定位算子');const crop=document.createElement('canvas');crop.width=rect[2];crop.height=rect[3];crop.getContext('2d').drawImage(inputPreviewImage,...rect,0,0,rect[2],rect[3]);selectedStep().reference=crop.toDataURL('image/png');delete selectedStep().params.templateRoi;}else selectedStep().params.roi=rect;dirty();renderParams();status('框选区域已应用','success');});
canvas.onpointercancel=()=>{dragging=null;paintSource();};
async function execute(single=false) {return executeRuntime(single);}
function setBusy(busy) {
  busy=busy||continuousState.busy||continuousStarting||mqttTriggerState.busy||mqttTriggerStarting;
  $('project-name').disabled=busy;$('configure-step').disabled=busy;
  for(const id of ['hmi-open','operator-publish-open','plugins-open','cameras-open','camera-config-open','communications-open','opcua-open-browser','open-cloud','cloud-file','cloud-reference-file','cloud-clear','run-all','run-step','source-file','sample','quick-sample','return-demo','save-project','load-project','import-project','reference-file','clear-reference','clear-roi','export-project','flow-layout','variables-open','script-code','script-trust'])$(id).disabled=busy;
  $('depth-import-fields').disabled=busy||depthImporting;document.querySelectorAll('.demo-load').forEach(button=>button.disabled=busy);
  $('stop').disabled=!busy;document.querySelectorAll('#parameter-dialog input,#parameter-dialog select,#parameter-dialog button,#parameter-dialog textarea').forEach(e=>e.disabled=busy);
  $('form-fields').querySelectorAll('input,select').forEach(el=>el.disabled=busy);
  document.querySelectorAll('.operator').forEach(el=>{el.disabled=busy;});
  $('operator-search').disabled=busy;$('flow-inputs').querySelectorAll('select').forEach(el=>el.disabled=busy||el.dataset.fixed==='true');subflowWorkspaceControls(busy);flowEditButtons();
}
function renderResults() {
  refreshOutputBindingValues();
  $('empty-result').querySelector('strong').textContent='等待处理结果';$('empty-result').querySelector('span').textContent='执行所选算子或运行完整流程';
  document.body.classList.toggle('has-results',results.length>0);
  $('result-tabs').replaceChildren();
  if(!results.length){resultCloud=null;drawCloud();displayedResultId='';renderDepthPreview();renderResultTable({'状态':'等待执行'});$('result-summary').textContent='等待执行';$('output-image').hidden=true;$('empty-result').hidden=false;$('elapsed').textContent='';return;}
  for(const result of results){const button=document.createElement('button');button.dataset.resultId=result.id;button.textContent=result.name+(result.error?' ×':result.skipped?' · 已跳过':' ✓');button.onclick=()=>{showResult(result);if(result.output?.cloud)setImageView('cloud');else if(document.querySelector('.views').dataset.view!=='split')setImageView('output');};$('result-tabs').append(button);}
  showResult(results.at(-1));
}
function showResult(item) {
  displayedResultId=item.id;renderDepthPreview();resultCloud=item.output?.cloud||null;drawCloud();
  document.querySelectorAll('#result-tabs button').forEach(button=>button.classList.toggle('active',button.dataset.resultId===item.id));
  renderResultTable(item.error?{错误:item.error,处理状态:item.handled?'已转入错误分支':'流程停止',...(item.output?.result?.trace?{内部执行明细:item.output.result.trace}:{})}:item.output.result);
  $('result-summary').textContent=item.error?(item.handled?'执行失败 · 已转入错误分支':'执行失败'):item.name;
  if(item.error){$('output-image').hidden=true;$('empty-result').hidden=false;$('elapsed').textContent='';return;}
  $('output-image').src=item.output.annotatedImage||'';$('output-image').hidden=!item.output.annotatedImage;$('empty-result').hidden=!!item.output.annotatedImage;
  if(!item.output.annotatedImage){$('empty-result').querySelector('strong').textContent='当前模块输出数据';$('empty-result').querySelector('span').textContent='查看下方结果表格；输入图像和点云继续传给下游';}
  $('elapsed').textContent=`· ${item.output.elapsedMs} ms`;
  if(item.skipped){$('empty-result').querySelector('strong').textContent='本分支已跳过';$('empty-result').querySelector('span').textContent=item.reason;$('elapsed').textContent='';}
}
function download(name,data,type='application/json') {
  const a=document.createElement('a');const url=URL.createObjectURL(new Blob([data],{type}));a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
}
function currentProject() {applyParams();project.name=$('project-name').value.trim()||'我的视觉工程';return project;}
function validateProject(value) {return FlowGraph.normalize(value);}
function useProject(value) {hmiRuntimeRenderedSignature='';subflowWorkspaceCheck(value);framePreviews.clear();bindingResultFields.clear();$('script-trust').checked=false;project=validateProject(value);flowEditReset();selected=project.steps.length?0:-1;results=[];flowLink=null;flowEdge=null;$('project-name').value=project.name;renderPipeline();renderParams();renderResults();$('run-timing').textContent='总耗时 —';requestAnimationFrame(flowFit);hmiSyncMode();}
$('source-file').onchange=safe(async event=>{await loadImage(await readFile(event.target.files[0]));event.target.value='';});
$('reference-file').onchange=safe(async event=>{if(!selectedStep())throw Error('请先选择算子');const data=await readFile(event.target.files[0]);const image=new Image();image.src=data;await image.decode();if(image.width*image.height>16000000)throw Error('参考图超过 1600 万像素');selectedStep().reference=data;dirty();renderParams();event.target.value='';});
$('clear-reference').onclick=()=>{if(selectedStep()){selectedStep().reference='';dirty();renderParams();}};
$('clear-roi').onclick=safe(()=>{applyParams();if(selectedStep()){delete selectedStep().params.roi;dirty();renderParams();}});

$('quick-sample').onclick=safe(async()=>{if(running||demoLoading)return;const op=selectedStep()?.operation;if(op?.startsWith('cloud_')){setSourceCloud(await demoCloud(['cloud_plane','cloud_cluster'].includes(op)?'cloud-scene.json':'cloud-box.json'));$('demo-dialog').close();return status('示例点云已载入');}const name=op==='barcode'?'codes':op==='ocr'?'text':'parts';const response=await fetch('samples/'+name+'.png');if(!response.ok)throw Error('演示图不存在');await loadImage(await readFile(await response.blob()));if(!project.steps.length)addStep('geometry');$('demo-dialog').close();});
$('sample').onclick=safe(async()=>{
  if(running||demoLoading)return;
  await loadOperatorPlugins();
  if(!demoCases){const response=await fetch('samples/demos.json');if(!response.ok)throw Error('无法读取演示案例');demoCases=await response.json();const chains=await fetch('samples/demos-inspection-chain.json');if(chains.ok)demoCases.push(...await chains.json());const quality=await fetch('samples/demos-image-quality.json');if(quality.ok)demoCases.push(...await quality.json());const deviation=await fetch('samples/demos-deviation.json');if(deviation.ok)demoCases.push(...await deviation.json());const relations=await fetch('samples/demos-relations.json');if(relations.ok)demoCases.push(...await relations.json());const segmentation=await fetch('samples/demos-segmentation.json');if(segmentation.ok)demoCases.push(...await segmentation.json());const clouds=await fetch('samples/demos-3d.json');if(clouds.ok)demoCases.push(...await clouds.json());const communications=await fetch('samples/demos-industrial.json');if(communications.ok)demoCases.push(...await communications.json());const s7=await fetch('samples/demos-s7.json');if(s7.ok)demoCases.push(...await s7.json());const serial=await fetch('samples/demos-serial.json');if(serial.ok)demoCases.push(...await serial.json());const sockets=await fetch('samples/demos-socket.json');if(sockets.ok)demoCases.push(...await sockets.json());const mqtt=await fetch('samples/demos-mqtt.json');if(mqtt.ok)demoCases.push(...await mqtt.json());const opcuaSignals=await fetch('samples/demos-opcua-wait.json');if(opcuaSignals.ok)demoCases.push(...await opcuaSignals.json());const opcua=await fetch('samples/demos-opcua.json');if(opcua.ok)demoCases.push(...await opcua.json());const cameras=await fetch('samples/demos-cameras.json');if(cameras.ok)demoCases.push(...await cameras.json());const controls=await fetch('samples/demos-control.json');if(controls.ok)demoCases.push(...await controls.json());const cylinders=await fetch('samples/demos-cylinder.json');if(cylinders.ok)demoCases.push(...await cylinders.json());const spheres=await fetch('samples/demos-sphere.json');if(spheres.ok)demoCases.push(...await spheres.json());const recordDemos=await fetch('samples/demos-records.json');if(recordDemos.ok)demoCases.push(...await recordDemos.json());const handeye=await fetch('samples/demos-handeye.json');if(handeye.ok)demoCases.push(...await handeye.json());const rigid=await fetch('samples/demos-rigid.json');if(rigid.ok)demoCases.push(...await rigid.json());const intrinsics=await fetch('samples/demos-intrinsics.json');if(intrinsics.ok)demoCases.push(...await intrinsics.json());const heightfields=await fetch('samples/demos-heightfield.json');if(heightfields.ok)demoCases.push(...await heightfields.json());const fixtures=await fetch('samples/demos-fixture.json');if(fixtures.ok)demoCases.push(...await fixtures.json());const orientedBoxes=await fetch('samples/demos-box.json');if(orientedBoxes.ok)demoCases.push(...await orientedBoxes.json());const depthFiles=await fetch('samples/demos-depth-file.json');if(depthFiles.ok)demoCases.push(...await depthFiles.json());const silhouettes=await fetch('samples/demos-shape.json');if(silhouettes.ok)demoCases.push(...await silhouettes.json());const circles=await fetch('samples/demos-circle.json');if(circles.ok)demoCases.push(...await circles.json());const calipers=await fetch('samples/demos-caliper.json');if(calipers.ok)demoCases.push(...await calipers.json());const plugins=await fetch('samples/demos-plugins.json');if(plugins.ok)demoCases.push(...await plugins.json());const hmi=await fetch('samples/demos-hmi.json');if(hmi.ok)demoCases.push(...await hmi.json());}
  renderDemoCases();$('demo-dialog').showModal();
});
function renderDemoCases() {
  $('demo-filters').replaceChildren();$('demo-cards').replaceChildren();
  for(const category of ['全部',...new Set(demoCases.map(item=>item.category))]) {
    const button=document.createElement('button');button.textContent=category;button.classList.toggle('active',category===demoCategory);button.setAttribute('aria-pressed',String(category===demoCategory));
    button.onclick=()=>{demoCategory=category;renderDemoCases();};$('demo-filters').append(button);
  }
  for(const item of demoCases.filter(item=>demoCategory==='全部'||item.category===demoCategory)) {
    const unavailable=DataPresentation.pluginRequirementError(item.steps,installedPlugins);
    const card=document.createElement('article');card.className='demo-card';
    const preview=document.createElement('img');preview.src='samples/'+item.image;preview.alt=item.name+'示例图';preview.loading='lazy';
    const content=document.createElement('div'),title=document.createElement('h3'),description=document.createElement('p'),expected=document.createElement('p'),button=document.createElement('button');
    title.textContent=item.name;description.textContent=item.description;expected.className='demo-card-expected';expected.textContent=item.expected;
    button.className='demo-load';button.textContent=unavailable?'算子暂不可用':item.loadOnly?'载入演示':'载入并运行';button.setAttribute('aria-label','运行演示：'+item.name);button.disabled=running||demoLoading||!!unavailable;button.title=unavailable;button.onclick=safe(()=>loadDemo(item));
    if(unavailable)content.append(formEl('p',unavailable+'。请在插件管理中检查服务加载状态。','form-notice'));
    content.append(title,description,expected,button);card.append(preview,content);$('demo-cards').append(card);
  }
}
async function demoImage(name) {
  const response=await fetch('samples/'+name);if(!response.ok)throw Error('演示素材读取失败：'+name);
  const data=await readFile(await response.blob()),image=new Image();image.src=data;await image.decode();return data;
}
async function loadDemo(item) {
  if(running||demoLoading)return;
  await loadOperatorPlugins();
  if(running||demoLoading)return;
  const unavailable=DataPresentation.pluginRequirementError(item.steps,installedPlugins);if(unavailable)throw Error(unavailable);
  applyParams();demoLoading=true;setBusy(true);
  try {
    const [image,steps,cloud,depthFrame]=await Promise.all([item.cloud||item.camera||item.depthFile?null:demoImage(item.image),Promise.all(item.steps.map(async step=>({...step,id:uid(),params:clone(step.params),reference:step.reference?await demoImage(step.reference):''}))),item.cloud?demoCloud(item.cloud):null,item.depthFile?demoDepth(item.depthFile,item.depthParams):null]);
    if(item.cameraSession)await prepareCameraSessionDemo(steps,item.cameraSession);
    const demoNodeIds=Object.fromEntries(item.steps.flatMap((step,index)=>step.id?[[step.id,steps[index].id]]:[]));
    for(const step of steps)step.params=DataPresentation.remapResultReferences(step.params,demoNodeIds);
    if(!demoBackup)demoBackup={project:clone(currentProject()),source,sourceCloud:clone(sourceCloud),sourceDepth:clone(sourceDepth),selected,results:clone(results),view:document.querySelector('.views').dataset.view,zoom:imageZoom,displayedResultId,saved:$('saved-state').textContent,timing:$('run-timing').textContent,parametersOpen:!$('parameter-dialog').hidden};
    for(const binding of item.bindings||[]){if(!steps[binding.step]||!steps[binding.source])throw Error('演示结果绑定无效');steps[binding.step].params[binding.param]={$ref:'results.'+steps[binding.source].id+'.'+binding.field};}
    let demoProject={version:1,...(item.subflows?{subflows:clone(item.subflows)}:{}),variables:clone(item.variables||{}),...(item.variableTypes?{variableTypes:clone(item.variableTypes)}:{}),name:'演示 · '+item.name,steps};
    if(item.connections){
      demoProject={...demoProject,version:2,edges:item.connections.map(([from,to,when])=>({id:uid(),from:from<0?'source':steps[from].id,to:steps[to].id,fromPort:'bottom',toPort:'top',...(when?{when}:{})}))};
      for(let i=0;i<steps.length;i++)if(item.imageParents?.[i]!==undefined)steps[i].imageFrom=item.imageParents[i]<0?'source':steps[item.imageParents[i]].id;
      demoProject=FlowGraph.layout(FlowGraph.normalize(demoProject));
    }
    if(item.hmi){demoProject.hmi=clone(item.hmi);const components=HmiLayout.allComponents(demoProject.hmi);for(const binding of item.hmiBindings||[]){if(!steps[binding.step]||!components[binding.component])throw Error('画面演示绑定无效');components[binding.component].binding.nodeId=steps[binding.step].id;}}
    setMode(false);useProject(demoProject);sourceCloud=null;sourceDepth=null;resultCloud=null;if(image)await loadImage(image);else{source='';originalImage=null;ctx.clearRect(0,0,canvas.width,canvas.height);$('empty-image').hidden=false;$('image-size').textContent='未载入图像';if(depthFrame)setSourceDepthFrame(depthFrame);else if(cloud)setSourceCloud(cloud);else setImageView('input');}
    selected=project.steps.length-1;renderPipeline();renderParams();
    $('demo-name').textContent=item.name;$('demo-expected').textContent='预期：'+item.expected;$('demo-banner').hidden=false;
    $('saved-state').textContent='临时演示 · 未保存';$('demo-dialog').close();
  } finally {demoLoading=false;setBusy(false);}
  if(FlowGraph.expanded(project).some(step=>step.operation==='script')&&!$('script-trust').checked){status('演示已载入：检查脚本并勾选“运行可信脚本”，然后运行流程');return;}
  if(item.loadOnly){status('演示已载入：打开事件触发，启动订阅后发送模拟测试消息');return;}
  await execute(false);
}
$('return-demo').onclick=safe(async()=>{
  if(running||demoLoading||!demoBackup)return;
  const saved=demoBackup;
  bindingResultFields.clear();project=clone(saved.project);flowEditReset();selected=saved.selected;$('project-name').value=project.name;
  if(saved.source)await loadImage(saved.source);
  else {source='';originalImage=null;ctx.clearRect(0,0,canvas.width,canvas.height);$('empty-image').hidden=false;$('image-size').textContent='未载入图像';}
  sourceCloud=saved.sourceCloud||null;sourceDepth=saved.sourceDepth||null;resultCloud=null;results=clone(saved.results);results.forEach(rememberFrame);renderPipeline();renderParams();renderResults();
  const shown=results.find(item=>item.id===saved.displayedResultId);if(shown)showResult(shown);
  setImageView(saved.view);setZoom(saved.zoom);$('saved-state').textContent=saved.saved;$('run-timing').textContent=saved.timing;
  if(saved.parametersOpen)openParameters();else closeParameters();
  demoBackup=null;$('demo-banner').hidden=true;status('已恢复进入演示前的工程和图像','success');
});
$('run-step').onclick=safe(()=>execute(true));$('run-all').onclick=safe(()=>execute(false));
$('stop').onclick=safe(async()=>{if(mqttTriggerState.busy)return mqttTriggerStop();if(continuousState.busy)return continuousStop();cancelled=true;if(runtimeJob)await api('runtime/jobs/'+runtimeJob+'/cancel',{method:'POST'});status('停止已请求；脚本和通信会中止，视觉算子结束后停止'+(project.steps.some(s=>['modbus_write','opcua_write','s7_write','mqtt_publish','tcp_exchange','udp_exchange','serial_exchange'].includes(s.operation))?'。已发出的设备写入不会回滚':''));});
$('save-project').onclick=safe(async()=>{const result=await api('project',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify(subflowProjectForSave())});$('saved-state').textContent='已保存 '+new Date(result.savedAt).toLocaleTimeString();status('工程已保存到服务器，可在局域网工作台中读取','success');});
$('load-project').onclick=safe(async()=>{const value=await api('project');if(!value)throw Error('尚无已保存的工程');useProject(value);$('saved-state').textContent='已读取';status('已读取服务器工程');});
$('export-project').onclick=safe(()=>download('machine-vision-project.json',JSON.stringify(currentProject(),null,2)));
$('import-project').onchange=safe(async event=>{const file=event.target.files[0];if(!file)return;if(file.size>35000000)throw Error('工程文件超过 35 MB');useProject(JSON.parse(await file.text()));dirty();event.target.value='';status('工程已导入');});
$('project-name').oninput=()=>{project.name=$('project-name').value.trim()||'我的视觉工程';dirty(false);};
function setMode(runtime) {if(runtime){closeParameters();document.body.classList.remove('flow-expanded');$('flow-expand').textContent='展开';$('flow-expand').setAttribute('aria-expanded','false');}document.body.classList.toggle('runtime',runtime);$('runtime').classList.toggle('active',runtime);$('develop').classList.toggle('active',!runtime);$('view-title').textContent=runtime?'视觉运行平台':'图像';hmiSyncMode();}
function closeParameters() {$('parameter-dialog').hidden=true;document.body.classList.remove('parameters-open','parameters-expanded');$('expand-parameters').textContent='展开编辑';$('expand-parameters').setAttribute('aria-expanded','false');$('configure-step').setAttribute('aria-expanded','false');}
function openParameters() {if(!selectedStep())return status('请先选择一个算子');if(document.body.classList.contains('flow-expanded')){$('flow-expand').click();}$('parameter-dialog').hidden=false;document.body.classList.add('parameters-open');$('configure-step').setAttribute('aria-expanded','true');}
$('configure-step').onclick=safe(openParameters);
$('expand-parameters').onclick=()=>{const expanded=document.body.classList.toggle('parameters-expanded');$('expand-parameters').textContent=expanded?'收起编辑':'展开编辑';$('expand-parameters').setAttribute('aria-expanded',String(expanded));};
$('close-parameters').onclick=safe(()=>{applyParams();closeParameters();});
$('parameter-dialog').addEventListener('keydown',safe(event=>{if(event.key==='Escape'){event.preventDefault();applyParams();closeParameters();$('configure-step').focus();}}));
$('toggle-results').onclick=()=>{const collapsed=document.body.classList.toggle('results-collapsed');$('toggle-results').textContent=collapsed?'⌃':'⌄';$('toggle-results').title=collapsed?'展开结果区':'收起结果区';$('toggle-results').setAttribute('aria-label',$('toggle-results').title);$('toggle-results').setAttribute('aria-expanded',String(!collapsed));};
$('develop').onclick=()=>setMode(false);$('runtime').onclick=()=>setMode(true);
$('operator-search').oninput=renderLibrary;
$('zoom-in').onclick=()=>setZoom(imageZoom+.25);
$('zoom-out').onclick=()=>setZoom(imageZoom-.25);
$('fit-image').onclick=()=>setZoom(1);
$('draw-mode').onchange=()=>{setImageView('input');status($('draw-mode').value==='template'?'请选中模板定位算子，然后在图像上框选模板':'在输入图像上拖动绘制矩形 ROI');};
$('help').onclick=()=>$('help-dialog').showModal();
document.querySelectorAll('.ribbon-group button,.ribbon-group a,.ribbon-button').forEach(control=>{if(!control.title)control.title=control.textContent.trim();});
document.querySelectorAll('button[data-view]').forEach(button=>button.onclick=()=>{setImageView(button.dataset.view);button.closest('.menu')?.removeAttribute('open');});
document.querySelectorAll('[data-command]').forEach(button=>button.onclick=()=>{$(button.dataset.command).click();button.closest('.menu').removeAttribute('open');});
document.querySelectorAll('[data-result-tab]').forEach(button=>button.onclick=()=>{
  document.querySelectorAll('[data-result-tab]').forEach(item=>item.classList.toggle('active',item===button));
  $('result-table-panel').hidden=button.dataset.resultTab!=='table';

  $('log-panel').hidden=button.dataset.resultTab!=='log';
});
document.querySelector('.ribbon-button').onkeydown=event=>{if(event.key==='Enter'||event.key===' '){event.preventDefault();$('source-file').click();}};
document.addEventListener('click',event=>document.querySelectorAll('.menu[open]').forEach(menu=>{if(!menu.contains(event.target))menu.open=false;}));
document.addEventListener('keydown',event=>{
  if(event.key==='Escape')document.querySelectorAll('.menu[open]').forEach(menu=>menu.open=false);
  if((event.ctrlKey||event.metaKey)&&event.key.toLowerCase()==='s'){event.preventDefault();if(!running)$('save-project').click();}
  if((event.ctrlKey||event.metaKey)&&event.key==='Enter'){event.preventDefault();if(!running)$('run-all').click();}
});
renderLibrary();renderPipeline();renderParams();
initOperatorPublication();
initDiagnosticsUI();
initOperationHistoryUI();
initAccountsUI();
initSessionManagementUI();
if(new URLSearchParams(location.search).get('mode')==='run')setMode(true);
initPluginUI().then(()=>api('project')).then(value=>{if(value&&!source&&!project.steps.length){useProject(value);$('saved-state').textContent='已载入保存的工程';}}).catch(error=>status(error.message,'error'));
api('models').then(value=>{$('models').textContent=value.models.length?value.models.join(' · '):'暂无权重文件；将 YOLO 检测模型放入 models 目录';$('engine-state').textContent='服务已连接';$('engine-dot').classList.add('ready');}).catch(error=>{renderDataMessage($('models'),error.message);$('engine-state').textContent='服务未连接';});

flowInit();flowWorkbenchInit();

$('output-image').onload=imageSizeStatus;
initRuntimeUI();initCloudUI();initIndustrialUI();initS7UI();initMqttUI();initSocketUI();initOpcuaUI();initCameraUI();initHmiUI();initContinuousUI();initMqttTriggerUI();initHistoryUI();initTrainingUI();initAnnotationUI();initComputeUI();initSubflowUI();initMonitorUI();

Object.assign(resultLabels,{triggered:'是否触发',firstValue:'首次采样值',predicate:'最后采样条件成立',samples:'采样次数',triggerMode:'触发方式',stableMs:'采样稳定时间 (ms)',pollIntervalMs:'采样间隔 (ms)',waitTimeoutMs:'等待超时 (ms)',waitElapsedMs:'实际等待耗时 (ms)',expectedValue:'比较值'});

Object.assign(resultLabels,{subflowId:'子流程编号',completedIterations:'完成轮次',stoppedEarly:'提前满足停止条件',iterations:'各轮输出',iteration:'轮次',trace:'内部执行明细',nodeId:'子模块编号',handled:'错误已处理',skipped:'已跳过',operation:'算子类型',variables:'局部变量',result:'结果'});

Object.assign(resultLabels,{error:'错误信息',elapsedMs:'耗时 (ms)',_iteration:'当前轮次',_iterations:'最大轮数',limit:'判定阈值'});

api('version').then(info=>{document.querySelector('footer .version').textContent='SIEANS Vision / '+info.version;}).catch(()=>{});
