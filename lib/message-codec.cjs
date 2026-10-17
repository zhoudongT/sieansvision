'use strict';
const MAX_PAYLOAD=65536;
function requireThat(ok,message){if(!ok)throw Error(message);}
function validateData(value,depth=0){
 requireThat(depth<=20,'消息数据嵌套最多 20 层');
 if(value===null||typeof value==='boolean')return;
 if(typeof value==='number'){requireThat(Number.isFinite(value)&&(!Number.isInteger(value)||Number.isSafeInteger(value)),'消息数值必须有限，大整数请用文本表示');return;}
 if(typeof value==='string'){requireThat(value.isWellFormed()&&Buffer.byteLength(value)<=MAX_PAYLOAD,'消息文本无效或超过 64 KiB');return;}
 requireThat(value&&typeof value==='object'&&(Array.isArray(value)||Object.getPrototypeOf(value)===Object.prototype),'消息仅支持数值、文本、开关、数组和结构体');
 requireThat(Object.keys(value).length<=10000,'消息字段或元素超过 10000 项');
 for(const [key,item] of Object.entries(value)){requireThat(!['__proto__','prototype','constructor'].includes(key),'消息字段包含保留名称');validateData(item,depth+1);}
}
function encode(value,encoding){
 let payload;if(encoding==='bytes'){requireThat(Array.isArray(value)&&value.length<=MAX_PAYLOAD&&value.every(n=>Number.isInteger(n)&&n>=0&&n<=255),'字节消息须为 0–255 的数值数组，最多 64 KiB');payload=Buffer.from(value);}
 else if(encoding==='text'){requireThat(typeof value==='string'&&value.isWellFormed(),'文本消息必须是有效文本');payload=Buffer.from(value,'utf8');}
 else {validateData(value);payload=Buffer.from(JSON.stringify(value),'utf8');}
 requireThat(payload.length<=MAX_PAYLOAD,'消息体超过 64 KiB');return payload;
}
function decode(payload,encoding){
 requireThat(payload.length<=MAX_PAYLOAD,'收到的消息体超过 64 KiB');if(encoding==='bytes')return Array.from(payload);
 let value;try{value=new TextDecoder('utf-8',{fatal:true,ignoreBOM:true}).decode(payload);}catch{throw Error('消息不是有效 UTF-8 文本，请选择字节数组');}
 if(encoding==='text')return value;
 try{value=JSON.parse(value);}catch{throw Error('消息不是有效的结构化数据，请检查发送格式或选择文本');}
 validateData(value);return value;
}
module.exports={encode,decode};
