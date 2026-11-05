"""Operator helper for the authorized existing Podman/Caddy host. No credentials in source.

Run as root, after loading the verified image and checking out v1.0.1 into
/opt/catstudio/source-v1.0.1. Authentication hash must already be at
/opt/catstudio/private/access.json (0600). Never supply a plaintext password.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time
import urllib.error
import urllib.request

ROOT=Path('/opt/catstudio')
SOURCE=ROOT/'source-v1.0.1'
UNIT=Path('/etc/containers/systemd/catstudio.container')
DOMAIN='maopian.migucomi.com'
IMAGE='localhost/catstudio:1.0.1'
CADDY_CONFIG=Path('/etc/caddy/Caddyfile')


def run(*args):
    return subprocess.run(args,check=True,capture_output=True,text=True).stdout.strip()


def wait_ready():
    for _ in range(60):
        try:
            urllib.request.urlopen('http://127.0.0.1:8776/api/health',timeout=3)
            raise RuntimeError('Backend unexpectedly allows unauthenticated access')
        except urllib.error.HTTPError as exc:
            if exc.code==401:
                print(json.dumps({'service':run('systemctl','is-active','catstudio'), 'anonymous_http':401}))
                return
        except (urllib.error.URLError,TimeoutError):pass
        time.sleep(1)
    raise RuntimeError('Backend did not become ready; inspect journalctl -u catstudio')


def bootstrap():
    assert not UNIT.exists(), 'An application unit already exists; inspect before making changes'
    assert (SOURCE/'VERSION').read_text().strip()=='1.0.1'
    run('podman','image','exists',IMAGE)
    auth=ROOT/'private/access.json'
    assert auth.is_file() and not auth.is_symlink() and auth.stat().st_mode & 0o077==0
    cfg=json.loads(auth.read_text());assert cfg['algorithm']=='pbkdf2-sha256' and cfg['iterations']==600000
    for name in ['catstudio-data','catstudio-secrets','catstudio-acceptance-data','catstudio-acceptance-secrets']:
        exists=subprocess.run(['podman','volume','exists',name],capture_output=True).returncode==0
        assert not exists, 'Refusing to use an existing volume without inspection: '+name
        run('podman','volume','create',name)
        info=json.loads(run('podman','volume','inspect',name))[0]
        mount=Path(info['Mountpoint']).resolve()
        assert mount.is_relative_to('/var/lib/containers/storage/volumes') and mount.name=='_data'
        os.chown(mount,10001,10001)
        if name.endswith('secrets'):
            mount.chmod(0o700)
            target=mount/'access.json';shutil.copyfile(auth,target);target.chmod(0o600);os.chown(target,10001,10001)
    UNIT.parent.mkdir(parents=True,exist_ok=True)
    content=(SOURCE/'deploy/catstudio.container').read_text()
    content=content.replace('catstudio-data:', 'catstudio-acceptance-data:').replace('catstudio-secrets:', 'catstudio-acceptance-secrets:')
    UNIT.write_text(content);UNIT.chmod(0o644)
    run('systemctl','daemon-reload')
    run('systemctl','start','catstudio')
    wait_ready()
    print('Independent acceptance volumes active; production volumes remain empty.')


def proxy():
    config=CADDY_CONFIG
    body=config.read_text();assert DOMAIN not in body, 'Domain already configured; inspect before changing'
    backup=ROOT/'backups';backup.mkdir(mode=0o700,exist_ok=True)
    saved=backup/('Caddyfile-before-catstudio-'+time.strftime('%Y%m%d-%H%M%S'))
    shutil.copyfile(config,saved);saved.chmod(0o600)
    block='\n\n# CatStudio V1.0.1\n'+DOMAIN+' {\n    encode zstd gzip\n    request_body {\n        max_size 2048MB\n    }\n    reverse_proxy 127.0.0.1:8776\n    header Strict-Transport-Security "max-age=31536000"\n}\n'
    pending=config.with_name('Caddyfile.catstudio-pending')
    metadata=config.stat();pending.write_text(body+block)
    pending.chmod(metadata.st_mode & 0o777);os.chown(pending,metadata.st_uid,metadata.st_gid)
    run('/usr/local/bin/caddy','validate','--config',str(pending),'--adapter','caddyfile')
    os.replace(pending,config)
    try:run('/usr/local/bin/caddy','reload','--config',str(config),'--adapter','caddyfile')
    except Exception:
        shutil.copyfile(saved,config)
        config.chmod(metadata.st_mode & 0o777);os.chown(config,metadata.st_uid,metadata.st_gid)
        run('/usr/local/bin/caddy','reload','--config',str(config),'--adapter','caddyfile')
        raise
    print(json.dumps({'caddy':'reloaded','domain':DOMAIN,'previous_config_sha256':hashlib.sha256(saved.read_bytes()).hexdigest()}))


def production():
    content=UNIT.read_text()
    assert 'catstudio-acceptance-data:' in content, 'Acceptance mode required before clean production activation'
    run('systemctl','stop','catstudio')
    content=content.replace('catstudio-acceptance-data:', 'catstudio-data:').replace('catstudio-acceptance-secrets:', 'catstudio-secrets:')
    UNIT.write_text(content)
    run('systemctl','daemon-reload');run('systemctl','start','catstudio')
    wait_ready()
    print('Clean production volumes activated; acceptance volumes retained separately.')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('phase',choices=['bootstrap','proxy','production'])
    args=parser.parse_args()
    assert os.geteuid()==0,'This helper is for the authorized root operator only'
    {'bootstrap':bootstrap,'proxy':proxy,'production':production}[args.phase]()
