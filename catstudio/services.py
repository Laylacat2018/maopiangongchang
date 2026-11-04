import json, re, math, csv, io, hashlib, zipfile
from datetime import datetime, timezone
from pathlib import Path
from decimal import Decimal, ROUND_HALF_UP
from fastapi import HTTPException
from sqlmodel import select
from .db import *
from . import storage

STAGES=['人群简报','素材调研','剧本分镜','数字资产','视频生成','剪辑交付','数据复盘']
def fail(msg,code=422):raise HTTPException(code,msg)
def brief(s,pid):
    bs=rows(s,'brief',pid)
    return bs[0].data if bs else {}
def money(value):
    try:d=Decimal(str(value or 0))
    except Exception:fail('金额必须是数字')
    if not d.is_finite() or d<0:fail('金额不能是负数或非有限数')
    return int((d*100).quantize(Decimal('1'),rounding=ROUND_HALF_UP))
def spend(s,pid=None,month=None):
    return sum(x.amount_fen for x in rows(s,'cost_entry',pid) if not month or x.created_at[:7]==month)/100
def cost(s,pid,category,ref_id,amount=0,credits=0,model_id=None):
    return add(s,'cost_entry',project_id=pid,parent_id=ref_id,name=category,amount_fen=money(amount),status='recorded',data={'credits':credits,'model_profile_id':model_id,'occurred_at':now()})
def shots(s,pid):return sorted(rows(s,'shot',pid),key=lambda x:(x.seq,x.created_at))
def timeline(s,pid):
    result=[]; start=0
    for shot in shots(s,pid):
        d=jsonable(shot);d['start']=round(start,3);start+=shot.duration_s;d['end']=round(start,3);result.append(d)
    return result
def selected(s,shot_id):return next((x for x in rows(s,'candidate') if x.shot_id==shot_id and x.status=='selected'),None)
def invalidate(s,pid,stage,note):
    project=get(s,'project',pid)
    completed=project.data.get('completed_stages',[])
    if any(x>=stage for x in completed):
        project.data={**project.data,'completed_stages':[x for x in completed if x<stage],'stage':min(project.data.get('stage',1),stage)};touch(project)
        add(s,'gate_event',project_id=pid,name=note,status='rollback',data={'stage':stage})
    if stage<=6:
        for final in rows(s,'final_cut',pid):
            if final.status=='publishable':
                final.status='historical';final.data={**final.data,'stale_reason':note};touch(final)
def reset_shot(s,shot,note):
    old=selected(s,shot.id)
    if old:old.status='backup';old.data={**old.data,'stale_reason':note};touch(old)
    shot.status='binding';touch(shot);invalidate(s,shot.project_id,5,note)

def gate_errors(s,pid,stage):
    b=brief(s,pid);errors=[]
    if stage==1:
        if not b.get('audience','').strip() or len(b.get('audience',''))>200:errors.append('请填写不超过 200 字的目标人群')
        if not b.get('direction') or not b.get('platforms'):errors.append('内容方向和发布平台不能为空')
        if b.get('aspect_ratio') not in ['9:16','16:9']:errors.append('请选择支持的画幅')
        if not 0<float(b.get('duration_min_s',0))<=float(b.get('duration_max_s',0))<=600:errors.append('目标时长范围无效（0–600 秒）')
        money(b.get('budget_cap',0))
    if stage==2:
        d=next((x for x in rows(s,'story_direction',pid) if x.data.get('is_selected')),None)
        if not d:errors.append('请选择一个故事方向')
        else:
            refs={x.id for x in rows(s,'reference',pid)};evs={x.id for x in rows(s,'evidence',pid)}
            if not (set(d.data.get('cited_reference_ids',[]))&refs or set(d.data.get('cited_evidence_ids',[]))&evs):errors.append('故事方向至少引用一条本项目素材或评论')
    if stage==3:
        if not any(x.status=='confirmed' for x in rows(s,'script',pid)):errors.append('请先确认剧情稿')
        ss=shots(s,pid)
        if not ss:errors.append('请添加分镜')
        for shot in ss:
            if shot.duration_s<=0 or not shot.data.get('action'):errors.append(f'{shot.name}：缺少有效时长或动作')
            if not all(shot.data.get('checks',{}).get(k) for k in ['single','anatomy','continuity']):errors.append(f'{shot.name}：三项镜头检查尚未完成')
        total=sum(x.duration_s for x in ss)
        if not b.get('duration_min_s',0)<=total<=b.get('duration_max_s',600):errors.append('分镜总时长不在简报范围内')
    if stage==4:
        req=rows(s,'shot_binding',pid)
        if not req:errors.append('请按分镜登记必需资产需求与绑定')
        for bind in req:
            if not bind.data.get('required',True):continue
            vid=bind.data.get('asset_version_id')
            if not vid:errors.append(f'{bind.name}：资产未绑定定稿版本')
            elif get(s,'asset_version',vid).status!='final':errors.append(f'{bind.name}：版本尚未定稿')
    if stage==5:
        if not shots(s,pid):errors.append('没有镜头')
        for shot in shots(s,pid):
            c=selected(s,shot.id)
            if not c:errors.append(f'{shot.name}：还没有已选用候选')
            elif c.data.get('analysis_status')!='ready':errors.append(f'{shot.name}：媒体检测未完成')
    if stage==6:
        if not any(x.status=='publishable' for x in rows(s,'final_cut',pid)):errors.append('请回传成片并通过自动检查与三项人工确认')
    if stage==7:
        if not any(x.data.get('observation') and x.data.get('exp_change') for x in rows(s,'retro',pid)):errors.append('请保存复盘观察及下一条单变量实验')
    return errors

def advance(s,pid,stage):
    p=get(s,'project',pid)
    completed=p.data.get('completed_stages',[])
    if any(n not in completed for n in range(1,stage)):fail('前置阶段尚未确认')
    errors=gate_errors(s,pid,stage)
    if errors:fail('；'.join(errors))
    completed=sorted(set(completed+[stage]))
    p.data={**p.data,'completed_stages':completed,'stage':min(stage+1,7)};p.status='complete' if stage==7 else 'active';touch(p)
    add(s,'gate_event',project_id=pid,name=STAGES[stage-1],status='confirmed',data={'stage':stage})
    return jsonable(p)

def config(s,key,default=None):
    obj=next((x for x in rows(s,'app_setting') if x.name==key),None)
    return obj.data if obj else (default or {})

def package_preview(s,shot_id):
    shot=get(s,'shot',shot_id);b=brief(s,shot.project_id);p=get(s,'project',shot.project_id)
    mid=shot.data.get('model_profile_id') or p.data.get('default_model_id')
    errors=[]
    model=get(s,'model_profile',mid) if mid else None
    if not model:errors.append('请选择视频模型档案')
    elif not model.data.get('verified_at'):errors.append('请先核对模型档案并登记核对日期')
    prompt=shot.data.get('prompt',''); rendered=prompt;upload=[];snapshot=[]
    binds=[x for x in rows(s,'shot_binding',shot.project_id) if x.shot_id==shot_id]
    slots={x.data.get('slot') for x in binds if x.data.get('asset_version_id')}
    if not {'主体','场景','道具'}<=slots:errors.append('主体、场景和道具必须绑定')
    for bind in sorted(binds,key=lambda x:x.seq):
        vid=bind.data.get('asset_version_id')
        if not vid:
            if bind.data.get('required',True):errors.append(bind.name+'缺少定稿资产')
            continue
        av=get(s,'asset_version',vid);asset=get(s,'asset',av.parent_id)
        if av.status!='final':errors.append(asset.name+'不是定稿版本')
        variants=[(asset,av)]
        if bind.data.get('with_accessories'):
            for link in rows(s,'asset_link',parent=asset.id):
                accessory=get(s,'asset',link.data['accessory_asset_id'])
                versions=[v for v in rows(s,'asset_version',parent=accessory.id) if v.status=='final']
                if not versions:errors.append(accessory.name+'固定配饰未定稿')
                else:variants.append((accessory,max(versions,key=lambda v:v.version)))
        for a,v in variants:
            subjects=[x for x in rows(s,'platform_subject',parent=v.id) if x.data.get('model_profile_id')==mid]
            subject=subjects[0].name if subjects else None
            files=rows(s,'asset_file',parent=v.id)
            if not files:errors.append(a.name+'缺少素材文件')
            numbers=[]
            for af in files:
                f=get(s,'file_object',af.data['file_id'])
                n=len(upload)+1;numbers.append(n)
                safe=re.sub(r'[^\w\u4e00-\u9fff-]','_',a.name)
                filename=f'{n:02d}_{bind.data.get("slot","素材")}_{safe}_v{v.version}{Path(f.data["original_name"]).suffix}'
                upload.append({'order':n,'asset_id':a.id,'asset_version_id':v.id,'file_id':f.id,'filename':filename,'subject':subject,'role':af.name,'is_audio':f.data.get('mime','').startswith('audio/')})
            replacement='@'+subject if subject else '、'.join('图'+str(n) for n in numbers)
            # Internal references remain stable after renaming.
            for token in ('{{asset:'+a.id+'}}','@'+a.name,'{{'+bind.data.get('slot','')+'}}'):
                rendered=rendered.replace(token,replacement)
            snapshot.append({'binding_id':bind.id,'asset_id':a.id,'asset_name':a.name,'asset_version_id':v.id,'version':v.version,'official_subject':subject,'slot':bind.data.get('slot')})
    if not prompt.strip():errors.append('请填写视频提示词')
    if re.search(r'\{\{.*?\}\}|@资产|\[待.*?\]',rendered):errors.append('提示词仍含未替换占位符')
    params={**p.data.get('generation_settings',{}),**shot.data.get('settings',{}),'duration_s':shot.duration_s,'ratio':b.get('aspect_ratio','9:16')}
    params.setdefault('resolution','720p');params.setdefault('candidates',1);params.setdefault('mode','参考生视频');params.setdefault('audio_strategy','后期补充')
    estimate=None
    if model:
        m=model.data;params['model']=model.name;params['model_version']=m.get('version','')
        for key,val,label in [('durations',shot.duration_s,'时长档位'),('ratios',params['ratio'],'画幅'),('resolutions',params['resolution'],'分辨率'),('modes',params['mode'],'模式')]:
            if val not in m.get(key,[]):errors.append(label+'不在模型档案支持范围内')
        image_count=sum(not x['is_audio'] for x in upload);audio_count=sum(x['is_audio'] for x in upload)
        if image_count>m.get('max_ref_images',0):errors.append('参考图片数量超过模型上限')
        if audio_count>m.get('max_audio',0):errors.append('音频数量超过模型上限')
        if m.get('credit_price') is not None and m.get('credit_to_cny') is not None:
            estimate=round(float(m['credit_price'])*float(m['credit_to_cny'])*int(params['candidates']),4)
        else:errors.append('请在档案中填写每候选积分和人民币换算单价')
    return {'shot_id':shot.id,'project_id':shot.project_id,'prompt':rendered,'params':params,'upload_order':upload,'bindings':snapshot,'estimate_cny':estimate,'errors':errors,'model_id':mid}

def budget_check(s,pid):
    b=brief(s,pid);settings=config(s,'budget',{'monthly_cap':500,'pause':True})
    if b.get('pause_on_budget',True) and spend(s,pid)>=float(b.get('budget_cap',0)):fail('项目预算已达上限，请核对费用流水或调整预算后导出',409)
    month=datetime.now().strftime('%Y-%m')
    if settings.get('pause',True) and spend(s,month=month)>=float(settings.get('monthly_cap',500)):fail('月度预算已达上限，已暂停导出',409)

def export_submission(s,shot_id,confirmation=False,nonce=None):
    if not confirmation:fail('请确认预计费用后导出提交包')
    shot=get(s,'shot',shot_id)
    # Retries of a single export intention return its immutable original.
    if nonce:
        existing=next((x for x in rows(s,'generation_record',shot.project_id) if x.data.get('nonce')==nonce and x.shot_id==shot_id),None)
        if existing:return jsonable(existing)
    if any(i not in get(s,'project',shot.project_id).data.get('completed_stages',[]) for i in range(1,5)):fail('请先通过简报、调研、分镜与资产关卡')
    preview=package_preview(s,shot_id)
    if preview['errors']:fail('；'.join(preview['errors']))
    budget_check(s,shot.project_id)
    lines=['# '+shot.name+' 官网提交说明','', '## 最终提示词',preview['prompt'],'','## 参数',json.dumps(preview['params'],ensure_ascii=False,indent=2),'','## 上传顺序与官网主体']
    for u in preview['upload_order']:lines.append(f'{u["order"]}. {u["filename"]} — '+('在提示词中手动点选 @'+u['subject'] if u['subject'] else '引用图'+str(u['order'])))
    lines+=['','官网生成后请下载视频，回到本条生成记录回传，并登记实际积分。档案估算不是实际账单。']
    file=storage.zip_files(s,shot.name+'-提交包',{'submission.md':'\n'.join(lines),'manifest.json':json.dumps(preview,ensure_ascii=False,indent=2)},[(u['filename'],u['file_id']) for u in preview['upload_order']])
    record=add(s,'generation_record',project_id=shot.project_id,shot_id=shot.id,parent_id=shot.id,name=shot.name,status='awaiting',data={**preview,'package_file_id':file.id,'nonce':nonce,'exported_at':now(),'input_hash':hashlib.sha256(json.dumps(preview,sort_keys=True).encode()).hexdigest()})
    shot.status='awaiting';touch(shot)
    return jsonable(record)

def review_candidate(s,cid,body):
    c=get(s,'candidate',cid);shot=get(s,'shot',c.shot_id)
    verdict=body.get('verdict');checks=body.get('checks',{})
    if verdict not in ['selected','rejected','rewrite','backup']:fail('审片结论无效')
    if verdict=='selected':
        if c.data.get('analysis_status')!='ready':fail('媒体尚未完成检测，暂不能选用')
        if not all(checks.get(x) for x in ['identity','contact','prop','continuity']):fail('四项人工审片检查必须全部通过')
        # Snapshot must still match current binding and prompt.
        original=get(s,'generation_record',c.parent_id)
        current=package_preview(s,shot.id)
        for key in ('prompt','bindings','params'):
            if original.data.get(key)!=current.get(key):fail('镜头输入已变化，请重新导出并回传候选；旧候选保留为历史',409)
        old=selected(s,shot.id)
        if old and old.id!=c.id:old.status='backup';s.flush()
        c.status='selected';shot.status='selected'
    elif verdict=='rewrite':c.status='backup';reset_shot(s,shot,'审片要求重写提示词')
    else:c.status=verdict
    add(s,'review',project_id=c.project_id,parent_id=c.id,shot_id=c.shot_id,name=verdict,status=verdict,data={'checks':checks,'issues':body.get('issues',[]),'in_point':body.get('in_point',0),'out_point':body.get('out_point')})
    touch(c);touch(shot)
    return jsonable(c)

def srt_time(t):
    t=round(float(t)*1000);return f'{t//3600000:02}:{t//60000%60:02}:{t//1000%60:02},{t%1000:03}'
def srt_draft(s,pid):
    return '\n\n'.join(f'{i+1}\n{srt_time(x["start"])} --> {srt_time(x["end"])}\n{x["data"]["line_text"]}' for i,x in enumerate([x for x in timeline(s,pid) if x['data'].get('line_text')]))+'\n'
def validate_srt(text,total=None):
    if not text.strip():return True
    parts=re.split(r'\n\s*\n',text.strip().replace('\r',''))
    for part in parts:
        lines=part.splitlines()
        if len(lines)<3 or not lines[0].isdigit():fail('SRT 格式错误，需编号、时间区间和文字')
        m=re.fullmatch(r'(\d{2}):(\d{2}):(\d{2}),(\d{3}) --> (\d{2}):(\d{2}):(\d{2}),(\d{3})',lines[1])
        if not m:fail('SRT 时间格式错误')
        v=list(map(int,m.groups()));a=v[0]*3600+v[1]*60+v[2]+v[3]/1000;b=v[4]*3600+v[5]*60+v[6]+v[7]/1000
        if a>=b or total and b>total+.1:fail('SRT 时间区间无效或超出成片')
    return True

def edit_package(s,pid,srt=None):
    if gate_errors(s,pid,5):fail('请先为所有镜头选用有效候选')
    project=get(s,'project',pid);content=[];sources=[];manifest=[]
    for i,sh in enumerate(shots(s,pid)):
        c=selected(s,sh.id)
        enhanced=sorted([x for x in rows(s,'candidate',pid) if x.data.get('enhanced_parent_id')==c.id and x.data.get('approved') and x.data.get('analysis_status')=='ready'],key=lambda x:x.created_at)
        chosen=enhanced[-1] if enhanced else c
        f=get(s,'file_object',chosen.data['file_id']);filename=f'{i+1:02d}_{sh.name}.mp4';sources.append((filename,f.id))
        reviews=rows(s,'review',parent=c.id)
        content.append(f'{i+1}. {sh.name} / {sh.duration_s}s / {sh.data.get("sound", "")} / 审片标记：'+json.dumps([r.data for r in reviews],ensure_ascii=False))
        manifest.append({'shot_id':sh.id,'candidate_id':chosen.id,'file_id':f.id,'duration_s':sh.duration_s})
    for asset in rows(s,'asset'):
        if asset.project_id not in (None,pid) or asset.data.get('type') not in ['VOICE','SFX','BGM']:continue
        for v in rows(s,'asset_version',parent=asset.id):
            if v.status=='final':
                if not v.data.get('license_note'):fail('声音资产缺少授权说明：'+asset.name)
                for af in rows(s,'asset_file',parent=v.id):
                    f=get(s,'file_object',af.data['file_id']);sources.append(('声音/'+asset.name+Path(f.data['original_name']).suffix,f.id))
    srt=srt if srt is not None else project.data.get('srt',srt_draft(s,pid))
    validate_srt(srt,sum(x.duration_s for x in shots(s,pid)))
    content+=['','在剪映内完成剪辑、配音与字幕对齐。参考建议：对白期间适度压低 BGM，避免重复环境声；字幕避开脸部和平台遮挡。导出后完整播放并实际试听。',project.data.get('edit_notes','')]
    file=storage.zip_files(s,project.name+'-剪映素材包',{'字幕初稿.srt':srt,'剪辑说明.md':'\n'.join(content),'manifest.json':json.dumps(manifest,ensure_ascii=False,indent=2)},sources)
    ep=add(s,'edit_package',project_id=pid,name='剪映素材包',version=len(rows(s,'edit_package',pid))+1,status='exported',data={'file_id':file.id,'manifest':manifest,'srt':srt,'notes':project.data.get('edit_notes','')})
    return jsonable(ep)

METRIC_KEYS=['plays','retain_3s','completion','avg_watch_s','likes','comments','shares','saves']
def csv_preview(file):
    import pandas as pd
    for enc in ['utf-8-sig','gb18030']:
        try:df=pd.read_csv(file,encoding=enc).fillna('');break
        except UnicodeDecodeError:continue
    else:fail('CSV 编码无法识别，请使用 UTF-8 或 GBK')
    if len(df)>50000:fail('CSV 超过 50000 行，请分批导入')
    return {'columns':list(df.columns),'rows':df.head(10).to_dict('records'),'total':len(df)}
def import_metrics(s,pid,file_id,release_id,mapping,period,row_index=None):
    import pandas as pd
    rel=get(s,'release',release_id)
    if rel.project_id!=pid:fail('发布记录不属于本项目')
    f=get(s,'file_object',file_id);preview=csv_preview(storage.path_for(f))
    for col in mapping.values():
        if col and col not in preview['columns']:fail('字段映射引用了不存在的列')
    if not any(mapping.get(k) for k in METRIC_KEYS):fail('请至少映射一个指标字段')
    fingerprint=hashlib.sha256(json.dumps([file_id,release_id,mapping,period,0 if row_index is None else int(row_index)],sort_keys=True).encode()).hexdigest()
    existing=next((x for x in rows(s,'metric_snapshot',pid) if x.data.get('fingerprint')==fingerprint),None)
    if existing:return jsonable(existing)
    for enc in ['utf-8-sig','gb18030']:
        try:df=pd.read_csv(storage.path_for(f),encoding=enc);break
        except UnicodeDecodeError:continue
    if len(df)>1 and row_index is None:fail('CSV 含多行，请选择对应当前成片与统计窗口的数据行，不能混加')
    row_index=0 if row_index is None else int(row_index)
    if row_index<0 or row_index>=len(df):fail('选择的 CSV 数据行不存在')
    data={k:None for k in METRIC_KEYS}
    row=df.iloc[row_index]
    for key,col in mapping.items():
        if key not in METRIC_KEYS or not col:continue
        raw=row.get(col)
        if pd.isna(raw):continue
        v=str(raw).strip().replace(',','');percent=v.endswith('%')
        try:num=float(v.rstrip('%'))
        except ValueError:fail('指标不是有效数字：'+col)
        if not math.isfinite(num) or num<0:fail('指标必须是非负有限数：'+col)
        if key in ['retain_3s','completion']:
            num=num/100 if percent else num
            if num>1:fail(col+'请填 0–1 的比例或带 % 的百分比')
        data[key]=num
    snapshot=add(s,'metric_snapshot',project_id=pid,parent_id=release_id,name=period,status='imported',data={**data,'period':period,'mapping':mapping,'file_id':file_id,'row_index':row_index,'fingerprint':fingerprint})
    return jsonable(snapshot)

def archive_project(s,pid,fid):
    final=get(s,'final_cut',fid)
    if final.project_id!=pid or final.status!='publishable':fail('仅已通过检查的成片可归档')
    existing=rows(s,'archive',parent=fid)
    if existing:return jsonable(existing[0])
    kinds=['project','brief','gate_event','reference','evidence','story_direction','script','shot','asset','asset_version','asset_file','platform_subject','shot_binding','generation_record','candidate','review','edit_package','final_cut','cost_entry']
    metadata={k:[jsonable(x) for x in rows(s,k,pid)] for k in kinds}
    # Include globally reused assets and their immutable version file manifests.
    vids={b.data.get('asset_version_id') for b in rows(s,'shot_binding',pid)}-{None}
    for vid in vids:
        v=get(s,'asset_version',vid)
        if not any(x['id']==vid for x in metadata['asset_version']):metadata['asset_version'].append(jsonable(v))
        a=get(s,'asset',v.parent_id)
        if not any(x['id']==a.id for x in metadata['asset']):metadata['asset'].append(jsonable(a))
        for af in rows(s,'asset_file',parent=vid):
            if not any(x['id']==af.id for x in metadata['asset_file']):metadata['asset_file'].append(jsonable(af))
    sources=[('成片.mp4',final.data['file_id'])]
    for af in metadata['asset_file']:
        fo=get(s,'file_object',af['data']['file_id']);sources.append(('资产/'+af['id']+Path(fo.data['original_name']).suffix,fo.id))
    rights=[{'name':a['name'],'source':v['data'].get('source'),'license_note':v['data'].get('license_note')} for a in metadata['asset'] for v in metadata['asset_version'] if v['parent_id']==a['id']]
    file=storage.zip_files(s,get(s,'project',pid).name+'-交付归档',{'项目元数据.json':json.dumps(metadata,ensure_ascii=False,indent=2),'资产授权.json':json.dumps(rights,ensure_ascii=False,indent=2),'质检记录.json':json.dumps(final.data,ensure_ascii=False,indent=2)},sources)
    return jsonable(add(s,'archive',project_id=pid,parent_id=fid,name='交付归档',status='ready',data={'file_id':file.id}))
