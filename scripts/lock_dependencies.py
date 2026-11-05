"""Regenerate the release lock from a clean, verified virtual environment."""
from pathlib import Path
from importlib import metadata

root=Path(__file__).resolve().parents[1]
packages=sorted((d.metadata['Name'],d.version) for d in metadata.distributions() if d.metadata['Name'].lower() not in {'pip','setuptools'})
lines=['# CatStudio V1.0 release lock, clean Windows Python 3.14 install, 2026-11-05.', '# OS-specific dependencies of keyring are selected by pip on the target OS.']
for name,version in packages:
    marker=' ; sys_platform == "win32"' if name.lower()=='pywin32-ctypes' else ''
    lines.append(f'{name}=={version}{marker}')
(root/'requirements-lock.txt').write_text('\n'.join(lines)+'\n',encoding='utf-8')
print(f'Locked {len(packages)} distributions.')
