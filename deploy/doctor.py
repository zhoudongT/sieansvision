"""Import and exact direct-dependency checks and optional CUDA availability. Output consumed by launcher."""
import importlib
import importlib.metadata
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
FILES={'2d':'vision/requirements.txt','3d':'vision/requirements-3d.txt','industrial':'industrial/requirements.txt','camera':'cameras/requirements.txt','yolo':'vision/requirements-yolo.txt','cuda':'vision/requirements-cuda.txt','depth':'cameras/requirements-depth.txt','orbbec':'cameras/requirements-orbbec.txt'}
MODULES={'numpy':'numpy','opencv-python':'cv2','zxing-cpp':'zxingcpp','rapidocr-onnxruntime':'rapidocr_onnxruntime','Pillow':'PIL','open3d':'open3d','scipy':'scipy','pymodbus':'pymodbus','pyserial':'serial','asyncua':'asyncua','python-snap7':'snap7','harvesters':'harvesters.core','genicam':'genicam','cv2-enumerate-cameras':'cv2_enumerate_cameras','ultralytics':'ultralytics','torch':'torch','torchvision':'torchvision','pyrealsense2':'pyrealsense2','pyorbbecsdk2':'pyorbbecsdk'}
required={}
def read(file):
    for line in file.read_text(encoding='utf-8').splitlines():
        line=line.strip()
        if not line or line.startswith('#'):continue
        if line.startswith('--extra-index-url '):continue
        if line.startswith('-r '):read(file.parent/line[3:]);continue
        name,version=line.split('==',1)
        if name in required and required[name]!=version:raise ValueError('Dependency version conflict: '+name)
        required[name]=version
for feature in sys.argv[1:]:read(ROOT/FILES[feature])
checks=[]
for name,expected in required.items():
    try:
        version=importlib.metadata.version(name)
        importlib.import_module(MODULES[name])
        checks.append(dict(name=name,ok=version==expected,detail=version if version==expected else f'{version}; expected {expected}'))
    except Exception as exc:checks.append(dict(name=name,ok=False,detail=str(exc)[:300]))
if 'cuda' in sys.argv[1:]:
    try:
        import torch
        available=torch.cuda.is_available()
        checks.append(dict(name='CUDA device',ok=available,detail=torch.cuda.get_device_name(0) if available else 'No available CUDA device/driver'))
    except Exception as exc:checks.append(dict(name='CUDA device',ok=False,detail=str(exc)[:300]))
print(json.dumps(checks,ensure_ascii=False))
