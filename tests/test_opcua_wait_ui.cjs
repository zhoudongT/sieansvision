'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
test('OPC UA wait form exposes subscription controls and omits inactive comparison/auth fields',()=>{
 const ctx=vm.createContext({});vm.runInContext(fs.readFileSync(path.join(__dirname,'../public/vision/opcua-ui.js'),'utf8'),ctx);ctx.step={operation:'opcua_wait',params:{connection:'simulator',comparison:'is_true'}};
 assert.equal(vm.runInContext("opcuaFieldVisible(step,'expectedValue')",ctx),false);assert.equal(vm.runInContext("opcuaFieldVisible(step,'endpoint')",ctx),false);assert.equal(vm.runInContext("opcuaFieldVisible(step,'publishingIntervalMs')",ctx),true);assert.equal(vm.runInContext("opcuaParamDefault(step,'triggerMode')",ctx),'level');
 ctx.step.params.comparison={$ref:'flow.condition'};assert.equal(vm.runInContext("opcuaFieldVisible(step,'expectedValue')",ctx),true);
 ctx.step.params.connection='server';ctx.step.params.security='Basic256Sha256';assert.equal(vm.runInContext("opcuaFieldVisible(step,'clientCertificate')",ctx),true);assert.equal(vm.runInContext("opcuaFieldVisible(step,'passwordEnv')",ctx),false);
 const fields=vm.runInContext('opcuaCatalog.opcua_wait.fields',ctx);assert(fields.some(f=>f[0]==='waitTimeoutMs'));assert(fields.some(f=>f[0]==='publishingIntervalMs'));assert(!fields.some(f=>f[0]==='requireGood'));
});
