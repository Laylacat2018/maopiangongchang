"""Desktop defaults and explicit single-owner server configuration."""
import base64
import hashlib
import hmac
import json
import os
import stat
from pathlib import Path
from urllib.parse import urlsplit

LOCAL_HOSTS = {'localhost', '127.0.0.1', 'testserver', '::1'}


def read_private_file(path):
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise RuntimeError('密钥/认证文件必须是普通文件，不能使用符号链接')
    if os.name != 'nt' and stat.S_IMODE(path.stat().st_mode) & 0o077:
        raise RuntimeError('密钥/认证文件权限必须为 0600 或更严格')
    return path.read_text(encoding='utf-8').strip()


def allowed_hosts():
    hosts = {x.strip().lower() for x in os.environ.get(
        'CATSTUDIO_ALLOWED_HOSTS', ','.join(sorted(LOCAL_HOSTS))).split(',') if x.strip()}
    if not hosts or '*' in hosts or any('/' in h or ' ' in h for h in hosts):
        raise RuntimeError('必须配置明确的访问主机白名单，禁止通配符')
    return hosts


def auth_config():
    path = os.environ.get('CATSTUDIO_AUTH_FILE')
    if not path:
        return None
    try:
        cfg = json.loads(read_private_file(path))
        assert cfg['username'] and ':' not in cfg['username']
        assert cfg['algorithm'] == 'pbkdf2-sha256' and cfg['iterations'] == 600000
        assert len(bytes.fromhex(cfg['salt'])) == 32 and len(bytes.fromhex(cfg['hash'])) == 32
        return cfg
    except Exception as e:
        raise RuntimeError('访问认证配置不可用，请检查私有认证文件') from e


def validate_server_config():
    hosts = allowed_hosts()
    auth = auth_config()
    if hosts - LOCAL_HOSTS:
        if not auth or not os.environ.get('CATSTUDIO_MASTER_KEY_FILE'):
            raise RuntimeError('域名部署必须同时配置访问认证文件和持久化主密钥文件')
    return auth


def authorized(header, cfg):
    if cfg is None:
        return True
    try:
        scheme, encoded = header.split(' ', 1)
        if scheme.lower() != 'basic':
            return False
        user, password = base64.b64decode(encoded, validate=True).decode('utf-8').split(':', 1)
        if not hmac.compare_digest(user.encode('utf-8'), cfg['username'].encode('utf-8')):
            return False
        if len(password) > 1024:
            return False
        value = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), bytes.fromhex(cfg['salt']), cfg['iterations'])
        return hmac.compare_digest(value, bytes.fromhex(cfg['hash']))
    except (ValueError, UnicodeError):
        return False


def valid_origin(origin, hosts):
    try:
        parsed = urlsplit(origin)
        host = parsed.hostname
        if host not in hosts or parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment:
            return False
        if host in LOCAL_HOSTS:
            return parsed.scheme in {'http', 'https'}
        return parsed.scheme == 'https' and parsed.port in {None, 443}
    except ValueError:
        return False
