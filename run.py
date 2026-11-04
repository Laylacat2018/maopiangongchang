"""一条命令安装依赖、构建前端并启动本地工作台；服务在后台运行。"""
import json, os, socket, subprocess, sys, time, urllib.request, webbrowser
from pathlib import Path
ROOT=Path(__file__).resolve().parent
PORT=int(os.environ.get('CATSTUDIO_PORT','8776'))
PY=ROOT/'.venv'/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
def command(args,cwd=ROOT):subprocess.run([str(x) for x in args],cwd=cwd,check=True)
def main():
    if not PY.exists():
        print('正在创建 Python 虚拟环境…')
        command([sys.executable,'-m','venv',ROOT/'.venv'])
        command([PY,'-m','pip','install','-r','requirements.txt'])
    check=subprocess.run([str(PY),'-c','import fastapi,uvicorn,sqlmodel,huey,PIL,pandas,httpx,cryptography,keyring,jinja2,multipart'],capture_output=True)
    if check.returncode:command([PY,'-m','pip','install','-r','requirements.txt'])
    web=ROOT/'web';dist=web/'dist/index.html'
    npm='npm.cmd' if os.name=='nt' else 'npm'
    if not (web/'node_modules').exists():command([npm,'ci','--no-audit','--no-fund'],web)
    if not dist.exists() or max(p.stat().st_mtime for p in (web/'src').rglob('*') if p.is_file())>dist.stat().st_mtime:
        command([npm,'run','build'],web)
    url=f'http://127.0.0.1:{PORT}'
    try:
        info=json.load(urllib.request.urlopen(url+'/api/health',timeout=2))
        if info.get('app_id')!='catstudio':raise RuntimeError(f'{PORT} 端口被其他应用占用，请设置 CATSTUDIO_PORT')
        print('猫片工场已在运行：'+url)
    except (OSError,ValueError):
        (ROOT/'data').mkdir(exist_ok=True)
        log=open(ROOT/'data/server.log','ab')
        proc=subprocess.Popen([str(PY),'-X','utf8','-m','uvicorn','catstudio.main:app','--host','127.0.0.1','--port',str(PORT),'--no-access-log'],cwd=ROOT,stdin=subprocess.DEVNULL,stdout=log,stderr=log,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0),start_new_session=os.name!='nt')
        (ROOT/'data/server-pid.json').write_text(json.dumps({'pid':proc.pid,'port':PORT,'python':str(PY),'cwd':str(ROOT)}),encoding='utf-8')
        for _ in range(80):
            try:
                info=json.load(urllib.request.urlopen(url+'/api/health',timeout=1))
                if info.get('app_id')=='catstudio':break
            except OSError:pass
            if proc.poll() is not None:raise RuntimeError('启动失败，请检查 data/server.log')
            time.sleep(.25)
        else:raise RuntimeError('启动超时，请检查 data/server.log')
        print('猫片工场已启动：'+url)
    if '--no-browser' not in sys.argv:webbrowser.open(url)
if __name__=='__main__':main()
