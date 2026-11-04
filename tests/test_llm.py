"""以本地协议服务器验证真正的 HTTP 适配、结构校验与一次重试，不连接付费服务。"""
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from threading import Thread
import json,time
import pytest
from test_workflow import client,post,state,wait

@pytest.fixture
def vendor():
    class Handler(BaseHTTPRequestHandler):
        calls=[];mode='retry'
        def log_message(self,*_):pass
        def do_POST(self):
            d=json.loads(self.rfile.read(int(self.headers['Content-Length'])));self.calls.append({'path':self.path,'body':d})
            if self.mode=='failure':content='not json'
            elif self.mode=='retry' and len(self.calls)==1:content='{"summary":null}'
            else:content=json.dumps({'summary':'本地协议验收剧情','emotion_landing':'共情'},ensure_ascii=False)
            payload={'choices':[{'message':{'content':content}}],'usage':{'prompt_tokens':100,'completion_tokens':30}}
            self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(json.dumps(payload).encode())
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler);Thread(target=server.serve_forever,daemon=True).start()
    yield server,Handler
    server.shutdown();server.server_close()

def test_llm_http_retry_validation_and_logging(client,vendor):
    c=client;s,h=vendor;p=post(c,'/projects',{'name':'LLM本地协议验收'})
    post(c,'/settings/llm_text',{'provider':'openai','base_url':f'http://127.0.0.1:{s.server_port}/v1','model':'test-only','api_key':'test-key','input_price_per_million':1,'output_price_per_million':2})
    t=post(c,'/llm',{'project_id':p['id'],'purpose':'script','confirmed':True});done=wait(c,t['id'])
    assert done['data']['result']['result']['summary']=='本地协议验收剧情';assert len(h.calls)==2
    logs=c.get('/api/llm/logs').json();assert logs[-1]['data']['attempts']==2;assert logs[-1]['data']['input_tokens']==200
    costs=[x for x in state(c)['cost_entry'] if x['project_id']==p['id']];assert len(costs)==1;assert costs[0]['data']['estimated']

def test_llm_failed_output_keeps_raw_after_two_attempts(client,vendor):
    c=client;s,h=vendor;h.mode='failure';p=post(c,'/projects',{'name':'LLM错误校验'})
    post(c,'/settings/llm_text',{'base_url':f'http://127.0.0.1:{s.server_port}/v1','model':'test-only','api_key':'test-key'})
    t=post(c,'/llm',{'project_id':p['id'],'purpose':'script','confirmed':True})
    for _ in range(100):
        task=next(x for x in state(c)['task'] if x['id']==t['id'])
        if task['status']=='failed':break
        time.sleep(.1)
    assert task['status']=='failed';assert len(h.calls)==2
    assert c.get('/api/llm/logs').json()[-1]['data']['raw_response']=='not json'
