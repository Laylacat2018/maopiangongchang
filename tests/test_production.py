"""V1.1 workflow invariants; synthetic media is never presented as AI output."""
import json
import uuid
import pytest
from sqlmodel import Session
from test_workflow import client, media_files, production, post, put, create, state, upload, ok, wait, inspect_zip
from catstudio import production as prod
from catstudio.db import engine, get, rows


@pytest.fixture
def imported(client, media_files, monkeypatch):
    monkeypatch.setattr(prod, 'verified_media', lambda key: media_files[0])
    nonce = str(uuid.uuid4())
    p = post(client, '/production/example/import', {'nonce': nonce})
    again = post(client, '/production/example/import', {'nonce': nonce})
    assert p['id'] == again['id']
    return p


def test_example_gracefully_handles_missing_media(client, tmp_path, monkeypatch):
    monkeypatch.setenv('CATSTUDIO_EXAMPLES_DIR', str(tmp_path))
    example = ok(client.get('/api/production/example'))
    assert len(example['shots']) == 8
    assert example['cost']['cash_cny'] is None
    assert not any(x['available'] for x in example['media'].values())
    assert 'Wan2.1' in example['provenance']
    assert client.get('/api/production/example/media/final').status_code == 404
    assert client.get('/api/production/example/media/not-allowlisted').status_code == 404
    before = len(state(client)['project'])
    assert client.post('/api/production/example/import', json={'nonce': str(uuid.uuid4())}).status_code == 404
    assert len(state(client)['project']) == before


def test_import_is_draft_and_preserves_no_historical_approvals(client, imported):
    pid = imported['id']; data = state(client)
    assert imported['data']['completed_stages'] == []
    assert not any(x['project_id'] == pid for x in data['candidate'] + data['generation_record'] + data['gate_event'])
    ss = [x for x in data['shot'] if x['project_id'] == pid]
    assert len(ss) == 8
    assert sum(x['duration_s'] for x in ss) == 38
    assert all(not x['data'].get('keyframe_review') for x in ss)
    assert all(not any(x['data']['checks'].values()) for x in ss)
    assert all(x['data']['image_prompt'] and x['data']['prompt'] for x in ss)
    role=next(x for x in data['asset'] if x['project_id']==pid)
    assert role['data']['locked_traits'] and role['data']['prompt']
    assert client.post(f'/api/projects/{pid}/gate/4', json={}).status_code == 422


def test_first_frame_review_and_membership_submission(client, imported):
    pid = imported['id']
    sh = next(x for x in state(client)['shot'] if x['project_id'] == pid)
    model = create(client, 'model_profile', name='会员验收模型', data={
        'kind':'video', 'version':'synthetic-test', 'site_url':'https://example.com',
        'verified_at':'2026-11-06', 'billing_mode':'membership', 'credit_price':12,
        'credit_to_cny':None, 'max_ref_images':1, 'max_audio':0,
        'durations':[5], 'ratios':['9:16'], 'resolutions':['720p'], 'modes':['首帧图生视频']})
    sh = put(client, 'shot', sh, data={**sh['data'], 'model_profile_id':model['id'], 'generation_duration_s':5})
    preview = ok(client.get(f'/api/shots/{sh["id"]}/preview'))
    assert preview['errors'] and '分镜图' in '；'.join(preview['errors'])
    checks = dict.fromkeys(prod.FRAME_CHECKS, True)
    assert client.post(f'/api/production/shots/{sh["id"]}/frame-review', json={'revision':sh['revision'], 'checks':{}}).status_code == 422
    sh = post(client, f'/production/shots/{sh["id"]}/frame-review', {'revision':sh['revision'], 'checks':checks})
    preview = ok(client.get(f'/api/shots/{sh["id"]}/preview'))
    assert preview['errors'] == []
    assert len(preview['upload_order']) == 1
    assert preview['estimate_cny'] is None and preview['estimate_credits'] == 12
    assert preview['params']['duration_s'] == 5 and preview['edit_duration_s'] == 4
    assert client.post(f'/api/production/shots/{sh["id"]}/frame-review', json={'revision':sh['revision']-1,'checks':checks}).status_code == 409
    # Earlier gates are covered end-to-end by test_workflow; isolate the new ZIP route here.
    with Session(engine) as s:
        p=get(s,'project',pid);p.data={**p.data,'completed_stages':[1,2,3,4],'stage':5};s.commit()
    record=post(client,f'/shots/{sh["id"]}/export',{'confirmed':True,'nonce':str(uuid.uuid4())})
    bundle=inspect_zip(client,record['data']['package_file_id'])
    assert len([name for name in bundle.namelist() if name.endswith('.png')])==1
    manifest=json.loads(bundle.read('manifest.json'))
    assert manifest['estimate_cny'] is None and manifest['estimate_credits']==12
    assert manifest['image_prompt'] and manifest['edit_duration_s']==4
    assert '待核价' in bundle.read('submission.md').decode('utf-8')
    sh=next(x for x in state(client)['shot'] if x['id']==sh['id'])
    sh = put(client, 'shot', sh, data={**sh['data'], 'image_prompt':'新的静帧状态'})
    assert not sh['data']['keyframe_review']
    assert '分镜图' in '；'.join(ok(client.get(f'/api/shots/{sh["id"]}/preview'))['errors'])
    # A generic update cannot forge an approval.
    sh = put(client, 'shot', sh, data={**sh['data'],'keyframe_review':{'checks':checks,'fingerprint':'forged'}})
    assert not sh['data']['keyframe_review']
    sh=post(client,f'/production/shots/{sh["id"]}/frame-review',{'revision':sh['revision'],'checks':checks})
    assert ok(client.get(f'/api/shots/{sh["id"]}/preview'))['errors']==[]
    with Session(engine) as s:
        from catstudio.db import add
        from catstudio import services as svc
        current=svc.package_preview(s,sh['id'])
        record=add(s,'generation_record',project_id=pid,shot_id=sh['id'],data=current)
        add(s,'candidate',project_id=pid,shot_id=sh['id'],parent_id=record.id,status='selected',data={'analysis_status':'ready'})
        # Account profile edits after selection must also block handoff, even if the shot itself was untouched.
        m=get(s,'model_profile',model['id']);m.data={**m.data,'version':'changed-account-model'};s.commit()
        assert any(sh['name'] in e and '输入已变化' in e for e in svc.gate_errors(s,pid,5))


def test_replacing_frame_invalidates_selection_and_final(client, media_files):
    # Use an independent imported shot so the established legacy end-to-end case stays intact.
    p = post(client, '/projects', {'name':'首帧失效测试'})
    sh = create(client, 'shot', project_id=p['id'], name='测试镜', duration_s=5, data={'action':'眨眼'})
    video = upload(client, media_files[1])
    assert client.post(f'/api/production/shots/{sh["id"]}/frame',json={'file_id':video['id'],'revision':sh['revision']}).status_code == 422
    image = upload(client, media_files[0])
    with Session(engine) as s:
        from catstudio.db import add
        add(s,'candidate',project_id=p['id'],shot_id=sh['id'],status='selected')
        add(s,'final_cut',project_id=p['id'],status='publishable')
        obj=get(s,'project',p['id']);obj.data={**obj.data,'completed_stages':[1,2,3,4,5,6],'stage':7};s.commit()
    post(client, f'/production/shots/{sh["id"]}/frame', {'file_id':image['id'],'revision':sh['revision']})
    data=state(client)
    assert next(x for x in data['candidate'] if x['project_id']==p['id'])['status']=='backup'
    assert next(x for x in data['final_cut'] if x['project_id']==p['id'])['status']=='historical'
    assert next(x for x in data['project'] if x['id']==p['id'])['data']['completed_stages']==[1,2,3]


def test_unpriced_candidate_and_export_never_report_zero(client, imported, media_files):
    pid=imported['id'];sh=next(x for x in state(client)['shot'] if x['project_id']==pid)
    model=create(client,'model_profile',name='待核价会员',data={'credit_to_cny':None,'billing_mode':'membership'})
    with Session(engine) as s:
        from catstudio.db import add
        record=add(s,'generation_record',project_id=pid,shot_id=sh['id'],data={'model_id':model['id'],'params':{'duration_s':6,'ratio':'9:16','resolution':'360p'},'billing_snapshot':{'credit_to_cny':None}})
        rid=record.id;s.commit()
    clip=upload(client,media_files[1])
    result=post(client,f'/generations/{rid}/candidates',{'file_id':clip['id'],'credits':12})
    wait(client,result['task_id'])
    cost=next(x for x in state(client)['cost_entry'] if x['parent_id']==result['id'])
    assert cost['data']['unpriced'] is True
    export=client.get('/api/costs/export',params={'project_id':pid}).text
    assert ',12.0,,待核价,' in export
    again=post(client,f'/generations/{rid}/candidates',{'file_id':clip['id'],'credits':12})
    assert again['id']==result['id']
    assert len([x for x in state(client)['cost_entry'] if x['project_id']==pid])==1


def test_new_workflow_final_requires_rights_confirmation(client, production):
    pid=production['pid'];fid=production['final']['id']
    with Session(engine) as s:
        p=get(s,'project',pid);before=dict(p.data);p.data={**p.data,'production_workflow':True};s.commit()
    try:
        response=client.post(f'/api/finals/{fid}/confirm',json={'checks':{'motion':True,'audio':True,'subtitle':True}})
        assert response.status_code==422 and '商业' in response.json()['detail']
        post(client,f'/finals/{fid}/confirm',{'checks':dict.fromkeys(['motion','audio','subtitle','rights'],True)})
    finally:
        with Session(engine) as s:
            p=get(s,'project',pid);p.data=before;s.commit()


def test_parallel_case_import_deduplicates(client,media_files,monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    monkeypatch.setattr(prod,'verified_media',lambda key:media_files[0])
    nonce=str(uuid.uuid4())
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(lambda _:post(client,'/production/example/import',{'nonce':nonce}),range(2)))
    assert results[0]['id']==results[1]['id']
