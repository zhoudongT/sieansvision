const { spawnSync } = require('node:child_process');
const path = require('node:path');
const root = path.resolve(__dirname, '..');
const python = process.env.VISION_PYTHON || path.join(root, '.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python');
const commands = [[process.execPath,['--test','tests/test_deployment.cjs','tests/test_deployment_accounts.cjs','tests/test_process_supervisor.cjs','tests/test_serial.cjs','tests/test_socket.cjs','tests/test_sphere.cjs','tests/test_cylinder.cjs','tests/test_caliper.cjs','tests/test_relations.cjs','tests/test_deviation.cjs','tests/test_image_quality.cjs','tests/test_intrinsics.cjs','tests/test_rigid.cjs','tests/test_handeye.cjs','tests/test_records.cjs','tests/test_camera_session.cjs','tests/test_camera_session_ui.cjs','tests/test_data_presentation.cjs','tests/test_flow_graph.cjs','tests/test_runtime.cjs','tests/test_flow_control.cjs','tests/test_error_routes.cjs','tests/test_subflows.cjs','tests/test_operator_plugins.cjs','tests/test_operator_bridge.cjs','tests/test_hmi.cjs','tests/test_hmi_pages.cjs','tests/test_runtime_monitor.cjs','tests/test_continuous.cjs','tests/test_run_history.cjs','tests/test_mqtt.cjs','tests/test_mqtt_trigger.cjs']],[python,['tests/test_vision.py']], [python,['tests/test_inspection_operators.py']], [python,['tests/test_planar.py']], [process.execPath,['tests/test_integration.cjs']]];
commands.splice(commands.length-1,0,[python,['tests/test_normals.py']]);
commands.push([python,['tests/test_caliper.py']]);
commands.push([python,['tests/test_deviation.py']]);
commands.push([python,['tests/test_intrinsics.py']]);
commands.push([python,['tests/test_rigid.py']]);
commands.push([python,['tests/test_handeye.py']]);
commands.push([python,['tests/test_records.py']]);
commands.push([process.execPath,['scripts/test-circle.cjs']]);
commands.push([process.execPath,['scripts/test-shape.cjs']]);
commands.push([process.execPath,['scripts/test-depth-import.cjs']]);
commands.push([process.execPath,['scripts/test-box.cjs']]);
commands.push([process.execPath,['scripts/test-opcua-wait.cjs']]);
commands.push([process.execPath,['--test','tests/test_runtime_diagnostics.cjs','tests/test_operation_history.cjs','tests/test_user_store.cjs','tests/test_accounts_operations_ui.cjs']]);
commands.push([process.execPath,['scripts/test-fixture.cjs']]);
commands.push([process.execPath,['scripts/test-heightfield.cjs']]);
commands.push([process.execPath,['scripts/test-operator-access.cjs']]);
commands.push([process.execPath,['--test','tests/test_web_sessions.cjs','tests/test_session_ui.cjs']]);
commands.push([process.execPath,['tests/test_web_sessions_http.cjs']]);
commands.push([process.execPath,['tests/test_web_sessions_http.cjs','--geometry']]);
commands.push([process.execPath,['tests/test_web_sessions_http.cjs','--inspection-chain']]);
commands.push([process.execPath,['--test','tests/test_cloud_widget.cjs']]);
commands.push([process.execPath,['scripts/test-backup.cjs']]);
commands.push([process.execPath,['tests/test_records_http.cjs']]);
commands.push([process.execPath,['tests/test_handeye_http.cjs']]);
commands.push([process.execPath,['tests/test_rigid_http.cjs']]);
commands.push([python,['tests/test_camera_stream.py']]);
commands.push([process.execPath,['tests/test_camera_session_http.cjs']]);
commands.push([process.execPath,['tests/test_intrinsics_http.cjs']]);
commands.push([python,['tests/test_sphere.py']]);
commands.push([python,['tests/test_cylinder.py']]);
commands.push([python,['tests/test_serial.py']]);
commands.push([process.execPath,['tests/test_error_routes_http.cjs']]);
commands.push([process.execPath,['tests/test_subflows_http.cjs']]);
commands.push([process.execPath,['tests/test_monitor_http.cjs']]);
commands.push([process.execPath,['tests/test_hmi_pages_http.cjs']]);
commands.push([process.execPath,['tests/test_history_http.cjs']]);
commands.push([process.execPath,['tests/test_mqtt_http.cjs']]);
commands.push([process.execPath,['tests/test_mqtt_trigger_http.cjs']]);
commands.push([process.execPath,['tests/test_socket_http.cjs']]);
commands.push([process.execPath,['tests/test_serial_http.cjs']]);
commands.push([python,['tests/test_release.py']]);
commands.push([process.execPath,['tests/test_deployment_http.cjs']]);
if(process.argv.includes('--yolo'))commands.push([python,['tests/test_yolo.py']]);
async function freeTestPort(){
 const net=require('node:net'),listener=net.createServer();
 await new Promise((resolve,reject)=>{listener.once('error',reject);listener.listen(0,'127.0.0.1',resolve);});
 const port=listener.address().port;await new Promise((resolve,reject)=>listener.close(error=>error?reject(error):resolve()));return port;
}
async function main(){
 for(const [program,args] of commands){
  const port=await freeTestPort();
  const result=spawnSync(program,args,{cwd:root,stdio:'inherit',windowsHide:true,env:{...process.env,SIEANS_TEST_HTTP_PORT:String(port)}});
  if(result.error)throw result.error;if(result.status!==0){process.exitCode=result.status||1;return;}
 }
}
main().catch(error=>{console.error(error.message);process.exitCode=1;});
