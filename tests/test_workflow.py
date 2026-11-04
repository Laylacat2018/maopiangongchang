"""真实文件端到端验收；媒体为 FFmpeg 合成测试条，不表示 AI 内容生成能力。"""
import os, tempfile, time, zipfile, io, json, subprocess, hashlib
from pathlib import Path
import pytest

TEST_ROOT=Path(tempfile.mkdtemp(prefix='catstudio-acceptance-'))
os.environ['CATSTUDIO_DATA']=str(TEST_ROOT/'data')
from fastapi.testclient import TestClient
from catstudio.main import app
from catstudio.db import engine,MODELS
from sqlmodel import Session,select
from PIL import Image

@pytest.fixture(scope='module')
def client():
    with TestClient(app) as c:yield c

def ok(r,code=200):
    assert r.status_code==code,r.text
    return r.json()
def post(c,path,payload=None):return ok(c.post('/api'+path,json=payload or {}))
def put(c,k,obj,**changes):return ok(c.put('/api/items/'+k+'/'+obj['id'],json=changes))
def create(c,k,**body):return post(c,'/items/'+k,body)
def state(c):return ok(c.get('/api/state'))
def wait(c,tid):
    for _ in range(240):
        task=next(t for t in state(c)['task'] if t['id']==tid)
        if task['status']=='success':return task
        if task['status']=='failed':pytest.fail(task['data'].get('error'))
        time.sleep(.25)
    pytest.fail('后台任务超时')
def upload(c,path):
    with path.open('rb') as f:return ok(c.post('/api/upload',files={'file':(path.name,f)}))
def inspect_zip(c,fid):
    r=c.get('/files/'+fid);assert r.status_code==200
    z=zipfile.ZipFile(io.BytesIO(r.content));assert z.testzip() is None;return z

@pytest.fixture(scope='module')
def media_files():
    image=TEST_ROOT/'cat-test.png';Image.new('RGB',(300,300),(180,130,70)).save(image)
    clip=TEST_ROOT/'clip.mp4';final=TEST_ROOT/'final.mp4'
    for target,w,h,duration in [(clip,360,640,6),(final,1080,1920,24)]:
        args=['ffmpeg','-y','-v','error','-f','lavfi','-i',f'color=c=0x52806c:s={w}x{h}:r=30:d={duration}','-f','lavfi','-i',f'sine=frequency=440:duration={duration}','-vf',"drawbox=x='20+mod(t*25,150)':y=200:w=80:h=80:color=orange:t=fill",'-c:v','libx264','-preset','ultrafast','-pix_fmt','yuv420p','-c:a','aac','-shortest',str(target)]
        subprocess.run(args,check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    return image,clip,final

@pytest.fixture(scope='module')
def production(client,media_files):
    c=client;img,clip,final=media_files
    p=post(c,'/projects',{'name':'端到端自测·说好六点下班'})
    pid=p['id'];b=next(x for x in state(c)['brief'] if x['project_id']==pid)
    put(c,'brief',b,data={**b['data'],'audience':'22–35 岁城市上班族，经常临时加班','duration_min_s':24,'duration_max_s':24})
    post(c,f'/projects/{pid}/gate/1')
    ref=create(c,'reference',project_id=pid,name='加班的共鸣',data={'url':'https://www.douyin.com/video/test','title':'说好六点下班','is_cited':True})
    create(c,'evidence',project_id=pid,parent_id=ref['id'],name='评论',data={'text':'下班前突然被留下太真实了','likes':20,'nickname':'不应保存'})
    create(c,'story_direction',project_id=pid,name='说好六点下班',data={'title':'说好六点下班','resonance':'临时加班','cat_acting':'把罐子挪向自己','is_selected':True,'cited_reference_ids':[ref['id']]})
    post(c,f'/projects/{pid}/gate/2')
    script=create(c,'script',project_id=pid,name='剧情稿',status='confirmed',data={'summary':'草帽猫准备离开，收到通知，只挪动罐子，克制地继续工作。'})
    ss=[]
    for i,title in enumerate(['准备下班','扒饮料罐','休息转头','回到工位']):
        sh=create(c,'shot',project_id=pid,parent_id=script['id'],name=title,seq=i,duration_s=6,data={'action':'猫的前爪轻推罐子','end_state':'罐子停在两爪间','line_text':'这一点，有点多。' if i==3 else '', 'prompt':'{{主体}}在{{场景}}中，前爪轻推{{道具}}。','checks':{'single':True,'anatomy':True,'continuity':True}});ss.append(sh)
    post(c,f'/projects/{pid}/gate/3')
    assets=[];versions=[]
    f=upload(c,img)
    for ty,name in [('CHAR','草帽猫'),('SCN','办公室'),('PROP','饮料罐')]:
        a=create(c,'asset',project_id=pid,name=name,data={'type':ty});assets.append(a)
        v=create(c,'asset_version',project_id=pid,parent_id=a['id'],name=name,status='pending',data={'source':'AI生成','license_note':'自动验收合成占位素材，不用于发布'})
        create(c,'asset_file',project_id=pid,parent_id=v['id'],name='主图',data={'file_id':f['id']})
        v=put(c,'asset_version',v,status='final');versions.append(v)
    for sh in ss:
        for i,slot in enumerate(['主体','场景','道具']):create(c,'shot_binding',project_id=pid,shot_id=sh['id'],parent_id=sh['id'],name=slot,seq=i,data={'slot':slot,'required':True,'asset_version_id':versions[i]['id']})
    post(c,f'/projects/{pid}/gate/4')
    model=create(c,'model_profile',name='合成验收模型',data={'kind':'video','site_url':'https://example.com/','version':'test-only','modes':['参考生视频'],'max_ref_images':3,'max_audio':0,'durations':[6],'resolutions':['720p'],'ratios':['9:16'],'credit_price':10,'credit_to_cny':.01,'verified_at':'2026-11-04'})
    p=next(x for x in state(c)['project'] if x['id']==pid)
    put(c,'project',p,data={**p['data'],'default_model_id':model['id']})
    create(c,'platform_subject',project_id=pid,parent_id=versions[0]['id'],name='草帽猫官方主体',data={'model_profile_id':model['id']})
    file=upload(c,clip);records=[];cs=[]
    for sh in ss:
        preview=ok(c.get('/api/shots/'+sh['id']+'/preview'));assert not preview['errors'];assert '@草帽猫官方主体' in preview['prompt'];assert '图2' in preview['prompt'];assert '{{' not in preview['prompt']
        rec=post(c,'/shots/'+sh['id']+'/export',{'confirmed':True,'nonce':sh['id']});records.append(rec)
        rec2=post(c,'/shots/'+sh['id']+'/export',{'confirmed':True,'nonce':sh['id']});assert rec['id']==rec2['id']
        z=inspect_zip(c,rec['data']['package_file_id']);assert 'submission.md' in z.namelist();assert len(z.namelist())==5;assert '@草帽猫官方主体' in z.read('submission.md').decode()
        cand=post(c,'/generations/'+rec['id']+'/candidates',{'file_id':file['id'],'credits':10});wait(c,cand['task_id']);cs.append(cand)
        assert c.post('/api/candidates/'+cand['id']+'/review',json={'verdict':'selected','checks':{}}).status_code==422
        post(c,'/candidates/'+cand['id']+'/review',{'verdict':'selected','checks':{'identity':True,'contact':True,'prop':True,'continuity':True}})
    post(c,f'/projects/{pid}/gate/5')
    ep=post(c,f'/projects/{pid}/edit-package');z=inspect_zip(c,ep['data']['file_id']);assert len([x for x in z.namelist() if x.endswith('.mp4')])==4;assert b'00:00:18,000 --> 00:00:24,000' in z.read('字幕初稿.srt')
    finalf=upload(c,final);fc=post(c,f'/projects/{pid}/finals',{'file_id':finalf['id'],'edit_package_id':ep['id'],'edit_version':'v1','platform_variant':'抖音'});wait(c,fc['task_id'])
    actual=next(x for x in state(c)['final_cut'] if x['id']==fc['id']);assert actual['data']['auto_checks']['passed'],actual
    post(c,'/finals/'+fc['id']+'/confirm',{'checks':{'motion':True,'audio':True,'subtitle':True}})
    post(c,f'/projects/{pid}/gate/6')
    arc=post(c,f'/projects/{pid}/archive/'+fc['id']);z=inspect_zip(c,arc['data']['file_id']);assert '成片.mp4' in z.namelist();assert '质检记录.json' in z.namelist();assert b'encrypted_key' not in z.read('项目元数据.json')
    release=create(c,'release',project_id=pid,parent_id=fc['id'],name='抖音',data={'url':'https://www.douyin.com/video/test-release','published_at':'2026-11-04T08:00:00'})
    csv=TEST_ROOT/'指标.csv';csv.write_text('播放,三秒,完播,平均,赞,评,分享,收藏\n100,72%,20%,10.8,5,2,1,1\n',encoding='utf-8-sig');csvf=upload(c,csv)
    mapping=dict(zip(['plays','retain_3s','completion','avg_watch_s','likes','comments','shares','saves'],['播放','三秒','完播','平均','赞','评','分享','收藏']))
    snap=post(c,f'/projects/{pid}/metrics',{'file_id':csvf['id'],'release_id':release['id'],'mapping':mapping,'period':'7天'})
    snap2=post(c,f'/projects/{pid}/metrics',{'file_id':csvf['id'],'release_id':release['id'],'mapping':mapping,'period':'7天'});assert snap['id']==snap2['id'];assert snap['data']['completion']==.2
    for t,r in [(0,1),(3,.72),(6,.5),(24,.2)]:create(c,'retention_point',project_id=pid,parent_id=snap['id'],data={'second':t,'ratio':r})
    retro=create(c,'retro',project_id=pid,parent_id=release['id'],name='复盘',status='待验证',data={'observation':'前6秒留存下降','hypothesis':'动作信息给得太慢','evidence':'真实测试CSV，不用于业务推断','exp_goal':'验证首镜动作','exp_keep':'角色、受众、时长','exp_change':'只改首镜起始动作'})
    post(c,f'/projects/{pid}/gate/7');nextp=post(c,f'/projects/{pid}/next',{'retro_id':retro['id']});assert nextp['data']['stage']==1
    return {'pid':pid,'shots':ss,'assets':assets,'versions':versions,'records':records,'candidates':cs,'model':model,'final':fc,'edit':ep,'img':f,'video':file,'release':release}

def test_01_complete_production_chain(production,client):
    p=production;data=state(client);proj=next(x for x in data['project'] if x['id']==p['pid'])
    assert proj['status']=='complete';assert proj['data']['completed_stages']==list(range(1,8))
    assert data['timelines'][p['pid']][3]['start']==18;assert data['timelines'][p['pid']][3]['end']==24
    costs=[x for x in data['cost_entry'] if x['project_id']==p['pid']];assert sum(x['amount_fen'] for x in costs)==40
    assert data['evidence'][0]['data'].get('nickname') is None

def test_02_stage_gates_and_missing_fields(client):
    p=post(client,'/projects',{'name':'关卡测试'});pid=p['id']
    assert client.post(f'/api/projects/{pid}/gate/1').status_code==422
    assert client.post(f'/api/projects/{pid}/gate/5').status_code==422
    assert client.post('/api/llm',json={'project_id':pid,'purpose':'script','confirmed':False}).status_code==422

def test_03_version_immutability_and_global_library(production,client):
    p=production;c=client;v=p['versions'][0]
    assert c.put('/api/items/asset_version/'+v['id'],json={'data':{'source':'其他'}}).status_code==409
    v2=create(c,'asset_version',project_id=p['pid'],parent_id=v['parent_id'],version=2,status='pending',data={'source':'自拍'})
    create(c,'asset_file',project_id=p['pid'],parent_id=v2['id'],name='主图',data={'file_id':p['img']['id']});put(c,'asset_version',v2,status='final')
    data=state(c);assert all(x['data']['asset_version_id']==v['id'] for x in data['shot_binding'] if x['project_id']==p['pid'] and x['data']['slot']=='主体')
    assert c.delete('/api/items/asset/'+p['assets'][0]['id']).status_code==409
    assert c.put('/api/items/generation_record/'+p['records'][0]['id'],json={'data':{}}).status_code==403

def test_04_idempotent_ingest_and_cost(production,client):
    p=production;c=client;before=len(state(c)['cost_entry'])
    r=post(c,'/generations/'+p['records'][0]['id']+'/candidates',{'file_id':p['video']['id'],'credits':10})
    assert r['id']==p['candidates'][0]['id'];assert len(state(c)['cost_entry'])==before
    assert upload(c,Path(p['img']['data']['rel_path']) if False else TEST_ROOT/'cat-test.png')['id']==p['img']['id']

def test_05_budget_pause_and_model_validation(production,client):
    p=production;c=client
    post(c,'/settings/budget',{'monthly_cap':0,'pause':True})
    assert c.post('/api/shots/'+p['shots'][0]['id']+'/export',json={'confirmed':True,'nonce':'overbudget'}).status_code==409
    post(c,'/settings/budget',{'monthly_cap':500,'pause':True})
    m=next(x for x in state(c)['model_profile'] if x['id']==p['model']['id'])
    put(c,'model_profile',m,data={**m['data'],'max_ref_images':1})
    preview=ok(c.get('/api/shots/'+p['shots'][0]['id']+'/preview'));assert '参考图片数量超过模型上限' in preview['errors']
    assert c.post('/api/shots/'+p['shots'][0]['id']+'/export',json={'confirmed':True}).status_code==422
    put(c,'model_profile',m,data=m['data'])

def test_06_enhancement_parent_and_archive(production,client):
    p=production;c=client
    settings=ok(c.get('/api/candidates/'+p['candidates'][0]['id']+'/enhancement'));assert settings['source_file_id']==p['video']['id']
    x=post(c,'/generations/'+p['records'][0]['id']+'/candidates',{'file_id':p['video']['id'],'enhanced_parent_id':p['candidates'][0]['id'],'amount_cny':0.2});wait(c,x['task_id'])
    post(c,'/candidates/'+x['id']+'/review',{'verdict':'selected','checks':dict.fromkeys(['identity','contact','prop','continuity'],True)})
    data=state(c);assert len([r for r in data['candidate'] if r['shot_id']==p['shots'][0]['id'] and r['status']=='selected'])==1
    ep=post(c,f'/projects/{p["pid"]}/edit-package');assert ep['data']['manifest'][0]['candidate_id']==x['id']

def test_07_srt_invalid_and_upload_safety(client,production):
    p=production;c=client
    r=c.post(f'/api/projects/{p["pid"]}/edit-package',json={'srt':'1\n00:00:03,000 --> 00:00:01,000\nbad'});assert r.status_code==422
    r=c.post('/api/upload',files={'file':('bad.png',b'not an image')});assert r.status_code==422
    assert c.get('/files/../../Windows/win.ini').status_code!=200 or 'text/html' in c.get('/files/../../Windows/win.ini').headers.get('content-type','')
    assert c.post('/api/projects',json={'name':'external'},headers={'origin':'https://evil.example'}).status_code==403

def test_08_backup_restore_and_zip_slip(client,production):
    p=production;c=client
    t=post(c,'/backup');done=wait(c,t['id']);fid=done['data']['file_id'];z=inspect_zip(c,fid);assert 'catstudio.db' in z.namelist()
    count=len(state(c)['project']);extra=post(c,'/projects',{'name':'恢复后应消失的测试项目'})
    post(c,'/restore',{'file_id':fid,'confirmed':True});assert len(state(c)['project'])==count
    evil=TEST_ROOT/'evil.zip'
    with zipfile.ZipFile(evil,'w') as z:
        z.writestr('catstudio.db',b'bad');z.writestr('backup-manifest.json',json.dumps({'format':'catstudio-backup'}));z.writestr('../escape.txt','bad')
    f=upload(c,evil);assert c.post('/api/restore',json={'file_id':f['id'],'confirmed':True}).status_code==422

def test_09_conflict_and_upstream_invalidates_selection(client,production):
    p=production;c=client;sh=next(x for x in state(c)['shot'] if x['id']==p['shots'][0]['id'])
    assert c.put('/api/items/shot/'+sh['id'],json={'revision':0,'name':'conflict'}).status_code==409
    put(c,'shot',sh,data={**sh['data'],'prompt':'{{主体}}在{{场景}}向右推{{道具}}。'})
    data=state(c);assert not any(x['shot_id']==sh['id'] and x['status']=='selected' for x in data['candidate'])
    assert next(x for x in data['final_cut'] if x['id']==p['final']['id'])['status']=='historical'
    assert c.post('/api/candidates/'+p['candidates'][0]['id']+'/review',json={'verdict':'selected','checks':dict.fromkeys(['identity','contact','prop','continuity'],True)}).status_code==409

def test_10_credential_encryption_and_template_versions(client):
    c=client
    post(c,'/settings/llm_text',{'provider':'openai','base_url':'http://127.0.0.1:1/v1','model':'local-test','api_key':'synthetic-test-key-not-real'})
    data=state(c);assert data['settings']['llm_text']['has_key'];assert 'encrypted_key' not in data['settings']['llm_text'];assert 'synthetic-test-key-not-real' not in json.dumps(data)
    with Session(engine) as s:
        cfg=s.exec(select(MODELS['app_setting']).where(MODELS['app_setting'].name=='llm_text')).first();assert 'synthetic-test-key-not-real' not in cfg.data['encrypted_key']
    t=next(x for x in data['prompt_template'] if x['name']=='script');t2=put(c,'prompt_template',t,data={**t['data'],'body':t['data']['body']+'\n新的约束。'});assert t2['version']==t['version']+1;assert t2['id']!=t['id']

def test_11_persistent_sqlite_reopen(client,production):
    from sqlalchemy import create_engine,text
    other=create_engine('sqlite:///'+str(TEST_ROOT/'data'/'catstudio.db'))
    with other.connect() as conn:assert conn.execute(text('select count(*) from generation_record')).scalar()>=4
    other.dispose()

def test_12_csv_multirow_and_comments_privacy(client,production):
    c=client;p=production
    f=TEST_ROOT/'multi.csv';f.write_text('播放,完播\n80,10%\n200,50%\n',encoding='utf-8-sig');fo=upload(c,f)
    body={'file_id':fo['id'],'release_id':p['release']['id'],'mapping':{'plays':'播放','completion':'完播'},'period':'第2条数据'}
    assert c.post(f'/api/projects/{p["pid"]}/metrics',json=body).status_code==422
    result=post(c,f'/projects/{p["pid"]}/metrics',{**body,'row_index':1});assert result['data']['plays']==200;assert result['data']['completion']==.5;assert result['data']['likes'] is None
    f=TEST_ROOT/'comments.csv';f.write_text('昵称,文字,赞,头像\n用户1,这只猫太像我了,20,private\n用户2,有点多,3,private\n',encoding='gb18030');fo=upload(c,f)
    body={'file_id':fo['id'],'text_column':'文字','likes_column':'赞'}
    r=post(c,f'/projects/{p["pid"]}/comments-csv',body);assert r['imported']==2
    assert post(c,f'/projects/{p["pid"]}/comments-csv',body)['imported']==0
    for e in state(c)['evidence']:
        assert 'nickname' not in e['data'];assert '头像' not in e['data']

def test_13_asset_license_and_nonfinal_binding(client,production):
    c=client;p=production
    a=create(c,'asset',project_id=p['pid'],name='环境声',data={'type':'SFX'})
    r=c.post('/api/items/asset_version',json={'parent_id':a['id'],'status':'pending','data':{'source':'自录'}});assert r.status_code==422
    v=create(c,'asset_version',project_id=p['pid'],parent_id=p['assets'][0]['id'],status='pending',data={'source':'自拍'})
    b=next(x for x in state(c)['shot_binding'] if x['project_id']==p['pid'])
    assert c.put('/api/items/shot_binding/'+b['id'],json={'data':{**b['data'],'asset_version_id':v['id']}}).status_code==422

def test_14_replacing_selected_candidate_is_atomic(client,production,media_files):
    c=client;p=production;sh=p['shots'][2];rec=p['records'][2]
    f=TEST_ROOT/'second.mp4';data=media_files[1].read_bytes()+b'variant';f.write_bytes(data);fo=upload(c,f)
    new=post(c,'/generations/'+rec['id']+'/candidates',{'file_id':fo['id'],'credits':2});wait(c,new['task_id'])
    post(c,'/candidates/'+new['id']+'/review',{'verdict':'selected','checks':dict.fromkeys(['identity','contact','prop','continuity'],True)})
    cs=[x for x in state(c)['candidate'] if x['shot_id']==sh['id']];assert len([x for x in cs if x['status']=='selected'])==1;assert next(x for x in cs if x['id']==new['id'])['status']=='selected'

def test_15_product_placement_changes_only_target_shot(client,production):
    c=client;p=production;target=p['shots'][1];other=p['shots'][3]
    a=create(c,'asset',project_id=p['pid'],name='示例商品',data={'type':'PROD'});v=create(c,'asset_version',project_id=p['pid'],parent_id=a['id'],status='pending',data={'source':'自拍'})
    create(c,'asset_file',project_id=p['pid'],parent_id=v['id'],name='主图',data={'file_id':p['img']['id']});put(c,'asset_version',v,status='final')
    post(c,f'/projects/{p["pid"]}/placement',{'shot_id':target['id'],'asset_version_id':v['id'],'checks':dict.fromkeys(['package','pattern','contact','identity'],True)})
    cs=state(c)['candidate'];assert not any(x['shot_id']==target['id'] and x['status']=='selected' for x in cs);assert any(x['shot_id']==other['id'] and x['status']=='selected' for x in cs)
    assert any(x['id']==p['candidates'][1]['id'] for x in cs)

def test_16_bad_final_is_not_publishable(client,production,media_files):
    c=client;p=production;clip=upload(c,media_files[1]);f=post(c,f'/projects/{p["pid"]}/finals',{'file_id':clip['id'],'edit_package_id':p['edit']['id'],'edit_version':'bad','platform_variant':'主版'});wait(c,f['task_id'])
    fc=next(x for x in state(c)['final_cut'] if x['id']==f['id']);assert not fc['data']['auto_checks']['passed']
    assert c.post('/api/finals/'+f['id']+'/confirm',json={'checks':dict.fromkeys(['motion','audio','subtitle'],True)}).status_code in [409,422]
