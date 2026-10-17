'use strict';
const test=require('node:test'),assert=require('node:assert/strict');
const {logParts,structuredParts,joinParts}=require('../public/vision/data-presentation.js');
const {fieldValue}=require('../public/vision/data-presentation.js');
const {messageSummary}=require('../public/vision/data-presentation.js');
test('nearest cloud sample distances are labeled without changing signed surface deviations',()=>{
 const {recordFieldLabel}=require('../public/vision/data-presentation.js');
 for(const direction of ['输入→参考','参考→输入']){
  assert.equal(recordFieldLabel([{direction,distance:2}],'distance','有符号偏差'),'最近点距离');
  assert.equal(recordFieldLabel([{direction,distance:2}],'direction','direction'),'比较方向');
 }
 assert.equal(recordFieldLabel([{distance:-.3}],'distance','有符号偏差'),'有符号偏差');
 assert.equal(recordFieldLabel([],'distance','距离'),'距离');
 assert.equal(recordFieldLabel([{direction:'自定义'}],'distance','距离'),'距离');
 assert.equal(recordFieldLabel([{direction:'输入→参考'}],'x','X'),'X');
});
test('demo ID remapping changes only explicit result references and leaves source data untouched',()=>{
 const {remapResultReferences}=require('../public/vision/data-presentation.js');
 const input={rows:[{x:{$ref:'results.edge.line.start.0'},y:{$ref:'flow.x'}}],text:'results.edge.line',code:'results.edge',unknown:{$ref:'results.other.x'}};
 const copy=remapResultReferences(input,{edge:'newEdge'});
 assert.equal(copy.rows[0].x.$ref,'results.newEdge.line.start.0');assert.equal(copy.rows[0].y.$ref,'flow.x');assert.equal(copy.unknown.$ref,'results.other.x');assert.equal(copy.text,input.text);assert.equal(copy.code,input.code);assert.equal(input.rows[0].x.$ref,'results.edge.line.start.0');
});
test('demo preflight distinguishes missing, disabled, wrong version and missing operators',()=>{
 const {pluginRequirementError}=require('../public/vision/data-presentation.js');
 const steps=[{operation:'plugin',params:{pluginId:'test',pluginVersion:'1.0.0',operatorId:'inspect'}}],plugin={id:'test',name:'测试插件',enabled:true,version:'1.0.0',operators:[{id:'inspect'}]};
 assert.match(pluginRequirementError(steps,[]),/尚未加载/);
 assert.match(pluginRequirementError(steps,[{...plugin,enabled:false}]),/停用/);
 assert.match(pluginRequirementError(steps,[{...plugin,version:'2.0.0'}]),/版本不匹配/);
 assert.match(pluginRequirementError(steps,[{...plugin,operators:[]}]),/缺少/);
 assert.equal(pluginRequirementError(steps,[plugin]),'');
 assert.equal(pluginRequirementError([{operation:'variables'}],[]),'');
});

test('compact status preserves error context while structured details stay in the log table',()=>{
 assert.equal(messageSummary('读取失败：{"device":"camera-1","code":0}，请检查连接'),'读取失败：〔结构化数据，详见运行日志〕，请检查连接');
 assert.equal(messageSummary('[INFO] ready'),'[INFO] ready');
 assert.equal(messageSummary(null),'');
});
test('output previews distinguish missing fields from false, zero, null and nested records',()=>{
 const result={count:0,passed:false,empty:null,items:[{x:12}],text:'{"count":3}'};
 for(const key of ['count','passed','empty','items','text'])assert.deepEqual(fieldValue(result,key),{found:true,value:result[key]});
 assert.deepEqual(fieldValue(result,'items.0.x'),{found:true,value:12});
 for(const key of ['', 'missing','items.2.x','items.0.x.value','constructor','__proto__.polluted','passed.value'])assert.deepEqual(fieldValue(result,key),{found:false});
 assert.deepEqual(fieldValue(undefined,'count'),{found:false});
});
test('script logs split labels, multiline records and trailing text without exposing serialized data',()=>{
 const parts=logParts('检测开始\n[INFO] result = {\n "passed":true,\n "items":[{"x":12,"y":24}]\n}\n检测结束');
 assert.deepEqual(parts,[{kind:'text',value:'检测开始\n[INFO] result ='},{kind:'data',value:{passed:true,items:[{x:12,y:24}]}},{kind:'text',value:'检测结束'}]);
});
test('quoted brackets, escaped quotes, backslashes and consecutive records retain values',()=>{
 const records=[{text:'a } [ "quoted" \\ path',nested:{empty:[]}},[1,false,null,'中文']];
 assert.deepEqual(logParts(records.map(JSON.stringify).join('\n')).map(x=>x.value),records);
});
test('ordinary logs, empty input and invalid structures remain readable without executing anything',()=>{
 assert.deepEqual(logParts(''),[]);
 for(const value of ['INFO ready','[INFO] ready','{bad: true}','{"x":1','[1} bad','<script>alert(1)</script>'])assert.deepEqual(logParts(value),[{kind:'text',value}]);
});
test('empty objects and arrays remain data, reserved field names do not mutate objects',()=>{
 const parts=logParts('{} [] {"__proto__":{"polluted":true}}');
 assert.equal(parts.length,3);assert.ok(parts.every(x=>x.kind==='data'));assert.equal({}.polluted,undefined);
 assert.ok(Object.hasOwn(parts[2].value,'__proto__'));
});
test('field editing preserves text type, surrounding whitespace and untouched records',()=>{
 const value='  result = { "count": 3, "passed": true }\r\nnext: [ 1, 2 ]\r\n';
 const parts=structuredParts(value);assert.equal(joinParts(parts),value);
 const record=parts.find(p=>p.kind==='data');record.value.count=7;delete record.raw;
 assert.equal(joinParts(parts),'  result = {"count":7,"passed":true}\r\nnext: [ 1, 2 ]\r\n');
 assert.equal(typeof joinParts(parts),'string');
});
test('structured presentation recognizes prefixed records but preserves ordinary and invalid text',()=>{
 for(const value of ['plain text','[INFO] ready','{bad: true}',null,42,{x:1},'x'.repeat(1000001)])assert.equal(structuredParts(value),null);
 const value='[INFO] result={"nested":"{\\"value\\":2}","label":"中文"} done';
 assert.equal(joinParts(structuredParts(value)),value);
 assert.deepEqual(structuredParts(value).filter(p=>p.kind==='data').map(p=>p.value),[{nested:'{"value":2}',label:'中文'}]);
});
