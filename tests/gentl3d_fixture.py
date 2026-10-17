"""Export decoded synthetic GenTL multipart data to the cross-language runtime test."""
import sys
import base64
import json
import cv2
from test_gentl3d import fixture,integer_fixture,params,g

components,calibration=(integer_fixture if '--integer' in sys.argv else fixture)(True)
image,info,depth,cloud=g.capture(components,params(confidenceComponent=2,intensityComponent=0,alignedComponents=True),calibration)
ok,png=cv2.imencode('.png',image)
assert ok
print(json.dumps(dict(image='data:image/png;base64,'+base64.b64encode(png).decode(),cloud=cloud,depth=depth),allow_nan=False))
