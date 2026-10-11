from __future__ import annotations
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import statistics
import struct
import subprocess
import time
from .artifact_surface import prepare_surface, inspect_surface

ROOT = Path(__file__).resolve().parents[2]
LLVM = ROOT / 'toolchain/clang+llvm-20.1.8-x86_64-pc-windows-msvc'

def sha256(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        while b := f.read(1024*1024): h.update(b)
    return h.hexdigest()

def within_output(path, root=ROOT):
    p = Path(path).resolve()
    if not p.is_relative_to(root.resolve()) or p == root.resolve():
        raise ValueError('Output must be a child of the Wuxiang project: ' + str(p))
    return p

def load_config(path):
    path = Path(path).resolve()
    c = json.loads(path.read_text(encoding='utf-8-sig'))
    if c.get('schema_version') != 1: raise ValueError('Expected config schema_version=1')
    if c.get('mode', 'balanced') != 'balanced': raise ValueError('Only balanced mode is supported')
    prepare_surface(c.get('agent_surface'), c.get('seed', 11))
    for part in ('module', 'main'):
        if not c.get(part, {}).get('sources'): raise ValueError('Missing ' + part + '.sources')
        c[part]['sources'] = [str((path.parent / p).resolve()) for p in c[part]['sources']]
        for p in c[part]['sources']:
            if not Path(p).is_file(): raise ValueError('Missing source ' + p)
    c['include_dirs'] = [str((path.parent/p).resolve()) for p in c.get('include_dirs', [])]
    c['output_dir'] = str(within_output(path.parent / c.get('output_dir', '../build/example')))
    c['config_path'] = str(path)
    return c

def write_json(path, data):
    p = within_output(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2, ensure_ascii=False)+'\n', encoding='utf-8')

def validate_options(options):
    import re
    allowed={'/fp:strict','/fp:precise','/fp:fast','/arch:avx','/arch:avx2','/arch:sse2','/zc:__cplusplus','/zc:preprocessor','/permissive-','/utf-8','/wx'}
    if not isinstance(options,list):raise ValueError('compile_options must be an array')
    for option in options:
        if not isinstance(option,str) or (option.lower() not in allowed and not re.fullmatch(r'/[Ww][0-4]|/[Ww][Dd][0-9]+',option)):
            raise ValueError('Unsupported compiler option (output and ABI overrides forbidden): '+str(option))

def build_identity(c, compiler_dependencies=()):
    # Source/header closure owned by this project; system toolchains separately fingerprinted.
    paths=set(Path(p) for part in ('module','main') for p in c[part]['sources'])
    for directory in set(Path(p).parent for p in paths)|set(Path(p) for p in c.get('include_dirs',[]))|{ROOT/'include'}:
        if directory.is_dir():
            for suffix in ('*.h','*.hpp','*.hxx','*.inl','*.inc'):
                paths.update(directory.rglob(suffix))
    paths.update(Path(p) for p in compiler_dependencies)
    paths.update([ROOT/'src/transform.cpp',ROOT/'CMakeLists.txt',Path(__file__),
                  Path(__file__).with_name('artifact_surface.py')])
    identity={k:v for k,v in c.items() if k not in ('config_path','verification')}
    return {'config_sha256':hashlib.sha256(json.dumps(identity,sort_keys=True).encode()).hexdigest(),
            'dependencies':[{'path':str(p),'sha256':sha256(p)} for p in sorted(paths)]}

def make_dependencies(path):
    import re
    text=Path(path).read_text(encoding='utf-8').replace('\\\n','')
    text=re.split(r':\s',text,maxsplit=1)[1]
    tokens=re.findall(r'(?:\\.|[^\s\\])+',text)
    result=[]
    for token in tokens:
        token=re.sub(r'\\([ #$:\\])',r'\1',token)
        result.append(str(Path(token).resolve()))
    return result

def run(args, env=None, cwd=None, timeout=300, log=None, input=None):
    r = subprocess.run([str(a) for a in args], env=env, cwd=cwd, input=input,
                       text=True, encoding='utf-8', errors='replace', capture_output=True, timeout=timeout)
    if log: Path(log).write_text(r.stdout+r.stderr, encoding='utf-8')
    if r.returncode: raise RuntimeError(f'Command failed ({r.returncode}): {args[0]}\n{(r.stdout+r.stderr)[-6000:]}')
    return r.stdout

def msvc_environment():
    vswhere = Path(os.environ.get('ProgramFiles(x86)', 'C:/Program Files (x86)')) / 'Microsoft Visual Studio/Installer/vswhere.exe'
    if not vswhere.is_file(): raise ValueError('VS2022 vswhere.exe is missing')
    vs = run([vswhere, '-latest','-products','*','-requires','Microsoft.VisualStudio.Component.VC.Tools.x86.x64','-property','installationPath']).strip()
    script = Path(vs)/'Common7/Tools/VsDevCmd.bat'
    if not script.is_file(): raise ValueError('VS native build environment missing')
    env = dict(os.environ)
    env = {k.upper():v for k,v in env.items()}
    env['Path']=env.pop('PATH','')
    for k in ('CL','_CL_','LINK','_LINK_'):env.pop(k,None)
    import winreg
    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r'SOFTWARE\Microsoft\Windows Kits\Installed Roots') as key:
        sdk = Path(winreg.QueryValueEx(key,'KitsRoot10')[0])
    vc = sorted((Path(vs)/'VC/Tools/MSVC').iterdir(),key=lambda p:tuple(int(x) for x in p.name.split('.')))[-1]
    version = sorted((sdk/'Include').iterdir(),key=lambda p:tuple(int(x) for x in p.name.split('.')))[-1].name
    includes=[vc/'include',sdk/'Include'/version/'ucrt',sdk/'Include'/version/'shared',sdk/'Include'/version/'um',sdk/'Include'/version/'winrt']
    libs=[vc/'lib/x64',sdk/'Lib'/version/'ucrt/x64',sdk/'Lib'/version/'um/x64']
    env['INCLUDE']=';'.join(map(str,includes)); env['LIB']=';'.join(map(str,libs))
    env['Path']=str(vc/'bin/Hostx64/x64')+';'+str(sdk/'bin'/version/'x64')+';'+env.get('Path',env.get('PATH',''))
    env['VCToolsVersion']=vc.name; env['WindowsSDKVersion']=version; env['WindowsSdkDir']=str(sdk)
    return env, Path(vs)

def tool_paths():
    env, vs = msvc_environment()
    cmake = vs / 'Common7/IDE/CommonExtensions/Microsoft/CMake/CMake/bin/cmake.exe'
    tools = {'cl': shutil.which('cl.exe', path=env.get('Path',env.get('PATH'))),
             'link': shutil.which('link.exe', path=env.get('Path',env.get('PATH'))),
             'cmake':str(cmake), 'clang':str(LLVM/'bin/clang-cl.exe'),
             'llc':str(LLVM/'bin/llc.exe'),'objdump':str(LLVM/'bin/llvm-objdump.exe'),
             'transform':str(ROOT/'build/transform/bin/Release/wuxiang-ir.exe')}
    for name in ('cl','link','cmake','clang','llc','objdump'):
        if not tools[name] or not Path(tools[name]).is_file(): raise ValueError('Missing '+name+'; run tools/bootstrap_llvm.py')
    if '20.1.8' not in run([tools['clang'],'--version'],env):raise ValueError('Compiler is not pinned LLVM 20.1.8')
    if '20.1.8' not in run([tools['llc'],'--version'],env):raise ValueError('Code generator is not pinned LLVM 20.1.8')
    return tools, env

def doctor():
    result = {'schema_version':1, 'ok':False, 'capabilities':{},'errors':[]}
    try:
        tools, env = tool_paths()
        version = run([tools['clang'],'--version'],env)
        result.update(tools=tools, llvm_version=version.strip(), sdk=env.get('WindowsSDKVersion'), msvc_version=env.get('VCToolsVersion'))
        result['ok'] = '20.1.8' in version
        result['capabilities'] = {'native_build':result['ok'], 'transformer':Path(tools['transform']).is_file(),
                                  'dynamic_attack_evaluated':False, 'rea_agent_attack_evaluated':False}
    except (ValueError, RuntimeError) as e: result['errors'].append(str(e))
    write_json(ROOT/'reports/doctor.json',result)
    return result

def ensure_transformer(tools, env):
    exe=Path(tools['transform'])
    newest=max(p.stat().st_mtime for p in (ROOT/'src/transform.cpp',ROOT/'CMakeLists.txt'))
    if exe.is_file() and exe.stat().st_mtime>=newest: return
    run([tools['cmake'],'-S',ROOT,'-B',ROOT/'build/transform','-G','Visual Studio 17 2022','-A','x64',
         '-DLLVM_DIR='+str(LLVM/'lib/cmake/llvm')],env,timeout=300,log=ROOT/'reports/cmake-configure.log')
    run([tools['cmake'],'--build',ROOT/'build/transform','--config','Release','--parallel','8'],env,timeout=900,log=ROOT/'reports/transform-build.log')

def code_size(path):
    data=Path(path).read_bytes()
    machine,nsections,_,_,_,optional,_=struct.unpack_from('<HHIIIHH',data)
    if machine != 0x8664: raise ValueError('Expected Win64 COFF object')
    total=0
    for i in range(nsections):
        offset=20+optional+i*40
        name=data[offset:offset+8].rstrip(b'\0')
        if name.startswith(b'.text'):
            total+=struct.unpack_from('<I',data,offset+16)[0]
    return total

def function_code(tools, path, env):
    import re
    text=run([tools['objdump'],'--disassemble',path],env)
    bodies={}; name=None
    for line in text.splitlines():
        m=re.match(r'^[0-9a-fA-F]+ <(.+)>:$',line)
        if m: name=m.group(1); bodies[name]=[]
        elif name and re.match(r'^\s*[0-9a-fA-F]+:',line):
            # Raw bytes are compared; instruction addresses do not count as a change.
            fields=line.split(':',1)[1].strip().split('\t')
            bodies[name].append(fields[0].strip())
    return {n:'\n'.join(b) for n,b in bodies.items()}

def linked_symbol_present(exe,map_path,symbol):
    import re
    text=map_path.read_text(encoding='utf-8',errors='replace')
    addresses=[]
    for line in text.splitlines():
        columns=line.split()
        if len(columns)>=3 and columns[1]==symbol and re.fullmatch('[0-9A-Fa-f]+',columns[2]):addresses.append(int(columns[2],16))
    data=exe.read_bytes();pe=struct.unpack_from('<I',data,0x3c)[0]
    if data[pe:pe+4]!=b'PE\0\0':return False
    n=struct.unpack_from('<H',data,pe+6)[0];opt_size=struct.unpack_from('<H',data,pe+20)[0]
    image_base=struct.unpack_from('<Q',data,pe+24+24)[0]
    for i in range(n):
        offset=pe+24+opt_size+40*i
        virtual_size,rva,raw_size=struct.unpack_from('<III',data,offset+8)
        flags=struct.unpack_from('<I',data,offset+36)[0]
        if flags&0x20000000 and any(image_base+rva<=address<image_base+rva+max(virtual_size,raw_size) for address in addresses):return True
    return False

def protect(config):
    c = load_config(config) if not isinstance(config,dict) else config
    out=within_output(c['output_dir']); out.mkdir(parents=True,exist_ok=True)
    write_json(out/'build-status.json',{'schema_version':1,'ok':False,'status':'building'})
    for name in ('build-manifest.json','verification.json'):
        prior=out/name
        if prior.exists():prior.unlink()
    (ROOT/'reports').mkdir(exist_ok=True)
    tools,env=tool_paths(); ensure_transformer(tools,env)
    initial_identity=build_identity(c)
    validate_options(c.get('compile_options',[]))
    common=['/nologo','/MD','/EHsc','/GR','/std:'+c.get('standard','c++20'),'/O2','/DNDEBUG','/c', '/I'+str(ROOT/'include')]
    common+=['/I'+p for p in c.get('include_dirs',[])]+['/D'+d for d in c.get('defines',[])]+c.get('compile_options',[])
    forbidden=('/gl','-flto','/mt','/mdd','/eha','/gr-','/interface','/experimental:module','/clang:-flto','/clang:-fmodules','/clang:-fmodule')
    if any(a.lower().startswith(forbidden) for a in common): raise ValueError('Unsupported LTO, modules, mismatched CRT or SEH compilation flag')
    if c.get('standard','c++20') not in ('c++17','c++20'):raise ValueError('Supported standards: c++17 and c++20')
    if any(Path(p).suffix.lower() in ('.ixx','.cppm') for part in ('module','main') for p in c[part]['sources']):raise ValueError('C++ Modules are unsupported')
    main=[]; dependencies=[]
    for i,src in enumerate(c['main']['sources']):
        obj=out/f'main{i}.obj'; dep=out/f'main{i}.deps.json'
        run([tools['cl'],*common,src,'/Fo'+str(obj),'/sourceDependencies',dep],env,cwd=out,log=out/f'main{i}.log'); main.append(obj)
        dependencies+=json.loads(dep.read_text(encoding='utf-8-sig'))['Data']['Includes']
    objects={v:[] for v in ('baseline','protected','msvc')}; coverage=[]; inputs=[]
    surface = prepare_surface(c.get('agent_surface'), c.get('seed', 11))
    surface_args = []
    if surface:
        source = out / 'agent-surface.cpp'
        source.write_text(surface.cpp_source(), encoding='utf-8')
        obj = out / 'agent-surface.obj'
        run([tools['cl'], *common, source, '/Fo'+str(obj)], env, cwd=out,
            log=out/'agent-surface-compile.log')
        objects['protected'].append(obj)
        surface_args = ['--surface-symbol', surface.symbol, '--surface-offsets',
                        ','.join(str(e['offset']) for e in surface.entries)]
    for i,src in enumerate(c['module']['sources']):
        inputs.append({'path':src,'sha256':sha256(src)})
        bc=out/f'module{i}.bc'; pbc=out/f'module{i}.protected.bc'; rep=out/f'module{i}.coverage.json'
        dep=out/f'module{i}.d'
        run([tools['clang'],*common,src,'/clang:-emit-llvm','/clang:-o','/clang:'+str(bc),'/clang:-MD','/clang:-MF','/clang:'+str(dep)],env,cwd=out,log=out/f'clang{i}.log')
        dependencies+=make_dependencies(dep)
        args=[tools['transform'],bc,'-o',pbc,'--report',rep,'--seed',str(c.get('seed',11)),'--mode','balanced',*surface_args]
        if c['module'].get('functions'): args += ['--functions',','.join(c['module']['functions'])]
        run(args,env,log=out/f'transform{i}.log')
        report=json.loads(rep.read_text(encoding='utf-8')); coverage.append(report)
        for variant,ir in (('baseline',bc),('protected',pbc)):
            obj=out/f'module{i}.{variant}.obj'; run([tools['llc'],'-O2','--filetype=obj',ir,'-o',obj],env,log=out/f'{variant}{i}.log'); objects[variant].append(obj)
        obj=out/f'module{i}.msvc.obj'; dep=out/f'module{i}.msvc.deps.json'
        run([tools['cl'],*common,src,'/Fo'+str(obj),'/sourceDependencies',dep],env,cwd=out,log=out/f'msvc{i}.log'); objects['msvc'].append(obj)
        dependencies+=json.loads(dep.read_text(encoding='utf-8-sig'))['Data']['Includes']
        before=function_code(tools,objects['baseline'][-1],env); after=function_code(tools,objects['protected'][-1],env)
        for f in report['functions']:
            f['machine_code_changed']=f['name'] in before and f['name'] in after and before[f['name']]!=after[f['name']]
        write_json(rep,report)
    binaries={}
    for variant,objs in objects.items():
        exe=out/(variant+'.exe')
        surface_link = ['/INCLUDE:'+surface.symbol] if surface and variant=='protected' else []
        run([tools['cl'],'/nologo','/MD',*main,*objs,'/Fe'+str(exe),'/link','/INCREMENTAL:NO','/OPT:REF','/OPT:ICF',
             '/MAP:'+str(out/(variant+'.map')),*surface_link,*['/EXPORT:'+name for name in c.get('exports',[])]],env,cwd=out,log=out/f'link-{variant}.log')
        binaries[variant]={'path':str(exe),'sha256':sha256(exe),'module_code_size':sum(code_size(o) for o in objs),
                          'file_size':exe.stat().st_size}
    surface_evidence = inspect_surface(binaries['protected']['path'])
    surface_evidence['requested'] = surface is not None
    surface_evidence['function_references'] = sum(f['transformations'].get('surface_references',0) for r in coverage for f in r['functions'])
    if surface:
        if not surface_evidence['present'] or surface_evidence['payload_sha256'] != surface.sha256:
            raise RuntimeError('Requested agent surface did not survive final linking')
        expected = len(surface.entries)*sum(len(r['functions']) for r in coverage)
        if surface_evidence['function_references'] != expected:
            raise RuntimeError('Not every selected function references the agent surface')
        if any(inspect_surface(binaries[v]['path'])['present'] for v in ('baseline','msvc')):
            raise RuntimeError('Control binaries unexpectedly contain an agent surface')
    elif surface_evidence['present']:
        raise RuntimeError('Unrequested agent surface present in protected binary')
    for r in coverage:
        for f in r['functions']:
            f['object_machine_code_changed']=f['machine_code_changed']
            f['linked_symbol_present']={v:linked_symbol_present(Path(b['path']),out/(v+'.map'),f['name']) for v,b in binaries.items() if v!='msvc'}
            f['machine_code_changed']=f['object_machine_code_changed'] and all(f['linked_symbol_present'].values())
    if build_identity(c)!=initial_identity:raise ValueError('Source or build configuration changed during compilation; rebuild required')
    manifest={'schema_version':1,'seed':c.get('seed',11),'mode':'balanced','inputs':inputs,
              'compile_options':common,'tools':tools,'llvm_version':'20.1.8','binaries':binaries,'coverage':coverage,
              'agent_surface':surface_evidence,
              'ok':all(f.get('machine_code_changed') for r in coverage for f in r['functions']),
              'build_identity':build_identity(c,dependencies),'tool_hashes':{name:sha256(tools[name]) for name in ('cl','link','clang','llc','transform')},
              'behavior_verified':False,'anti_rea_effectiveness_verified':False}
    write_json(out/'build-manifest.json',manifest)
    if not manifest['ok']: raise RuntimeError('Selected function did not retain a machine-code change; see build-manifest.json')
    write_json(out/'build-status.json',{'schema_version':1,'ok':True,'status':'built'})
    return manifest

def evaluate_limits(baseline,protected,baseline_size,protected_size):
    for samples in (baseline,protected):
        if not samples or any(isinstance(x,bool) or not isinstance(x,(int,float)) or not math.isfinite(x) or x<=0 for x in samples):
            raise ValueError('Invalid timing measurement: samples must be finite and positive')
    if any(isinstance(x,bool) or not isinstance(x,int) or x<=0 for x in (baseline_size,protected_size)):
        raise ValueError('Invalid code size measurement: sizes must be positive integers')
    b=statistics.median(baseline); p=statistics.median(protected)
    ratio=p/b; size_ratio=protected_size/baseline_size
    return {'ok':ratio<=1.20 and size_ratio<=2.0,'baseline_median':b,'protected_median':p,
            'runtime_ratio':ratio,'code_size_ratio':size_ratio,'performance_pass':ratio<=1.20,'size_pass':size_ratio<=2.0,
            'limits':{'runtime_ratio':1.20,'code_size_ratio':2.0}}

def verify(config):
    c=load_config(config); out=Path(c['output_dir']); manifest=json.loads((out/'build-manifest.json').read_text(encoding='utf-8'))
    deps=[item['path'] for item in manifest.get('build_identity',{}).get('dependencies',[])]
    if manifest.get('build_identity')!=build_identity(c,deps):raise ValueError('Stale build: source, header, transform or config changed; run protect again')
    for name,digest in manifest.get('tool_hashes',{}).items():
        if sha256(manifest['tools'][name])!=digest:raise ValueError('Stale build: toolchain changed')
    if json.loads((out/'build-status.json').read_text())['status']!='built':raise ValueError('Build was not completed')
    for b in manifest['binaries'].values():
        if sha256(b['path'])!=b['sha256']: raise ValueError('Build artifact hash mismatch')
    surface_evidence = inspect_surface(manifest['binaries']['protected']['path'])
    surface = prepare_surface(c.get('agent_surface'),c.get('seed',11))
    surface_ok = surface_evidence['present'] == (surface is not None)
    if surface: surface_ok = surface_ok and surface_evidence.get('payload_sha256') == surface.sha256
    cfg=c.get('verification',{}); stdin=cfg.get('stdin','')
    outputs={v:run([b['path'],*cfg.get('args',[])],input=stdin,timeout=60).strip() for v,b in manifest['binaries'].items()}
    expected=cfg.get('expected_stdout')
    equivalent=len(set(outputs.values()))==1 and (expected is None or outputs['baseline']==expected.strip())
    selected={f['name'] for r in manifest['coverage'] for f in r['functions']}
    timings=cfg.get('timings')
    if timings is None:
        if len(selected)!=1:raise ValueError('Multiple selected functions require verification.timings for every exact symbol; aggregate timing is not accepted')
        timings=[{'function':next(iter(selected)),'args':['--timing']}]
    if {t.get('function') for t in timings}!=selected or len(timings)!=len(selected):raise ValueError('Timing coverage must match every selected function exactly once')
    function_limits={};all_samples={}
    for entry in timings:
        samples={'baseline':[],'protected':[]};args=entry.get('args',['--timing'])
        for v in samples:
            exe=manifest['binaries'][v]['path']
            for _ in range(3):run([exe,*args],timeout=60)
        for i in range(31):
            for v in (('baseline','protected') if i%2==0 else ('protected','baseline')):
                timing=json.loads(run([manifest['binaries'][v]['path'],*args],timeout=60))
                samples[v].append(float(timing.get('ns_per_call',timing.get('median_ns_per_call'))))
        limits=evaluate_limits(samples['baseline'],samples['protected'],manifest['binaries']['baseline']['module_code_size'],manifest['binaries']['protected']['module_code_size'])
        function_limits[entry['function']]=limits;all_samples[entry['function']]=samples
    limits=next(iter(function_limits.values())) if len(function_limits)==1 else {'ok':all(l['ok'] for l in function_limits.values()),'per_function':function_limits}
    report={'schema_version':1,'ok':equivalent and limits['ok'] and surface_ok,'behavior_equivalent':equivalent,'outputs':outputs,
            'samples':all_samples,'limits':limits,'function_limits':function_limits,'coverage':manifest['coverage'],'anti_rea_effectiveness_verified':False,
            'agent_surface':surface_evidence,'surface_verified':surface_ok,
            'binary_size_delta_bytes':manifest['binaries']['protected'].get('file_size',0)-manifest['binaries']['baseline'].get('file_size',0),
            'input_build_manifest_sha256':sha256(out/'build-manifest.json')}
    write_json(out/'verification.json',report)
    return report
