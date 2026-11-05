"""Server access, CSRF boundaries and durable secret storage."""
import base64
import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import pytest
from catstudio import security


@pytest.fixture
def owner(tmp_path):
    path=tmp_path/'access.json'
    script=Path(__file__).resolve().parents[1]/'scripts/create_server_auth.py'
    result=subprocess.run([sys.executable,str(script),'--file',str(path),'--stdin'],
                          input='synthetic-owner-password-123!\n',text=True,capture_output=True,check=True)
    assert 'synthetic-owner' not in result.stdout
    return path


def test_server_requires_explicit_auth_and_master_key(monkeypatch,owner,tmp_path):
    monkeypatch.setenv('CATSTUDIO_ALLOWED_HOSTS','maopian.migucomi.com,localhost')
    monkeypatch.delenv('CATSTUDIO_AUTH_FILE',raising=False)
    monkeypatch.delenv('CATSTUDIO_MASTER_KEY_FILE',raising=False)
    with pytest.raises(RuntimeError):security.validate_server_config()
    monkeypatch.setenv('CATSTUDIO_AUTH_FILE',str(owner))
    with pytest.raises(RuntimeError):security.validate_server_config()
    monkeypatch.setenv('CATSTUDIO_MASTER_KEY_FILE',str(tmp_path/'master.key'))
    assert security.validate_server_config()['username']=='admin'


def test_owner_auth_verifies_hash_and_rejects_bad_headers(monkeypatch,owner):
    monkeypatch.setenv('CATSTUDIO_AUTH_FILE',str(owner))
    cfg=security.auth_config()
    def basic(value):return 'Basic '+base64.b64encode(value.encode()).decode()
    assert security.authorized(basic('admin:synthetic-owner-password-123!'),cfg)
    for header in ['', 'Bearer abc', 'Basic !!!', basic('admin:wrong'),basic('other:synthetic-owner-password-123!'),basic('no-colon')]:
        assert not security.authorized(header,cfg)
    assert 'synthetic-owner-password' not in owner.read_text()


@pytest.mark.parametrize('origin,expected',[
    ('https://maopian.migucomi.com',True),('https://maopian.migucomi.com:443',True),
    ('http://maopian.migucomi.com',False),('https://maopian.migucomi.com:8443',False),
    ('https://evil.example',False),('null',False),('https://maopian.migucomi.com.evil.example',False),
    ('https://admin@maopian.migucomi.com',False),('http://localhost:5173',True),
    ('https://maopian.migucomi.com/path',False),('https://maopian.migucomi.com:bad',False),
])
def test_exact_secure_origins(origin,expected):
    assert security.valid_origin(origin,{'maopian.migucomi.com','localhost'}) is expected


def test_wildcard_hosts_forbidden(monkeypatch):
    monkeypatch.setenv('CATSTUDIO_ALLOWED_HOSTS','*')
    with pytest.raises(RuntimeError):security.allowed_hosts()


def test_server_master_key_is_durable_and_concurrency_safe(monkeypatch,tmp_path):
    from catstudio import llm
    path=tmp_path/'private'/'master.key'
    monkeypatch.setenv('CATSTUDIO_MASTER_KEY_FILE',str(path))
    with ThreadPoolExecutor(max_workers=8) as pool:
        tokens=list(pool.map(lambda _:llm.encrypt('synthetic-not-a-real-api-key'),range(8)))
    first=path.read_bytes()
    assert all(llm.decrypt(t)=='synthetic-not-a-real-api-key' for t in tokens)
    assert path.read_bytes()==first
    path.write_text('invalid-key')
    with pytest.raises(ValueError):llm.fernet()
    assert path.read_text()=='invalid-key'  # Never silently replace a lost/corrupt key.


@pytest.mark.skipif(os.name=='nt',reason='Unix file modes')
def test_server_secrets_reject_world_readable_files(monkeypatch,owner):
    owner.chmod(0o644)
    monkeypatch.setenv('CATSTUDIO_AUTH_FILE',str(owner))
    with pytest.raises(RuntimeError):security.auth_config()


def test_credentials_cannot_be_overwritten(owner):
    original=owner.read_bytes()
    script=Path(__file__).resolve().parents[1]/'scripts/create_server_auth.py'
    result=subprocess.run([sys.executable,str(script),'--file',str(owner),'--stdin'],
                          input='replacement-is-not-allowed\n',text=True,capture_output=True)
    assert result.returncode!=0 and owner.read_bytes()==original
