'use strict';
const {spawnSync}=require('node:child_process'),path=require('node:path');
const root=path.resolve(__dirname,'..');
const python=process.env.VISION_PYTHON||path.join(root,'.venv',process.platform==='win32'?'Scripts/python.exe':'bin/python');
for(const [command,args] of [[python,['tests/test_yolo_segmentation.py']],[process.execPath,['--test','tests/test_segmentation_runtime.cjs']],[process.execPath,['tests/test_segmentation_http.cjs']]]){
 const result=spawnSync(command,args,{cwd:root,stdio:'inherit',windowsHide:true});
 if(result.error)throw result.error;if(result.status!==0)process.exit(result.status||1);
}
