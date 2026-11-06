"""Upgrade the existing single-owner host, preserving volumes, auth and gateway.

Run only after loading the verified release image. The sample ZIP is uploaded
through the existing authenticated file API. No plaintext credentials in argv.
"""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import sqlite3
import subprocess
import tarfile
import tempfile
import time
import urllib.error
import urllib.request
import zipfile

ROOT = Path('/opt/catstudio')
UNIT = Path('/etc/containers/systemd/catstudio.container')


def run(*args, **kw):
    return subprocess.run(args, check=True, capture_output=True, **kw)


def volume(name):
    info = json.loads(run('podman', 'volume', 'inspect', name).stdout)[0]
    path = Path(info['Mountpoint']).resolve()
    if not path.is_relative_to('/var/lib/containers/storage/volumes') or path.name != '_data':
        raise RuntimeError('Unexpected volume path')
    return path


def updated_unit(body, image):
    if not re.fullmatch(r'localhost/catstudio:\d+\.\d+\.\d+', image):
        raise ValueError('Expected a fixed release image')
    if len(re.findall(r'^Image=.*$', body, re.M)) != 1:
        raise ValueError('Expected exactly one image declaration')
    for required in ('Volume=catstudio-data:', 'Volume=catstudio-secrets:', 'PublishPort=127.0.0.1:8776:8776', 'ReadOnly=true'):
        if required not in body:
            raise ValueError('Production unit layout differs; inspect before upgrading')
    body = re.sub(r'^Image=.*$', 'Image=' + image, body, flags=re.M)
    entry = 'Environment=CATSTUDIO_EXAMPLES_DIR=/var/lib/catstudio/data/examples'
    if 'Environment=CATSTUDIO_EXAMPLES_DIR=' in body:
        body = re.sub(r'^Environment=CATSTUDIO_EXAMPLES_DIR=.*$', entry, body, flags=re.M)
    else:
        body = body.replace('[Container]', '[Container]\n' + entry, 1)
    return body


def sample_archive(data, file_id, manifest):
    with sqlite3.connect(data / 'catstudio.db') as db:
        row = db.execute('SELECT data FROM file_object WHERE id=? AND deleted_at IS NULL', (file_id,)).fetchone()
    if not row:
        raise RuntimeError('Uploaded asset pack not found')
    file = json.loads(row[0]); path = (data / file['rel_path']).resolve()
    if not path.is_relative_to(data) or not path.is_file():
        raise RuntimeError('Invalid uploaded asset path')
    with path.open('rb') as f:
        if hashlib.file_digest(f, 'sha256').hexdigest() != file['sha256']:
            raise RuntimeError('Uploaded pack hash mismatch')
    with zipfile.ZipFile(path) as z:
        entries = {x['filename']: x for x in manifest['media'].values()}
        if len(z.namelist()) != len(entries) or set(z.namelist()) != set(entries):
            raise RuntimeError('Sample ZIP does not match the release allowlist')
        for name, entry in entries.items():
            if z.getinfo(name).file_size != entry['size']:
                raise RuntimeError('Sample size mismatch: ' + name)
            with z.open(name) as f:
                if hashlib.file_digest(f, 'sha256').hexdigest() != entry['sha256']:
                    raise RuntimeError('Sample hash mismatch: ' + name)
    return path


def encrypted_secret_backup(secrets, destination):
    key = ROOT / 'private/backup-encryption.key'
    key.parent.mkdir(mode=0o700, exist_ok=True)
    if not key.exists():
        fd = os.open(key, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'w') as f:
            f.write(os.urandom(48).hex())
    if key.is_symlink() or key.stat().st_mode & 0o077:
        raise RuntimeError('Backup key must be a private regular file')
    payload = io.BytesIO()
    with tarfile.open(fileobj=payload, mode='w') as tar:
        tar.add(secrets, arcname='secrets')
    run('openssl', 'enc', '-aes-256-cbc', '-salt', '-pbkdf2', '-iter', '200000',
        '-pass', 'file:' + str(key), '-out', str(destination), input=payload.getvalue())
    destination.chmod(0o600)


def wait_ready(version):
    for _ in range(60):
        try:
            urllib.request.urlopen('http://127.0.0.1:8776/api/health', timeout=2)
            raise RuntimeError('Authentication unexpectedly absent')
        except urllib.error.HTTPError as exc:
            if exc.code == 401:
                actual = run('podman', 'exec', 'catstudio', 'python', '-c', 'from catstudio import __version__; print(__version__)').stdout.decode().strip()
                if actual == version:
                    return
        except (urllib.error.URLError, TimeoutError):
            pass
        time.sleep(1)
    raise RuntimeError('New release failed its readiness check')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--version', required=True)
    parser.add_argument('--example-file-id', required=True)
    args = parser.parse_args()
    if os.geteuid() != 0 or not re.fullmatch(r'\d+\.\d+\.\d+', args.version):
        raise RuntimeError('Root operator and fixed version required')
    if not shutil.which('openssl'):
        raise RuntimeError('openssl is required for encrypted secret backup')
    image = 'localhost/catstudio:' + args.version
    run('podman', 'image', 'exists', image)
    if run('systemctl', 'is-active', 'catstudio').stdout.strip() != b'active':
        raise RuntimeError('Expected the existing service to be active')
    body = UNIT.read_text(); pending = updated_unit(body, image)
    data, secrets = volume('catstudio-data'), volume('catstudio-secrets')
    source = Path(__file__).resolve().parents[1]
    if (source / 'VERSION').read_text().strip() != args.version:
        raise RuntimeError('Source and image versions differ')
    manifest = json.loads((source / 'catstudio/resources/pet-campus-001.json').read_text())
    archive = sample_archive(data, args.example_file_id, manifest)
    if (data / 'examples/pet-campus-001').exists():
        raise RuntimeError('Example directory already exists; inspect before replacing')
    required = sum(p.stat().st_size for p in data.rglob('*') if p.is_file())
    if shutil.disk_usage(ROOT).free < required * 2 + 512 * 1024**2:
        raise RuntimeError('Insufficient space for a safe backup and sample install')
    backups = ROOT / 'backups'; backups.mkdir(mode=0o700, exist_ok=True)
    backup = Path(tempfile.mkdtemp(prefix='before-' + args.version + '-', dir=backups)); backup.chmod(0o700)
    (backup / 'catstudio.container').write_text(body)
    (backup / 'catstudio.container').chmod(0o600)
    encrypted_secret_backup(secrets, backup / 'secrets.tar.enc')
    gateway_hash = hashlib.sha256(Path('/etc/caddy/Caddyfile').read_bytes()).hexdigest()
    run('systemctl', 'stop', 'catstudio')
    try:
        with tarfile.open(backup / 'data.tar.gz', 'w:gz') as tar:
            tar.add(data, arcname='data')
        (backup / 'data.tar.gz').chmod(0o600)
        dest = data / 'examples/pet-campus-001'
        if dest.exists():
            raise RuntimeError('Example directory already exists; inspect before replacing')
        dest.mkdir(parents=True, mode=0o755)
        with zipfile.ZipFile(archive) as z:
            for entry in manifest['media'].values():
                target = dest / entry['filename']
                with z.open(entry['filename']) as src, target.open('wb') as out:
                    shutil.copyfileobj(src, out)
                os.chown(target, 10001, 10001); target.chmod(0o644)
        os.chown(dest, 10001, 10001)
        UNIT.write_text(pending)
        run('systemctl', 'daemon-reload'); run('systemctl', 'start', 'catstudio')
        wait_ready(args.version)
        if hashlib.sha256(Path('/etc/caddy/Caddyfile').read_bytes()).hexdigest() != gateway_hash:
            raise RuntimeError('Shared gateway changed unexpectedly')
    except Exception:
        UNIT.write_text(body)
        run('systemctl', 'daemon-reload'); run('systemctl', 'restart', 'catstudio')
        raise
    (backup / 'upgrade.json').write_text(json.dumps({'version': args.version, 'image': image, 'gateway_sha256': gateway_hash, 'sample_files': len(manifest['media']), 'data_restored': False}))
    print(json.dumps({'version': args.version, 'backup': str(backup), 'sample_files': len(manifest['media']), 'status': 'ready'}))


if __name__ == '__main__':
    main()
