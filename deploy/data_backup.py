"""Portable runtime-data ZIP snapshots. Called by the locked Node maintenance CLI."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import sys
import time
import unicodedata
import uuid
import zipfile

MAX_FILES=100000
MAX_BYTES=20*1024**3
MAX_FILE=5*1024**3
MAX_MANIFEST=64*1024**2
MANIFEST='sieans-backup.json'
MARKER='.sieans-restore-incomplete'
LOCK='.sieans-runtime.lock'
ROOT=Path(__file__).resolve().parents[1]
last_progress=0


def progress(phase,files,bytes_count,total):
    global last_progress
    if time.monotonic()-last_progress>=2:
        last_progress=time.monotonic();print(json.dumps(dict(event='progress',phase=phase,files=files,bytes=bytes_count,totalBytes=total)),flush=True)


def inside(parent,child):return child==parent or parent in child.parents


def no_links(path,exists=True):
    path=Path(os.path.abspath(path))
    for part in [*reversed(path.parents),path]:
        if part.is_symlink() or getattr(part,'is_junction',lambda:False)():raise ValueError('不允许符号链接或目录联接：'+str(part))
    if exists and not path.exists():raise ValueError('路径不存在：'+str(path))
    return path


def portable(value):
    if not isinstance(value,str) or not value or len(value)>240 or '\\' in value or value.startswith('/'):
        raise ValueError('备份内文件路径无效')
    for component in value.split('/'):
        if not component or component in ('.','..') or component[-1:] in (' ','.') or any(ord(c)<32 or c in '<>:"|?*' for c in component):raise ValueError('文件路径不适合跨平台恢复：'+value)
        base=component.split('.')[0].upper()
        if base in {'CON','PRN','AUX','NUL'} or base in {'COM'+str(i) for i in range(1,10)} or base in {'LPT'+str(i) for i in range(1,10)}:raise ValueError('文件路径包含保留名称：'+value)
    return value


def folded(value):return unicodedata.normalize('NFC',value).casefold()


def validate_paths(entries):
    seen={}
    for name,kind in entries:
        parts=name.split('/')
        for i in range(1,len(parts)+1):
            prefix='/'.join(parts[:i]);entry=(prefix,kind if i==len(parts) else 'directory');identity=folded(prefix)
            if identity in seen and seen[identity]!=entry:raise ValueError('备份存在文件/目录、大小写或 Unicode 路径冲突')
            seen[identity]=entry


def excluded(relative):
    first=folded(relative.split('/')[0])
    return first in ('cache','logs',MARKER) or first.startswith(LOCK)


def signature(st):
    # Python 3.12 on Windows can report different creation-time values through
    # stat and fstat immediately after close; ctime is not a change clock there.
    return st.st_dev,st.st_ino,st.st_size,st.st_mtime_ns,st.st_ctime_ns if os.name!='nt' else 0


def inventory(root,prefix):
    root=no_links(root)
    if not root.is_dir():raise ValueError('备份来源必须为目录')
    files=[];dirs=[]
    for folder,children,names in os.walk(root,followlinks=False):
        parent=Path(folder)
        kept=[]
        for child in sorted(children):
            p=parent/child;relative=p.relative_to(root).as_posix()
            if prefix=='data' and excluded(relative):continue
            no_links(p);name=portable(prefix+'/'+relative);dirs.append(name);kept.append(child)
            if len(files)+len(dirs)>MAX_FILES:raise ValueError('备份文件/目录数超过上限')
        children[:]=kept
        for child in sorted(names):
            p=parent/child;relative=p.relative_to(root).as_posix()
            if prefix=='data' and excluded(relative):continue
            no_links(p);st=p.stat()
            if not stat.S_ISREG(st.st_mode):raise ValueError('备份来源包含非普通文件：'+str(p))
            if st.st_size>MAX_FILE:raise ValueError('单个备份文件超过 5 GiB：'+relative)
            files.append((portable(prefix+'/'+relative),p,signature(st),st.st_mode))
            if len(files)+len(dirs)>MAX_FILES:raise ValueError('备份文件/目录数超过上限')
    return files,dirs


def digest_file(file):
    digest=hashlib.sha256()
    with open(file,'rb') as source:
        for chunk in iter(lambda:source.read(1024*1024),b''):digest.update(chunk)
    return digest.hexdigest()


def backup(request):
    data=no_links(request['data']);output=no_links(request['output'],False)
    if not data.is_dir() or inside(ROOT,data) or inside(data,ROOT):raise ValueError('运行数据须在程序目录之外')
    no_links(output.parent,False);output.parent.mkdir(parents=True,exist_ok=True);no_links(output.parent)
    if inside(data,output) or inside(ROOT,output):raise ValueError('备份输出须在运行数据和程序目录之外')
    files,dirs=inventory(data,'data');model=dict(kind='none')
    if request.get('models'):
        models=no_links(request['models'])
        if inside(models,ROOT) or inside(ROOT,models):raise ValueError('模型来源不能与程序目录重叠')
        if not models.is_dir():raise ValueError('模型来源必须为目录')
        if inside(data,models) and excluded(models.relative_to(data).as_posix()):raise ValueError('模型目录不能位于排除目录')
        if inside(data,models):model=dict(kind='internal',relative=models.relative_to(data).as_posix())
        else:
            if inside(models,data) or inside(models,output):raise ValueError('独立模型目录不能包含数据目录或备份输出')
            external,external_dirs=inventory(models,'models');files+=external;dirs+=external_dirs;model=dict(kind='external')
    if len(files)+len(dirs)>MAX_FILES:raise ValueError('备份文件/目录数超过上限')
    expected_bytes=sum(info[2][2] for info in files)
    if expected_bytes>MAX_BYTES:raise ValueError('备份数据超过 20 GiB')
    all_names=[name for name,*_ in files]+dirs
    if len({folded(n) for n in all_names})!=len(all_names):raise ValueError('备份存在大小写或 Unicode 等价路径冲突')
    validate_paths([(n,'file') for n,*_ in files]+[(n,'directory') for n in dirs])
    token=('SIEANS_BACKUP_IN_PROGRESS:'+uuid.uuid4().hex).encode('ascii')
    # Reserve the new name exclusively, then atomically replace only our own
    # reservation. A competing backup cannot overwrite an existing archive.
    fd=os.open(output,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'wb') as reservation:reservation.write(token)
    reservation_stat=signature(output.stat());temp=output.with_name(output.name+'.tmp-'+uuid.uuid4().hex)
    entries=[];total=0;success=False
    try:
        with os.fdopen(os.open(temp,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'wb') as stream,zipfile.ZipFile(stream,'w',compression=zipfile.ZIP_DEFLATED,allowZip64=True) as archive:
            for name,source,before,mode in sorted(files):
                digest=hashlib.sha256();count=0
                info=zipfile.ZipInfo(name);info.compress_type=zipfile.ZIP_DEFLATED;info.create_system=3;info.external_attr=(stat.S_IFREG|(0o700 if mode&stat.S_IXUSR else 0o600))<<16
                with source.open('rb') as reader,archive.open(info,'w',force_zip64=True) as target:
                    if signature(os.fstat(reader.fileno()))!=before:raise ValueError('备份期间文件变化：'+name)
                    while True:
                        chunk=reader.read(1024*1024)
                        if not chunk:break
                        count+=len(chunk)
                        if count>before[2]:raise ValueError('备份期间文件增长：'+name)
                        digest.update(chunk);target.write(chunk)
                    if count!=before[2] or signature(os.fstat(reader.fileno()))!=before:raise ValueError('备份期间文件变化：'+name)
                total+=count;entries.append(dict(path=name,bytes=count,sha256=digest.hexdigest()));progress('backup',len(entries),total,expected_bytes)
            current,current_dirs=inventory(data,'data')
            if model['kind']=='external':extra,extra_dirs=inventory(models,'models');current+=extra;current_dirs+=extra_dirs
            if [(n,s) for n,_,s,_ in sorted(current)]!=[(n,s) for n,_,s,_ in sorted(files)] or sorted(current_dirs)!=sorted(dirs):raise ValueError('备份期间目录内容变化，请停止全部相关写入后重试')
            manifest=dict(format=1,product='SIEANS Vision',kind='runtime-data',id=uuid.uuid4().hex,createdAt=int(time.time()*1000),programVersion=request['programVersion'],models=model,excluded=['cache','logs',LOCK+'*',MARKER],directories=sorted(dirs),files=entries,totalBytes=total)
            content=json.dumps(manifest,ensure_ascii=False,separators=(',',':')).encode('utf-8')
            if len(content)>MAX_MANIFEST:raise ValueError('备份清单过大')
            archive.writestr(MANIFEST,content)
        if signature(output.stat())!=reservation_stat or output.read_bytes()!=token:raise ValueError('备份输出预留文件被修改，拒绝替换')
        os.replace(temp,output);success=True
        return dict(archive=str(output),sha256=digest_file(output),archiveBytes=output.stat().st_size,files=len(entries),directories=len(dirs),dataBytes=total,models=model['kind'],createdAt=manifest['createdAt'],programVersion=manifest['programVersion'])
    finally:
        if temp.exists():temp.unlink()
        if not success and output.exists() and signature(output.stat())==reservation_stat and output.read_bytes()==token:output.unlink()


def load_archive(file):
    path=no_links(file)
    if not path.is_file():raise ValueError('备份必须为普通 ZIP 文件')
    archive=zipfile.ZipFile(path,'r')
    try:
        names=archive.namelist()
        if len(names)>MAX_FILES+1 or len(set(names))!=len(names) or names.count(MANIFEST)!=1:raise ValueError('备份条目数量或重复名称无效')
        header=archive.getinfo(MANIFEST)
        if header.file_size>MAX_MANIFEST or header.flag_bits&1 or header.compress_type not in (zipfile.ZIP_STORED,zipfile.ZIP_DEFLATED) or stat.S_IFMT(header.external_attr>>16) not in (0,stat.S_IFREG):raise ValueError('备份清单大小、类型或编码无效')
        manifest=json.loads(archive.read(header))
        if not isinstance(manifest,dict) or manifest.get('format')!=1 or manifest.get('product')!='SIEANS Vision' or manifest.get('kind')!='runtime-data':raise ValueError('不是兼容的 SIEANS 数据备份')
        if not isinstance(manifest.get('createdAt'),int) or not isinstance(manifest.get('programVersion'),str):raise ValueError('备份来源信息无效')
        files=manifest.get('files');dirs=manifest.get('directories');model=manifest.get('models')
        if not isinstance(files,list) or not isinstance(dirs,list) or len(files)+len(dirs)>MAX_FILES or not isinstance(model,dict) or model.get('kind') not in ('none','internal','external'):raise ValueError('备份清单结构无效')
        if model['kind']=='internal':
            relative=model.get('relative')
            if relative!='.':portable(relative)
        expected={MANIFEST};all_paths={};total=0
        for directory in dirs:
            portable(directory)
            if not directory.startswith(('data/','models/')) or directory.startswith('models/') and model['kind']!='external':raise ValueError('目录命名空间无效')
            if directory.startswith('data/') and excluded(directory[5:]):raise ValueError('备份包含保留目录')
            identity=folded(directory)
            if identity in all_paths:raise ValueError('备份路径重复或大小写冲突')
            all_paths[identity]='directory'
        for entry in files:
            if not isinstance(entry,dict) or set(entry)!={'path','bytes','sha256'}:raise ValueError('文件清单无效')
            name=portable(entry['path']);size=entry['bytes'];digest=entry['sha256']
            if not name.startswith(('data/','models/')) or name.startswith('models/') and model['kind']!='external':raise ValueError('文件命名空间无效')
            if name.startswith('data/') and excluded(name[5:]):raise ValueError('备份包含运行锁、恢复标记或已排除目录')
            if isinstance(size,bool) or not isinstance(size,int) or not 0<=size<=MAX_FILE or not isinstance(digest,str) or len(digest)!=64 or any(c not in '0123456789abcdef' for c in digest):raise ValueError('文件大小或摘要无效')
            identity=folded(name)
            if identity in all_paths:raise ValueError('备份路径重复或大小写冲突')
            all_paths[identity]='file';expected.add(name);total+=size
            info=archive.getinfo(name)
            if info.file_size!=size or info.flag_bits&1 or info.compress_type not in (zipfile.ZIP_STORED,zipfile.ZIP_DEFLATED) or stat.S_IFMT(info.external_attr>>16) not in (0,stat.S_IFREG):raise ValueError('文件条目大小、类型或编码无效')
        if total>MAX_BYTES or total!=manifest.get('totalBytes') or set(names)!=expected:raise ValueError('备份大小或文件集合与清单不符')
        validate_paths([(entry['path'],'file') for entry in files]+[(n,'directory') for n in dirs])
        if model['kind']=='internal' and model['relative']!='.' and all_paths.get(folded('data/'+model['relative']))!='directory':raise ValueError('内部模型目录未包含在备份中')
        for name,kind in all_paths.items():
            for parent in Path(name).parents:
                if str(parent)=='.':continue
                if all_paths.get(parent.as_posix())=='file':raise ValueError('文件与目录路径冲突')
        return archive,manifest
    except BaseException:
        archive.close();raise


def verify_members(archive,manifest,target=None,external_name=None):
    processed=0;count=0
    def destination(name):
        if name.startswith('data/'):relative=name[5:]
        else:relative=external_name+'/'+name[7:]
        result=target/relative
        if not inside(target,result):raise ValueError('恢复文件超出目标')
        no_links(result,False);return result
    if target:
        for name in manifest['directories']:destination(name).mkdir(parents=True,exist_ok=True,mode=0o700)
    for entry in manifest['files']:
        digest=hashlib.sha256();size=0;writer=None
        try:
            if target:
                output=destination(entry['path']);output.parent.mkdir(parents=True,exist_ok=True,mode=0o700);writer=os.fdopen(os.open(output,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600),'wb')
                if os.name!='nt':os.chmod(output,0o700 if archive.getinfo(entry['path']).external_attr>>16&stat.S_IXUSR else 0o600)
            with archive.open(entry['path']) as source:
                while True:
                    chunk=source.read(1024*1024)
                    if not chunk:break
                    size+=len(chunk)
                    if size>entry['bytes']:raise ValueError('解压数据超过声明大小')
                    digest.update(chunk)
                    if writer:writer.write(chunk)
            if size!=entry['bytes'] or digest.hexdigest()!=entry['sha256']:raise ValueError('文件摘要校验失败：'+entry['path'])
        finally:
            if writer:writer.close()
        processed+=size;count+=1;progress('restore' if target else 'verify',count,processed,manifest['totalBytes'])


def inspect(request):
    before=digest_file(request['archive'])
    archive,manifest=load_archive(request['archive'])
    with archive:verify_members(archive,manifest)
    if before!=digest_file(request['archive']):raise ValueError('校验期间备份发生变化')
    return dict(sha256=before,archiveBytes=Path(request['archive']).stat().st_size,files=len(manifest['files']),directories=len(manifest['directories']),dataBytes=manifest['totalBytes'],models=manifest['models']['kind'],createdAt=manifest['createdAt'],programVersion=manifest['programVersion'])


def restore(request):
    source=no_links(request['archive']);target=no_links(request['target'])
    if inside(ROOT,target) or inside(target,ROOT) or not target.is_dir() or not (target/MARKER).is_file() or set(p.name for p in target.iterdir())!={LOCK,MARKER}:raise ValueError('恢复目标未被维护工具正确预留或已含其他文件')
    if digest_file(source)!=request['expectedSha256']:raise ValueError('备份在校验后发生变化，未恢复')
    archive,manifest=load_archive(source)
    if shutil.disk_usage(target).free<manifest['totalBytes']+64*1024**2:archive.close();raise ValueError('恢复目标磁盘空间不足')
    external_name='.sieans-models-'+uuid.uuid4().hex
    if any(entry['path'].startswith('data/'+external_name) for entry in manifest['files']) or any(n.startswith('data/'+external_name) for n in manifest['directories']):archive.close();raise ValueError('模型恢复路径冲突')
    with archive:verify_members(archive,manifest,target,external_name)
    if digest_file(source)!=request['expectedSha256']:raise ValueError('恢复期间备份发生变化')
    kind=manifest['models']['kind']
    models=target/external_name if kind=='external' else target/manifest['models']['relative'] if kind=='internal' else target/'models'
    models.mkdir(parents=True,exist_ok=True,mode=0o700)
    return dict(files=len(manifest['files']),dataBytes=manifest['totalBytes'],modelsPath=str(models),sourceVersion=manifest['programVersion'],sha256=request['expectedSha256'])


if __name__=='__main__':
    try:
        request=json.loads(sys.stdin.read(20001))
        action={'backup':backup,'inspect':inspect,'restore':restore}.get(request.get('action'))
        if action is None:raise ValueError('未知备份动作')
        print(json.dumps(dict(event='result',data=action(request)),ensure_ascii=True),flush=True)
    except BaseException as error:
        print(json.dumps(dict(event='error',error=str(error)[:2000]),ensure_ascii=True),flush=True);sys.exit(1)
