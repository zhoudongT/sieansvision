const fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const file=path.join(__dirname,'../plugins/node-red-contrib-machine/nodes/industrial.html');
new vm.Script(fs.readFileSync(file,'utf8').replace(/^<script[^>]*>/,'').replace(/<\/script>\s*$/,''),{filename:file});
