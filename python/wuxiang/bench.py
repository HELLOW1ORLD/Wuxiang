"""Offline benchmark packs and executable candidate scoring (Python 3.10 stdlib).

Candidates are native programs: the local runner is NOT a security sandbox. Use
an isolated scoring VM for adversarial submissions. Never pass the private pack
to an attack agent. Transcripts are imported evidence, not independent proof.
"""
from __future__ import annotations

import hashlib
import json
import os
import random
import shutil
import statistics
import subprocess
import tempfile
import uuid
from pathlib import Path

CATEGORIES = ('branch', 'state', 'parser', 'table', 'buffer', 'callgraph')
MASK = (1 << 64) - 1
ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / '.state' / 'benchmark_trust.json'
TABLE = (31, 7, 101, 53, 19, 233, 11, 89, 41, 157, 3, 67, 211, 29, 131, 17)


def _json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding='utf-8-sig'))
    except (OSError, ValueError) as exc:
        raise ValueError(f'Cannot read JSON {path}: {exc}') from exc
    if not isinstance(value, dict) or value.get('schema_version') != 1:
        raise ValueError(f'Unsupported JSON schema_version: {path}')
    return value


def _write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def _hash(path: Path) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except OSError as exc:
        raise ValueError(f'Cannot hash {path}: {exc}') from exc


def _path(value: str, base: Path) -> Path:
    if not isinstance(value, str) or not value:
        raise ValueError('Missing path')
    p = Path(value)
    return (p if p.is_absolute() else base / p).resolve()


def reference(category: str, x: int, data: bytes, capacity: int) -> tuple[int, bytes]:
    """Independent unsigned integer reference; output bytes are observable state."""
    x &= MASK
    if category == 'branch':
        if x < 17:
            return ((x * 3) ^ 0x19) & MASK, b''
        if x & 1:
            return ((x ^ 0xA53) + (x >> 3)) & MASK, b''
        return ((x << 2) - 7) & MASK, b''
    if category == 'state':
        state, total = x & 3, x
        for b in data:
            if b == 0:
                state = 0
            elif b & 1:
                state = (state + 1) & 3
            else:
                state ^= 2
            total = (total * 33 + state * 7 + b) & MASK
        return total ^ state, b''
    if category == 'parser':
        if not data:
            return MASK, b''
        value = 0
        for b in data:
            if not 48 <= b <= 57 or value > (MASK - (b - 48)) // 10:
                return MASK, b''
            value = value * 10 + b - 48
        return value, b''
    if category == 'table':
        value = TABLE[x & 15]
        for b in data:
            value = (value * 17 + TABLE[(b ^ x) & 15]) & MASK
        return value, b''
    if category == 'buffer':
        output = bytes((b ^ ((x + i * 17) & 255)) for i, b in enumerate(data[:capacity]))
        value = x
        for b in output:
            value = ((value << 5) ^ (value >> 2) ^ b) & MASK
        return value, output
    if category == 'callgraph':
        def rotate(v: int) -> int:
            return ((v << 7) | (v >> 57)) & MASK
        def mix(v: int, b: int) -> int:
            return rotate((v ^ b) * 0x9E3779B185EBCA87 & MASK) ^ (v >> 11)
        value = x ^ 0xC0FFEE
        for b in data:
            value = mix(value, b)
        return mix(value, len(data)), b''
    raise ValueError(f'Unknown category: {category}')


def cases(category: str, seed: int) -> list[dict]:
    if category not in CATEGORIES:
        raise ValueError('Unknown category')
    rng = random.Random(seed)
    inputs = [(x, d, c) for x in (0, 1, 16, 17, 18, 255, MASK)
              for d, c in ((b'', 0), (b'\x00\x01\xff', 0), (b'\x00\x01\xff', 1), (b'\x00\x01\xff', 3))]
    if category == 'parser':
        inputs.extend((0, d, 0) for d in (b'0', b'123', b'000042', b'18446744073709551615',
                      b'18446744073709551616', b'12x', b'-1', b' 1', b'999999999999999999999999'))
    for _ in range(96):
        d = bytes(rng.randrange(256) for _ in range(rng.randrange(65)))
        if category == 'parser' and rng.randrange(2):
            d = str(rng.getrandbits(rng.randrange(80))).encode('ascii')
        inputs.append((rng.getrandbits(64), d, rng.randrange(80)))
    result = []
    for x, data, capacity in inputs:
        value, output = reference(category, x, data, capacity)
        full_output = output + bytes([0xCD]) * (capacity - len(output))
        result.append(dict(x=x, input_hex=data.hex(), capacity=capacity,
                           expected_value=value, expected_output_hex=full_output.hex()))
    return result


def prepare(config: dict, config_path: Path) -> dict:
    options = config.get('benchmark')
    if not isinstance(options, dict):
        raise ValueError('Config requires benchmark object')
    base = Path(config_path).resolve().parent
    manifest_path = _path(options.get('build_manifest_path'), base)
    manifest = _json(manifest_path)
    caps = manifest.get('balanced_caps_all_pass')
    if type(caps) is not bool:
        raise ValueError('Missing or invalid balanced caps evidence')
    if caps is False and options.get('allow_failed_caps_for_research') is not True:
        raise ValueError('Balanced caps failed; only explicit allow_failed_caps_for_research permits an unaccepted research pack')
    entries = manifest.get('tasks')
    if not isinstance(entries, list) or not entries:
        raise ValueError('Build manifest requires tasks')
    validated = []
    seen = set()
    for task in entries:
        category = task.get('category')
        variant = task.get('variant')
        seed = task.get('seed')
        if category not in CATEGORIES or variant not in ('baseline', 'protected', 'msvc') or type(seed) is not int:
            raise ValueError('Invalid benchmark task category/variant/seed')
        key = category, variant, seed
        if key in seen:
            raise ValueError('Duplicate benchmark task')
        seen.add(key)
        if task.get('verified') is not True:
            raise ValueError('Every benchmark binary must be verified before export')
        artifact = _path(task.get('artifact_path'), manifest_path.parent)
        if artifact.suffix.lower() != '.exe' or artifact.read_bytes()[:2] != b'MZ':
            raise ValueError('Benchmark artifact must be a Windows EXE')
        if _hash(artifact) != task.get('sha256'):
            raise ValueError('Benchmark artifact hash mismatch')
        validated.append((task, artifact))
    required_seeds = options.get('seeds', [11, 23, 47])
    required = {(c, v, s) for c in CATEGORIES for v in ('baseline', 'protected', 'msvc') for s in required_seeds}
    if seen != required:
        raise ValueError('Require six categories, all requested seeds and three build variants')
    output = _path(options.get('output_dir'), base)
    if not output.is_relative_to(ROOT.resolve()) or output == ROOT.resolve():
        raise ValueError('Benchmark output must remain within the Wuxiang project')
    if output.exists() and any(output.iterdir()):
        raise ValueError('Benchmark output directory must be empty (prevents stale source leaks)')
    attacker = output / 'attacker'
    adaptive = output / 'adaptive'
    private = output / 'scorer'
    attacker.mkdir(parents=True, exist_ok=True)
    adaptive.mkdir(parents=True, exist_ok=True)
    private.mkdir(parents=True, exist_ok=True)
    records = []
    rng = random.SystemRandom()
    rng.shuffle(validated)
    for task, artifact in validated:
        pack_id = uuid.uuid4().hex
        pack = attacker / pack_id
        pack.mkdir()
        target = pack / 'target.exe'
        shutil.copyfile(artifact, target)
        shutil.copyfile(ROOT / 'bench' / 'task.h', pack / 'task.h')
        _write(pack / 'task.json', dict(schema_version=1, pack_id=pack_id,
               sha256=task['sha256'], task_api='wuxiang_task',
               budget={'seconds': 1800, 'tool_calls': 100},
               protocol='stdin decimal_x hex_input_or_dash decimal_capacity; stdout decimal_result hex_output_or_dash'))
        (pack / 'README.md').write_text(
            'Recover a behavior-equivalent implementation of the API in task.h.\n'
            'target.exe accepts one or more input lines; use - for empty byte strings.\n'
            'Treat x as unsigned 64-bit, capacity as output buffer length.\n'
            'Output is prefilled with 0xCD; bytes beyond input length remain unwritten.\n'
            'Each output line contains the return value and entire output buffer.\n'
            'Public research and custom analysis\n'
            'scripts are allowed. Record every tool call and capability limitation.\n'
            'This is a blind session: no transform design or variant assignment is supplied.\n'
            'Run independently from other packs; do not reuse another session transcript.\n'
            'Example input lines: `0 - 0` (empty input/output), `17 303132 4`\n'
            '(three input bytes and four-byte output capacity). Return values must be\n'
            'determined from analysis, not assumed from these examples.\n'
            'Budget: 30 minutes / 100 tool calls. Do not supply self-reported scores.\n', encoding='utf-8')
        adaptive_pack = adaptive / pack_id
        shutil.copytree(pack, adaptive_pack)
        instructions = (adaptive_pack / 'README.md').read_text(encoding='utf-8')
        instructions = instructions.replace('This is a blind session: no transform design or variant assignment is supplied.',
            'This is an adaptive session. Read protection-design.md before analysis. Variant assignment remains withheld.')
        (adaptive_pack / 'README.md').write_text(instructions, encoding='utf-8')
        (adaptive_pack / 'protection-design.md').write_text(
            '# Public Wuxiang v1 transform design\n\n'
            'The test set mixes control builds with protected builds; pack labels are withheld.\n'
            'Protection runs after ordinary LLVM optimization and before native code generation.\n'
            'The balanced budget rewrites at most one eligible integer site and introduces\n'
            'at most one split/control region per selected function. No full dispatcher\n'
            'virtual machine or cryptographic secrecy is assumed.\n\n'
            'Integer substitutions use unsigned modular identities: add may become\n'
            '`(a xor b) + 2*(a and b)` or `2*(a or b) - (a xor b)`; subtract\n'
            'uses complement-plus-one; xor may become `(a or b) and ~(a and b)`.\n'
            'Operands can be frozen in IR to avoid introducing undefined choices.\n\n'
            'Control regions use a local 32-bit stack cell, a volatile store of a\n'
            'seed-derived constant, a volatile load and equality test, and two routes\n'
            'that store different derived constants before joining the original flow.\n'
            'Both routes preserve the algorithm output. Loop regions and exception\n'
            'control structure are skipped conservatively. Exception-handling arithmetic\n'
            'may add and subtract two volatile loads from the same local mask cell.\n\n'
            'You may simplify these constructs, trace runtime values, build signatures,\n'
            'or write scripts. This document supplies no original algorithm, seed,\n'
            'symbol mapping, hidden tests or per-target coverage. Record bypass methods\n'
            'and tool availability in the transcript. Use fresh independent sessions.\n', encoding='utf-8')
        records.append(dict(pack_id=pack_id, category=task['category'], variant=task['variant'],
                            seed=task['seed'], sha256=task['sha256'], artifact_path=str(target),
                            hidden_cases=cases(task['category'], task['seed'])))
    shutil.copyfile(ROOT / 'bench' / 'harness.cpp', private / 'harness.cpp')
    shutil.copyfile(ROOT / 'bench' / 'task.h', private / 'task.h')
    scoring_path = private / 'manifest.json'
    toolchain = dict(manifest.get('toolchain', {}))
    if isinstance(toolchain.get('compiler_environment'), dict):
        allowed = {'PATH','INCLUDE','LIB','LIBPATH','SYSTEMROOT','WINDIR','TEMP','TMP','COMSPEC','PATHEXT','SYSTEMDRIVE'}
        incoming = toolchain['compiler_environment']
        filtered = {k.upper(): v for k, v in incoming.items() if k.upper() in allowed}
        # cmd.exe can expose both inherited Path and VS-modified PATH.
        if 'PATH' in incoming:
            filtered['PATH'] = incoming['PATH']
        toolchain['compiler_environment'] = filtered
    _write(scoring_path, dict(schema_version=1, tasks=records,
               harness_sha256=_hash(private / 'harness.cpp'), header_sha256=_hash(private / 'task.h'),
               toolchain=toolchain, budget={'seconds':1800, 'tool_calls':100},
               build_manifest_sha256=_hash(manifest_path)))
    registry = _json(REGISTRY) if REGISTRY.exists() else {'schema_version':1, 'manifests':{}}
    registry['manifests'][str(scoring_path.resolve())] = _hash(scoring_path)
    _write(REGISTRY, registry)
    return dict(schema_version=1, pack_count=len(records), attacker_dir=str(attacker),
                adaptive_dir=str(adaptive), session_pack_count=len(records) * 2,
                scoring_manifest=str(scoring_path), private_mapping=str(scoring_path),
                effectiveness_claim=False, balanced_caps_all_pass=manifest.get('balanced_caps_all_pass'),
                research_only=manifest.get('balanced_caps_all_pass') is False, status='prepared_no_attack_sessions')


def _submission_file(value: str, parent: Path) -> Path:
    path = _path(value, parent)
    if not path.is_relative_to(parent):
        raise ValueError('Submission source/transcript must remain inside submission directory')
    if not path.is_file():
        raise ValueError(f'Missing submission file: {path}')
    return path


def summarize_records(records: list[dict]) -> dict:
    """Report imported paired observations, never establish efficacy by fiat.

    A pair matches category, seed, attack mode and environment. Duplicate session
    IDs are excluded rather than counted as independent replicates. Only successful
    reconstructions yield a recovery-time ratio; failures remain censored outcomes.
    """
    session_counts = {}
    for row in records:
        session = row.get('session_id')
        session_counts[session] = session_counts.get(session, 0) + 1
    grouped = {}
    for row in records:
        if not row.get('pair_id') or session_counts.get(row.get('session_id')) != 1:
            continue
        if row.get('variant') not in ('baseline', 'protected'):
            continue
        environment = json.dumps(row.get('environment', {}), sort_keys=True)
        key = (row.get('category'), row.get('seed'), row.get('mode'), environment)
        pair = grouped.setdefault(key, {}).setdefault(row['pair_id'], {})
        if row['variant'] in pair:
            pair[row['variant']] = None  # duplicate pair leg is ineligible
        else:
            pair[row['variant']] = row
    groups = []
    for key, pairs in sorted(grouped.items(), key=lambda item: str(item[0])):
        complete = [p for p in pairs.values() if p.get('baseline') and p.get('protected')]
        ratios = []
        for pair in complete:
            baseline, protected = pair['baseline'], pair['protected']
            if baseline.get('status') == protected.get('status') == 'semantic_success' and baseline.get('elapsed_seconds', 0) > 0:
                ratios.append(protected['elapsed_seconds'] / baseline['elapsed_seconds'])
        groups.append(dict(category=key[0], seed=key[1], mode=key[2],
                           environment=json.loads(key[3]), complete_pair_count=len(complete),
                           successful_pair_count=len(ratios), repeat_requirement_met=len(complete) >= 3,
                           median_time_ratio=statistics.median(ratios) if len(ratios) >= 3 else None,
                           outcomes=[{'baseline':p['baseline']['status'], 'protected':p['protected']['status']} for p in complete]))
    eligible = [g for g in groups if g['repeat_requirement_met']]
    required = {(c,s,m) for c in CATEGORIES for s in (11,23,47) for m in ('blind','adaptive')}
    observed = {(g['category'],g['seed'],g['mode']) for g in eligible}
    return dict(schema_version=1, groups=groups, eligible_group_count=len(eligible),
                required_group_count=len(required), complete_matrix=required.issubset(observed),
                formal_evidence='paired_observations_available' if required.issubset(observed) else 'insufficient_evidence',
                effectiveness_claim=False,
                limitation='Imported transcripts/times and native local execution are not independently attested; confirm isolated blind sessions before interpreting efficacy.')


def _persist_score(result: dict, manifest_path: Path) -> dict:
    result['ok']=result.get('status')=='semantic_success'
    scores = manifest_path.parent / 'scores'
    _write(scores / (uuid.uuid4().hex + '.json'), result)
    result['paired_summary'] = summarize_records([_json(path) for path in scores.glob('*.json')])
    _write(manifest_path.parent / 'paired_summary.json', result['paired_summary'])
    return result


def score(submission_path: Path) -> dict:
    submission_path = Path(submission_path).resolve()
    submission = _json(submission_path)
    manifest_path = _path(submission.get('scoring_manifest'), submission_path.parent)
    if not REGISTRY.exists():
        raise ValueError('Scoring requires a previously prepared trusted manifest')
    registry = _json(REGISTRY)
    if registry.get('manifests', {}).get(str(manifest_path)) != _hash(manifest_path):
        raise ValueError('Scoring manifest is not trusted or its hash changed')
    manifest = _json(manifest_path)
    if _hash(manifest_path.parent / 'harness.cpp') != manifest.get('harness_sha256') or _hash(manifest_path.parent / 'task.h') != manifest.get('header_sha256'):
        raise ValueError('Trusted scoring harness/header hash changed')
    matches = [t for t in manifest['tasks'] if t['pack_id'] == submission.get('pack_id')]
    if len(matches) != 1:
        raise ValueError('Unknown pack_id')
    task = matches[0]
    if submission.get('artifact_sha256') != task['sha256'] or _hash(Path(task['artifact_path'])) != task['sha256']:
        raise ValueError('Submission artifact hash mismatch')
    if submission.get('mode') not in ('blind', 'adaptive'):
        raise ValueError('mode must be blind or adaptive')
    environment = submission.get('environment')
    if not isinstance(environment, dict) or not all(k in environment for k in ('model', 'rea_version', 'tools', 'dynamic_available')):
        raise ValueError('Missing attack environment/capability record')
    if not isinstance(environment['tools'], list) or type(environment['dynamic_available']) is not bool:
        raise ValueError('Invalid environment capability record')
    transcript_path = _submission_file(submission.get('transcript_path'), submission_path.parent)
    transcript = _json(transcript_path)
    events = transcript.get('events')
    if not isinstance(events, list) or not all(isinstance(e, dict) and isinstance(e.get('kind'), str) for e in events):
        raise ValueError('Transcript requires events with kinds')
    tool_calls = sum(e['kind'] == 'tool_call' for e in events)
    elapsed = submission.get('elapsed_seconds')
    if type(elapsed) not in (int, float) or not 0 <= elapsed < float('inf'):
        raise ValueError('elapsed_seconds must be finite and nonnegative')
    if not isinstance(submission.get('session_id'), str) or not submission['session_id']:
        raise ValueError('Missing session_id')
    result = dict(schema_version=1, session_id=submission['session_id'], pair_id=submission.get('pair_id'), pack_id=task['pack_id'],
                  category=task['category'], variant=task['variant'], seed=task['seed'],
                  artifact_sha256=task['sha256'], scoring_manifest_sha256=_hash(manifest_path),
                  mode=submission['mode'], environment=environment, elapsed_seconds=elapsed,
                  tool_calls=tool_calls, transcript_sha256=_hash(transcript_path),
                  dynamic_analysis='available' if environment['dynamic_available'] else 'unevaluated',
                  execution_isolation='working_directory_only',
                  score_integrity='not_attested', hidden_tests_access_protected=False,
                  effectiveness_claim=False, formal_evidence='insufficient_evidence',
                  passed_cases=0, total_cases=len(task['hidden_cases']))
    if elapsed > manifest['budget']['seconds'] or tool_calls > manifest['budget']['tool_calls']:
        result['status'] = 'budget_exceeded'
        return _persist_score(result, manifest_path)
    if submission.get('outcome') in ('timeout', 'tool_error'):
        result['status'] = submission['outcome']
        return _persist_score(result, manifest_path)
    candidate = _submission_file(submission.get('candidate_source'), submission_path.parent)
    if candidate.suffix.lower() != '.cpp' or candidate.stat().st_size > 1024 * 1024:
        raise ValueError('Candidate must be a C++ source file at most 1 MiB')
    result['candidate_sha256'] = _hash(candidate)
    toolchain = manifest.get('toolchain', {})
    compiler = toolchain.get('compiler')
    if not compiler or not Path(compiler).is_file():
        result.update(status='tool_error', error='Trusted MSVC compiler unavailable')
        return _persist_score(result, manifest_path)
    compiler_env=toolchain.get('compiler_environment')
    if not isinstance(compiler_env,dict) or not all(k in compiler_env for k in ('INCLUDE','LIB','PATH')):
        result.update(status='tool_error',error='Trusted compiler environment missing; ambient environment fallback is forbidden')
        return _persist_score(result,manifest_path)
    work_root = manifest_path.parent / 'work'
    work_root.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=work_root) as directory:
        work = Path(directory)
        shutil.copyfile(candidate, work / 'candidate.cpp')
        shutil.copyfile(manifest_path.parent / 'harness.cpp', work / 'harness.cpp')
        shutil.copyfile(manifest_path.parent / 'task.h', work / 'task.h')
        command = [str(compiler), '/nologo', '/std:c++17', '/O2', '/EHsc', '/MD',
                   'candidate.cpp', 'harness.cpp', '/Fe:candidate.exe', '/link', '/INCREMENTAL:NO']
        try:
            built = subprocess.run(command, cwd=work, env=compiler_env,
                                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors='replace', timeout=60)
        except subprocess.TimeoutExpired:
            result.update(status='compilation_timeout')
            return _persist_score(result, manifest_path)
        except OSError as exc:
            result.update(status='tool_error', error=str(exc))
            return _persist_score(result, manifest_path)
        result['compiler_output'] = built.stdout[-12000:]
        if built.returncode != 0:
            result['status'] = 'compilation_error'
            return _persist_score(result, manifest_path)
        input_text = ''.join(f"{c['x']} {c['input_hex'] or '-'} {c['capacity']}\n" for c in task['hidden_cases'])
        try:
            runtime_env={k:v for k,v in (toolchain.get('compiler_environment') or {}).items()
                         if k.upper() in {'PATH','SYSTEMROOT','WINDIR','SYSTEMDRIVE','PATHEXT'}}
            for k in ('SystemRoot','WINDIR'):
                if not any(n.upper()==k.upper() for n in runtime_env):runtime_env[k]=os.environ.get(k,'C:\\Windows')
            runtime_env.update(TEMP=str(work),TMP=str(work))
            ran = subprocess.run([str(work / 'candidate.exe')], input=input_text, cwd=work, env=runtime_env,
                                 stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                 errors='replace', timeout=10)
        except subprocess.TimeoutExpired:
            result['status'] = 'execution_timeout'
            return _persist_score(result, manifest_path)
        except OSError as exc:
            result.update(status='tool_error', error=str(exc))
            return _persist_score(result, manifest_path)
        result['candidate_exit_code'] = ran.returncode
        if ran.returncode != 0:
            result['status'] = 'execution_error'
            return _persist_score(result, manifest_path)
        lines = ran.stdout.splitlines()
        for i, case in enumerate(task['hidden_cases']):
            if i >= len(lines):
                continue
            try:
                value, output = lines[i].split()
                if int(value) == case['expected_value'] and ('' if output == '-' else output.lower()) == case['expected_output_hex']:
                    result['passed_cases'] += 1
            except ValueError:
                pass
        result['extra_output_lines'] = max(0, len(lines) - len(task['hidden_cases']))
        result['test_pass_rate'] = result['passed_cases'] / result['total_cases']
        result['status'] = 'semantic_success' if result['passed_cases'] == result['total_cases'] and not result['extra_output_lines'] else 'semantic_failure'
    return _persist_score(result, manifest_path)
