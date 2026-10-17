"""Local, bounded YOLO training worker. Structured events are internal protocol only."""
import base64
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import sys
import threading
import time

PREFIX = 'SIEANS_TRAIN:'

def watch_parent():
    # A blocking Windows CRT stdin read can prevent unrelated file imports.
    if os.name == 'nt':
        import ctypes
        import msvcrt
        from ctypes import wintypes
        kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        peek=kernel.PeekNamedPipe
        peek.argtypes=[wintypes.HANDLE,wintypes.LPVOID,wintypes.DWORD,wintypes.LPVOID,wintypes.LPVOID,wintypes.LPVOID]
        peek.restype=wintypes.BOOL
        handle=msvcrt.get_osfhandle(sys.stdin.fileno())
        while True:
            if not peek(handle,None,0,None,None,None):os._exit(72)
            time.sleep(1)
    else:
        import select
        while True:
            ready,_,_=select.select([sys.stdin.fileno()],[],[],1)
            if ready and not os.read(sys.stdin.fileno(),1):os._exit(72)

def emit(kind, **values):
    print(PREFIX + json.dumps(dict(kind=kind, **values), ensure_ascii=True, allow_nan=False), flush=True)

def contained(root, path):
    root, path = Path(root).resolve(), Path(path).resolve()
    if not path.is_relative_to(root):
        raise ValueError('文件不能离开数据集目录')
    return path

def parse_labels(text,task,names):
    lines=[line.split() for line in text.splitlines() if line.strip()]
    if len(lines)>1000:raise ValueError('单张图最多 1000 个标注')
    records=[]
    for fields in lines:
        values=list(map(float,fields));category=values[0];coords=values[1:]
        if not all(math.isfinite(v) for v in values) or not category.is_integer() or not 0<=category<len(names):raise ValueError('标注类别或数值无效')
        if any(not 0<=v<=1 for v in coords):raise ValueError('标注坐标必须归一化到 0–1')
        if task=='detect':
            if len(coords)!=4:raise ValueError('检测标注需要中心 X/Y、宽、高')
            x,y,w,h=coords
            if w<=0 or h<=0 or min(x-w/2,y-h/2)<-1e-6 or max(x+w/2,y+h/2)>1+1e-6:raise ValueError('检测框为空或越界')
            records.append(dict(classId=int(category),box=coords))
        elif task=='segment':
            if len(coords)<6 or len(coords)%2:raise ValueError('分割标注至少需要 3 个坐标点')
            if len(coords)>1000:raise ValueError('单个轮廓最多 500 个点')
            points=list(zip(coords[::2],coords[1::2]))
            if len(points)>3 and points[0]==points[-1]:points.pop()
            cross=lambda a,b,c:(b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
            def on(a,b,p):return abs(cross(a,b,p))<1e-12 and min(a[0],b[0])-1e-12<=p[0]<=max(a[0],b[0])+1e-12 and min(a[1],b[1])-1e-12<=p[1]<=max(a[1],b[1])+1e-12
            for i,a in enumerate(points):
                b=points[(i+1)%len(points)]
                if a==b:raise ValueError('分割轮廓存在重复顶点')
                for j in range(i+1,len(points)):
                    if j==i+1 or (i==0 and j==len(points)-1):continue
                    c,d=points[j],points[(j+1)%len(points)]
                    if (cross(a,b,c)*cross(a,b,d)<0 and cross(c,d,a)*cross(c,d,b)<0) or on(a,b,c) or on(a,b,d) or on(c,d,a) or on(c,d,b):raise ValueError('分割轮廓不能自相交或相切')
            area=abs(sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(points,points[1:]+points[:1])))/2
            if area<1e-8:raise ValueError('分割多边形面积为零')
            records.append(dict(classId=int(category),points=[list(p) for p in points]))
        else:raise ValueError('未知标注任务')
    return records

def inspect_dataset(folder, task, names):
    import cv2
    if task not in ('detect', 'segment') or not isinstance(names, list) or not 1 <= len(names) <= 100:
        raise ValueError('需要检测或分割任务及 1–100 个类别')
    if any(not isinstance(n, str) or not n.strip() or len(n) > 80 for n in names) or len(set(names)) != len(names):
        raise ValueError('类别名称不能为空、重复或超过 80 字符')
    folder = Path(folder).resolve()
    counts, files, seen, per_class = {}, [], {}, [0] * len(names)
    for split in ('train', 'val'):
        image_dir = contained(folder, folder / 'images' / split)
        if not image_dir.is_dir(): raise ValueError(f'缺少 images/{split} 目录')
        images = sorted(p for p in image_dir.iterdir() if p.suffix.lower() in ('.jpg', '.jpeg', '.png', '.bmp'))
        if not images or len(images) > 20000: raise ValueError(f'{split} 图片数需要为 1–20000')
        positives, objects, stems = 0, 0, set()
        for image in images:
            contained(folder, image)
            if image.stem in stems: raise ValueError('同一划分不能有同名不同扩展图片')
            stems.add(image.stem)
            if image.stat().st_size > 12_000_000: raise ValueError('单张图片不能超过 12 MB')
            array = cv2.imread(str(image))
            if array is None or array.shape[0] * array.shape[1] > 16_000_000: raise ValueError('图片无效或超过 1600 万像素：' + image.name)
            digest = hashlib.sha256(image.read_bytes()).hexdigest()
            if digest in seen: raise ValueError('图片内容重复，不能在训练/验证中重复使用：' + image.name)
            seen[digest] = split
            label = contained(folder, folder / 'labels' / split / (image.stem + '.txt'))
            if not label.is_file(): raise ValueError('缺少标注：' + str(label.relative_to(folder)))
            if label.stat().st_size > 1_000_000: raise ValueError('单张标注不能超过 1 MB')
            records=parse_labels(label.read_text(encoding='utf-8-sig'),task,names)
            for record in records:per_class[record['classId']]+=1
            positives += bool(records); objects += len(records)
            files.append((image, label, split, digest))
        if not positives: raise ValueError(split + ' 至少需要一张含目标的标注图')
        counts[split] = dict(images=len(images), positiveImages=positives, objects=objects)
    return dict(splits=counts, classes=[dict(id=i,name=n,objects=per_class[i]) for i,n in enumerate(names)], fingerprint=hashlib.sha256(''.join(d+hashlib.sha256(l.read_bytes()).hexdigest() for _,l,_,d in files).encode()).hexdigest()), files

def demo(folder, task):
    import cv2
    import numpy as np
    folder = Path(folder)
    if folder.exists(): raise ValueError('示例数据集目录已存在，请选新名称')
    for split, count, seed in [('train',12,37),('val',4,91)]:
        (folder/'images'/split).mkdir(parents=True)
        (folder/'labels'/split).mkdir(parents=True)
        rng = np.random.default_rng(seed)
        for i in range(count):
            img = rng.integers(12,36,(128,128,3),dtype=np.uint8)
            x,y = (int(v) for v in rng.integers(12,56,2)); w,h = (int(v) for v in rng.integers(30,60,2))
            img[y:y+h,x:x+w] = (60,180,220)
            cv2.imwrite(str(folder/'images'/split/f'part-{i}.png'),img)
            coords = [(x+w/2)/128,(y+h/2)/128,w/128,h/128] if task=='detect' else [x/128,y/128,(x+w)/128,y/128,(x+w)/128,(y+h)/128,x/128,(y+h)/128]
            (folder/'labels'/split/f'part-{i}.txt').write_text('0 '+' '.join(str(v) for v in coords)+'\n',encoding='utf-8')

def train(request):
    import torch
    from ultralytics import YOLO, settings
    from ultralytics.utils import YAML
    from compute_device import select_device
    selection=select_device(request['config'].get('device','cpu'))
    emit('device',**selection)
    settings.update({key:False for key in ('sync','wandb','mlflow','clearml','comet','dvc','neptune','tensorboard','hub') if key in settings})
    torch.set_num_threads(2)
    info, files = inspect_dataset(request['folder'], request['task'], request['names'])
    job = Path(request['jobFolder']); snapshot = job/'dataset'
    for image,label,split,_ in files:
        for source,kind in [(image,'images'),(label,'labels')]:
            target = snapshot/kind/split/source.name; target.parent.mkdir(parents=True,exist_ok=True); shutil.copyfile(source,target)
    # Recheck the immutable snapshot, including image/label hashes, before training.
    snapshot_info,_ = inspect_dataset(snapshot,request['task'],request['names'])
    if snapshot_info['fingerprint'] != info['fingerprint']: raise ValueError('复制期间数据集发生变化，请重试')
    yaml = job/'dataset.yaml'; YAML.save(yaml,dict(path=str(snapshot.resolve()),train='images/train',val='images/val',names=request['names']))
    model = YOLO(request['modelPath'])
    if model.task != request['task']: raise ValueError('基础模型的任务类型与数据集不一致')
    emit('dataset',summary=info)
    def epoch(trainer):
        if trainer.epoch >= request['config']['epochs']:return
        values = {str(k):float(v) for k,v in (trainer.metrics or {}).items() if isinstance(v,(float,int)) and math.isfinite(float(v))}
        if trainer.tloss is not None:
            for k,v in trainer.label_loss_items(trainer.tloss,prefix='train').items():
                if math.isfinite(v): values[k]=float(v)
        emit('epoch',epoch=trainer.epoch+1,metrics=values)
    model.add_callback('on_fit_epoch_end',epoch)
    config=request['config']
    emit('phase',message='训练与验证')
    model.train(data=str(yaml),epochs=config['epochs'],imgsz=config['imageSize'],batch=config['batch'],lr0=config['learningRate'],seed=config['seed'],
                device=selection['device'],workers=0,optimizer='AdamW',amp=False,cache=False,plots=False,save=True,save_period=-1,
                project=str(job),name='run',exist_ok=False,verbose=False,patience=0,mosaic=0,close_mosaic=0,fliplr=0,
                val=True,deterministic=True)
    best = contained(job,job/'run/weights/best.pt')
    if not best.is_file(): raise ValueError('训练未生成 best.pt')
    emit('complete',checkpoint=str(best),sha256=hashlib.sha256(best.read_bytes()).hexdigest())

def main():
    request=json.loads(sys.stdin.readline())
    emit('phase',message='准备数据集')
    # Parent keeps stdin open; an unexpected parent exit also terminates training.
    threading.Thread(target=watch_parent,daemon=True).start()
    emit('phase',message='检查训练环境')
    if request['action']=='demo':
        demo(request['folder'],request['task']); emit('complete')
    elif request['action']=='check':
        info,_=inspect_dataset(request['folder'],request['task'],request['names']);emit('complete',summary=info)
    elif request['action']=='train':train(request)
    elif request['action']=='annotation_suggest':
        from annotation_suggestions import suggest
        emit('complete',**suggest(request))
    elif request['action'].startswith('annotation_'):
        from annotations import handle
        emit('complete',**handle(request))
    else: raise ValueError('未知训练操作')

if __name__=='__main__':
    try: main()
    except Exception as exc:
        emit('error',message=str(exc));sys.exit(1)
