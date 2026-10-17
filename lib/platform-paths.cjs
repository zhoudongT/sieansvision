'use strict';
const path=require('node:path');
const root=path.resolve(__dirname,'..');
function paths(env=process.env){
 const data=path.resolve(env.MACHINE_DATA_DIR||path.join(root,'data'));
 return {root,data,models:path.resolve(env.VISION_MODEL_DIR||path.join(root,'models')),yoloConfig:path.resolve(env.YOLO_CONFIG_DIR||path.join(data,'yolo-config'))};
}
module.exports={paths};
