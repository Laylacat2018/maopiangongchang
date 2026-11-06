"""Install only the allowlisted first-film assets. No voices or credentials copied."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]


def install(source, destination):
    source = Path(source).resolve()
    dest = Path(destination).resolve() / 'pet-campus-001'
    data = json.loads((ROOT / 'catstudio/resources/pet-campus-001.json').read_text(encoding='utf-8'))
    checked = []
    for entry in data['media'].values():
        path = (source / entry['source_relative']).resolve()
        target = (dest / entry['filename']).resolve()
        if not path.is_relative_to(source) or not target.is_relative_to(dest):
            raise ValueError('素材路径越界')
        with path.open('rb') as f:
            if hashlib.file_digest(f, 'sha256').hexdigest() != entry['sha256']:
                raise ValueError('素材校验不符：' + entry['filename'])
        checked.append((path, target))
    dest.mkdir(parents=True, exist_ok=True)
    for path, target in checked:
        if path != target:
            shutil.copyfile(path, target)
    print(f'已校验并安装 {len(checked)} 个首片素材：{dest}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', help='首片 episode 目录')
    parser.add_argument('--destination', default=str(ROOT / 'sample-media'))
    args = parser.parse_args()
    install(args.source, args.destination)
