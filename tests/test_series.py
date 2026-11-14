"""系列层：导入首季、台账计算、档位建项目、发布前检查、工时与门槛进度。"""
import pytest
from test_workflow import client, post, put, create, state, ok


@pytest.fixture(scope='module')
def series(client):
    first = post(client, '/series/import', {'key': 'biscuit-domino-s1'})
    again = post(client, '/series/import', {'key': 'biscuit-domino-s1'})
    assert first['id'] == again['id']
    return first


def board(client, series):
    return ok(client.get(f"/api/series/{series['id']}/board"))


def test_templates_listed(client):
    items = ok(client.get('/api/series/templates'))
    assert items[0]['episodes'] == 28 and 'Domino' in items[0]['characters']


def test_import_builds_season(client, series):
    b = board(client, series)
    assert b['summary']['total'] == 28
    assert b['summary']['by_tier'] == {'A': 8, 'B': 20}
    assert b['summary']['by_subseries'] == {'campus': 10, 'holiday': 10, 'kitchen': 8}
    assert b['summary']['ending_conflicts'] == []
    assert [w['planned_hours'] for w in b['weeks']] == [12.0] * 4
    assert b['episodes'][0]['publish_date'] == '2026-11-30' and b['episodes'][27]['publish_date'] == '2026-12-27'
    late = next(t for t in b['threads'] if t['key'] == 'late')
    assert [e['no'] for e in late['episodes']] == [1, 22, 28]
    st = state(client)
    assert len([c for c in st['character'] if c['parent_id'] == series['id']]) == 4
    assert len([c for c in st['scene'] if c['parent_id'] == series['id']]) == 7


def test_episode_project_uses_tier_template(client, series):
    b = board(client, series)
    for no, shots, low, high in [(6, 8, 40, 50), (2, 4, 20, 25)]:
        ep = next(e for e in b['episodes'] if e['no'] == no)
        p = post(client, f"/series/episodes/{ep['id']}/project")
        assert post(client, f"/series/episodes/{ep['id']}/project")['id'] == p['id']
        st = state(client)
        brief = next(x for x in st['brief'] if x['project_id'] == p['id'])['data']
        assert brief['platforms'] == ['YouTube'] and brief['language'] == 'English'
        assert (brief['duration_min_s'], brief['duration_max_s']) == (low, high)
        mine = [x for x in st['shot'] if x['project_id'] == p['id']]
        assert len(mine) == shots and low <= sum(x['duration_s'] for x in mine) <= high
        assert p['data']['stage'] == 1 and p['data']['completed_stages'] == []
        assert ok(client.get(f"/api/projects/{p['id']}/gate/1"))['errors'] == []
        assert ok(client.get(f"/api/projects/{p['id']}/gate/2"))['errors'] == []
        assert ok(client.get(f"/api/projects/{p['id']}/gate/3"))['errors']  # script and shots still need human work


def test_checks_gate_publishing(client, series):
    b = board(client, series)
    ep = next(e for e in b['episodes'] if e['no'] == 3)
    full = {k: True for k in ['silent_readable', 'hook_3s', 'ending_varies', 'no_ip', 'safe_disclosed']}
    url = {'youtube_url': 'https://www.youtube.com/shorts/abc123'}
    assert client.post(f"/api/series/episodes/{ep['id']}/publish", json=url).status_code == 409
    partial = post(client, f"/series/episodes/{ep['id']}/checks", {'checks': {**full, 'hook_3s': False}})
    assert partial['status'] == 'draft'
    assert post(client, f"/series/episodes/{ep['id']}/checks", {'checks': full})['status'] == 'ready'
    # generic edits cannot set status or forge checks
    assert client.put(f"/api/items/episode/{ep['id']}", json={'status': 'published'}).status_code == 403
    # changing the ending to repeat a neighbour clears the checks and is refused on re-check
    current = next(x for x in state(client)['episode'] if x['id'] == ep['id'])
    prev_ending = next(e for e in b['episodes'] if e['no'] == 2)['ending_type']
    changed = put(client, 'episode', current, data={**current['data'], 'ending_type': prev_ending, 'checks': full})
    assert changed['status'] == 'draft' and changed['data']['checks'] == {}
    assert board(client, series)['summary']['ending_conflicts'] == [3]
    assert client.post(f"/api/series/episodes/{ep['id']}/checks", json={'checks': full}).status_code == 422
    current = next(x for x in state(client)['episode'] if x['id'] == ep['id'])
    put(client, 'episode', current, data={**current['data'], 'ending_type': '意外成功'})
    assert post(client, f"/series/episodes/{ep['id']}/checks", {'checks': full})['status'] == 'ready'
    assert client.post(f"/api/series/episodes/{ep['id']}/publish", json={'youtube_url': 'http://example.com/x'}).status_code == 422
    done = post(client, f"/series/episodes/{ep['id']}/publish", url)
    assert done['status'] == 'published' and done['data']['youtube_url'] == url['youtube_url']
    assert client.post(f"/api/series/episodes/{ep['id']}/checks", json={'checks': full}).status_code == 409


def test_worklog_and_weekly_budget(client, series):
    b = board(client, series)
    ep = next(e for e in b['episodes'] if e['no'] == 6)
    assert client.post(f"/api/series/episodes/{ep['id']}/worklog", json={'hours': 0}).status_code == 422
    post(client, f"/series/episodes/{ep['id']}/worklog", {'hours': 3.5, 'note': '生图返工两次'})
    post(client, f"/series/episodes/{ep['id']}/worklog", {'hours': 9})
    b = board(client, series)
    assert next(e for e in b['episodes'] if e['no'] == 6)['hours'] == 12.5
    week1 = b['weeks'][0]
    assert week1['actual_hours'] == 12.5 and week1['over_budget'] is True
    assert b['weeks'][1]['over_budget'] is False


def test_eligibility_progress(client, series):
    start = board(client, series)['eligibility']
    assert [t['met'] for t in start['tiers']] == [False, False]
    assert client.post(f"/api/series/{series['id']}/channel", json={'subscribers': -1}).status_code == 422
    r = post(client, f"/series/{series['id']}/channel", {'subscribers': 620, 'shorts_views_90d': 3200000})
    shopping, ads = r['tiers']
    assert shopping['met'] is True and ads['met'] is False
    assert ads['subscribers']['ratio'] == 0.62 and ads['shorts_views_90d']['target'] in (10000000, 20000000)


def test_products_link_to_episodes(client, series):
    assert client.post('/api/items/product', json={'name': 'x', 'data': {'url': 'javascript:alert(1)'}}).status_code == 422
    product = create(client, 'product', parent_id=series['id'], name='迷你松饼机', data={'category': '宿舍小家电', 'platform': 'Shopify', 'url': 'https://example.com/p/1', 'commission_pct': 10})
    ep = next(x for x in state(client)['episode'] if x['parent_id'] == series['id'] and x['seq'] == 2)
    put(client, 'episode', ep, data={**ep['data'], 'product_ids': [product['id']]})
    assert 2 not in board(client, series)['summary']['without_product']


def test_reference_recognises_youtube_and_tiktok(client):
    p = post(client, '/projects', {'name': '平台识别'})
    a = create(client, 'reference', project_id=p['id'], name='r1', data={'url': 'https://www.youtube.com/shorts/xyz'})
    b = create(client, 'reference', project_id=p['id'], name='r2', data={'url': 'https://www.tiktok.com/@a/video/1'})
    assert (a['data']['platform'], b['data']['platform']) == ('YouTube', 'TikTok')
