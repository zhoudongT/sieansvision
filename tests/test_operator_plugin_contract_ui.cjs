'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
class Element{
 constructor(tag,text){this.tagName=tag;this.textContent=text??'';this.children=[];this.style={};this.attributes={};this.handlers={};this.value='';this.dataset={};}
 append(...nodes){for(const n of nodes){n.parent=this;this.children.push(n);}}
 replaceChildren(...nodes){this.children=[];this.append(...nodes);}
 replaceWith(next){const index=this.parent.children.indexOf(this);next.parent=this.parent;this.parent.children[index]=next;}
 setAttribute(name,value){this.attributes[name]=String(value);}
 addEventListener(name,fn){this.handlers[name]=fn;}
 checkValidity(){return !this.required||this.value!=='';}
 focus(){this.focused=true;}
}
function fixture(){
 const holder=new Element('main'),nodes=new Map([['structured-params',holder]]);
 const formEl=(tag,text)=>new Element(tag,text),formSelect=(options,value,label)=>{const e=formEl('select');e.setAttribute('aria-label',label);e.value=value;for(const [key,text] of options){const o=formEl('option',text);o.value=key;e.append(o);}return e;};
 const point={key:'point',label:'参考点',type:'object',required:true,properties:[{key:'x',label:'X',type:'number',required:true,unit:'mm'},{key:'y',label:'Y',type:'number',default:0}]};
 const op={id:'typed',name:'几何测试',description:'具名输入验收',input:'image',inputs:[point],parameters:[{key:'enabled',label:'启用判定',type:'boolean',required:true},{key:'gain',label:'增益',type:'number',default:2,group:'计算',unit:'倍',description:'增益说明'},{key:'values',label:'采样',type:'array',minimumRows:1,maximumRows:2,items:{type:'integer'},default:[1]}],outputs:[point]};
 const step={id:'typed-step',operation:'plugin',params:{pluginId:'test',pluginVersion:'1.0.0',operatorId:'typed',inputs:{point:{x:1,y:2}},arguments:{enabled:false,values:[1]},outputBindings:[]}};
 let changes=0;const context=vm.createContext({formEl,formSelect,$:id=>nodes.get(id),formTypes:{number:'数值',string:'文本',boolean:'开关',object:'结构体',array:'数组'},formType:v=>v===null?'null':Array.isArray(v)?'array':typeof v==='object'&&v&&Object.keys(v).length===1&&typeof v.$ref==='string'?'reference':typeof v,structuredClone,DataPresentation:{structuredParts:()=>null},referenceEditor:(v,change,label)=>{const e=formEl('input');e.value=v.$ref;e.setAttribute('aria-label',label+' 绑定');e.oninput=()=>change({$ref:e.value});return e;},renderOutputBindings:(s,h)=>{h.replaceChildren(formEl('p',String(s.params.outputBindings.length)+' 条绑定'));},dirty:()=>changes++,renderPipeline(){},renderParams(){vm.runInContext('renderPluginParams(step)',context);},valueEditor:()=>formEl('div','通用字段'),step,plugins:[{id:'test',name:'测试插件',version:'1.0.0',enabled:true,operators:[op]}]});
 vm.runInContext(fs.readFileSync(path.join(__dirname,'../public/vision/plugin-ui.js'),'utf8'),context);vm.runInContext('installedPlugins=plugins;renderPluginParams(step)',context);
 const all=(root,p)=>[...(p(root)?[root]:[]),...root.children.flatMap(c=>all(c,p))],find=p=>all(holder,p)[0],byLabel=label=>find(e=>e.attributes['aria-label']===label);
 return {holder,context,step,op,find,all,byLabel,changes:()=>changes};
}
test('plugin editor separates input/parameter/output tabs and retains tab through rerenders',()=>{
 const f=fixture(),tabs=f.all(f.holder,e=>e.attributes.role==='tab'),panels=f.all(f.holder,e=>e.attributes.role==='tabpanel');
 assert.deepEqual(tabs.map(t=>t.textContent),['输入','参数','输出']);assert.equal(panels[1].hidden,false);assert.equal(panels[0].hidden,true);
 tabs[0].onclick();assert.equal(panels[0].hidden,false);vm.runInContext('renderPluginParams(step)',f.context);assert.equal(f.find(e=>e.id==='plugin-panel-0').hidden,false);
 f.find(e=>e.id==='plugin-tab-0').onkeydown({key:'End',preventDefault(){}});assert.equal(f.find(e=>e.id==='plugin-panel-2').hidden,false);assert.equal(f.find(e=>e.id==='plugin-tab-2').focused,true);
 f.find(e=>e.id==='plugin-panel-1').handlers.invalid();assert.equal(f.find(e=>e.id==='plugin-panel-1').hidden,false);
 assert.equal(f.all(f.holder,e=>e.tagName==='textarea').length,0);assert(f.find(e=>e.textContent==='增益说明'));assert(f.find(e=>e.textContent==='计算'));
});
test('nested input fixed values and references persist to params.inputs without changing arguments',()=>{
 const f=fixture(),x=f.byLabel('参考点 · X');x.value='7';x.oninput();assert.equal(f.step.params.inputs.point.x,7);assert.equal(f.step.params.arguments.enabled,false);
 f.byLabel('参考点 · X 绑定变量或结果').onclick();const input=f.byLabel('参考点 · X 绑定');input.value='results.source.point.x';input.oninput();assert.equal(f.step.params.inputs.point.x.$ref,'results.source.point.x');
 f.byLabel('参考点 · X 使用固定值').onclick();assert.equal(f.step.params.inputs.point.x,0);assert(f.changes()>0);
});
test('typed array controls enforce row limits and keep integer inputs, while nested output binding names remain unique',()=>{
 const f=fixture(),item=f.byLabel('采样 第 1 项');assert.equal(item.type,'number');assert.equal(item.step,'1');item.value='5';item.oninput();assert.deepEqual(f.step.params.arguments.values,[5]);
 let remove=f.all(f.holder,e=>e.textContent==='删除')[0];assert.equal(remove.disabled,true);f.find(e=>e.textContent==='添加一项').onclick();assert.deepEqual(f.step.params.arguments.values,[5,0]);assert.equal(f.find(e=>e.textContent==='添加一项').disabled,true);
 f.byLabel('绑定输出 point.x').onclick();f.byLabel('绑定输出 point.x').onclick();assert.deepEqual(JSON.parse(JSON.stringify(f.step.params.outputBindings)),[{field:'point.x',scope:'flow',name:'x'},{field:'point.x',scope:'flow',name:'x_1'}]);
});
test('required boolean without a default stays unselected instead of silently displaying false',()=>{
 const f=fixture();delete f.step.params.arguments.enabled;vm.runInContext('renderPluginParams(step)',f.context);const input=f.byLabel('启用判定');assert.equal(input.value,'');assert.equal(input.required,true);input.value='0';input.onchange();assert.equal(f.step.params.arguments.enabled,true);
});
test('legacy manifests receive empty named inputs and keep parameter defaults',()=>{
 const f=fixture();delete f.op.inputs;vm.runInContext('defaults=pluginDefaults("test/typed")',f.context);const defaults=f.context.defaults;assert.deepEqual(JSON.parse(JSON.stringify(defaults.inputs)),{});assert.equal(defaults.arguments.gain,2);vm.runInContext('renderPluginParams(step)',f.context);assert(f.find(e=>e.textContent==='此算子未声明额外命名输入。'));
});
