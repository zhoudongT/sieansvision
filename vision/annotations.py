"""Image and YOLO-label operations scoped to a managed training dataset."""
import base64
import hashlib
import json
import os
from pathlib import Path
import re
import uuid
from training import contained,parse_labels

def image_path(folder,split,name):
    if split not in ('train','val'):raise ValueError('请选择训练集或验证集')
    if not isinstance(name,str) or not 1<=len(name)<=160 or re.search(r'[<>:"/\\|?*\x00-\x1f]',name) or name.startswith('.') or name.endswith((' ','.')):raise ValueError('图片文件名无效')
    if Path(name).suffix.lower() not in ('.jpg','.jpeg','.png','.bmp'):raise ValueError('仅支持 JPG、PNG 或 BMP 图片')
    if re.fullmatch(r'(CON|PRN|AUX|NUL|COM[0-9]|LPT[0-9])',Path(name).stem,re.I):raise ValueError('图片名称不可使用系统保留字')
    image=contained(folder,Path(folder)/'images'/split/name)
    label=contained(folder,Path(folder)/'labels'/split/(Path(name).stem+'.txt'))
    return image,label

def read_image(path):
    import cv2
    if not path.is_file() or path.stat().st_size>12_000_000:raise ValueError('图片不存在或超过 12 MB')
    image=cv2.imread(str(path))
    if image is None or image.shape[0]*image.shape[1]>16_000_000:raise ValueError('图片无效或超过 1600 万像素')
    return image

def revision(image,label):
    return hashlib.sha256(image.read_bytes()+b'\0'+(label.read_bytes() if label.is_file() else b'\xffMISSING')).hexdigest()

def load(request):
    import cv2
    image,label=image_path(request['folder'],request['split'],request['name']);pixels=read_image(image)
    if label.is_file() and label.stat().st_size>1_000_000:raise ValueError('单张标注不能超过 1 MB')
    records=parse_labels(label.read_text(encoding='utf-8-sig'),request['task'],request['names']) if label.is_file() else []
    # Normalize preview encoding: a renamed image never becomes executable browser content.
    scale=min(1,1600/max(pixels.shape[:2]))
    preview=cv2.resize(pixels,(round(pixels.shape[1]*scale),round(pixels.shape[0]*scale))) if scale<1 else pixels
    ok,encoded=cv2.imencode('.png',preview)
    if not ok:raise ValueError('图片预览编码失败')
    return dict(name=image.name,split=request['split'],width=pixels.shape[1],height=pixels.shape[0],records=records,revision=revision(image,label),hasLabel=label.is_file(),image='data:image/png;base64,'+base64.b64encode(encoded).decode())

def save(request):
    image,label=image_path(request['folder'],request['split'],request['name']);read_image(image)
    if request.get('revision')!=revision(image,label):raise ValueError('图片或标注已被其他页面修改，请重新载入后编辑')
    records=request.get('records')
    if not isinstance(records,list) or len(records)>1000:raise ValueError('标注应为最多 1000 个目标')
    lines=[]
    for record in records:
        if not isinstance(record,dict) or isinstance(record.get('classId'),bool) or not isinstance(record.get('classId'),int):raise ValueError('目标类别编号无效')
        if request['task']=='detect':coords=record.get('box')
        else:
            points=record.get('points')
            if not isinstance(points,list) or any(not isinstance(p,list) or len(p)!=2 for p in points):raise ValueError('轮廓需要二维点坐标')
            coords=[v for p in points for v in p]
        if not isinstance(coords,list) or any(isinstance(v,bool) or not isinstance(v,(int,float)) for v in coords):raise ValueError('目标坐标必须为数值')
        lines.append(str(record['classId'])+' '+' '.join(format(v,'.12g') for v in coords))
    text='\n'.join(lines)+ ('\n' if lines else '')
    if len(text.encode())>1_000_000:raise ValueError('标注超过 1 MB，请减少轮廓点')
    parse_labels(text,request['task'],request['names'])
    label.parent.mkdir(parents=True,exist_ok=True)
    if label.exists():
        # Retain a recoverable copy before replacing annotations, including background edits.
        backup=contained(request['folder'],Path(request['folder'])/'annotation-history'/request['split']/label.stem/(uuid.uuid4().hex+'.txt'))
        backup.parent.mkdir(parents=True,exist_ok=True);backup.write_bytes(label.read_bytes())
    temporary=label.with_name(label.name+'.'+uuid.uuid4().hex+'.tmp')
    temporary.write_text(text,encoding='utf-8');os.replace(temporary,label)
    return dict(revision=revision(image,label),objects=len(records),hasLabel=True)

def upload(request):
    import cv2
    import numpy as np
    image,label=image_path(request['folder'],request['split'],request['name'])
    if image.exists() or label.exists() or any(p.stem.casefold()==image.stem.casefold() for p in image.parent.iterdir()):raise ValueError('同名图片或标注已存在，不会覆盖')
    raw=request.get('image')
    if not isinstance(raw,str) or len(raw)>17_000_000:raise ValueError('图片编码无效或过大')
    if ',' in raw:raw=raw.split(',',1)[1]
    try:content=base64.b64decode(raw,validate=True)
    except Exception as exc:raise ValueError('图片编码无效') from exc
    if len(content)>12_000_000:raise ValueError('图片不能超过 12 MB')
    pixels=cv2.imdecode(np.frombuffer(content,np.uint8),cv2.IMREAD_COLOR)
    if pixels is None or pixels.shape[0]*pixels.shape[1]>16_000_000:raise ValueError('图片无效或超过 1600 万像素')
    # Reject duplicates in either split at import time, before creating any file.
    digest=hashlib.sha256(content).digest()
    for split in ('train','val'):
        for candidate in (Path(request['folder'])/'images'/split).iterdir():
            contained(request['folder'],candidate)
            if candidate.is_file() and hashlib.sha256(candidate.read_bytes()).digest()==digest:raise ValueError('该图片已在数据集中，不能重复导入或跨划分使用')
    image.parent.mkdir(parents=True,exist_ok=True)
    with image.open('xb') as output:output.write(content)
    # Leave the label absent until the user explicitly saves an object or background annotation.
    return dict(name=image.name,width=pixels.shape[1],height=pixels.shape[0],hasLabel=False)


def history(request):
    image,label=image_path(request['folder'],request['split'],request['name']);read_image(image)
    current=revision(image,label)
    if current!=request.get('revision'):raise ValueError('图片或标注已被其他页面修改，请重新载入后编辑')
    directory=contained(request['folder'],Path(request['folder'])/'annotation-history'/request['split']/label.stem)
    if request['action']=='annotation_history_load':
        identifier=request.get('historyId')
        if not isinstance(identifier,str) or not re.fullmatch(r'[0-9a-f]{32}',identifier):raise ValueError('历史版本编号无效')
        file=contained(directory,directory/(identifier+'.txt'))
        if not file.is_file() or file.stat().st_size>1_000_000:raise ValueError('历史版本不存在或超过大小限制')
        records=parse_labels(file.read_text(encoding='utf-8-sig'),request['task'],request['names'])
        if revision(image,label)!=current:raise ValueError('图片或标注已被其他页面修改，请重新载入后编辑')
        return dict(records=records,revision=current,createdAt=round(file.stat().st_mtime*1000))
    files=[]
    if directory.exists():
        for file in directory.iterdir():
            if re.fullmatch(r'[0-9a-f]{32}\.txt',file.name):
                file=contained(directory,file)
                if file.is_file():files.append(file)
    files.sort(key=lambda p:(p.stat().st_mtime_ns,p.name),reverse=True)
    entries=[]
    for file in files[:200]:
        try:
            if file.stat().st_size>1_000_000:raise ValueError('历史标注超过 1 MB')
            records=parse_labels(file.read_text(encoding='utf-8-sig'),request['task'],request['names'])
            entries.append(dict(id=file.stem,createdAt=round(file.stat().st_mtime*1000),objects=len(records),valid=True))
        except (ValueError,UnicodeError) as error:
            entries.append(dict(id=file.stem,createdAt=round(file.stat().st_mtime*1000),valid=False,error=str(error)))
    return dict(entries=entries,limitReached=len(files)>200,revision=current)

def handle(request):
    action=request['action']
    if action in ('annotation_history','annotation_history_load'):return history(request)
    if action=='annotation_load':return load(request)
    if action=='annotation_save':return save(request)
    if action=='annotation_upload':return upload(request)
    if action=='annotation_list':
        items=[]
        for split in ('train','val'):
            for image in sorted((Path(request['folder'])/'images'/split).iterdir()):
                if image.suffix.lower() not in ('.jpg','.jpeg','.png','.bmp'):continue
                _,label=image_path(request['folder'],split,image.name)
                items.append(dict(name=image.name,split=split,hasLabel=label.is_file()))
        return dict(items=items)
    raise ValueError('未知标注操作')
