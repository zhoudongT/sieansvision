const fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const file=path.join(__dirname,'../plugins/node-red-contrib-machine/nodes/vision.html');
const code=fs.readFileSync(file,'utf8').match(/<script type="text\/javascript">([\s\S]*?)<\/script>/)[1];
new vm.Script(code,{filename:file});
