"""Check release versions and prevent local runtime files/secrets entering Git."""
import ast, json, re, subprocess
from pathlib import Path
root=Path(__file__).resolve().parents[1]
version=(root/'VERSION').read_text().strip()
assert re.fullmatch(r'\d+\.\d+\.\d+',version), 'VERSION must use SemVer'
module=ast.parse((root/'catstudio/__init__.py').read_text(encoding='utf-8'))
backend=next(ast.literal_eval(n.value) for n in module.body if isinstance(n,ast.Assign) and any(getattr(t,'id','')=='__version__' for t in n.targets))
assert backend==version
assert json.loads((root/'web/package.json').read_text())['version']==version
assert json.loads((root/'web/package-lock.json').read_text())['version']==version
paths=subprocess.check_output(['git','ls-files','-z'],cwd=root).decode('utf-8').split('\0')
issues=[]
patterns=[re.compile(r'gh[pousr]_[A-Za-z0-9_]{25,}'),re.compile(r'github_pat_[A-Za-z0-9_]{30,}'),re.compile(r'\bsk-(?:proj-)?[A-Za-z0-9_-]{24,}'),re.compile(r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----')]
for relative in filter(None,paths):
    p=Path(relative)
    if any(x in p.parts for x in ['data','node_modules','.venv','.venv-release','release-artifacts']) or p.suffix in {'.db','.pem','.key'} or p.name=='.env':issues.append(relative+' contains local runtime data')
    try:body=(root/p).read_text(encoding='utf-8')
    except (UnicodeDecodeError,OSError):continue
    for number,line in enumerate(body.splitlines(),1):
        if any(pattern.search(line) for pattern in patterns):issues.append(f'{relative}:{number}: possible secret (value suppressed)')
if issues:raise SystemExit('\n'.join(issues))
print(f'Release {version}: versions consistent; {len(list(filter(None,paths)))} tracked files checked; no runtime data or matching secrets.')
