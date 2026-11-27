"""Dispatch explicit tasks through official agy; import local Git deliveries for Codex."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / 'config/private/antigravity-bridge.local.json'
RUNTIME = ROOT / 'artifacts/collaboration/bridge'
STATE = RUNTIME / 'state.json'


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    os.replace(temp, path)


def git(repo, *args):
    return subprocess.check_output(['git', '-C', str(repo), *args], stderr=subprocess.PIPE).decode('utf-8').strip()


def check_repo(repo):
    url = git(repo, 'remote', 'get-url', 'origin').rstrip('/').removesuffix('.git')
    if url != 'https://github.com/kaiy860123/ble-mobile-inventory':
        raise ValueError('Configured checkout is not the authorized project')


def allowed(path, task):
    p = Path(path)
    return not p.is_absolute() and '..' not in p.parts and (
        path in task['allowed_paths'] or any(path.startswith(prefix) for prefix in task['allowed_prefixes']))


def changed_paths(repo):
    tracked = git(repo, 'diff', '--name-only', '-z', 'HEAD')
    new = git(repo, 'ls-files', '--others', '--exclude-standard', '-z')
    return sorted(set(filter(None, (tracked + '\0' + new).split('\0'))))


def ready_handoff(text):
    import re
    return bool(re.search(r'^\s*(?:[-*]\s*)?(?:狀態|Status)\s*[:：]\s*`?ready_for_review`?\s*$', text, re.M | re.I))


def session_settings(task, python, existing=None, workspace=None):
    # Editing phase only. Codex owns command execution and independent verification.
    workspace = Path(workspace or ROOT).resolve()
    def workspace_target(path):
        if not allowed(path, task):
            raise ValueError('Permission target is outside the task scope')
        target = (workspace / path).resolve()
        if not target.is_relative_to(workspace):
            raise ValueError('Permission target escapes workspace')
        return str(target)
    rules = {
        'allow': [f'write_file({workspace_target(p)})' for p in task['allowed_paths'] + task['allowed_prefixes']],
        'deny': ['command(*)'] + [f'write_file({workspace / p})' for p in ('src', 'config', 'infra', '.git')]
    }
    for key, values in (existing or {}).items():
        if key in ('allow', 'deny', 'ask'):
            rules[key] = list(dict.fromkeys(values + rules.get(key, [])))
    return {'permissions': rules}


def state():
    saved = read_json(STATE) if STATE.exists() else {'jobs': {}, 'accepted': {}}
    for path in (RUNTIME / 'accepted').glob('AG-*.json'):
        receipt = read_json(path)
        saved['accepted'][receipt['task_id']] = receipt['sha']
        job = saved['jobs'].get(receipt['task_id'])
        if job and job['status'] != 'running' and receipt.get('accepted_at', 0) >= job.get('started_at', 0):
            job['status'] = 'accepted'
    return saved


def deliveries(repo):
    output = git(repo, 'for-each-ref', '--format=%(refname:short)\t%(objectname)', 'refs/heads/antigravity/')
    result = []
    for line in output.splitlines():
        branch, sha = line.split('\t')
        for task_id in ('AG-001', 'AG-002', 'AG-003', 'AG-004', 'AG-005'):
            if f'/{task_id}-' not in branch:
                continue
            try:
                handoff = git(repo, 'show', f'{sha}:docs/handoffs/{task_id}-result.md')
            except subprocess.CalledProcessError:
                continue
            if ready_handoff(handoff):
                result.append({'task_id': task_id, 'branch': branch, 'sha': sha})
    return result


def status(config):
    repo = Path(config['checkout'])
    check_repo(repo)
    saved = state()
    pending = [d for d in deliveries(repo) if saved['accepted'].get(d['task_id']) != d['sha']]
    return {'checkout': str(repo), 'branch': git(repo, 'branch', '--show-current'),
            'dirty': changed_paths(repo), 'jobs': saved['jobs'], 'pending_deliveries': pending}


def dispatch(config, task_id, resume=False):
    if task_id not in ('AG-001', 'AG-003', 'AG-004', 'AG-005'):
        raise ValueError('Task is not in the explicit dispatch queue')
    repo = Path(config['checkout'])
    check_repo(repo)
    task = read_json(ROOT / f'docs/collaboration/queue/{task_id}.json')
    saved = state()
    previous = saved['jobs'].get(task_id)
    if previous and not resume:
        raise ValueError('Task already dispatched; inspect its result instead of launching a duplicate')
    if resume and (not previous or previous['status'] != 'blocked'):
        raise ValueError('Only a blocked, stopped task can be resumed')
    if resume and previous.get('attempt', 1) >= 3:
        raise ValueError('Three attempts reached; review the failure before defining new work')
    if any(j['status'] == 'running' for j in saved['jobs'].values()):
        raise ValueError('Another bridge task is running')
    if any(d not in saved['accepted'] for d in task['depends_on']):
        raise ValueError('Required Codex reviews have not been accepted')
    dirty = changed_paths(repo)
    if resume:
        base = previous['base_sha']
        if git(repo, 'branch', '--show-current') != task['branch'] or git(repo, 'rev-parse', 'HEAD') != base:
            raise ValueError('Resume branch or HEAD changed; inspect manually without discarding work')
        if any(not allowed(p, task) for p in dirty):
            raise ValueError('Resume contains out-of-scope changes; preserve for Codex review')
    else:
        if dirty:
            raise ValueError('Worker checkout has uncommitted changes; preserve them and wait')
        if git(repo, 'branch', '--list', task['branch']):
            raise ValueError('Task branch already exists; inspect it before retrying')
        base = git(repo, 'rev-parse', 'HEAD')
        git(repo, 'checkout', '-b', task['branch'])
    run_dir = RUNTIME / (task_id + '-' + uuid.uuid4().hex[:10])
    run_dir.mkdir(parents=True)
    job = {'status': 'running', 'base_sha': base, 'branch': task['branch'], 'started_at': time.time(),
           'runner_pid': os.getpid(), 'run_dir': str(run_dir), 'attempt': previous.get('attempt', 1) + 1 if previous else 1}
    if previous:
        saved.setdefault('history', []).append({'task_id': task_id, **previous})
    saved['jobs'][task_id] = job
    write_json(STATE, saved)
    python = str(ROOT / '.venv/Scripts/python.exe')
    prompt = (f'你是本專題 Antigravity 開發者，由使用者授權 Codex 自動派工。使用繁體中文。任務 {task_id}。'
              f'此獨立 checkout 的基準為 {base}，Codex 已建立工作分支，這份派工取代舊版啟動文件的人工詢問流程。'
              '只在目前 checkout 編輯下列任務範圍；不切分支、不做 git add/commit/push、reset/stash，不改 RPi/AWS/帳號設定。'
              '保留已存在的 AG-002 交付。不要讀取憑證、私密設定或非專題個人檔案。'
              f'允許檔案：{task["allowed_paths"]}；允許前綴：{task["allowed_prefixes"]}。'
              '此任務是編輯交付階段：只使用內建檔案讀取／寫入工具，命令、終端、shell、MCP 與瀏覽器工具均不使用。'
              'Codex 已確認基準、分支與工作目錄，無須用 git 或列目錄確認。讀取已知的 docs/collaboration/tasks.md、docs/report/methods.md、scripts/evaluate-run.py 及相關檔案即可。'
              '不必安裝付費服務或使用 API key；使用既有登入。若必要操作無法完成，將未測項目與原因寫入交接。'
              '完成程式與測試檔後，在交接明確寫「本階段測試未執行，由 Codex 接續」，不要宣稱通過。Codex 將自動執行並回歸，不需要詢問使用者。'
              + task['instruction'])
    if resume:
        prompt = '這是已查明阻塞原因後的接續工作。先讀取並保留目前未完成檔案，補足缺口，不重新 clone 或丟棄已有成果。' + prompt
    (run_dir / 'prompt.txt').write_text(prompt, encoding='utf-8')
    settings_path = run_dir / 'session-settings.json'
    try:
        global_settings = Path.home() / '.gemini/antigravity-cli/settings.json'
        existing_permissions = read_json(global_settings).get('permissions', {}) if global_settings.exists() else {}
        write_json(settings_path, session_settings(task, python, existing_permissions, workspace=repo))
        with (run_dir / 'stdout.json').open('wb') as out, (run_dir / 'stderr.log').open('wb') as err:
            proc = subprocess.run([config['cli'], '-p', prompt, '--mode', 'accept-edits', '--sandbox', '--settings', str(settings_path),
                                   '--output-format', 'json', '--print-timeout', '20m'],
                                  cwd=repo, env={**os.environ, 'PYTHONPATH': str(repo / 'src')}, stdout=out, stderr=err, timeout=1250)
        result = read_json(run_dir / 'stdout.json')
        job.update(returncode=proc.returncode, provider_status=result.get('status'))
        if proc.returncode != 0 or result.get('status') != 'SUCCESS':
            raise ValueError('Agent did not produce a successful terminal result; inspect private logs')
        if git(repo, 'rev-parse', 'HEAD') != base:
            raise ValueError('Agent changed HEAD unexpectedly; preserve changes for review')
        changed = changed_paths(repo)
        if not changed or any(not allowed(p, task) for p in changed):
            raise ValueError('Changed files are empty or outside the task scope; preserve for review')
        if not ready_handoff((repo / task['handoff']).read_text(encoding='utf-8')):
            raise ValueError('Handoff is missing ready_for_review; no delivery commit created')
        git(repo, 'add', '--', *changed)
        git(repo, 'commit', '-m', f'{task_id}: deliver independent work for Codex review')
        job.update(status='delivered', delivery_sha=git(repo, 'rev-parse', 'HEAD'), files=changed)
    except Exception as error:
        job.update(status='blocked', error=str(error))
    finally:
        job['finished_at'] = time.time()
        saved = state()
        saved['jobs'][task_id] = job
        write_json(STATE, saved)
    return job


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['status', 'run', 'resume', 'import', 'accept'])
    parser.add_argument('task', nargs='?')
    parser.add_argument('--sha')
    parser.add_argument('--review-file', type=Path)
    args = parser.parse_args()
    try:
        config = read_json(CONFIG)
        RUNTIME.mkdir(parents=True, exist_ok=True)
        if args.action == 'status':
            result = status(config)
        elif args.action in ('run', 'resume'):
            lock = RUNTIME / 'dispatch.lock'
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            try:
                os.close(fd)
                result = dispatch(config, args.task, resume=args.action == 'resume')
            finally:
                lock.unlink()
        else:
            if args.task not in ('AG-001', 'AG-002', 'AG-003', 'AG-004', 'AG-005'):
                raise ValueError('Unknown task')
            repo = Path(config['checkout'])
            check_repo(repo)
            match = next((d for d in deliveries(repo) if d['task_id'] == args.task and d['sha'] == args.sha), None)
            if not match:
                raise ValueError('Delivery SHA or ready handoff does not match')
            if args.action == 'import':
                ref = f'refs/remotes/antigravity-local/{args.task}'
                git(ROOT, 'fetch', str(repo), f'refs/heads/{match["branch"]}:{ref}')
                result = {'imported': args.sha, 'ref': ref}
            else:
                review = args.review_file.resolve() if args.review_file else None
                if not review or not review.is_relative_to(ROOT / 'docs/reviews') or not review.is_file():
                    raise ValueError('A saved Codex review under docs/reviews is required')
                if args.sha not in review.read_text(encoding='utf-8'):
                    raise ValueError('Review must identify the exact delivery SHA')
                saved = state()
                saved['accepted'][args.task] = args.sha
                write_json(RUNTIME / f'accepted/{args.task}.json', {'task_id': args.task, 'sha': args.sha,
                           'review_file': str(review), 'accepted_at': time.time()})
                write_json(STATE, saved)
                result = {'accepted': args.task, 'sha': args.sha}
        print(json.dumps(result, ensure_ascii=False))
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        parser.exit(2, f'Bridge error: {error}\n')


if __name__ == '__main__':
    main()
