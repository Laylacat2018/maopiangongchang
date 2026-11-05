"""Real HTTP acceptance on an isolated server, using synthetic media only.

The full mode creates marked acceptance projects. Do not use it on user data.
Password comes from a private local JSON file, never a CLI argument.
"""
import argparse
import importlib.util
import json
import sys
import time
from pathlib import Path
import httpx

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url',required=True)
    parser.add_argument('--credentials',required=True)
    parser.add_argument('--evidence',required=True)
    parser.add_argument('--resume',action='store_true',help='Verify the previous acceptance data after a restart')
    args=parser.parse_args()
    cfg=json.loads(Path(args.credentials).read_text(encoding='utf-8'))
    with httpx.Client(base_url=args.url,auth=(cfg['username'],cfg['password']),timeout=180) as c:
        for _ in range(60):
            try:
                if c.get('/api/health').status_code==200:break
            except httpx.TransportError:pass
            time.sleep(1)
        else:raise RuntimeError('Server did not become healthy')
        health=c.get('/api/health').json()
        assert health['ffmpeg'] and health['ffprobe']
        assert c.get('/').status_code==200
        with httpx.Client(base_url=args.url,timeout=20) as anon:
            for path in ['/','/api/health','/api/state','/docs','/files/unknown']:
                assert anon.get(path).status_code==401,path
        assert c.get('/api/state',headers={'Host':'evil.example'}).status_code==403
        assert c.post('/api/projects',json={'name':'must-not-exist'},headers={'Origin':'https://evil.example'}).status_code==403
        if args.resume:
            saved=json.loads(Path(args.evidence).read_text())
            state=c.get('/api/state').json()
            p=next(p for p in state['project'] if p['id']==saved['project_id'])
            assert p['status']=='complete'
            assert state['settings']['llm_text']['has_key']
            response=c.get('/files/'+saved['file_id'],headers={'Range':'bytes=0-63'})
            assert response.status_code==206 and len(response.content)==64
            print('PASS: restart preserved projects, media and encrypted credential configuration.')
            return
        spec=importlib.util.spec_from_file_location('acceptance_workflow',ROOT/'tests/test_workflow.py')
        module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
        media=module.media_files.__wrapped__()
        result=module.production.__wrapped__(c,media)
        module.test_01_complete_production_chain(result,c)
        assert c.post('/api/settings/llm_text',json={'provider':'openai','base_url':'http://127.0.0.1:1/v1',
                    'model':'synthetic-test-only','api_key':'synthetic-server-test-key-not-real'}).status_code==200
        response=c.get('/files/'+result['video']['id'],headers={'Range':'bytes=0-63'})
        assert response.status_code==206 and len(response.content)==64
        evidence={'version':health['version'],'project_id':result['pid'],'file_id':result['video']['id'],
                  'checks':['authentication','host/origin boundaries','7 production stages','media Range','packages','final QC','CSV retrospective']}
        Path(args.evidence).parent.mkdir(parents=True,exist_ok=True)
        Path(args.evidence).write_text(json.dumps(evidence,indent=2),encoding='utf-8')
        print('PASS: authenticated HTTP production workflow completed; evidence contains IDs only.')


if __name__=='__main__':main()
