'use strict';
// Extract only repository-owned declarative metadata; never run browser UI code.
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),acorn=require('acorn');
const root=path.resolve(__dirname,'..'),context=vm.createContext({});
const files=['cloud','industrial','s7','mqtt','socket','serial','opcua','camera'];
function declarations(file,target){
  const source=fs.readFileSync(path.join(root,'public/vision',file),'utf8');
  const ast=acorn.parse(source,{ecmaVersion:'latest'});
  for(const node of ast.body){
    if(node.type!=='VariableDeclaration')continue;
    for(const d of node.declarations){
      if(d.id.type!=='Identifier'||!d.init)continue;
      if(d.id.name===target||/(Fields|Defaults|Types)$/.test(d.id.name)){
        vm.runInContext('var '+source.slice(d.start,d.end)+';',context,{timeout:500});
        if(d.id.name===target)return;
      }
    }
  }
  throw Error('Missing metadata '+target);
}
for(const file of files)declarations(file+'-ui.js',file==='industrial'?'industrialCatalog':file+'Catalog');
declarations('app.js','catalog');
const catalog=vm.runInContext('catalog',context,{timeout:500});
const output=path.join(root,'desktop/builtin-catalog.json');
fs.writeFileSync(output,JSON.stringify(catalog,null,2)+'\n');
console.log('Exported '+Object.keys(catalog).length+' native operator definitions');
