const {spawnSync}=require('node:child_process');
const path=require('node:path');
const root=path.resolve(__dirname,'..');
const python=process.env.VISION_PYTHON||path.join(root,'.venv',process.platform==='win32'?'Scripts/python.exe':'bin/python');
for(const [command,args]of [[python,['tests/test_modbus.py']],[python,['tests/test_modbus_wait.py']],[process.execPath,['--test','tests/test_industrial_runtime.cjs','tests/test_modbus_wait_runtime.cjs']],[process.execPath,['tests/test_integration.cjs']]]){
 const result=spawnSync(command,args,{cwd:root,stdio:'inherit',windowsHide:true,env:{...process.env,TEST_INDUSTRIAL:'true'}});
 if(result.error)throw result.error;if(result.status!==0)process.exit(result.status||1);
}
