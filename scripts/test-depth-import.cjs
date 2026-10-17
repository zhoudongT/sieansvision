'use strict';
const {spawnSync}=require('node:child_process'),path=require('node:path');
const root=path.resolve(__dirname,'..'),python=process.env.VISION_PYTHON||path.join(root,'.venv',process.platform==='win32'?'Scripts/python.exe':'bin/python');
for(const [program,args] of [[python,['-X','utf8','tests/test_depth_import.py']],[process.execPath,['--test','tests/test_depth_import.cjs','tests/test_depth_import_ui.cjs']],[process.execPath,['tests/test_depth_import_http.cjs']]]){const r=spawnSync(program,args,{cwd:root,windowsHide:true,stdio:'inherit'});if(r.error)throw r.error;if(r.status!==0)process.exit(r.status||1);}
