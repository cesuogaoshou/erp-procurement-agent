"""Start isolated loopback services; never imports, resets, or switches V1."""
import argparse
import json
import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

from backend.app.db.import_v2_data import validate_target
from backend.app.services.dataset_v2 import ROOT


def main():
    parser=argparse.ArgumentParser(description='Start V2 on 8002/5176 using explicit V2_DATABASE_URL; no initialization.')
    parser.add_argument('--backend-port',type=int,default=8002)
    parser.add_argument('--frontend-port',type=int,default=5176)
    args=parser.parse_args()
    url=os.environ.get('V2_DATABASE_URL','')
    validate_target(url)
    for port in (args.backend_port,args.frontend_port):
        with socket.socket() as s:
            try: s.bind(('127.0.0.1',port))
            except OSError: raise SystemExit('V2_port_in_use:'+str(port)) from None
    out=ROOT/'reports/generated/v2_acceptance_20261029'
    out.mkdir(parents=True,exist_ok=True)
    env=os.environ.copy()
    env.update(DATABASE_URL=url,ERP_API_PROXY_TARGET=f'http://127.0.0.1:{args.backend_port}',
        VITE_API_BASE_URL='/api', VITE_DEMO_LABEL=' ')
    flags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0
    processes=[]
    try:
        for name,cmd in [('backend',[sys.executable,'-m','uvicorn','backend.app.v2_main:app','--host','127.0.0.1','--port',str(args.backend_port)]),
                         ('frontend',['node',str(ROOT/'frontend/node_modules/vite/bin/vite.js'),'--host','127.0.0.1','--port',str(args.frontend_port),'--strictPort'])]:
            with (out/f'v2-{name}.log').open('a',encoding='utf-8') as log:
                child=subprocess.Popen(cmd,cwd=ROOT/'frontend' if name=='frontend' else ROOT,env=env,
                    stdout=log,stderr=log,creationflags=flags)
                processes.append(child)
        for _ in range(40):
            if any(p.poll() is not None for p in processes): raise RuntimeError('V2_service_exited')
            try:
                with urllib.request.urlopen(f'http://127.0.0.1:{args.backend_port}/environment',timeout=1) as r:
                    assert json.load(r)['environment']=='V2'
                with urllib.request.urlopen(f'http://127.0.0.1:{args.frontend_port}',timeout=1): pass
                break
            except (OSError,AssertionError): time.sleep(.5)
        else: raise RuntimeError('V2_start_timeout')
        result={'backend_pid':processes[0].pid,'frontend_pid':processes[1].pid,
                'api':f'http://127.0.0.1:{args.backend_port}', 'page':f'http://127.0.0.1:{args.frontend_port}',
                'environment':'V2','database':'erp_procurement_demo_v2'}
        (out/'services.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
        print(json.dumps(result))
    except Exception:
        for p in processes:
            if p.poll() is None: p.terminate()
        raise SystemExit('V2_start_failed; inspect isolated logs') from None


if __name__=='__main__': main()
