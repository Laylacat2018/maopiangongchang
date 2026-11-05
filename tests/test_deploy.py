"""Check shared-gateway updates preserve existing sites and roll back on failure."""
import importlib.util
from pathlib import Path
import pytest


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
