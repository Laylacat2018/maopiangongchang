"""系列层：系列、分集、角色与场景库、剧集台账、发布前检查、工时记录、带货门槛进度。

一个系列下挂多集；每集可生成一个按 A/B 档预填的制作项目，沿用既有七步制片流程。
"""
import json
import threading
from datetime import date
from pathlib import Path

from fastapi import APIRouter
from sqlmodel import Session

from .db import engine, get, rows, add, jsonable, touch, now, MODELS
from . import services as svc

router = APIRouter(prefix='/api/series', tags=['series'])
RESOURCES = Path(__file__).with_name('resources')
TEMPLATES = {'biscuit-domino-s1': 'biscuit-domino-s1.json'}
import_lock = threading.Lock()
CHECK_KEYS = ['silent_readable', 'hook_3s', 'ending_varies', 'no_ip', 'safe_disclosed']


def template(key):
    if key not in TEMPLATES:
        svc.fail('未知的系列模板', 404)
    return json.loads((RESOURCES / TEMPLATES[key]).read_text(encoding='utf-8'))


def episodes(s, series_id):
    return sorted(rows(s, 'episode', parent=series_id), key=lambda x: (x.seq, x.created_at))


def ending_conflict(eps, ep):
    """True when this episode's ending type repeats either of the two episodes before it."""
    index = next(i for i, x in enumerate(eps) if x.id == ep.id)
    mine = ep.data.get('ending_type')
    previous = [x.data.get('ending_type') for x in eps[max(0, index - 2):index]]
    return bool(mine) and mine in previous


def hours(ep):
    return round(sum(float(x.get('hours', 0)) for x in ep.data.get('worklog', [])), 2)


def progress(current, target):
    return {'current': current, 'target': target, 'met': current >= target,
            'ratio': round(min(1, current / target), 4) if target else 1}


def eligibility(series):
    channel = series.data.get('channel', {})
    subs = int(channel.get('subscribers') or 0)
    views = int(channel.get('shorts_views_90d') or 0)
    rules = series.data.get('eligibility', {})
    result = []
    for tier in rules.get('tiers', []):
        target = tier['shorts_views_90d']
        later = tier.get('from_2027_02_01_shorts_views_90d')
        if later and date.today() >= date(2027, 2, 1):
            target = later
        item = {'key': tier['key'], 'label': tier['label'],
                'subscribers': progress(subs, tier['subscribers']),
                'shorts_views_90d': progress(views, target)}
        item['met'] = item['subscribers']['met'] and item['shorts_views_90d']['met']
        if later:
            item['later_target'] = later
        result.append(item)
    return {'updated_at': channel.get('updated_at'), 'as_of': rules.get('as_of'), 'note': rules.get('note'), 'tiers': result}


def board_data(s, series):
    eps = episodes(s, series.id)
    tiers = series.data.get('tiers', {})
    items = []
    for ep in eps:
        d = ep.data
        project_id = d.get('project_id')
        checks = d.get('checks', {})
        items.append({
            'id': ep.id, 'no': ep.seq, 'name': ep.name, 'status': ep.status, 'revision': ep.revision,
            'week': (ep.seq - 1) // 7 + 1, 'publish_date': d.get('publish_date'), 'subseries': d.get('subseries'),
            'tier': d.get('tier'), 'logline': d.get('logline'), 'ending_type': d.get('ending_type'),
            'ending_conflict': ending_conflict(eps, ep), 'threads': d.get('threads', []), 'scene': d.get('scene'),
            'product_categories': d.get('product_categories', []), 'product_ids': d.get('product_ids', []),
            'project_id': project_id, 'checks': checks, 'checks_done': sum(bool(checks.get(k)) for k in CHECK_KEYS),
            'hours': hours(ep), 'planned_hours': tiers.get(d.get('tier'), {}).get('planned_hours', 0),
            'cost_cny': svc.spend(s, project_id) if project_id else 0,
            'youtube_url': d.get('youtube_url'), 'published_at': d.get('published_at')})
    weeks = []
    budget = series.data.get('weekly_hours_budget', 0)
    for number in sorted({x['week'] for x in items}):
        group = [x for x in items if x['week'] == number]
        planned = round(sum(x['planned_hours'] for x in group) + series.data.get('publish_hours_per_week', 0), 2)
        actual = round(sum(x['hours'] for x in group), 2)
        weeks.append({'week': number, 'episodes': len(group), 'planned_hours': planned, 'actual_hours': actual,
                      'budget_hours': budget, 'over_budget': bool(budget) and actual > budget,
                      'ready': sum(x['status'] in ('ready', 'published') for x in group),
                      'published': sum(x['status'] == 'published' for x in group)})
    threads = [{**t, 'episodes': [{'no': x['no'], 'name': x['name'], 'status': x['status']} for x in items if t['key'] in x['threads']]}
               for t in series.data.get('threads', [])]
    count = lambda key: {v: sum(x[key] == v for x in items) for v in sorted({x[key] for x in items if x[key]})}
    return {'series': jsonable(series), 'episodes': items, 'weeks': weeks, 'threads': threads,
            'summary': {'total': len(items), 'by_subseries': count('subseries'), 'by_tier': count('tier'), 'by_status': count('status'),
                        'ending_conflicts': [x['no'] for x in items if x['ending_conflict']],
                        'without_product': [x['no'] for x in items if not x['product_ids']],
                        'hours': round(sum(x['hours'] for x in items), 2), 'cost_cny': round(sum(x['cost_cny'] for x in items), 2)},
            'eligibility': eligibility(series)}


@router.get('/templates')
def list_templates():
    result = []
    for key in TEMPLATES:
        data = template(key)
        result.append({'key': key, 'name': data['name'], 'season': data['season'], 'start_date': data['start_date'],
                       'positioning': data['positioning'], 'episodes': len(data['episodes']),
                       'characters': [x['name'] for x in data['characters']]})
    return result


@router.post('/import')
def import_series(body: dict):
    data = template(body.get('key', 'biscuit-domino-s1'))
    with import_lock, Session(engine) as s:
        old = next((x for x in rows(s, 'series') if x.data.get('template_key') == data['key']), None)
        if old:
            return jsonable(old)
        keep = ['season', 'start_date', 'positioning', 'world', 'language', 'weekly_hours_budget', 'publish_hours_per_week',
                'brief', 'subseries', 'ending_types', 'threads', 'tiers', 'checks', 'eligibility']
        series = add(s, 'series', name=data['name'], status='active',
                     data={'template_key': data['key'], 'channel': {}, **{k: data[k] for k in keep}})
        for i, item in enumerate(data['characters']):
            add(s, 'character', parent_id=series.id, name=item['name'], seq=i, status='draft',
                data={**item, 'asset_id': None})
        for i, item in enumerate(data['scenes']):
            add(s, 'scene', parent_id=series.id, name=item['name'], seq=i, status='draft', data={**item, 'asset_id': None})
        for item in data['episodes']:
            add(s, 'episode', parent_id=series.id, name=item['title'], seq=item['no'], status='draft',
                data={k: v for k, v in item.items() if k not in ('no', 'title')} | {'product_ids': [], 'checks': {}, 'worklog': []})
        s.commit()
        return jsonable(series)


@router.get('/{id}/board')
def board(id: str):
    with Session(engine) as s:
        return board_data(s, get(s, 'series', id))


@router.post('/{id}/channel')
def channel_stats(id: str, body: dict):
    try:
        subs = int(body.get('subscribers', 0))
        views = int(body.get('shorts_views_90d', 0))
    except (TypeError, ValueError):
        svc.fail('订阅数和播放量必须是整数')
    if subs < 0 or views < 0:
        svc.fail('订阅数和播放量不能为负')
    with Session(engine) as s:
        series = get(s, 'series', id)
        series.data = {**series.data, 'channel': {'subscribers': subs, 'shorts_views_90d': views, 'updated_at': now()}}
        touch(series)
        s.commit()
        return eligibility(series)


@router.post('/episodes/{id}/project')
def episode_project(id: str):
    """Create the production project for an episode, pre-filled from its tier template. No approvals are granted."""
    with import_lock, Session(engine) as s:
        ep = get(s, 'episode', id)
        series = get(s, 'series', ep.parent_id)
        d = ep.data
        if d.get('project_id'):
            project = s.get(MODELS['project'], d['project_id'])
            if project and not project.deleted_at:
                return jsonable(project)
        tier = series.data.get('tiers', {}).get(d.get('tier'))
        if not tier:
            svc.fail('本集未设置有效的档位')
        sub = next((x for x in series.data.get('subseries', []) if x['key'] == d.get('subseries')), {})
        label = f"EP{ep.seq:02d} {ep.name}"[:60]
        project = add(s, 'project', name=label, status='active', data={
            'stage': 1, 'completed_stages': [], 'production_workflow': True,
            'series_id': series.id, 'episode_id': ep.id, 'tier': d.get('tier'),
            'generation_settings': {'mode': '首帧图生视频', 'resolution': '720p', 'candidates': 1}})
        add(s, 'brief', project_id=project.id, name='创作简报', data={
            **series.data.get('brief', {}), 'tags': [sub.get('label', ''), series.name],
            'direction': f"{series.name} · {sub.get('name', '')}：{sub.get('frame', '')}",
            'duration_min_s': tier['duration_min_s'], 'duration_max_s': tier['duration_max_s']})
        ref = add(s, 'reference', project_id=project.id, name=f'{series.name} 首季策划 EP{ep.seq:02d}', data={
            'title': ep.name, 'source_type': '自有系列策划', 'platform': 'YouTube',
            'notes': f"{d.get('logline', '')}｜结局类型：{d.get('ending_type', '')}", 'metrics_verified': False})
        add(s, 'story_direction', project_id=project.id, name=ep.name, data={
            'title': ep.name, 'resonance': d.get('logline', ''), 'is_selected': True, 'cited_reference_ids': [ref.id]})
        script = add(s, 'script', project_id=project.id, name=f'EP{ep.seq:02d} 分镜草稿', status='draft', data={
            'summary': d.get('logline', ''), 'review_note': f"{tier['label']}；配音：{tier.get('voice', '')}；英文字幕每句不超过 7 个词"})
        cast = {x.data.get('code'): x for x in rows(s, 'character', parent=series.id)}
        lead = cast.get('BISCUIT')
        traits = f"{lead.data.get('look', '')}，{lead.data.get('outfit', '')}" if lead else ''
        shot_s = round((tier['duration_min_s'] + tier['duration_max_s']) / 2 / len(tier['shots']), 1)
        for i, role in enumerate(tier['shots']):
            add(s, 'shot', project_id=project.id, parent_id=script.id, name=role, seq=i, duration_s=shot_s, status='draft', data={
                'action': '', 'line_text': '', 'sound': '', 'prompt': '', 'input_mode': 'first_frame',
                'image_prompt': f'保持同一主角：{traits}。' if traits else '',
                'checks': {'single': False, 'anatomy': False, 'continuity': False},
                'origin': f"系列模板骨架 · {tier['label']} · {role}"})
        ep.data = {**d, 'project_id': project.id}
        touch(ep)
        s.commit()
        return jsonable(project)


@router.post('/episodes/{id}/checks')
def episode_checks(id: str, body: dict):
    checks = {k: bool(body.get('checks', {}).get(k)) for k in CHECK_KEYS}
    with Session(engine) as s:
        ep = get(s, 'episode', id)
        if ep.status == 'published':
            svc.fail('已发布的分集不能再改检查结果', 409)
        if checks['ending_varies'] and ending_conflict(episodes(s, ep.parent_id), ep):
            svc.fail('本集结局类型与前两集之一相同，请先调整结局类型')
        ep.data = {**ep.data, 'checks': checks, 'checked_at': now()}
        ep.status = 'ready' if all(checks.values()) else 'draft'
        touch(ep)
        s.commit()
        return jsonable(ep)


@router.post('/episodes/{id}/worklog')
def episode_worklog(id: str, body: dict):
    try:
        spent = float(body.get('hours'))
    except (TypeError, ValueError):
        svc.fail('请填写工时（小时）')
    if not 0 < spent <= 24:
        svc.fail('单次工时须在 0–24 小时之间')
    with Session(engine) as s:
        ep = get(s, 'episode', id)
        entry = {'hours': round(spent, 2), 'note': str(body.get('note', ''))[:200], 'at': now()}
        ep.data = {**ep.data, 'worklog': [*ep.data.get('worklog', []), entry]}
        touch(ep)
        s.commit()
        return jsonable(ep)


@router.post('/episodes/{id}/publish')
def episode_publish(id: str, body: dict):
    url = str(body.get('youtube_url', '')).strip()
    if not url.startswith('https://') or not any(h in url for h in ('youtube.com/', 'youtu.be/')):
        svc.fail('请填写 https 开头的 YouTube 视频链接')
    with Session(engine) as s:
        ep = get(s, 'episode', id)
        if ep.status not in ('ready', 'published'):
            svc.fail('请先完成五项发布前检查', 409)
        ep.data = {**ep.data, 'youtube_url': url, 'published_at': body.get('published_at') or now()}
        ep.status = 'published'
        touch(ep)
        s.commit()
        return jsonable(ep)
