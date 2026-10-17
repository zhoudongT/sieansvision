const {test,after}=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),os=require('node:os');
const {Runtime}=require('../lib/runtime.cjs'),camera=require('../lib/camera-client.cjs'),vision=require('../lib/vision-client.cjs'),{depth}=require('../lib/frame.cjs');
const params={driver:'rgbd_simulator',deviceId:'synthetic-rgbd',pointStride:1,minDepth:.1,maxDepth:2};
const runtime=()=>new Runtime(fs.mkdtempSync(path.join(os.tmpdir(),'sieans-depth-')),vision);
const node=(id,operation,params)=>({id,operation,params});
async function run(r,steps,extra={}){const job=r.start({project:{version:1,name:'RGB-D',steps},...extra});await r.jobs.get(job.id).promise;return r.poll(job.id);}
after(()=>{camera.stop();vision.stop();});
test('RGB-D capture validates depth, scale and point-cloud metadata',async()=>{
 const out=await camera.run({operation:'camera_capture',params});assert.equal(out.cloud.points.length,3071);assert.equal(out.depth.width,64);assert.equal(out.depth.scaleMeters,.001);assert.equal(out.result.simulated,true);assert.equal(depth(out.depth).format,'png16');
 for(const value of [{...out.depth,width:65},{...out.depth,scaleMeters:0},{...out.depth,image:out.annotatedImage}])assert.throws(()=>depth(value));
});
test('captured point cloud flows into real Open3D crop and dimensional measurement',async()=>{
 const job=await run(runtime(),[node('cam','camera_capture',params),node('crop','cloud_filter',{method:'crop',minimum:[-1000,-1000,970],maximum:[1000,1000,980]}),node('measure','cloud_measure',{}),node('save','variables',{scope:'flow',name:'topWidth',value:{$ref:'results.measure.sizeX'}})]);
 assert.equal(job.state,'completed',job.error);assert.equal(job.results[1].output.cloud.points.length,200);assert(Math.abs(job.variables.flow.topWidth-185.25)<1e-6);assert.equal(job.results[2].output.result.sizeZ,0);
});
test('Python receives exact raw depth and calibration; 2D recapture clears old depth and cloud',async()=>{
 const code='def run(ctx):\n    import base64, cv2, numpy as np\n    d=ctx["depth"]\n    raw=cv2.imdecode(np.frombuffer(base64.b64decode(d["image"].split(",")[1]), dtype=np.uint8), cv2.IMREAD_UNCHANGED)\n    return dict(result=dict(raw=int(raw[20,25]), millimeters=float(raw[20,25])*d["scaleMeters"]*1000))';
 const job=await run(runtime(),[node('cam','camera_capture',params),node('script','script',{code,timeoutMs:5000}),node('flat','camera_capture',{driver:'simulator'}),node('check','script',{code:'def run(ctx):\n    return dict(result=dict(cleared=ctx["depth"] is None and ctx["cloud"] is None))',timeoutMs:5000})],{allowScripts:true});
 assert.equal(job.state,'completed',job.error);assert.equal(job.results[1].output.result.raw,975);assert.equal(job.results[1].output.result.millimeters,975);assert.equal(job.results[3].output.result.cleared,true);
});
test('depth branch routing retains camera identity at a join',async()=>{
 const graph=require('../public/vision/flow-graph.js');
 const r=runtime(),p=graph.normalize({version:2,name:'two sources',steps:[node('depth','camera_capture',params),node('flat','camera_capture',{driver:'simulator'}),node('measure','cloud_measure',{})],edges:[{id:'a',from:'source',to:'depth'},{id:'b',from:'source',to:'flat'},{id:'c',from:'depth',to:'measure'},{id:'d',from:'flat',to:'measure'}]});p.steps[2].imageFrom='depth';
 const start=r.start({project:p});await r.jobs.get(start.id).promise;const job=r.poll(start.id);assert.equal(job.state,'completed',job.error);assert.equal(job.results[2].output.cloud.points.length,3071);
});
test('conditional merge selects active depth or flat frame without retaining the other capture',async()=>{
 const graph=require('../public/vision/flow-graph.js');
 const p=graph.normalize({version:2,name:'RGB-D conditional routing',steps:[node('choice','condition',{left:false,right:true}),node('flat','camera_capture',{driver:'simulator'}),node('depth','camera_capture',params),node('merge','branch_merge',{}),node('inspect','script',{code:'def run(ctx):\n    return dict(result=dict(hasDepth=ctx["depth"] is not None,hasCloud=ctx["cloud"] is not None))',timeoutMs:5000})],edges:[{id:'s',from:'source',to:'choice'},{id:'yes',from:'choice',to:'flat',when:'true'},{id:'no',from:'choice',to:'depth',when:'false'},{id:'f',from:'flat',to:'merge'},{id:'d',from:'depth',to:'merge'},{id:'i',from:'merge',to:'inspect'}]});
 const r=runtime();for(const [choice,expected] of [[false,true],[true,false]]){
   p.steps[0].params.left=choice;const start=r.start({project:p,allowScripts:true});await r.jobs.get(start.id).promise;const job=r.poll(start.id);assert.equal(job.state,'completed',job.error);assert.equal(job.results.at(-1).output.result.hasDepth,expected);assert.equal(job.results.at(-1).output.result.hasCloud,expected);
 }
});
