'use strict';
const {spawnSync}=require('node:child_process'),path=require('node:path');
const root=path.resolve(__dirname,'..'),python=process.env.VISION_PYTHON||path.join(root,'.venv',process.platform==='win32'?'Scripts/python.exe':'bin/python');
for(const [cmd,args] of [[python,['tests/test_gentl3d.py']],[python,['tests/test_cameras.py']],[process.execPath,['--test','tests/test_gentl3d_runtime.cjs','tests/test_camera_runtime.cjs']]]){
 const out=spawnSync(cmd,args,{cwd:root,stdio:'inherit',windowsHide:true});if(out.error)throw out.error;if(out.status!==0)process.exit(out.status||1);
}
