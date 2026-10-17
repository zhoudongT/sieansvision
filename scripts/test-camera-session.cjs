const {spawnSync}=require('node:child_process'),path=require('node:path');
const root=path.resolve(__dirname,'..'),python=process.env.VISION_PYTHON||path.join(root,'.venv',process.platform==='win32'?'Scripts/python.exe':'bin/python');
for(const [program,args] of [[python,['tests/test_camera_stream.py']],[process.execPath,['--test','tests/test_camera_session.cjs','tests/test_camera_session_ui.cjs']],[process.execPath,['tests/test_camera_session_http.cjs']]]){
 const result=spawnSync(program,args,{cwd:root,windowsHide:true,stdio:'inherit'});if(result.error)throw result.error;if(result.status!==0)process.exit(result.status||1);
}
