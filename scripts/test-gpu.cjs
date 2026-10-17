'use strict';
const {spawnSync}=require('node:child_process'),path=require('node:path'),fs=require('node:fs');
const root=path.resolve(__dirname,'..'),python=process.env.VISION_GPU_PYTHON||path.join(root,'.venv-gpu',process.platform==='win32'?'Scripts/python.exe':'bin/python');
if(!fs.existsSync(python))throw Error('请先配置可信 CUDA Python 环境，通过 VISION_GPU_PYTHON 指定解释器');
for(const [command,args] of [[python,['tests/test_compute_device.py']],[python,['tests/test_gpu.py']],[process.execPath,['tests/test_segmentation_http.cjs']],[process.execPath,['tests/test_training_http.cjs']],[process.execPath,['tests/test_annotation_assist_http.cjs']]]){
 const result=spawnSync(command,args,{cwd:root,stdio:'inherit',windowsHide:true,env:{...process.env,VISION_PYTHON:python,TEST_COMPUTE_DEVICE:'cuda:0',TEST_TRAIN_DEVICE:'cuda:0',CUBLAS_WORKSPACE_CONFIG:':4096:8'}});if(result.error)throw result.error;if(result.status!==0)process.exit(result.status||1);
}
