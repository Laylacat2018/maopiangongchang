from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from uuid import uuid4
import csv, io, json, os, re, shutil, tempfile, threading, time
from urllib.parse import urlparse
from fastapi import FastAPI, HTTPException, UploadFile, File, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from sqlmodel import Session, select
from .db import *
from . import storage, media, services as svc, llm, tasks

@asynccontextmanager
async def lifespan(app):
    init()
    with Session(engine) as s:
        llm.seed(s)
        if not rows(s,'model_profile'):
            for name,url in [('Seedance','https://jimeng.jianying.com/'),('MiniMax H3','https://hailuoai.com/'),('Vidu','https://www.vidu.cn/')]:
                add(s,'model_profile',name=name,status='unverified',data={'kind':'video','site_url':url,'version':'','modes':[],'max_ref_images':0,'max_audio':0,'durations':[],'resolutions':[],'ratios':[],'credit_price':None,'credit_to_cny':None,'verified_at':None})
        s.commit()
    worker_thread=tasks.start()
    def daily():
        while not tasks.stop_event.wait(30):
            try:
                today=datetime.now().strftime('%Y%m%d')
                if not any(today in x.name for x in (DATA/'backups').glob('catstudio-*.zip')):
                    storage.backup()
                    old=sorted((DATA/'backups').glob('catstudio-*.zip'),key=lambda f:f.stat().st_mtime,reverse=True)
                    for f in old[7:]:f.unlink()
            except Exception:pass
    threading.Thread(target=daily,daemon=True).start()
    yield
    tasks.stop_event.set()
    worker_thread.join(timeout=3)

app=FastAPI(title='猫片工场',version='1.0.0',lifespan=lifespan)

@app.middleware('http')
async def local_only(request,call_next):
    host=request.headers.get('host','').split(':')[0]
    if host not in ['localhost','127.0.0.1','testserver']:
        return JSONResponse({'detail':'仅允许本机访问'},status_code=403)
    origin=request.headers.get('origin')
    if request.method not in ['GET','HEAD','OPTIONS'] and origin:
        parsed=urlparse(origin)
        if parsed.hostname not in ['localhost','127.0.0.1','testserver']:
            return JSONResponse({'detail':'拒绝跨站写入请求'},status_code=403)
    response=await call_next(request)
    response.headers['X-Content-Type-Options']='nosniff'
    return response

@app.exception_handler(ValueError)
def invalid(request,exc):return JSONResponse({'detail':str(exc)},status_code=422)

@app.get('/api/health')
def health():return {'app_id':'catstudio','status':'ok','version':'1.0.0','ffmpeg':bool(shutil.which('ffmpeg')),'ffprobe':bool(shutil.which('ffprobe')),'mode':'manual','data_dir':str(DATA)}

@app.get('/api/state')
def state():
    with Session(engine) as s:
        # Keys, encrypted or clear, never leave backend.
        all_data={k:[jsonable(x) for x in rows(s,k)] for k in KINDS if k not in ['file_object','llm_call','app_setting']}
        settings={x.name:{k:v for k,v in x.data.items() if k!='encrypted_key'}|({'has_key':bool(x.data.get('encrypted_key'))} if x.name.startswith('llm_') else {}) for x in rows(s,'app_setting')}
        all_data['settings']=settings
        all_data['timelines']={p.id:svc.timeline(s,p.id) for p in rows(s,'project')}
        all_data['total_spend']=svc.spend(s)
        return all_data

SYSTEM_KINDS={'gate_event','generation_record','candidate','review','edit_package','final_cut','archive','file_object','llm_call','app_setting','task'}

def check_kind(kind):
    if kind not in MODELS:svc.fail('未知对象类型',404)

def validate_save(s,kind,obj,data,is_new):
    if obj.project_id:get(s,'project',obj.project_id)
    d=obj.data
    if kind=='brief':
        if len(d.get('audience',''))>200:svc.fail('目标人群最多 200 字')
        svc.money(d.get('budget_cap',0))
        if not is_new:svc.invalidate(s,obj.project_id,1,'简报已修改，请复核下游')
    if kind=='reference':
        url=d.get('url','')
        if url and urlparse(url).scheme not in ['http','https']:svc.fail('素材链接必须使用 http 或 https')
        host=urlparse(url).hostname or ''
        d['platform']='抖音' if 'douyin' in host else '小红书' if any(x in host for x in ['xiaohongshu','xhslink']) else d.get('platform','其他')
        obj.data={**d}
    if kind=='evidence':
        if not d.get('text','').strip():svc.fail('评论文字不能为空')
        obj.data={k:v for k,v in d.items() if k not in ['nickname','avatar','user_id']}
        if obj.parent_id and get(s,'reference',obj.parent_id).project_id!=obj.project_id:svc.fail('评论来源不属于本项目')
    if kind=='story_direction':
        for field,k in [('cited_reference_ids','reference'),('cited_evidence_ids','evidence')]:
            for id in d.get(field,[]):
                if get(s,k,id).project_id!=obj.project_id:svc.fail('故事方向不能引用其他项目素材')
        if d.get('is_selected'):
            for other in rows(s,kind,obj.project_id):
                if other.id!=obj.id:other.data={**other.data,'is_selected':False}
        if not is_new:svc.invalidate(s,obj.project_id,2,'选题已修改')
    if kind=='script':
        if obj.status=='confirmed' and not d.get('summary','').strip():svc.fail('剧情稿不能为空')
        if not is_new:svc.invalidate(s,obj.project_id,3,'剧情稿已修改')
    if kind=='shot':
        if obj.duration_s<=0 or obj.duration_s>600:svc.fail('镜头时长必须在 0–600 秒内')
        if not is_new:
            old=selected_before=getattr(obj,'_old_data',None)
            svc.reset_shot(s,obj,'分镜或提示词修改')
            svc.invalidate(s,obj.project_id,3,'分镜修改，请重新确认')
        if d.get('prompt'):
            previous=rows(s,'prompt_version',parent=obj.id)
            if not previous or previous[-1].data.get('body')!=d['prompt']:
                add(s,'prompt_version',project_id=obj.project_id,parent_id=obj.id,name='视频提示词',version=len(previous)+1,data={'body':d['prompt'],'owner_type':'shot','origin':d.get('origin','用户')})
    if kind=='asset':
        if not d.get('code'):
            prefix=d.get('type','CHAR')
            used=[int(a.data.get('code','').split('-')[-1]) for a in s.exec(select(MODELS['asset'])).all() if a.id!=obj.id and a.data.get('code','').startswith(prefix+'-') and a.data.get('code','').split('-')[-1].isdigit()]
            obj.data={**d,'code':f'{prefix}-{max(used,default=0)+1:03}'}
        if d.get('prompt'):
            previous=rows(s,'prompt_version',parent=obj.id)
            if not previous or previous[-1].data.get('body')!=d['prompt']:
                add(s,'prompt_version',project_id=obj.project_id,parent_id=obj.id,name='图片提示词',version=len(previous)+1,data={'body':d['prompt'],'owner_type':'asset'})
    if kind=='asset_version':
        asset=get(s,'asset',obj.parent_id)
        if d.get('source') not in ['AI生成','自拍','自录','购买','其他']:svc.fail('请填写资产来源')
        if asset.data.get('type') in ['VOICE','SFX','BGM'] and not d.get('license_note'):svc.fail('声音素材必须填写授权来源')
        if obj.status=='final' and not rows(s,'asset_file',parent=obj.id):svc.fail('请回传素材文件后再定稿')
        obj.project_id=asset.project_id
    if kind=='asset_file':
        v=get(s,'asset_version',obj.parent_id)
        if v.status=='final':svc.fail('定稿版本不可修改文件，请回传新版本',409)
        get(s,'file_object',d['file_id']);obj.project_id=v.project_id
    if kind=='asset_link':get(s,'asset',obj.parent_id);get(s,'asset',d['accessory_asset_id'])
    if kind=='platform_subject':get(s,'asset_version',obj.parent_id);get(s,'model_profile',d['model_profile_id'])
    if kind=='shot_binding':
        sh=get(s,'shot',obj.shot_id)
        if sh.project_id!=obj.project_id:svc.fail('镜头不属于本项目')
        if d.get('asset_version_id'):
            av=get(s,'asset_version',d['asset_version_id']);asset=get(s,'asset',av.parent_id)
            if av.status!='final':svc.fail('只能绑定已定稿的版本')
            if asset.project_id not in (None,obj.project_id):svc.fail('资产不属于本项目或全局库')
            allowed={'主体':['CHAR'],'场景':['SCN'],'道具':['PROP','PROD'],'声音':['VOICE','SFX','BGM']}
            if asset.data.get('type') not in allowed.get(d.get('slot'),[]):svc.fail('资产类型与素材槽位不匹配：'+str(d.get('slot')))
        svc.reset_shot(s,sh,'镜头素材绑定已更新')
        if not svc.package_preview(s,sh.id)['errors']:sh.status='ready'
    if kind=='model_profile':
        url=d.get('site_url','')
        if url and urlparse(url).scheme not in ['http','https']:svc.fail('官网地址无效')
        for field in ['max_ref_images','max_audio']:
            if float(d.get(field,0))<0:svc.fail('模型数量上限不能为负数')
        for field in ['credit_price','credit_to_cny']:
            if d.get(field) is not None:svc.money(d[field])
    if kind=='cost_entry':
        obj.amount_fen=svc.money(data.get('amount_cny',obj.amount_fen/100));obj.data={**obj.data,'unpriced':False}
    if kind=='release':
        fc=get(s,'final_cut',obj.parent_id)
        if fc.project_id!=obj.project_id or fc.status!='publishable':svc.fail('请选择本项目已通过检查的成片')
        if urlparse(d.get('url','')).scheme not in ['http','https']:svc.fail('请填写有效发布链接')
    if kind=='retention_point':
        if not 0<=float(d.get('ratio',0))<=1 or float(d.get('second',0))<0:svc.fail('留存比例应为 0–1，时间须非负')
        snap=get(s,'metric_snapshot',obj.parent_id)
        if snap.project_id!=obj.project_id:svc.fail('留存点不属于本项目')
    if kind=='prompt_template' and not d.get('body'):svc.fail('提示词模板不能为空')

@app.post('/api/items/{kind}')
def create(kind:str,body:dict):
    check_kind(kind)
    if kind in SYSTEM_KINDS:svc.fail('请使用对应业务操作创建记录',403)
    with Session(engine) as s:
        payload={k:v for k,v in body.items() if k in ['project_id','parent_id','shot_id','name','status','version','seq','duration_s','amount_fen','data']}
        obj=add(s,kind,**payload)
        validate_save(s,kind,obj,body,True)
        s.commit();return jsonable(obj)

@app.put('/api/items/{kind}/{id}')
def update(kind:str,id:str,body:dict):
    check_kind(kind)
    if kind in SYSTEM_KINDS:svc.fail('此记录不可直接修改',403)
    with Session(engine) as s:
        obj=get(s,kind,id)
        old_data=dict(obj.data)
        if body.get('revision') is not None and body['revision']!=obj.revision:svc.fail('记录已有新版本，请刷新后再保存',409)
        if kind=='asset_version' and obj.status=='final' and body.get('status')!='disabled':svc.fail('定稿版本不能改写，请上传新版本',409)
        if kind in ['script','prompt_template']:
            # Editing confirmed text creates a new version; former text remains immutable.
            if kind=='prompt_template' or obj.status=='confirmed':
                old=obj;payload={k:getattr(obj,k) for k in ['project_id','parent_id','name','data','status']};payload.update({k:v for k,v in body.items() if k in payload});payload['version']=obj.version+1
                if kind=='script':payload['status']='draft'
                else:old.status='superseded'
                obj=add(s,kind,**payload)
        for k,v in body.items():
            if k in ['name','status','seq','duration_s','data','amount_fen']:setattr(obj,k,v)
        if kind=='project':
            if old_data.get('generation_settings')!=obj.data.get('generation_settings') or old_data.get('default_model_id')!=obj.data.get('default_model_id'):
                for sh in svc.shots(s,obj.id):svc.reset_shot(s,sh,'项目模型或生成参数已变化')
            if old_data.get('srt')!=obj.data.get('srt') or old_data.get('edit_notes')!=obj.data.get('edit_notes'):
                svc.invalidate(s,obj.id,6,'剪辑字幕或说明已变化')
        validate_save(s,kind,obj,body,False);touch(obj);s.commit();return jsonable(obj)

@app.delete('/api/items/{kind}/{id}')
def soft_delete(kind:str,id:str):
    check_kind(kind)
    if kind in SYSTEM_KINDS or kind=='cost_entry':svc.fail('追溯记录不可删除；请保留历史',409)
    with Session(engine) as s:
        obj=get(s,kind,id)
        if kind in ['asset','asset_version']:
            version_ids={id} if kind=='asset_version' else {x.id for x in rows(s,'asset_version',parent=id)}
            if any(x.data.get('asset_version_id') in version_ids for x in rows(s,'shot_binding')):svc.fail('资产仍被镜头引用，请先解除引用或保留历史',409)
        if kind=='shot':svc.invalidate(s,obj.project_id,3,'删除镜头')
        if kind in ['reference','evidence']:svc.invalidate(s,obj.project_id,2,'删除选题依据')
        obj.deleted_at=now();touch(obj);s.commit();return {'ok':True}

@app.post('/api/projects')
def project_create(body:dict):
    name=body.get('name','').strip()
    if not name or len(name)>60:svc.fail('项目名须为 1–60 字')
    with Session(engine) as s:
        p=add(s,'project',name=name,data={'stage':1,'completed_stages':[]})
        reuse_brief={}
        if body.get('source_project_id'):
            source=get(s,'project',body['source_project_id']);reuse_brief=svc.brief(s,source.id)
            reused=[]
            for bind in rows(s,'shot_binding',source.id):
                vid=bind.data.get('asset_version_id')
                if vid:
                    a=get(s,'asset',get(s,'asset_version',vid).parent_id);a.project_id=None;reused.append(vid)
            p.data={**p.data,'source_project_id':source.id,'reused_asset_ids':reused}
        b={'audience':'','tags':[],'direction':'猫咪职场 Vlog','emotion':'真实共情，轻松治愈','platforms':['抖音'],'aspect_ratio':'9:16','duration_min_s':20,'duration_max_s':30,'language':'中文','budget_cap':50,'pause_on_budget':True,'quantity':1,**reuse_brief,**body.get('brief',{})}
        add(s,'brief',project_id=p.id,name='人群简报',data=b);s.commit();return jsonable(p)

@app.post('/api/projects/{id}/gate/{stage}')
def gate(id:str,stage:int):
    if not 1<=stage<=7:svc.fail('阶段无效')
    with Session(engine) as s:r=svc.advance(s,id,stage);s.commit();return r

@app.get('/api/projects/{id}/gate/{stage}')
def gate_preview(id:str,stage:int):
    with Session(engine) as s:return {'errors':svc.gate_errors(s,id,stage)}

@app.post('/api/projects/{id}/rollback/{stage}')
def rollback(id:str,stage:int):
    with Session(engine) as s:svc.invalidate(s,id,stage,'用户返回修改');s.commit();return {'ok':True}

@app.post('/api/projects/{id}/reorder')
def reorder(id:str,body:dict):
    with Session(engine) as s:
        ss=svc.shots(s,id);ids=body.get('ids',[])
        if len(ids)!=len(set(ids)) or set(ids)!={x.id for x in ss}:svc.fail('排序必须包含本项目全部镜头且不重复')
        for x in ss:x.seq=ids.index(x.id);touch(x)
        svc.invalidate(s,id,3,'镜头排序已变化');s.commit();return svc.timeline(s,id)

@app.post('/api/upload')
async def upload(file:UploadFile=File(...)):
    path=DATA/'tmp'/str(uuid4());total=0
    try:
        with path.open('wb') as out:
            while chunk:=await file.read(1024*1024):
                total+=len(chunk)
                if total>storage.MAX_BYTES:svc.fail('单文件上限为 2GB',413)
                out.write(chunk)
        with Session(engine) as s:obj=storage.store(s,path,file.filename or 'file.bin');s.commit();return jsonable(obj)
    finally:path.unlink(missing_ok=True)

@app.get('/files/{id}')
def download(id:str,download:bool=False):
    with Session(engine) as s:
        f=get(s,'file_object',id);p=storage.path_for(f)
        if not p.exists():svc.fail('本地文件丢失，请从备份恢复',404)
        return FileResponse(p,media_type=f.data['mime'],filename=f.data['original_name'] if download else None,headers={'Cache-Control':'private, max-age=60'})

@app.get('/api/shots/{id}/preview')
def preview(id:str):
    with Session(engine) as s:return svc.package_preview(s,id)

@app.post('/api/shots/{id}/export')
def export(id:str,body:dict):
    with Session(engine) as s:r=svc.export_submission(s,id,body.get('confirmed'),body.get('nonce'));s.commit();return r

@app.post('/api/generations/{id}/candidates')
def ingest(id:str,body:dict):
    with Session(engine) as s:
        record=get(s,'generation_record',id);f=get(s,'file_object',body['file_id'])
        if not f.data['mime'].startswith('video/'):svc.fail('候选必须为视频文件')
        existing=next((x for x in rows(s,'candidate',record.project_id) if x.parent_id==id and x.data.get('file_id')==f.id and x.data.get('enhanced_parent_id')==body.get('enhanced_parent_id')),None)
        if existing:return jsonable(existing)
        enhanced=body.get('enhanced_parent_id')
        if enhanced:
            parent=get(s,'candidate',enhanced)
            if parent.status!='selected' or parent.parent_id!=id:svc.fail('仅同条记录的已选用候选可回传增强版')
        c=add(s,'candidate',project_id=record.project_id,parent_id=id,shot_id=record.shot_id,name=body.get('label') or chr(65+len([x for x in rows(s,'candidate',record.project_id) if x.shot_id==record.shot_id])),status='pending',data={'file_id':f.id,'credits':body.get('credits',0),'task_url':body.get('task_url',''),'enhanced_parent_id':enhanced,'analysis_status':'pending','approved':False})
        model=get(s,'model_profile',record.data['model_id'])
        amount=body.get('amount_cny')
        if amount is None:amount=float(body.get('credits',0))*float(model.data.get('credit_to_cny') or 0)
        svc.cost(s,c.project_id,'增强' if enhanced else '视频生成',c.id,amount,body.get('credits',0),model.id)
        record.status='returned';sh=get(s,'shot',record.shot_id);sh.status='review'
        s.commit();task=tasks.enqueue(s,'candidate',c.project_id,{'id':c.id});s.refresh(c);return {**jsonable(c),'task_id':task.id}

@app.post('/api/candidates/{id}/review')
def review(id:str,body:dict):
    with Session(engine) as s:
        c=get(s,'candidate',id)
        if c.data.get('enhanced_parent_id'):
            if c.data.get('analysis_status')!='ready' or not all(body.get('checks',{}).get(k) for k in ['identity','contact','prop','continuity']):svc.fail('增强版仍须完成媒体检测和四项人工审片')
            c.data={**c.data,'approved':body.get('verdict')=='selected'};c.status='enhanced' if c.data['approved'] else 'rejected';touch(c);s.commit();return jsonable(c)
        r=svc.review_candidate(s,id,body);s.commit();return r

@app.post('/api/candidates/{id}/reanalyze')
def reanalyze(id:str):
    with Session(engine) as s:
        c=get(s,'candidate',id);return jsonable(tasks.enqueue(s,'candidate',c.project_id,{'id':id}))

@app.get('/api/candidates/{id}/enhancement')
def enhancement(id:str):
    with Session(engine) as s:
        c=get(s,'candidate',id)
        if c.status!='selected':svc.fail('请先选用候选')
        return {'source_file_id':c.data['file_id'],'candidate_id':id,'source_meta':c.data.get('media_meta'),'target':'1080×1920（9:16）或 1920×1080（16:9）','instructions':'在外部增强工具保留帧率与音轨；输出 MP4；回传后重新检查身份、接触与首尾衔接。'}

@app.post('/api/projects/{id}/placement')
def placement(id:str,body:dict):
    with Session(engine) as s:
        sh=get(s,'shot',body['shot_id']);v=get(s,'asset_version',body['asset_version_id']);a=get(s,'asset',v.parent_id)
        if sh.project_id!=id or a.data.get('type')!='PROD' or v.status!='final':svc.fail('请选择本项目镜头及已定稿商品资产')
        if not all(body.get('checks',{}).get(k) for k in ['package','pattern','contact','identity']):svc.fail('四项商品植入检查尚未完成')
        bind=next((x for x in rows(s,'shot_binding',id) if x.shot_id==sh.id and x.data.get('slot')=='道具'),None)
        if not bind:svc.fail('镜头尚未绑定道具')
        old=bind.data.get('asset_version_id');bind.data={**bind.data,'asset_version_id':v.id};svc.reset_shot(s,sh,'商品替换，需重新审片')
        r=add(s,'placement',project_id=id,shot_id=sh.id,name='商品植入',status='applied',data={**body,'from_asset_version_id':old});s.commit();return jsonable(r)

@app.get('/api/projects/{id}/srt')
def draft_srt(id:str):
    with Session(engine) as s:return {'srt':get(s,'project',id).data.get('srt',svc.srt_draft(s,id))}

@app.post('/api/projects/{id}/edit-package')
def edit_package(id:str,body:dict):
    with Session(engine) as s:r=svc.edit_package(s,id,body.get('srt'));s.commit();return r

@app.get('/api/projects/{id}/todo')
def todo(id:str):
    with Session(engine) as s:
        lines=['# 待办镜头清单']
        for sh in svc.shots(s,id):
            if sh.status!='selected':lines.append(f'- [ ] {sh.seq+1:02d} {sh.name} | {sh.duration_s}s | 状态：{sh.status} | 本地进入镜头绑定，导出提交包后到官网手动操作')
        return Response('\n'.join(lines),media_type='text/markdown; charset=utf-8',headers={'Content-Disposition':"attachment; filename=todo.md"})

@app.post('/api/projects/{id}/finals')
def ingest_final(id:str,body:dict):
    with Session(engine) as s:
        ep=get(s,'edit_package',body['edit_package_id']);f=get(s,'file_object',body['file_id'])
        if ep.project_id!=id or not f.data['mime'].startswith('video/'):svc.fail('素材包或成片文件不符')
        fc=add(s,'final_cut',project_id=id,parent_id=ep.id,name=body.get('platform_variant','主版'),version=len(rows(s,'final_cut',id))+1,status='checking',data={**body,'analysis_status':'pending','manual_checks':{}});s.commit()
        task=tasks.enqueue(s,'final',id,{'id':fc.id});return {**jsonable(fc),'task_id':task.id}

@app.post('/api/finals/{id}/confirm')
def confirm_final(id:str,body:dict):
    with Session(engine) as s:
        fc=get(s,'final_cut',id);auto=fc.data.get('auto_checks',{})
        ep=get(s,'edit_package',fc.parent_id)
        for item in ep.data.get('manifest',[]):
            chosen=svc.selected(s,item['shot_id'])
            current=get(s,'candidate',item['candidate_id'])
            if not chosen or current.id!=chosen.id and current.data.get('enhanced_parent_id')!=chosen.id:svc.fail('素材选用已变化，此成片属于历史版本，请回传新成片',409)
        if fc.data.get('analysis_status')!='ready' or not auto.get('passed'):svc.fail('成片自动检测尚未通过，请查看具体时间点或参数差异')
        checks=body.get('checks',{})
        if not all(checks.get(k) for k in ['motion','audio','subtitle']):svc.fail('请完成动作、试听、字幕同步三项人工确认')
        fc.data={**fc.data,'manual_checks':checks,'confirmed_at':now()};fc.status='publishable';touch(fc);s.commit();return jsonable(fc)

@app.post('/api/finals/{id}/reanalyze')
def recheck_final(id:str):
    with Session(engine) as s:
        fc=get(s,'final_cut',id);return jsonable(tasks.enqueue(s,'final',fc.project_id,{'id':id}))

@app.post('/api/projects/{id}/archive/{fid}')
def archive(id:str,fid:str):
    with Session(engine) as s:r=svc.archive_project(s,id,fid);s.commit();return r

@app.get('/api/csv/{file_id}/preview')
def csv_preview(file_id:str):
    with Session(engine) as s:return svc.csv_preview(storage.path_for(get(s,'file_object',file_id)))

@app.post('/api/projects/{id}/metrics')
def csv_commit(id:str,body:dict):
    with Session(engine) as s:
        r=svc.import_metrics(s,id,body['file_id'],body['release_id'],body.get('mapping',{}),body.get('period','未命名区间'),body.get('row_index'))
        if body.get('save_mapping'):add(s,'csv_mapping',name=body.get('platform','其他'),data={'mapping':body['mapping']})
        s.commit();return r

@app.post('/api/projects/{id}/comments-csv')
def comments_csv(id:str,body:dict):
    import pandas as pd
    with Session(engine) as s:
        get(s,'project',id);f=get(s,'file_object',body['file_id']);path=storage.path_for(f)
        for enc in ['utf-8-sig','gb18030']:
            try:df=pd.read_csv(path,encoding=enc).fillna('');break
            except UnicodeDecodeError:continue
        text_col=body.get('text_column');likes_col=body.get('likes_column')
        if text_col not in df.columns:svc.fail('请选择评论文字列')
        if len(df)>5000:svc.fail('评论超过 5000 条，请分批导入')
        existing={x.data.get('import_hash') for x in rows(s,'evidence',id)};count=0
        for _,row in df.iterrows():
            content=str(row[text_col]).strip()
            if not content:continue
            fingerprint=__import__('hashlib').sha256((f.id+content).encode()).hexdigest()
            if fingerprint in existing:continue
            try:likes=max(0,int(float(row[likes_col]))) if likes_col in df.columns and row[likes_col]!='' else 0
            except (ValueError,TypeError):svc.fail('评论点赞列包含非数字')
            add(s,'evidence',project_id=id,name=content[:20],data={'text':content,'likes':likes,'source':'CSV','import_hash':fingerprint});existing.add(fingerprint);count+=1
        s.commit();return {'imported':count}

@app.post('/api/projects/{id}/next')
def next_project(id:str,body:dict):
    with Session(engine) as s:
        retro=get(s,'retro',body['retro_id'])
        if retro.project_id!=id or not retro.data.get('exp_change'):svc.fail('请保存单变量实验')
        if retro.data.get('next_project_id'):return jsonable(get(s,'project',retro.data['next_project_id']))
        reuse_versions=[x.data.get('asset_version_id') for x in rows(s,'shot_binding',id) if x.data.get('asset_version_id')]
        for vid in reuse_versions:
            asset=get(s,'asset',get(s,'asset_version',vid).parent_id)
            asset.project_id=None;asset.data={**asset.data,'promoted_for_reuse':True};touch(asset)
        old=get(s,'project',id);p=add(s,'project',name=(old.name+' · 下一条')[:60],data={'stage':1,'completed_stages':[],'source_project_id':id,'source_retro_id':retro.id,'reused_asset_ids':reuse_versions})
        b={**svc.brief(s,id),'experiment':retro.data};add(s,'brief',project_id=p.id,name='复盘生成简报',data=b)
        retro.data={**retro.data,'next_project_id':p.id};s.commit();return jsonable(p)

@app.post('/api/settings/{key}')
def settings(key:str,body:dict):
    if key not in ['llm_text','llm_vision','budget']:svc.fail('未知配置')
    with Session(engine) as s:
        obj=next((x for x in rows(s,'app_setting') if x.name==key),None)
        data={**(obj.data if obj else {}),**{k:v for k,v in body.items() if k not in ['api_key','encrypted_key','has_key']}}
        if body.get('api_key'):data['encrypted_key']=llm.encrypt(body['api_key'])
        if key.startswith('llm_'):
            for price in ['input_price_per_million','output_price_per_million']:
                data[price]=None if data.get(price) in ['',None] else float(data[price])
                if data[price] is not None and data[price]<0:svc.fail('Token 单价不能为负数')
        if key=='budget':svc.money(data.get('monthly_cap',500))
        if obj:obj.data=data;touch(obj)
        else:add(s,'app_setting',name=key,data=data)
        s.commit();return {'ok':True}

@app.post('/api/llm')
def llm_request(body:dict):
    if not body.get('confirmed'):svc.fail('请先确认将向已配置 LLM 发送素材并可能产生费用')
    with Session(engine) as s:
        pid=body.get('project_id');get(s,'project',pid)
        purpose=body.get('purpose')
        if purpose not in llm.PURPOSES:svc.fail('AI 用途无效')
        if not svc.config(s,'llm_vision' if body.get('image_file_id') else 'llm_text').get('encrypted_key'):svc.fail('请先配置并保存 LLM 凭证')
        context={'brief':svc.brief(s,pid),'references':[jsonable(x) for x in rows(s,'reference',pid)],'evidence':[jsonable(x) for x in rows(s,'evidence',pid)],'scripts':[jsonable(x) for x in rows(s,'script',pid)],'shots':svc.timeline(s,pid),**body.get('context',{})}
        return jsonable(tasks.enqueue(s,'llm',pid,{'purpose':purpose,'context':context,'image_file_id':body.get('image_file_id')}))

@app.get('/api/llm/logs')
def llm_logs():
    with Session(engine) as s:return [jsonable(x) for x in rows(s,'llm_call')]

@app.post('/api/backup')
def make_backup():
    with Session(engine) as s:return jsonable(tasks.enqueue(s,'backup',None,{}))

@app.post('/api/restore')
def restore(body:dict):
    if not body.get('confirmed'):svc.fail('恢复会替换当前记录，请先确认')
    with Session(engine) as s:
        if any(x.status in ['pending','running'] for x in rows(s,'task')):svc.fail('请等待后台处理完成再恢复',409)
        f=get(s,'file_object',body['file_id']);path=storage.path_for(f)
    storage.restore_backup(path)
    # A backup may capture its own task as running. Restored tasks are historical;
    # do not replay external calls or leave the UI permanently blocked.
    with Session(engine) as s:
        for task in rows(s,'task'):
            if task.status in ['pending','running']:
                task.status='failed';task.data={**task.data,'error':'已从备份恢复；如需处理请手动重新检测或重新调用'};touch(task)
        s.commit()
    return {'ok':True}

@app.get('/api/costs/export')
def cost_csv(project_id:str|None=None):
    with Session(engine) as s:
        out=io.StringIO();writer=csv.writer(out);writer.writerow(['ID','项目ID','分类','积分','人民币','计价状态','日期'])
        for c in rows(s,'cost_entry',project_id):writer.writerow([c.id,c.project_id,c.name,c.data.get('credits'),c.amount_fen/100,'待核价' if c.data.get('unpriced') else '估算' if c.data.get('estimated') else '已登记',c.created_at])
        return Response('\ufeff'+out.getvalue(),media_type='text/csv; charset=utf-8',headers={'Content-Disposition':'attachment; filename=costs.csv'})

DIST=ROOT/'web'/'dist'
if DIST.exists():
    app.mount('/assets',StaticFiles(directory=DIST/'assets'),name='assets')
    @app.get('/{path:path}')
    def spa(path:str):return FileResponse(DIST/'index.html')
