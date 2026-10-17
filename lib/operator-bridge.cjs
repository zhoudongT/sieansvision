'use strict';
const {frame,cloud,depth}=require('./frame.cjs');
const {object}=require('./variable-store.cjs');
function variables(value={}){
  const source=object(value,'算子消息变量'),result={global:{},flow:{},module:{}};
  for(const [scope,values] of Object.entries(source)){
    if(!Object.hasOwn(result,scope))throw Error('未知算子消息变量范围：'+scope);
    result[scope]=object(values,'算子消息变量 '+scope);
  }
  return result;
}
function createOperatorBridge(plugins){
  return {
    list:()=>plugins.list(),
    async run(request,{signal}={}){
      const input=frame(request),vars=variables(request.variables);
      const response=await plugins.run(request,{...input,vars,results:{}},{signal});
      const data=response.data,next={...vars};
      if(data.variables!==undefined){
        object(data.variables,'插件消息变量');
        for(const [scope,values] of Object.entries(data.variables)){
          if(!Object.hasOwn(next,scope))throw Error('未知插件消息变量范围：'+scope);
          next[scope]=object(values,'插件消息变量 '+scope);
        }
      }
      const image=data.image===undefined?input.image:data.image;
      if(typeof image!=='string'||image.length>17_000_000)throw Error('插件输出图像无效');
      const annotatedImage=data.annotatedImage===undefined?image:data.annotatedImage;
      if(typeof annotatedImage!=='string'||annotatedImage.length>17_000_000)throw Error('插件显示图像无效');
      return {result:data.result||{},image,annotatedImage,
        cloud:data.cloud===undefined?input.cloud:data.cloud===null?null:cloud(data.cloud),
        depth:data.depth===undefined?input.depth:data.depth===null?null:depth(data.depth),
        variables:next,elapsedMs:response.elapsedMs,logs:response.logs};
    }
  };
}
module.exports={createOperatorBridge};
