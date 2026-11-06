"""Check shared-gateway updates preserve existing sites and roll back on failure."""
import importlib.util
from pathlib import Path
import pytest


def upgrade_module():
    path=Path(__file__).resolve().parents[1]/'deploy/upgrade_existing_podman.py'
    spec=importlib.util.spec_from_file_location('upgrade_operator',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def test_upgrade_preserves_auth_volumes_and_loopback_binding():
    module=upgrade_module()
    body=(Path(__file__).resolve().parents[1]/'deploy/catstudio.container').read_text()
    updated=module.updated_unit(body.replace('localhost/catstudio:1.1.0','localhost/catstudio:1.0.1'),'localhost/catstudio:1.1.0')
    assert updated==body
    for field in ['CATSTUDIO_AUTH_FILE','CATSTUDIO_MASTER_KEY_FILE','Volume=catstudio-data:','Volume=catstudio-secrets:','PublishPort=127.0.0.1:8776:8776','ReadOnly=true','NoNewPrivileges=true']:
        assert field in updated
    with pytest.raises(ValueError):module.updated_unit(body.replace('127.0.0.1:8776:8776','0.0.0.0:8776:8776'),'localhost/catstudio:1.1.0')
    with pytest.raises(ValueError):module.updated_unit(body,'localhost/catstudio:latest')


def test_upgrade_rejects_tampered_or_extra_sample_files(tmp_path):
    import hashlib,json,sqlite3,zipfile
    module=upgrade_module();data=tmp_path.resolve();pack=data/'pack.zip'
    payload=b'only allowlisted content'
    manifest={'media':{'test':{'filename':'frame.png','size':len(payload),'sha256':hashlib.sha256(payload).hexdigest()}}}
    def write_pack(extra=False):
        with zipfile.ZipFile(pack,'w') as z:
            z.writestr('frame.png',payload)
            if extra:z.writestr('../unexpected.txt','reject')
        with sqlite3.connect(data/'catstudio.db') as db:
            db.execute('CREATE TABLE IF NOT EXISTS file_object (id TEXT,data TEXT,deleted_at TEXT)')
            db.execute('DELETE FROM file_object')
            db.execute('INSERT INTO file_object VALUES (?,?,NULL)',('test',json.dumps({'rel_path':'pack.zip','sha256':hashlib.sha256(pack.read_bytes()).hexdigest()})))
    write_pack()
    assert module.sample_archive(data,'test',manifest)==pack
    write_pack(extra=True)
    with pytest.raises(RuntimeError,match='allowlist'):module.sample_archive(data,'test',manifest)
    write_pack();pack.write_bytes(pack.read_bytes()+b'tampered')
    with pytest.raises(RuntimeError,match='hash mismatch'):module.sample_archive(data,'test',manifest)


@pytest.fixture
def operator(tmp_path,monkeypatch):
    path=Path(__file__).resolve().parents[1]/'deploy/install_existing_podman.py'
    spec=importlib.util.spec_from_file_location('deployment_operator',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    root=tmp_path/'app';root.mkdir()
    config=tmp_path/'Caddyfile'
    config.write_text('existing.example.com {\n    reverse_proxy 127.0.0.1:3001\n}\n')
    config.chmod(0o640)
    monkeypatch.setattr(module,'ROOT',root)
    monkeypatch.setattr(module,'CADDY_CONFIG',config)
    monkeypatch.setattr(module.os,'chown',lambda *args:None,raising=False)
    return module,config


def test_gateway_change_is_validated_before_replacement(operator,monkeypatch):
    module,config=operator;original=config.read_bytes()
    def rejected(*args):raise RuntimeError('synthetic invalid config')
    monkeypatch.setattr(module,'run',rejected)
    with pytest.raises(RuntimeError):module.proxy()
    assert config.read_bytes()==original
    assert next((module.ROOT/'backups').iterdir()).read_bytes()==original


def test_gateway_reload_failure_restores_original_config(operator,monkeypatch):
    module,config=operator;original=config.read_bytes();calls=[]
    def run(*args):
        calls.append(args)
        if args[1]=='reload' and len(calls)==2:raise RuntimeError('synthetic reload failure')
        return ''
    monkeypatch.setattr(module,'run',run)
    with pytest.raises(RuntimeError):module.proxy()
    assert config.read_bytes()==original
    assert [x[1] for x in calls]==['validate','reload','reload']


def test_gateway_keeps_existing_sites_and_refuses_duplicate_domain(operator,monkeypatch):
    module,config=operator;original=config.read_text();calls=[]
    monkeypatch.setattr(module,'run',lambda *args:calls.append(args) or '')
    module.proxy()
    assert config.read_text().startswith(original)
    assert config.read_text().count(module.DOMAIN)==1
    assert [x[1] for x in calls]==['validate','reload']
    with pytest.raises(AssertionError):module.proxy()
