from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from uuid import uuid4
import os
from sqlalchemy import Column, JSON, event, Index, text
from sqlmodel import SQLModel, Field, Session, create_engine, select

ROOT = Path(__file__).resolve().parents[1]
DATA = Path(os.environ.get('CATSTUDIO_DATA', str(ROOT / 'data'))).resolve()
DATA.mkdir(parents=True, exist_ok=True)
for name in ('files', 'exports', 'backups', 'tmp'):
    (DATA / name).mkdir(exist_ok=True)

def now():
    return datetime.now(timezone.utc).isoformat()

class Entity(SQLModel):
    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    project_id: Optional[str] = Field(default=None, index=True)
    parent_id: Optional[str] = Field(default=None, index=True)
    shot_id: Optional[str] = Field(default=None, index=True)
    name: str = ''
    status: str = 'draft'
    version: int = 1
    revision: int = 1
    seq: int = 0
    duration_s: float = 0
    amount_fen: int = 0
    owner_id: str = 'local-owner'
    created_at: str = Field(default_factory=now)
    updated_at: str = Field(default_factory=now)
    deleted_at: Optional[str] = None
    data: dict = Field(default_factory=dict, sa_type=JSON)

KINDS = 'project brief gate_event reference evidence story_direction script shot prompt_version asset asset_version asset_file asset_link platform_subject shot_binding model_profile generation_record candidate review placement edit_package final_cut archive release metric_snapshot retention_point retro file_object cost_entry prompt_template csv_mapping llm_call app_setting task'.split()
MODELS = {name: type(''.join(x.title() for x in name.split('_')), (Entity,), {'__tablename__': name, '__module__': __name__}, table=True) for name in KINDS}
Index('one_selected_candidate_per_shot', MODELS['candidate'].__table__.c.shot_id, unique=True, sqlite_where=text("status = 'selected' AND deleted_at IS NULL"))
engine = create_engine('sqlite:///' + str(DATA / 'catstudio.db'), connect_args={'check_same_thread': False, 'timeout': 30})

@event.listens_for(engine, 'connect')
def pragmas(dbapi_connection, _):
    dbapi_connection.execute('PRAGMA journal_mode=WAL')
    dbapi_connection.execute('PRAGMA foreign_keys=ON')
    dbapi_connection.execute('PRAGMA busy_timeout=30000')

def init():
    SQLModel.metadata.create_all(engine)

def get(s, kind, id):
    obj = s.get(MODELS[kind], id)
    if not obj or obj.deleted_at:
        from fastapi import HTTPException
        raise HTTPException(404, '对象不存在或已归档')
    return obj

def rows(s, kind, project=None, parent=None):
    q = select(MODELS[kind]).where(MODELS[kind].deleted_at == None)
    if project is not None: q = q.where(MODELS[kind].project_id == project)
    if parent is not None: q = q.where(MODELS[kind].parent_id == parent)
    return list(s.exec(q).all())

def add(s, kind, **kw):
    obj = MODELS[kind](**kw)
    s.add(obj)
    s.flush()
    return obj

def touch(obj):
    obj.updated_at = now()
    obj.revision += 1

def jsonable(obj):
    # SQLAlchemy expires fields on commit; access attributes before serialization.
    return {key:getattr(obj,key) for key in type(obj).model_fields}
