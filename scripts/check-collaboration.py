"""Fingerprint repository changes for the Codex review heartbeat; never runs code."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED = ('artifacts/', 'data/', 'deliverables/', 'node_modules/', '.venv/',
            'config/private/', 'secrets/', '.aws/', 'docs/reviews/')
OWN_LOGS = {'docs/test-log.md', 'docs/issues.md', 'docs/development-log.md', 'docs/progress/state.json'}


def collect(root):
    root = Path(root).resolve()
    paths = subprocess.check_output(['git', '-C', str(root), 'ls-files', '-z', '--cached', '--others', '--exclude-standard'])
    files = {}
    for name in sorted(set(paths.decode('utf-8').split('\0')) - {''}):
        if name.startswith(EXCLUDED) or name in OWN_LOGS:
            continue
        path = root / name
        if not path.resolve().is_relative_to(root):
            raise ValueError(f'File escapes project root: {name}')
        if not path.exists():
            continue
        if not path.is_file():
            raise ValueError(f'Unsupported file type: {name}')
        before = path.stat()
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        after = path.stat()
        if (before.st_mtime_ns, before.st_size) != (after.st_mtime_ns, after.st_size):
            raise ValueError(f'File changed while reading: {name}')
        files[name] = digest
    return files


def fingerprint(files):
    return hashlib.sha256(json.dumps(files, sort_keys=True).encode('utf-8')).hexdigest()


def changes(previous, current):
    return [{'path': p, 'change': 'added' if p not in previous else 'deleted' if p not in current else 'modified'}
            for p in sorted(previous.keys() | current.keys()) if previous.get(p) != current.get(p)]


def observe(state, files, now):
    changed = changes(state['reviewed_files'], files)
    token = fingerprint(files)
    if not changed:
        state.pop('pending', None)
        return {'status': 'unchanged', 'fingerprint': token, 'changes': []}
    if state.get('pending', {}).get('fingerprint') != token:
        state['pending'] = {'fingerprint': token, 'first_seen_at': now}
    elapsed = now - state['pending']['first_seen_at']
    return {'status': 'ready' if elapsed >= 60 else 'settling', 'fingerprint': token,
            'stable_for_s': max(0, elapsed), 'changes': changed}


def acknowledge(state, files, expected):
    if fingerprint(files) != expected or state.get('pending', {}).get('fingerprint') != expected:
        raise ValueError('Review input changed or was not scanned; keep pending and review the new version')
    state['reviewed_files'] = files
    state['last_reviewed_at'] = time.time()
    state.pop('pending', None)


def save(path, state):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding='utf-8')
    os.replace(temporary, path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['init', 'scan', 'ack'])
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--state', type=Path, default=ROOT / 'artifacts/collaboration/review-state.json')
    parser.add_argument('--fingerprint')
    args = parser.parse_args()
    try:
        files = collect(args.root)
        if args.action == 'init':
            if args.state.exists():
                raise ValueError('Review baseline already exists; initialization must not discard pending changes')
            state = {'schema_version': '1.0', 'root': str(args.root.resolve()), 'reviewed_files': files, 'initialized_at': time.time()}
            result = {'status': 'initialized', 'files': len(files), 'fingerprint': fingerprint(files)}
        else:
            state = json.loads(args.state.read_text(encoding='utf-8'))
            if Path(state['root']).resolve() != args.root.resolve():
                raise ValueError('State belongs to a different project')
            if args.action == 'scan':
                result = observe(state, files, time.time())
            else:
                acknowledge(state, files, args.fingerprint)
                result = {'status': 'acknowledged', 'fingerprint': fingerprint(files)}
        save(args.state, state)
        print(json.dumps(result, ensure_ascii=False))
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        parser.exit(2, f'Change monitor error: {error}\n')


if __name__ == '__main__':
    main()
