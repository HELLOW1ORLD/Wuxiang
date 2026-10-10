"""Read-only tool diagnostics; configuration does not imply attack readiness."""
from pathlib import Path
import json
import os
import shutil
import subprocess
from .build import ROOT, doctor as build_doctor, tool_paths, write_json


def _version(command, env=None):
    try:
        result = subprocess.run(list(map(str, command)), env=env, capture_output=True,
            text=True, encoding='utf-8', errors='replace', timeout=15)
        lines = (result.stdout + result.stderr).strip().splitlines()
        return {'exit_code': result.returncode, 'output': '\n'.join(lines[:6])}
    except (OSError, subprocess.TimeoutExpired) as error:
        return {'error': str(error)}


def doctor():
    report = build_doctor()
    if report['ok']:
        tools, env = tool_paths()
        report['tool_versions'] = {
            'msvc': _version([tools['cl'], '/Bv'], env),
            'linker': _version([tools['link'], '/?'], env),
            'cmake': _version([tools['cmake'], '--version'], env),
            'llc': _version([tools['llc'], '--version'], env),
            'objdump': _version([tools['objdump'], '--version'], env)}
        include_dirs = [Path(p) for p in env['INCLUDE'].split(';') if p]
        lib_dirs = [Path(p) for p in env['LIB'].split(';') if p]
        sdk_checks = {name: any((directory / name).is_file() for directory in directories)
                      for directories, names in ((include_dirs, ('windows.h', 'stdlib.h')),
                          (lib_dirs, ('kernel32.lib', 'ucrt.lib', 'vcruntime.lib')))
                      for name in names}
        report['sdk_files'] = sdk_checks
        if not all(sdk_checks.values()):
            report['ok'] = False
            report['capabilities']['native_build'] = False
            report['errors'].append('Required SDK/CRT headers or libraries missing')
    packages = Path(os.environ.get('LOCALAPPDATA', '')) / 'npm-cache/_npx'
    rea = []
    for path in packages.glob('*/node_modules/rea-agents/package.json'):
        try:
            metadata = json.loads(path.read_text(encoding='utf-8'))
            rea.append({'version': metadata.get('version'),
                        'cli': str(path.parent / 'scripts/rea.mjs')})
        except (OSError, ValueError):
            continue
    ghidra = ROOT.parent / 'Tools/Native/ghidra_12.1.4_PUBLIC'
    java = ROOT.parent / 'Tools/Native/jdk-21.0.12.1+1/bin/java.exe'
    node = shutil.which('node.exe')
    ghidra_properties = ghidra / 'Ghidra/application.properties'
    ghidra_version = None
    if ghidra_properties.is_file():
        for line in ghidra_properties.read_text(encoding='utf-8').splitlines():
            if line.startswith('application.version='):
                ghidra_version = line.split('=', 1)[1]
    report['evaluation_tools'] = {
        'rea': rea, 'node': {'path': node, 'version': _version([node, '--version']) if node else None},
        'ghidra': {'path': str(ghidra), 'version': ghidra_version},
        'java': {'path': str(java), 'version': _version([java, '-version']) if java.is_file() else None},
        'backend_readiness': 'not_probed_use_tools/rea_probe.py',
        'dynamic_debugging': 'unevaluated', 'os_attack_isolation': 'unavailable_in_current_runner'}
    report['capabilities']['rea_static_configured'] = bool(
        any(p['version'] == '6.2.0' and Path(p['cli']).is_file() for p in rea)
        and ghidra_properties.is_file() and java.is_file() and node)
    report['capabilities']['formal_rea_evaluation_complete'] = False
    write_json(ROOT / 'reports/doctor.json', report)
    return report
