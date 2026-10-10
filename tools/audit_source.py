"""Audit publishable files without claiming a complete secret/security proof."""
from pathlib import Path
import hashlib
import json
import os
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]
GENERATED = {'toolchain', 'build', 'build-transform', 'reports', 'pilot', 'submissions',
             '.state', 'dist', '.git', '.vs', '__pycache__'}
BAD_SUFFIXES = {'.exe', '.dll', '.pdb', '.obj', '.lib', '.bc', '.pyc', '.zip', '.tar', '.xz'}
TOKEN = re.compile(r'(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{40,}|sk-proj-[A-Za-z0-9_-]{24,})')


def source_files(root=ROOT):
    if (root / '.git').exists():
        result = subprocess.run(['git', '-C', str(root), 'ls-files', '-z', '--cached',
                                 '--others', '--exclude-standard'], capture_output=True)
        if result.returncode:
            raise RuntimeError('Could not read Git source inventory')
        return sorted({root / p.decode('utf-8') for p in result.stdout.split(b'\0') if p})
    files = []
    for directory, dirs, names in os.walk(root):
        dirs[:] = [d for d in dirs if d not in GENERATED and not d.startswith(('research-packs', 'benchmark-packs'))]
        files.extend(Path(directory) / name for name in names if not name.endswith('.pyc'))
    return sorted(files)


def audit(root=ROOT):
    errors = []; inventory = []
    for path in source_files(root):
        relative = path.relative_to(root).as_posix()
        parts = Path(relative).parts
        if any(p in GENERATED or p.startswith(('research-packs', 'benchmark-packs')) for p in parts):
            errors.append(relative + ': generated/private directory tracked')
        if path.is_symlink():
            errors.append(relative + ': symlink is not source-release input'); continue
        if not path.is_file():
            errors.append(relative + ': missing file'); continue
        if path.suffix.lower() in BAD_SUFFIXES or path.name.lower() in ('crypto.local.json', '.env') or path.name.startswith('.env.'):
            errors.append(relative + ': binary/credential file forbidden')
        data = path.read_bytes()
        if len(data) > 2 * 1024 * 1024:
            errors.append(relative + ': source file exceeds 2 MiB')
        try:
            text = data.decode('utf-8-sig')
        except UnicodeDecodeError:
            errors.append(relative + ': not UTF-8 source'); continue
        # Check concrete local provenance, not mock drive paths in parser tests.
        if re.search(r'(?:[A-Za-z]:[/\\]01Project[/\\]|[A-Za-z]:[/\\]Users[/\\][^/\\\s]+[/\\])', text, re.I):
            errors.append(relative + ': private local provenance found')
        if TOKEN.search(text):
            errors.append(relative + ': possible credential; inspect without printing it')
        if path.suffix.lower() == '.md':
            for target in re.findall(r'\[[^\]]*\]\(([^)]+)\)', text):
                if target.startswith(('https://', 'http://', '#', 'mailto:')): continue
                local = target.split('#', 1)[0]
                if local and not (path.parent / local).exists():
                    errors.append(relative + ': broken relative link: ' + local)
        inventory.append({'path': relative, 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()})
    return {'schema_version': 1, 'ok': not errors, 'file_count': len(inventory),
            'total_bytes': sum(r['bytes'] for r in inventory), 'errors': errors,
            'scope': 'tracked and nonignored files, or nongenerated files without Git',
            'complete_secret_audit': False}


if __name__ == '__main__':
    result = audit()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result['ok'] else 1)
