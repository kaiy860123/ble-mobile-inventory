import importlib.util
from pathlib import Path
import pytest

spec = importlib.util.spec_from_file_location('antigravity_bridge', Path(__file__).parents[1] / 'scripts/antigravity-bridge.py')
bridge = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bridge)


def test_handoff_status_is_an_explicit_line():
    assert bridge.ready_handoff('- 狀態：ready_for_review\n')
    assert bridge.ready_handoff('Status: `ready_for_review`\n')
    assert not bridge.ready_handoff('稍後將狀態改成 ready_for_review')
    assert not bridge.ready_handoff('- 狀態：in_progress\n')


def test_task_write_scope_is_explicit():
    task = {'allowed_paths': ['tests/a.py'], 'allowed_prefixes': ['tests/browser/']}
    assert bridge.allowed('tests/a.py', task)
    assert bridge.allowed('tests/browser/mobile.mjs', task)
    assert not bridge.allowed('src/ble_inventory/engine.py', task)
    assert not bridge.allowed('tests/browser/../../src/engine.py', task)
    assert not bridge.allowed('/tests/a.py', task)


def test_deliveries_use_committed_ready_handoff(monkeypatch):
    def fake(repo, *args):
        if args[0] == 'for-each-ref':
            return 'antigravity/AG-001-settings-review\taaa\nantigravity/AG-002-review\tbbb'
        return '- 狀態：ready_for_review' if args[1].startswith('bbb:') else '- 狀態：in_progress'
    monkeypatch.setattr(bridge, 'git', fake)
    assert bridge.deliveries(Path('.')) == [{'task_id': 'AG-002', 'branch': 'antigravity/AG-002-review', 'sha': 'bbb'}]


def test_wrong_repository_is_rejected(monkeypatch):
    monkeypatch.setattr(bridge, 'git', lambda *args: 'https://github.com/other/project.git')
    with pytest.raises(ValueError, match='authorized'):
        bridge.check_repo(Path('.'))


def test_ag005_delivery_is_discoverable_and_dispatch_checks_dependencies(tmp_path, monkeypatch):
    def fake(repo, *args):
        if args[0] == 'for-each-ref':
            return 'antigravity/AG-005-anchor-comparison\tnew-delivery'
        return '狀態：ready_for_review'
    monkeypatch.setattr(bridge, 'git', fake)
    assert bridge.deliveries(tmp_path) == [{'task_id': 'AG-005', 'branch': 'antigravity/AG-005-anchor-comparison', 'sha': 'new-delivery'}]
    monkeypatch.setattr(bridge, 'check_repo', lambda *args: None)
    monkeypatch.setattr(bridge, 'state', lambda: {'jobs': {}, 'accepted': {}})
    with pytest.raises(ValueError, match='reviews'):
        bridge.dispatch({'checkout': str(tmp_path)}, 'AG-005')


def test_session_permissions_are_scoped_and_do_not_enable_global_bypass():
    settings = bridge.session_settings({'allowed_paths': ['tests/a.py'], 'allowed_prefixes': []}, '/project/.venv/Scripts/python.exe')
    rules = settings['permissions']
    assert f'write_file({bridge.ROOT / "tests/a.py"})' in rules['allow']
    assert f'write_file({bridge.ROOT / "src"})' in rules['deny']
    assert 'command(*)' in rules['deny']
    assert not any('(*)' in rule for rule in rules['allow'])
    assert 'ask' not in rules


def test_session_permissions_preserve_existing_deny_and_ask():
    original = {'deny': ['command(custom-deploy)'], 'ask': ['command(*)']}
    result = bridge.session_settings({'allowed_paths': [], 'allowed_prefixes': []}, '/venv/python', original)
    assert 'command(custom-deploy)' in result['permissions']['deny']
    assert result['permissions']['ask'] == ['command(*)']
    assert original == {'deny': ['command(custom-deploy)'], 'ask': ['command(*)']}


def test_editing_worker_has_no_native_command_grants():
    rules = bridge.session_settings({'allowed_paths': ['tests/a.py'], 'allowed_prefixes': []}, '/venv/python')['permissions']['allow']
    assert not any(rule.startswith('command(') for rule in rules)
    assert 'command(*)' in bridge.session_settings({'allowed_paths': [], 'allowed_prefixes': []}, '/venv/python')['permissions']['deny']


def test_sandbox_permission_paths_are_absolute_and_cannot_escape(tmp_path):
    settings = bridge.session_settings({'allowed_paths': ['tests/a.py'], 'allowed_prefixes': []}, '/venv/python', workspace=tmp_path)
    assert f'write_file({tmp_path / "tests/a.py"})' in settings['permissions']['allow']
    with pytest.raises(ValueError, match='outside'):
        bridge.session_settings({'allowed_paths': ['../outside.py'], 'allowed_prefixes': []}, '/venv/python', workspace=tmp_path)


def test_dispatch_does_not_repeat_existing_job(tmp_path, monkeypatch):
    monkeypatch.setattr(bridge, 'check_repo', lambda *args: None)
    monkeypatch.setattr(bridge, 'state', lambda: {'jobs': {'AG-001': {'status': 'delivered'}}, 'accepted': {}})
    with pytest.raises(ValueError, match='already dispatched'):
        bridge.dispatch({'checkout': str(tmp_path)}, 'AG-001')


def test_accepted_receipt_survives_stale_worker_state_write(tmp_path, monkeypatch):
    monkeypatch.setattr(bridge, 'RUNTIME', tmp_path)
    monkeypatch.setattr(bridge, 'STATE', tmp_path / 'state.json')
    bridge.write_json(tmp_path / 'accepted/AG-002.json', {'task_id': 'AG-002', 'sha': 'delivered-sha'})
    bridge.write_json(tmp_path / 'state.json', {'jobs': {}, 'accepted': {}})
    assert bridge.state()['accepted'] == {'AG-002': 'delivered-sha'}


def test_dependencies_and_dirty_workspace_block_dispatch(tmp_path, monkeypatch):
    monkeypatch.setattr(bridge, 'check_repo', lambda *args: None)
    monkeypatch.setattr(bridge, 'state', lambda: {'jobs': {}, 'accepted': {}})
    with pytest.raises(ValueError, match='reviews'):
        bridge.dispatch({'checkout': str(tmp_path)}, 'AG-003')
    monkeypatch.setattr(bridge, 'changed_paths', lambda *args: ['existing-work.py'])
    with pytest.raises(ValueError, match='uncommitted'):
        bridge.dispatch({'checkout': str(tmp_path)}, 'AG-001')


def test_resume_requires_blocked_state_and_is_bounded(tmp_path, monkeypatch):
    monkeypatch.setattr(bridge, 'check_repo', lambda *args: None)
    monkeypatch.setattr(bridge, 'state', lambda: {'jobs': {}, 'accepted': {}})
    with pytest.raises(ValueError, match='blocked'):
        bridge.dispatch({'checkout': str(tmp_path)}, 'AG-001', resume=True)
    monkeypatch.setattr(bridge, 'state', lambda: {'jobs': {'AG-001': {'status': 'blocked', 'attempt': 3}}, 'accepted': {}})
    with pytest.raises(ValueError, match='Three attempts'):
        bridge.dispatch({'checkout': str(tmp_path)}, 'AG-001', resume=True)
