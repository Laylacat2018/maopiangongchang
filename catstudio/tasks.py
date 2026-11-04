import threading, time, base64
from pathlib import Path
from huey import SqliteHuey
from sqlmodel import Session
from .db import DATA, engine, get, add, rows, touch, now
from . import storage, media

huey=SqliteHuey('catstudio',filename=str(DATA/'tasks.db'),immediate=False)
stop_event=threading.Event()

@huey.task()
def execute_task(task_id):
    with Session(engine) as s:
        task=get(s,'task',task_id)
        if task.status in ['success','failed']:return
        task.status='running';touch(task);s.commit()
        try:
            d=task.data;kind=task.name
            if kind=='candidate':
                c=get(s,'candidate',d['id']);f=get(s,'file_object',c.data['file_id']);path=storage.path_for(f)
                meta=media.probe(path)
                if not meta['width'] or not meta['height']:raise ValueError('回传文件没有可播放的视频轨')
                record=get(s,'generation_record',c.parent_id);params=record.data['params'];mismatch=[]
                if abs(meta['duration']-params['duration_s'])>.25:mismatch.append('实际时长与提交参数不同')
                expected_ratio=9/16 if params['ratio']=='9:16' else 16/9
                if abs(meta['width']/meta['height']-expected_ratio)>.03:mismatch.append('实际画幅与提交参数不同')
                short=min(meta['width'],meta['height']);target=int(''.join(x for x in str(params['resolution']) if x.isdigit()) or 0)
                if target and short<target:mismatch.append('实际分辨率低于提交参数')
                directory=path.parent/(f.name+'-frames');fs=media.frames(path,directory)
                frame_ids=[]
                for frame in fs:frame_ids.append(storage.store(s,directory/frame,frame).id)
                c.data={**c.data,'media_meta':meta,'mismatch':mismatch,'frame_ids':frame_ids,'analysis_status':'ready'};touch(c)
            elif kind=='final':
                from .services import brief,validate_srt
                final=get(s,'final_cut',d['id']);f=get(s,'file_object',final.data['file_id'])
                checks=media.inspect_final(storage.path_for(f),brief(s,final.project_id))
                ep=get(s,'edit_package',final.parent_id)
                try:
                    validate_srt(ep.data.get('srt',''),checks['meta']['duration'])
                    checks['checks']['srt']=True
                except Exception as exc:
                    checks['checks']['srt']=False;checks['srt_error']=str(exc)
                checks['passed']=all(checks['checks'].values())
                final.data={**final.data,'auto_checks':checks,'analysis_status':'ready'};touch(final)
                if final.status not in ['publishable','historical']:final.status='checked' if checks['passed'] else 'check_failed'
            elif kind=='llm':
                from .llm import call
                image=None
                if d.get('image_file_id'):
                    f=get(s,'file_object',d['image_file_id'])
                    if f.data.get('size',0)>15*1024*1024:raise ValueError('截图超过 15MB')
                    image={'mime':f.data['mime'],'b64':base64.b64encode(storage.path_for(f).read_bytes()).decode()}
                result=call(s,task.project_id,d['purpose'],d.get('context',{}),image)
                task.data={**task.data,'result':result}
            elif kind=='backup':
                file=storage.store(s,storage.backup(),'猫片工场备份.zip');task.data={**task.data,'file_id':file.id}
            task.status='success';touch(task);s.commit()
        except Exception as exc:
            s.rollback();task=get(s,'task',task_id);task.status='failed';task.data={**task.data,'error':str(exc)[:1000]};touch(task)
            if task.name in ['candidate','final']:
                obj=get(s,'candidate' if task.name=='candidate' else 'final_cut',task.data['id']);obj.data={**obj.data,'analysis_status':'failed','analysis_error':str(exc)[:500]}
            s.commit()

def enqueue(s,kind,pid,data):
    t=add(s,'task',project_id=pid,name=kind,status='pending',data=data);s.commit();execute_task(t.id);return t

def worker():
    while not stop_event.is_set():
        task=huey.dequeue()
        if task:
            try:huey.execute(task)
            except Exception:pass
        else:stop_event.wait(.3)

def start():
    stop_event.clear()
    # Recompute local jobs after a crash; never replay potentially billable LLM calls.
    with Session(engine) as s:
        for task in rows(s,'task'):
            if task.status in ['running','pending']:
                if task.name=='llm':task.status='failed';task.data={**task.data,'error':'应用中断；请核对模型账单，再手动重试'}
                else:task.status='pending';execute_task(task.id)
        s.commit()
    thread=threading.Thread(target=worker,daemon=True,name='catstudio-worker');thread.start()
    return thread
