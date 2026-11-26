"""Render the evidence snapshot for the in-conversation project tracker."""
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
data = json.loads((root / 'docs/progress/state.json').read_text(encoding='utf-8'))
allowed = {'verified', 'in_progress', 'blocked', 'todo'}
assert len({t['id'] for t in data['tasks']}) == len(data['tasks'])
assert all(t['status'] in allowed and t['evidence'] and t['next'] for t in data['tasks'])
template = (root / 'docs/progress/template.html').read_text(encoding='utf-8')
payload = json.dumps(data, ensure_ascii=False).replace('<', '\\u003c')
output = root / 'artifacts/progress/project-progress.html'
output.parent.mkdir(parents=True, exist_ok=True)
output.write_text(template.replace('__PROGRESS_DATA__', payload), encoding='utf-8')
assert output.stat().st_size < 1_000_000
print(output)
