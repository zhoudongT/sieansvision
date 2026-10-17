const {test}=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs'),path=require('node:path');
test('session editor exposes identity/policy/timeout and hides physical device/trigger controls',()=>{
 const context=vm.createContext({});vm.runInContext(fs.readFileSync(path.join(__dirname,'../public/vision/camera-ui.js'),'utf8'),context);
 context.step={operation:'camera_capture',params:{driver:'session'}};
 for(const key of ['driver','sessionId','framePolicy','timeoutMs'])assert.equal(vm.runInContext(`cameraFieldVisible(step,${JSON.stringify(key)})`,context),true);
 for(const key of ['deviceId','providerId','trigger','exposureTime','width','pointStride','maxAgeMs'])assert.equal(vm.runInContext(`cameraFieldVisible(step,${JSON.stringify(key)})`,context),false);
 context.step.params.framePolicy='latest';assert.equal(vm.runInContext('cameraFieldVisible(step,"maxAgeMs")',context),true);
 assert.equal(vm.runInContext('cameraDefault(step,"maxAgeMs")',context),1000);
 context.step.params.driver='uvc';assert.equal(vm.runInContext('cameraFieldVisible(step,"sessionId")',context),false);
});
