import json, re, os, threading
from pathlib import Path
from typing import Any
import httpx, keyring
from cryptography.fernet import Fernet
from pydantic import BaseModel, Field, ValidationError
from .db import rows, add, now
from .services import config, cost, fail

PURPOSES={
 'directions':('故事方向',{'directions':[{'title':'方向标题','resonance':'共鸣点','cat_acting':'猫咪演法','emotion_landing':'情绪落点','cited_reference_ids':['已登记的素材ID'],'cited_evidence_ids':[]}]}),
 'script':('剧情稿',{'summary':'剧情正文','emotion_landing':'情绪落点'}),
 'storyboard':('分镜',{'shots':[{'title':'镜头标题','duration_s':6,'shot_size':'近景','angle':'第一视角','action':'单一主动作','end_state':'结束状态','sound':'声音需求','line_text':'心声台词','prompt':'主体{{主体}}在{{场景}}与{{道具}}互动'}]}),
 'video_prompt':('视频提示词',{'prompt':'保留 {{主体}} {{场景}} {{道具}} 占位符'}),
 'portrait':('定妆照提示词',{'prompt':'真实猫咪三视图，保留毛色分区和固定配饰，四脚站立，禁止拟人直立'}),
 'scene':('场景提示词',{'prompt':'场景空镜提示词'}),
 'prop':('道具提示词',{'prompt':'白底道具提示词'}),
 'screenshot':('截图识别',{'title':'标题','likes':0,'comments':[{'text':'评论文字','likes':0}]}),
 'comment_tags':('评论打标',{'comments':[{'id':'评论ID','tags':['情绪标签']}]}),
 'retro':('复盘建议',{'observation':'观察','hypothesis':'待验证假设','evidence':'数据依据','exp_goal':'验证目标','exp_keep':'保持不变','exp_change':'只改一个变量'})
}

class Direction(BaseModel):
    title:str; resonance:str; cat_acting:str; emotion_landing:str
    cited_reference_ids:list[str]=Field(default_factory=list)
    cited_evidence_ids:list[str]=Field(default_factory=list)
class Directions(BaseModel):directions:list[Direction]=Field(min_length=2,max_length=3)
class Script(BaseModel):summary:str=Field(min_length=1);emotion_landing:str=''
class Shot(BaseModel):
    title:str;duration_s:float=Field(gt=0,le=60);action:str;end_state:str='';shot_size:str='近景';angle:str='平视';sound:str='';line_text:str='';prompt:str=''
class Storyboard(BaseModel):shots:list[Shot]=Field(min_length=1,max_length=30)
class Prompt(BaseModel):prompt:str=Field(min_length=1)
class Comment(BaseModel):text:str;likes:int=Field(default=0,ge=0)
class Screenshot(BaseModel):title:str='';likes:int=0;comments:list[Comment]=Field(default_factory=list)
class Tags(BaseModel):comments:list[dict]
class Retro(BaseModel):observation:str;hypothesis:str;evidence:str;exp_goal:str;exp_keep:str;exp_change:str
SCHEMAS={'directions':Directions,'script':Script,'storyboard':Storyboard,'screenshot':Screenshot,'comment_tags':Tags,'retro':Retro}

_key_lock=threading.Lock()

def fernet():
    path=os.environ.get('CATSTUDIO_MASTER_KEY_FILE')
    if path:
        from .security import read_private_file
        path=Path(path)
        with _key_lock:
            path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
            try:
                fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
            except FileExistsError:pass
            else:
                with os.fdopen(fd,'wb') as f:
                    f.write(Fernet.generate_key());f.flush();os.fsync(f.fileno())
            return Fernet(read_private_file(path).encode())
    # Master key never enters the database or backups; Windows Credential Manager.
    key=keyring.get_password('CatStudio','master-key')
    if not key:
        key=Fernet.generate_key().decode();keyring.set_password('CatStudio','master-key',key)
    return Fernet(key.encode())
def encrypt(value):return fernet().encrypt(value.encode()).decode()
def decrypt(value):return fernet().decrypt(value.encode()).decode()

def seed(s):
    existing={x.name for x in rows(s,'prompt_template')}
    for key,(label,example) in PURPOSES.items():
        if key not in existing:add(s,'prompt_template',name=key,status='active',data={'label':label,'body':'你是猫咪剧情视频创作助手。围绕目标人群的真实情绪，用符合猫身体逻辑的行为表达。输出 JSON，禁止虚构素材来源、接口能力、统计数据。只给建议，不替代人工确认。\n上下文：{{ context }}\n输出结构：'+json.dumps(example,ensure_ascii=False)})

def call(s,pid,purpose,context,image=None):
    from jinja2 import Environment, StrictUndefined
    if purpose not in PURPOSES:fail('未知 AI 用途')
    cfg=config(s,'llm_vision' if image else 'llm_text')
    if not cfg.get('encrypted_key') or not cfg.get('model'):fail('请先在 LLM 配置中保存提供商、模型与 API Key')
    key=decrypt(cfg['encrypted_key']);endpoint=cfg.get('base_url','').rstrip('/')
    if not endpoint.startswith(('https://','http://localhost','http://127.0.0.1')):fail('LLM 地址必须为 HTTPS 或本地服务')
    template=next((t for t in sorted(rows(s,'prompt_template'),key=lambda x:x.version,reverse=True) if t.name==purpose and t.status=='active'),None)
    prompt=Environment(undefined=StrictUndefined,autoescape=False).from_string(template.data['body']).render(context=json.dumps(context,ensure_ascii=False))
    log=add(s,'llm_call',project_id=pid,name=purpose,status='running',data={'model':cfg['model'],'template_id':template.id,'template_version':template.version,'request':prompt})
    s.commit()
    raw='';total_in=0;total_out=0;error=None
    for attempt in range(2):
        try:
            text=prompt+('上次 JSON 校验失败，请严格按结构修复：'+str(error) if attempt else '')
            with httpx.Client(timeout=120) as client:
                if cfg.get('provider')=='anthropic':
                    blocks=[{'type':'text','text':text}]
                    if image:blocks.append({'type':'image','source':{'type':'base64','media_type':image['mime'],'data':image['b64']}})
                    r=client.post(endpoint+'/messages',headers={'x-api-key':key,'anthropic-version':'2023-06-01'},json={'model':cfg['model'],'max_tokens':4096,'messages':[{'role':'user','content':blocks}]})
                    r.raise_for_status();response=r.json();raw=''.join(x.get('text','') for x in response.get('content',[]));usage=response.get('usage',{});total_in+=usage.get('input_tokens',0);total_out+=usage.get('output_tokens',0)
                else:
                    content=text if not image else [{'type':'text','text':text},{'type':'image_url','image_url':{'url':'data:'+image['mime']+';base64,'+image['b64']}}]
                    r=client.post(endpoint+'/chat/completions',headers={'Authorization':'Bearer '+key},json={'model':cfg['model'],'messages':[{'role':'user','content':content}],'temperature':.65})
                    r.raise_for_status();response=r.json();raw=response['choices'][0]['message']['content'];usage=response.get('usage',{});total_in+=usage.get('prompt_tokens',0);total_out+=usage.get('completion_tokens',0)
            cleaned=re.sub(r'^```(?:json)?\s*|\s*```$','',raw.strip());data=json.loads(cleaned)
            result=SCHEMAS.get(purpose,Prompt).model_validate(data).model_dump()
            if purpose=='directions':
                refids={r['id'] for r in context.get('references',[])};evids={r['id'] for r in context.get('evidence',[])}
                for d in result['directions']:
                    if not (set(d['cited_reference_ids'])|set(d['cited_evidence_ids'])) or not set(d['cited_reference_ids'])<=refids or not set(d['cited_evidence_ids'])<=evids:raise ValueError('方向引用了不存在的素材或未引用依据')
            log.status='success';log.data={**log.data,'raw_response':raw,'result':result,'attempts':attempt+1};break
        except (json.JSONDecodeError,ValidationError,ValueError) as e:error=str(e)[:500]
        except Exception as e:
            error='LLM 服务请求失败，请核对地址、凭证、模型及服务额度。';break
    else:result=None
    if log.status!='success':log.status='failed';log.data={**log.data,'raw_response':raw,'error':error,'attempts':attempt+1}
    price_in=cfg.get('input_price_per_million');price_out=cfg.get('output_price_per_million')
    if price_in is not None and price_out is not None:
        amount=(total_in*float(price_in)+total_out*float(price_out))/1000000
        entry=cost(s,pid,'LLM',log.id,amount);entry.data={**entry.data,'estimated':True,'input_tokens':total_in,'output_tokens':total_out}
    else:
        entry=cost(s,pid,'LLM',log.id,0);entry.data={**entry.data,'unpriced':True,'input_tokens':total_in,'output_tokens':total_out}
    log.data={**log.data,'input_tokens':total_in,'output_tokens':total_out};s.commit()
    if log.status!='success':raise ValueError(error or 'AI 输出校验失败，原文已保留')
    return {'log_id':log.id,'result':result,'origin':'AI 建议'}
