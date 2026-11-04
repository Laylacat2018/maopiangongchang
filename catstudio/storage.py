import hashlib, mimetypes, os, shutil, sqlite3, zipfile, json
from contextlib import closing
from pathlib import Path
from PIL import Image
from .db import DATA, add, rows, get, MODELS
from sqlmodel import select
from fastapi import HTTPException

ALLOWED={'.png','.jpg','.jpeg','.webp','.wav','.mp3','.m4a','.mp4','.mov','.csv','.srt','.zip','.json','.txt','.md'}
MAX_BYTES=2*1024**3

def path_for(obj):
    path=(DATA/obj.data['rel_path']).resolve()
    if not path.is_relative_to(DATA): raise HTTPException(400,'文件路径无效')
    return path

def store(s, path, original):
    ext=Path(original).suffix.lower()
    if ext not in ALLOWED: raise HTTPException(422,'不支持此类型文件')
    if path.stat().st_size>MAX_BYTES: raise HTTPException(413,'文件超过 2GB')
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    sha=h.hexdigest()
    existing=s.exec(select(MODELS['file_object']).where(MODELS['file_object'].name==sha)).first()
    if existing:return existing
    if ext in {'.png','.jpg','.jpeg','.webp'}:
        try:
            with Image.open(path) as im:im.verify()
        except Exception:raise HTTPException(422,'图片损坏，无法读取')
    dest=DATA/'files'/sha[:2]/sha[2:4]/(sha+ext)
    dest.parent.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(path,dest)
    return add(s,'file_object',name=sha,status='ready',data={'sha256':sha,'rel_path':str(dest.relative_to(DATA)).replace('\\','/'),'original_name':Path(original).name,'size':dest.stat().st_size,'mime':mimetypes.guess_type(original)[0] or 'application/octet-stream'})

def zip_files(s, name, content, sources):
    import uuid
    dest=DATA/'exports'/(str(uuid.uuid4())+'.zip')
    with zipfile.ZipFile(dest,'w',zipfile.ZIP_DEFLATED) as z:
        for filename,text in content.items():z.writestr(filename,text)
        for filename,file_id in sources:
            z.write(path_for(get(s,'file_object',file_id)),filename)
    obj=store(s,dest,name+'.zip')
    dest.unlink(missing_ok=True)
    return obj

def backup():
    import datetime
    target=DATA/'backups'/('catstudio-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')+'.zip')
    dbcopy=DATA/'tmp'/(target.stem+'.db')
    with closing(sqlite3.connect(DATA/'catstudio.db')) as source,closing(sqlite3.connect(dbcopy)) as dest:source.backup(dest)
    with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED) as z:
        z.write(dbcopy,'catstudio.db')
        z.writestr('backup-manifest.json',json.dumps({'format':'catstudio-backup','version':1,'keys':'system-keyring-not-included'}))
        for f in (DATA/'files').rglob('*'):
            if f.is_file():z.write(f,str(f.relative_to(DATA)))
    dbcopy.unlink(missing_ok=True)
    return target

def restore_backup(path):
    from .db import engine
    with zipfile.ZipFile(path) as z:
        names=z.namelist()
        if 'catstudio.db' not in names or 'backup-manifest.json' not in names:raise ValueError('这不是猫片工场备份')
        if json.loads(z.read('backup-manifest.json')).get('format')!='catstudio-backup':raise ValueError('备份格式不符')
        if sum(x.file_size for x in z.infolist())>20*1024**3:raise ValueError('解压体积超限')
        for n in names:
            p=(DATA/n).resolve()
            if not p.is_relative_to(DATA) or (n not in {'catstudio.db','backup-manifest.json'} and not n.startswith('files/')):raise ValueError('备份包含不安全路径')
        # Validate before touching current database; retain a safety backup.
        check=DATA/'tmp'/'restore-check.db'; check.write_bytes(z.read('catstudio.db'))
        with closing(sqlite3.connect(check)) as c:
            if c.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise ValueError('备份数据库损坏')
        backup();engine.dispose()
        for side in ('catstudio.db-wal','catstudio.db-shm'):(DATA/side).unlink(missing_ok=True)
        os.replace(check,DATA/'catstudio.db')
        for n in names:
            if n.startswith('files/') and not n.endswith('/'):
                dest=DATA/n;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(z.read(n))
