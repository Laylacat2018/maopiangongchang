"""Seven-step workbench, immutable example evidence, and reviewed first frames."""
import hashlib
import json
import os
import threading
from pathlib import Path
from fastapi import APIRouter
from fastapi.responses import FileResponse
from sqlmodel import Session
from .db import engine, ROOT, add, get, rows, touch, now, jsonable
from . import storage, services as svc

router = APIRouter(prefix='/api/production')
CASE = 'pet-campus-001'
RESOURCE = Path(__file__).parent / 'resources' / (CASE + '.json')
FRAME_CHECKS = ('identity', 'paws', 'props', 'composition')
import_lock = threading.Lock()


def case_data():
    return json.loads(RESOURCE.read_text(encoding='utf-8'))


def media_path(key):
    entry = case_data()['media'].get(key)
    if not entry:
        svc.fail('样片素材不存在', 404)
    root = (Path(os.environ.get('CATSTUDIO_EXAMPLES_DIR', ROOT / 'sample-media')) / CASE).resolve()
    path = (root / entry['filename']).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        svc.fail('样片素材未安装，请安装首片素材包', 404)
    return path, entry


def verified_media(key):
    path, entry = media_path(key)
    with path.open('rb') as f:
        if hashlib.file_digest(f, 'sha256').hexdigest() != entry['sha256']:
            svc.fail('样片素材校验不符，请重新安装素材包', 409)
    return path


def frame_fingerprint(s, shot):
    refs = []
    for b in rows(s, 'shot_binding', shot.project_id):
        if b.shot_id != shot.id or b.data.get('slot') != '主体':
            continue
        vid = b.data.get('asset_version_id')
        if not vid:
            continue
        v = get(s, 'asset_version', vid)
        refs.append({'id': vid, 'status': v.status, 'files': sorted(
            get(s, 'file_object', f.data['file_id']).name for f in rows(s, 'asset_file', parent=vid))})
    fid = shot.data.get('keyframe_file_id')
    f = get(s, 'file_object', fid) if fid else None
    content = {'frame': f.name if f else None, 'image_prompt': shot.data.get('image_prompt', ''),
               'references': sorted(refs, key=lambda x: x['id'])}
    return hashlib.sha256(json.dumps(content, sort_keys=True).encode()).hexdigest()


def frame_errors(s, shot):
    if not shot.data.get('keyframe_file_id'):
        return ['请先回传独立分镜图']
    review = shot.data.get('keyframe_review', {})
    if review.get('fingerprint') != frame_fingerprint(s, shot) or not all(review.get('checks', {}).get(k) for k in FRAME_CHECKS):
        return ['分镜图尚未通过四项人工审核，或输入已变化，请重新审核']
    return []


@router.get('/example')
def example():
    data = case_data()
    for key, entry in data['media'].items():
        try:
            media_path(key)
            entry['available'] = True
        except Exception:
            entry['available'] = False
        entry['url'] = '/api/production/example/media/' + key
    return data


@router.get('/example/media/{key}')
def example_media(key: str):
    path, entry = media_path(key)
    return FileResponse(path, media_type=entry['mime'], filename=entry['filename'], content_disposition_type='inline')


@router.post('/example/import')
def import_example(body: dict):
    nonce = body.get('nonce')
    if not isinstance(nonce, str) or not 8 <= len(nonce) <= 100:
        svc.fail('请提供本次导入标识')
    with import_lock, Session(engine) as s:
        old = next((p for p in rows(s, 'project') if p.data.get('example_import_nonce') == nonce), None)
        if old:
            return jsonable(old)
        data = case_data()
        # Validate all media before writing any project rows. No historical approvals are copied.
        keys = ['identity'] + [x['image_key'] for x in data['shots']]
        paths = {key: verified_media(key) for key in keys}
        p = add(s, 'project', name=(body.get('name') or '今天没早八 · 我的新制作')[:60], status='active',
                data={'stage': 1, 'completed_stages': [], 'production_workflow': True,
                      'example_import_nonce': nonce, 'source_example': CASE,
                      'generation_settings': {'mode': '首帧图生视频', 'resolution': '720p', 'candidates': 1}})
        add(s, 'brief', project_id=p.id, name='创作简报', data=data['brief'])
        ref = add(s, 'reference', project_id=p.id, name='自有首片制作实录', data={
            'title': data['title'], 'source_type': '自有制作记录', 'notes': data['provenance'], 'metrics_verified': False})
        add(s, 'story_direction', project_id=p.id, name=data['title'], data={
            'title': data['title'], 'resonance': '越怕迟到越慌，最后发现今天休息',
            'is_selected': True, 'cited_reference_ids': [ref.id]})
        script = add(s, 'script', project_id=p.id, name='首片分镜草稿', status='draft', data={
            'summary': data['summary'], 'review_note': '参考案例，请人工确认故事与镜头'})
        identity_prompt = '以提供的A版身份母图为参考，保持'+data['identity']+' 单幅角色图，温暖柔光，不生成文字、人类手指或额外肢体。'
        role = add(s, 'asset', project_id=p.id, name='A版金渐层 · 米色睡衣', data={'type': 'CHAR',
            'code': 'CHAR-A', 'identity': data['identity'], 'locked_traits': data['identity'],
            'prompt': identity_prompt, 'prompt_origin': '根据母图重建的迁移参考词', 'commercial_rights': 'pending'})
        add(s, 'prompt_version', project_id=p.id, parent_id=role.id, name='角色生图参考词',
            data={'body': identity_prompt, 'owner_type': 'asset', 'origin': '根据母图重建的迁移参考词'})
        v = add(s, 'asset_version', project_id=p.id, parent_id=role.id, name='用户已选A版', status='final',
                data={'source': 'AI生成', 'license_note': '用户已选身份母图；商用权益仍需核对', 'commercial_rights': 'pending'})
        f = storage.store(s, paths['identity'], 'A版身份母图.png')
        add(s, 'asset_file', project_id=p.id, parent_id=v.id, name='身份母图', data={'file_id': f.id})
        for i, item in enumerate(data['shots']):
            f = storage.store(s, paths[item['image_key']], f'shot{i+1:02d}.png')
            sh = add(s, 'shot', project_id=p.id, parent_id=script.id, name=item['name'], seq=i,
                     duration_s=item['duration_s'], status='draft', data={
                'action': item['action'], 'line_text': item['caption'], 'sound': item['sound'],
                'image_prompt': item['image_prompt'], 'prompt': item['jimeng_video_prompt'],
                'input_mode': 'first_frame', 'keyframe_file_id': f.id,
                'checks': {'single': False, 'anatomy': False, 'continuity': False},
                'origin': '首片案例改编草稿；即梦提示词为迁移参考，未实测', 'source_example': CASE})
            add(s, 'shot_binding', project_id=p.id, parent_id=sh.id, shot_id=sh.id, name='主体',
                data={'slot': '主体', 'required': True, 'asset_version_id': v.id})
        s.commit()
        return jsonable(p)


@router.post('/shots/{id}/frame')
def attach_frame(id: str, body: dict):
    with Session(engine) as s:
        sh = get(s, 'shot', id)
        if body.get('revision') != sh.revision:
            svc.fail('镜头已有新版本，请刷新后再保存', 409)
        f = get(s, 'file_object', body.get('file_id', ''))
        if not f.data.get('mime', '').startswith('image/'):
            svc.fail('分镜图必须是图片')
        svc.reset_shot(s, sh, '分镜图已变化')
        svc.invalidate(s, sh.project_id, 4, '分镜图已变化，请重新审核')
        project = get(s, 'project', sh.project_id)
        project.data = {**project.data, 'production_workflow': True}
        touch(project)
        sh.data = {**sh.data, 'input_mode': 'first_frame', 'keyframe_file_id': f.id, 'keyframe_review': {}}
        touch(sh); s.commit()
        return jsonable(sh)


@router.post('/shots/{id}/frame-review')
def review_frame(id: str, body: dict):
    with Session(engine) as s:
        sh = get(s, 'shot', id)
        if body.get('revision') != sh.revision:
            svc.fail('镜头已有新版本，请刷新后再审核', 409)
        if not sh.data.get('keyframe_file_id'):
            svc.fail('请先回传分镜图')
        frame = get(s, 'file_object', sh.data['keyframe_file_id'])
        if not frame.data.get('mime', '').startswith('image/'):
            svc.fail('分镜图必须是图片')
        checks = {k: body.get('checks', {}).get(k) is True for k in FRAME_CHECKS}
        if not all(checks.values()):
            svc.fail('请完成身份、猫爪、道具与字幕空间四项人工检查')
        review = {'fingerprint': frame_fingerprint(s, sh), 'checks': checks,
                  'reviewer': '工作室人工审核', 'reviewed_at': now(), 'note': str(body.get('note', ''))[:1000]}
        sh.data = {**sh.data, 'keyframe_review': review}
        add(s, 'review', project_id=sh.project_id, parent_id=sh.id, shot_id=sh.id,
            name='分镜图人工审核', status='confirmed', data=review)
        touch(sh); s.commit()
        return jsonable(sh)
