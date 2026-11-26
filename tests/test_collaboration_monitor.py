import importlib.util
from pathlib import Path
import pytest

spec = importlib.util.spec_from_file_location('collaboration_monitor', Path(__file__).parents[1] / 'scripts/check-collaboration.py')
monitor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(monitor)


def test_add_modify_delete_are_detected():
    assert monitor.changes({'a': '1', 'b': '2'}, {'a': '3', 'c': '4'}) == [
        {'path': 'a', 'change': 'modified'}, {'path': 'b', 'change': 'deleted'}, {'path': 'c', 'change': 'added'}]


def test_stability_and_repeat_ack():
    state = {'reviewed_files': {'a': '1'}}
    files = {'a': '2'}
    assert monitor.observe(state, files, 100)['status'] == 'settling'
    assert monitor.observe(state, files, 159)['status'] == 'settling'
    ready = monitor.observe(state, files, 160)
    assert ready['status'] == 'ready'
    monitor.acknowledge(state, files, ready['fingerprint'])
    assert monitor.observe(state, files, 500)['status'] == 'unchanged'


def test_edit_resets_stability_and_reverted_change_disappears():
    state = {'reviewed_files': {'a': '1'}}
    monitor.observe(state, {'a': '2'}, 100)
    assert monitor.observe(state, {'a': '3'}, 200)['status'] == 'settling'
    assert monitor.observe(state, {'a': '1'}, 300)['status'] == 'unchanged'
    assert 'pending' not in state


def test_changes_during_review_cannot_be_acknowledged():
    state = {'reviewed_files': {'a': '1'}}
    result = monitor.observe(state, {'a': '2'}, 100)
    with pytest.raises(ValueError, match='changed'):
        monitor.acknowledge(state, {'a': '3'}, result['fingerprint'])
    assert state['reviewed_files'] == {'a': '1'}


def test_ignored_files_and_no_following_external_symlink(tmp_path, monkeypatch):
    (tmp_path / 'source.py').write_text('x=1', encoding='utf-8')
    (tmp_path / 'docs/progress').mkdir(parents=True)
    (tmp_path / 'docs/progress/template.html').write_text('<div>progress</div>', encoding='utf-8')
    monkeypatch.setattr(monitor.subprocess, 'check_output', lambda *a, **k: b'source.py\0artifacts/private.txt\0docs/progress/state.json\0docs/progress/template.html\0source.py\0')
    assert set(monitor.collect(tmp_path)) == {'source.py', 'docs/progress/template.html'}
    monkeypatch.setattr(monitor.subprocess, 'check_output', lambda *a, **k: b'../outside.txt\0')
    with pytest.raises(ValueError, match='escapes'):
        monitor.collect(tmp_path)
