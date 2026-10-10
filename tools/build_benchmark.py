"""Build all paired fixtures and check them against independent Python truth."""
from pathlib import Path
import json
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'python'))
from wuxiang.build import ROOT,protect,run,write_json,sha256,tool_paths,verify
from wuxiang.bench import CATEGORIES,cases

def main():
    tools,env=tool_paths(); entries=[]; checks=[]
    for task_id,category in enumerate(CATEGORIES):
        for seed in (11,23,47):
            out=ROOT/f'build/benchmark/{category}/{seed}'
            config={'schema_version':1,'mode':'balanced','standard':'c++20','seed':seed,
                    'module':{'sources':[str(ROOT/'bench/tasks.cpp')]},
                    'main':{'sources':[str(ROOT/'bench/harness.cpp')]},
                    'include_dirs':[str(ROOT/'bench')],'output_dir':str(out),'defines':['TASK_ID='+str(task_id)],'exports':['wuxiang_task']}
            build=protect(config)
            corpus=cases(category,seed)
            stdin=''.join(f"{r['x']} {r['input_hex'] or '-'} {r['capacity']}\n" for r in corpus)
            expected='\n'.join(f"{r['expected_value']} {r['expected_output_hex'] or '-'}" for r in corpus)
            for variant,b in build['binaries'].items():
                actual=run([b['path']],input=stdin,timeout=60).strip()
                passed=actual==expected
                checks.append({'category':category,'seed':seed,'variant':variant,'cases':len(corpus),'ok':passed})
                if not passed:
                    write_json(ROOT/'reports/benchmark-build-checks.json',{'schema_version':1,'ok':False,'checks':checks})
                    raise RuntimeError('Independent differential failure: '+category+'/'+str(seed)+'/'+variant)
                entries.append({'id':category+'-'+str(seed)+'-'+variant,'category':category,'seed':seed,'variant':variant,
                                'artifact_path':b['path'],'sha256':b['sha256'],'verified':True})
            # verify uses config file-relative paths: all paths are absolute here.
            config['verification']={'stdin':stdin,'expected_stdout':expected}
            path=out/'config.json';write_json(path,config)
            checked=verify(path)
            checks.append({'category':category,'seed':seed,'variant':'limits','ok':checked['ok'],'limits':checked['limits']})
            print(category,seed,'behavior PASS; caps',checked['limits']['ok'],flush=True)
    keep={'INCLUDE','LIB','LIBPATH','PATH','SYSTEMROOT','WINDIR','TEMP','TMP','COMSPEC','PATHEXT','SYSTEMDRIVE'}
    clean_env={k:v for k,v in env.items() if k.upper() in keep}
    caps_pass=all(c['ok'] for c in checks)
    manifest={'schema_version':1,'tasks':entries,'toolchain':{'compiler':tools['cl'],'compiler_environment':clean_env},
              'ok':caps_pass,'behavior_verified':True,'balanced_caps_all_pass':caps_pass,
              'anti_rea_effectiveness_verified':False}
    write_json(ROOT/'reports/benchmark-build-manifest.json',manifest)
    write_json(ROOT/'reports/benchmark-build-checks.json',{'schema_version':1,'ok':all(c['ok'] for c in checks),'checks':checks})
    write_json(ROOT/'bench-config.json',{'schema_version':1,'benchmark':{'build_manifest_path':'reports/benchmark-build-manifest.json','output_dir':'benchmark-packs','seeds':[11,23,47]}})
    write_json(ROOT/'bench-research-config.json',{'schema_version':1,'benchmark':{'build_manifest_path':'reports/benchmark-build-manifest.json','output_dir':'research-packs-final','seeds':[11,23,47],'allow_failed_caps_for_research':True}})
    print('Manifest ready; anti-REA effectiveness still requires real sessions.',flush=True)

if __name__=='__main__':main()
