"""Copy only Git-tracked source to a new directory, excluding local runtime data."""
import json, shutil, subprocess, tempfile
from pathlib import Path

root=Path(__file__).resolve().parents[1]
target=Path(tempfile.mkdtemp(prefix='catstudio-v1-clean-'))
files=subprocess.check_output(['git','ls-files','-z'],cwd=root).decode('utf-8').split('\0')
for relative in filter(None,files):
    source=root/relative
    if not source.is_file():continue
    destination=target/relative
    destination.parent.mkdir(parents=True,exist_ok=True)
    shutil.copy2(source,destination)
state=root/'tests/output/release-validation.json'
state.parent.mkdir(parents=True,exist_ok=True)
state.write_text(json.dumps({'clean_checkout':str(target),'copied_files':len([x for x in files if x])},ensure_ascii=False,indent=2),encoding='utf-8')
print(target)
