"""Scoped REA CLI fallback; no global MCP/environment configuration changes."""
from pathlib import Path
import argparse
import json
import os
import shutil
import subprocess
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'python'))
from wuxiang.build import ROOT,within_output,write_json,sha256

def discover():
    packages=Path(os.environ.get('LOCALAPPDATA',''))/'npm-cache/_npx'
    cli=None
    for pkg in packages.glob('*/node_modules/rea-agents/package.json'):
        if json.loads(pkg.read_text(encoding='utf-8')).get('version')=='6.2.0':
            cli=pkg.parent/'scripts/rea.mjs';break
    return cli,ROOT.parent/'Tools/Native/ghidra_12.1.4_PUBLIC',ROOT.parent/'Tools/Native/jdk-21.0.12.1+1'

def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=['analyze','decompile','trace']);p.add_argument('target',type=Path);p.add_argument('--query');p.add_argument('--out',type=Path,required=True)
    p.add_argument('--rea-cli',type=Path);p.add_argument('--ghidra',type=Path);p.add_argument('--java-home',type=Path)
    args=p.parse_args(); cli,ghidra,java=discover()
    cli=args.rea_cli or cli;ghidra=args.ghidra or ghidra;java=args.java_home or java
    out=within_output(args.out);out.mkdir(parents=True,exist_ok=True)
    env=dict(os.environ);env.update(GHIDRA_INSTALL_DIR=str(ghidra),JAVA_HOME=str(java),REA_GHIDRA_STARTUP_TIMEOUT_MS='120000')
    node=shutil.which('node.exe')
    if not cli or not cli.is_file() or not node:raise ValueError('Provide --rea-cli for pinned rea-agents 6.2.0 and install Node runtime')
    command=[node,str(cli),args.action,str(args.target.resolve())]
    if args.action!='analyze':
        if not args.query:raise ValueError('This operation requires --query')
        command.append(args.query)
    command+=['--provider','ghidra','--snapshot',str(out/'analysis.snapshot.json'),'--format','json','--full-output']
    r=subprocess.run(command,capture_output=True,text=True,encoding='utf-8',errors='replace',env=env,cwd=out,timeout=180)
    (out/'rea.stdout.json').write_text(r.stdout,encoding='utf-8');(out/'rea.stderr.log').write_text(r.stderr,encoding='utf-8')
    try:result=json.loads(r.stdout)
    except ValueError:result={}
    data=result.get('data') or {}
    ok=r.returncode==0 and result.get('ok') is True and not data.get('error') and data.get('code')!='provider_timeout'
    write_json(out/'probe.json',{'schema_version':1,'ok':ok,'target_sha256':sha256(args.target),'operation':args.action,'query':args.query,
               'rea_version':'6.2.0','provider':'ghidra','exit_code':r.returncode,'cli':str(cli),
               'is_ai_attack':False,'dynamic_analysis':'unevaluated'})
    print(json.dumps({'ok':ok,'output_dir':str(out)}));return 0 if ok else 1

if __name__=='__main__':sys.exit(main())
