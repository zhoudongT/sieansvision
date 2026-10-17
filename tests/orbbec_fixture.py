"""Native SDK software frame packet for cross-language tests; not camera capture."""
import os
import json
import base64
import sys
protocol=os.fdopen(os.dup(sys.stdout.fileno()),'w',encoding='utf-8')
os.dup2(sys.stderr.fileno(),sys.stdout.fileno())
from test_orbbec import software_frames,adapter,ob,cv2
frames,_=software_frames()
image,stats,depth,cloud=adapter.process_frames(frames,dict(deviceId='software-test',pointStride=1),ob)
encoded=cv2.imencode('.png',image)[1]
json.dump(dict(image='data:image/png;base64,'+base64.b64encode(encoded).decode('ascii'),depth=depth,cloud=cloud,result=stats),protocol,allow_nan=False)
protocol.close()
