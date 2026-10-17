const {spawnSync}=require('node:child_process'),path=require('node:path');
const root=path.resolve(__dirname,'..');
const python=process.env.VISION_PYTHON||path.join(root,'.venv',process.platform==='win32'?'Scripts/python.exe':'bin/python');
for(const [command,args]of [[python,['-X','utf8','tests/test_opcua.py']],[process.execPath,['--test','tests/test_opcua_runtime.cjs']],[process.execPath,['tests/test_integration.cjs']]]){
 const result=spawnSync(command,args,{cwd:root,stdio:'inherit',windowsHide:true,env:{...process.env,TEST_OPCUA:'true'}});if(result.error)throw result.error;if(result.status!==0)process.exit(result.status||1);
}
