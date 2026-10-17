const fs=require('node:fs'),vm=require('node:vm');
const html=fs.readFileSync('plugins/node-red-contrib-machine/nodes/mqtt.html','utf8');
for(const script of html.matchAll(/<script type="text\/javascript">([\s\S]*?)<\/script>/g))new vm.Script(script[1],{filename:'mqtt.html'});
