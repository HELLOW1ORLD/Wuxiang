import argparse
import json
import sys
from pathlib import Path
from .build import protect,verify
from .environment import doctor

def main():
    parser=argparse.ArgumentParser(prog='wuxiang')
    commands=parser.add_subparsers(dest='command',required=True)
    commands.add_parser('doctor')
    for name in ('protect','verify'):
        p=commands.add_parser(name);p.add_argument('--config',type=Path,required=True)
    p=commands.add_parser('bench'); sub=p.add_subparsers(dest='action',required=True)
    p=sub.add_parser('prepare');p.add_argument('--config',type=Path,required=True)
    p=sub.add_parser('score');p.add_argument('--submission',type=Path,required=True)
    p=sub.add_parser('summarize');p.add_argument('--scores',type=Path,required=True)
    args=parser.parse_args()
    try:
        if args.command=='doctor': result=doctor()
        elif args.command=='protect': result=protect(args.config)
        elif args.command=='verify': result=verify(args.config)
        else:
            from .bench import prepare,score,summarize_records
            if args.action=='summarize':result=summarize_records([json.loads(p.read_text(encoding='utf-8')) for p in args.scores.glob('*.json')])
            elif args.action=='score':result=score(args.submission)
            else:result=prepare(json.loads(args.config.read_text(encoding='utf-8-sig')),args.config)
        print(json.dumps(result,ensure_ascii=False,indent=2))
        return 0 if result.get('ok',True) else 1
    except Exception as e:
        print(json.dumps({'schema_version':1,'ok':False,'error':str(e)},ensure_ascii=False),file=sys.stderr)
        return 1

if __name__=='__main__':sys.exit(main())
