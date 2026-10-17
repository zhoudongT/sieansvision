// Generate the Node-RED form from the same field definitions used by the workbench.
'use strict';
const fs=require('node:fs'),vm=require('node:vm');
const context=vm.createContext({});vm.runInContext(fs.readFileSync('public/vision/socket-ui.js','utf8')+'\n'+fs.readFileSync('public/vision/serial-ui.js','utf8'),context);
const definitions=vm.runInContext('({socketCatalog,socketLabels,serialCatalog,serialLabels})',context);
const source=fs.readFileSync('plugins/node-red-contrib-machine/nodes/mqtt.html','utf8');
const valueEditor=source.slice(source.indexOf(' const types='),source.indexOf(" for(const operation of ['mqtt_publish'"));
const template=`<script type="text/javascript">+(function(){
 const catalog=CATALOG,labels={...LABELS,simulator:'本机回显设备',text:'UTF-8 文本',structured:'结构化数据',bytes:'字节数组'};
 EDITOR
 for(const [operation,definition] of Object.entries(catalog)){
  const type='machine-'+operation,name=definition.name;
  const html='<div class="form-row"><label for="node-input-name">名称</label><input id="node-input-name"></div><input type="hidden" id="node-input-params"><div id="socket-fields"></div><div class="form-row" id="socket-value-source"><label>发送内容来源</label><select id="node-input-valueSource" aria-label="发送内容来源"><option value="message">输入消息内容</option><option value="constant">表单常量</option></select></div><div id="socket-value"></div><p>'+definition.hint+'</p><p>输出报文在 msg.payload.value，完整通信结果在 msg.industrial。动态参数通过 msg.industrialParams 提供。此节点使用普通 TCP/UDP，不启用 TLS。</p>';
  $('<script>',{type:'text/html','data-template-name':type}).html(html).appendTo('body');
  $('<script>',{type:'text/html','data-help-name':type}).text(definition.description+' '+definition.hint).appendTo('body');
  RED.nodes.registerType(type,{category:'工业通信',color:'#86c6d9',paletteLabel:name,inputs:1,outputs:1,icon:'font-awesome/fa-exchange',label:function(){return this.name||name;},defaults:{name:{value:''},valueSource:{value:'message'},params:{value:JSON.stringify(definition.defaults),validate:function(v){try{const p={...definition.defaults,...JSON.parse(v)};return !!p&&['exchange','send','receive'].includes(p.mode)&&Number.isInteger(p.timeoutMs)&&p.timeoutMs>=100&&p.timeoutMs<=60000&&Number.isInteger(p.maxBytes)&&p.maxBytes>0&&p.maxBytes<=65536&&(p.connection==='simulator'?p.mode!=='receive':typeof p.host==='string'&&p.host.length>0&&Number.isInteger(p.port)&&p.port>=1&&p.port<=65535);}catch{return false;}}}},
   oneditprepare:function(){
    const p={...definition.defaults,...JSON.parse(this.params||'{}')};this._socket=p;
    for(const [key,label,kind,max,step] of definition.fields){const input=Array.isArray(kind)?$('<select>'):$('<input>').attr('type',kind==='text'?'text':'number');input.attr({id:'socket-'+key,'aria-label':label}).css('width','65%');if(Array.isArray(kind))for(const v of kind)input.append($('<option>').val(v).text(labels[v]||v));input.val(p[key]??'');if(typeof kind==='number')input.attr({min:kind,max,step:step||1,required:true});$('#socket-fields').append($('<div>').addClass('form-row').attr('data-key',key).append($('<label>').text(label).css('width','32%'),input));}
    $('#socket-value').append(editor(structuredClone(p.value),v=>p.value=v,'发送内容'));
    const visibility=()=>{const remote=$('#socket-connection').val()==='device',mode=$('#socket-mode').val(),fixed=$('#socket-rxFraming').val()==='fixed';$('#socket-fields [data-key]').each(function(){const key=$(this).attr('data-key');$(this).toggle(!((!remote&&['host','port','localAddress','localPort'].includes(key))||(mode==='receive'&&key==='txFraming')||(mode==='send'&&['maxBytes','rxFraming','responseBytes'].includes(key))||(key==='responseBytes'&&!fixed)));});$('#socket-value-source').toggle(mode!=='receive');$('#socket-value').toggle(mode!=='receive'&&$('#node-input-valueSource').val()==='constant');};
    $('#socket-fields select,#node-input-valueSource').on('change',visibility);visibility();
   },
   oneditsave:function(){const p=this._socket;for(const [key,,kind] of definition.fields){const input=$('#socket-'+key);p[key]=typeof kind==='number'?(input.val()===''?null:Number(input.val())):input.val();}this.params=JSON.stringify(p);$('#node-input-params').val(this.params);delete this._socket;},oneditcancel:function(){delete this._socket;}
  });
 }
})();</script>
`;
for(const name of ['socket','serial']){
 let sourceTemplate=template;
 if(name==='serial')sourceTemplate=sourceTemplate.replaceAll('socket','serial').replace('本机回显设备','软件回环模拟').replace('此节点使用普通 TCP/UDP，不启用 TLS。','串口由服务器打开，回环模拟不访问真实设备。')
  .replace('p.timeoutMs<=60000','p.timeoutMs<=10000').replace("typeof p.host==='string'&&p.host.length>0&&Number.isInteger(p.port)&&p.port>=1&&p.port<=65535","typeof p.serialPort==='string'&&p.serialPort.length>0")
  .replace("kind==='text'?'text':'number'","kind==='boolean'?'checkbox':kind==='text'?'text':'number'")
  .replace("input.val(p[key]??'');","if(kind==='boolean')input.prop('checked',p[key]);else input.val(p[key]??'');")
  .replace("['host','port','localAddress','localPort']","['serialPort','baudrate','dataBits','parity','stopbits','flowControl','rts','dtr']")
  .replace("mode==='receive'&&key==='txFraming'","mode==='receive'&&['txFraming','encoding','clearInput'].includes(key)")
  .replace("['maxBytes','rxFraming','responseBytes']","['maxBytes','responseEncoding','rxFraming','responseBytes']")
  .replace("this._serial=p;","if(!Object.hasOwn(JSON.parse(this.params||'{}'),'responseEncoding'))p.responseEncoding=p.encoding;this._serial=p;")
  .replace("(key==='responseBytes'&&!fixed)","(key==='responseBytes'&&!fixed)||(key==='rts'&&$('#serial-flowControl').val()==='rtscts')||(key==='dtr'&&$('#serial-flowControl').val()==='dsrdtr')")
  .replace("p[key]=typeof kind==='number'?","p[key]=kind==='boolean'?input.prop('checked'):typeof kind==='number'?");
 const labels=name==='serial'?{...definitions.socketLabels,...definitions.serialLabels,device:'实际串口设备',N:'无校验',E:'偶校验',O:'奇校验'}:definitions.socketLabels;
 const html=sourceTemplate.replace('CATALOG',JSON.stringify(definitions[name+'Catalog'])).replace('LABELS',JSON.stringify(labels)).replace('EDITOR',valueEditor);
 new vm.Script(html.match(/<script type="text\/javascript">([\s\S]*?)<\/script>/)[1]);
 const destination='plugins/node-red-contrib-machine/nodes/'+name+'.html';
 if(process.argv.includes('--check')){if(fs.readFileSync(destination,'utf8')!==html)throw Error(name+' editor needs regeneration: node scripts/build-socket-editor.cjs');}
 else fs.writeFileSync(destination,html);
}
