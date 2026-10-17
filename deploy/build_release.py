"""Build an auditable source release; dependencies, user data and model weights are excluded."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import zipfile
import uuid

ROOT=Path(__file__).resolve().parents[1]
DIRECTORIES=('lib','vision','cameras','industrial','plugins','operator-plugins','public','examples','scripts','deploy','docs','third_party','tests')
ROOT_FILES=('server.cjs','package.json','package-lock.json','README.md','models/README.md')
EXCLUDE={'node_modules','__pycache__','.venv','data','artifacts','.git'}
SUFFIXES={'.cjs','.js','.py','.json','.html','.css','.md','.txt','.rst','.svg','.png','.jpg','.jpeg','.webp','.ico','.woff','.woff2','.ply','.pcd','.xyz','.xyzn','.xyzrgb','.pts','.sh','.ps1'}

def files(root):
    found=[]
    for name in ROOT_FILES:
        p=root/name
        if not p.is_file() or p.is_symlink():raise ValueError('Missing or linked release file: '+name)
        found.append(p)
    for name in DIRECTORIES:
        folder=root/name
        if not folder.is_dir() or folder.is_symlink():raise ValueError('Missing or linked release folder: '+name)
        for current,dirs,names in os.walk(folder,followlinks=False):
            for child in dirs:
                if (Path(current)/child).is_symlink():raise ValueError('Symlink in release tree: '+str(Path(current)/child))
            dirs[:]=sorted(d for d in dirs if d not in EXCLUDE and not d.startswith('.'))
            for child in sorted(names):
                p=Path(current)/child
                if p.is_symlink():raise ValueError('Symlink in release tree: '+str(p))
                if child.startswith('.') or (p.suffix.lower() not in SUFFIXES and child not in ('LICENSE','NOTICE')):continue
                found.append(p)
    return sorted(found,key=lambda p:p.relative_to(root).as_posix())

def build(root,output):
    root=root.resolve();output=output.resolve()
    version=json.loads((root/'package.json').read_text(encoding='utf-8'))['version']
    if not re.fullmatch(r'\d+\.\d+\.\d+(?:-[A-Za-z0-9.-]+)?',version):raise ValueError('Invalid release version')
    selected=files(root)
    entries=[];contents={}
    for file in selected:
        data=file.read_bytes();name=file.relative_to(root).as_posix()
        if len(data)>50*1024*1024:raise ValueError('Oversized release file: '+name)
        contents[name]=data;entries.append(dict(path=name,bytes=len(data),sha256=hashlib.sha256(data).hexdigest()))
    manifest=dict(format=1,product='SIEANS Vision',version=version,kind='source-online-install',node='24.x',python='3.12.x',files=entries)
    contents['release-manifest.json']=(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n').encode('utf-8')
    output.parent.mkdir(parents=True,exist_ok=True)
    temporary=output.with_name(output.name+'.tmp-'+uuid.uuid4().hex)
    try:
        with zipfile.ZipFile(temporary,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
            for name,data in sorted(contents.items()):
                info=zipfile.ZipInfo('SIEANS-Vision-'+version+'/'+name,date_time=(1980,1,1,0,0,0))
                info.create_system=3;info.compress_type=zipfile.ZIP_DEFLATED
                info.external_attr=(stat.S_IFREG|(0o755 if name.endswith('.sh') else 0o644))<<16
                archive.writestr(info,data)
        # Link publishes the finished archive atomically without overwriting a
        # different release, including when concurrent builders race.
        try:
            os.link(temporary,output)
        except FileExistsError:
            if hashlib.sha256(temporary.read_bytes()).digest()!=hashlib.sha256(output.read_bytes()).digest():
                raise FileExistsError('Refusing to overwrite a different release: '+str(output))
    finally:
        if temporary.exists():temporary.unlink()
    digest=hashlib.sha256(output.read_bytes()).hexdigest()
    checksum=output.with_name(output.name+'.sha256');text=digest+'  '+output.name+'\n'
    try:
        with checksum.open('x',encoding='ascii',newline='\n') as sidecar:sidecar.write(text)
    except FileExistsError:
        if checksum.read_text(encoding='ascii')!=text:raise FileExistsError('Refusing to overwrite a different checksum: '+str(checksum))
    return dict(path=str(output),sha256=digest,files=len(entries),bytes=output.stat().st_size)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root',type=Path,default=ROOT);parser.add_argument('--output',type=Path)
    args=parser.parse_args();version=json.loads((args.root/'package.json').read_text(encoding='utf-8'))['version']
    output=args.output or args.root/'artifacts/releases'/('SIEANS-Vision-'+version+'-source.zip')
    print(json.dumps(build(args.root,output),ensure_ascii=False))
