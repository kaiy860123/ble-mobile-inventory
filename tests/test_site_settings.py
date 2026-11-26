import asyncio
import copy
import json
import pytest
from aiohttp.test_utils import TestClient, TestServer
from ble_inventory.config import load_config
from ble_inventory.coordinates import GeoReference
from ble_inventory.server import create_app
from ble_inventory.site_settings import editable_view, prepare_edit


def editable(config):
    view = editable_view(config)
    for row in view['anchors']:
        row.pop('computed_wgs84', None)
        if 'position_wgs84' in row:
            row.pop('position', None)
    return view


def test_wgs84_rotated_and_private_preserved(config):
    settings = editable(config)
    settings['georeference'] = dict(latitude_deg=25.0, longitude_deg=121.5, height_m=20, rotation_deg=37)
    ref = GeoReference(**settings['georeference'])
    for row in settings['anchors']:
        g = ref.to_wgs84(*row.pop('position'))
        g.pop('transform_id')
        row['position_wgs84'] = g
    result, _ = prepare_edit(config, settings)
    assert result['cloud'] == config['cloud']
    for before, after in zip(config['devices'][:4], result['devices'][:4]):
        assert after['position'] == pytest.approx(before['position'], abs=1e-5)


@pytest.mark.parametrize('case', ['nan', 'bounds', 'collinear', 'target_xy', 'new_id', 'cloud'])
def test_invalid_settings(config, case):
    settings = editable(config)
    if case == 'nan': settings['anchors'][0]['position'][0] = float('nan')
    if case == 'bounds': settings['bounds_m'] = [0, 0, 0, 9]
    if case == 'collinear':
        for i, row in enumerate(settings['anchors']): row['position'] = [i, 0, 1.2]
    if case == 'target_xy': settings['targets'][0]['position'] = [1, 2]
    if case == 'new_id': settings['anchors'][0]['id'] = 'A99'
    if case == 'cloud': settings['cloud'] = {'enabled': True}
    with pytest.raises((ValueError, TypeError)):
        prepare_edit(config, settings)


def test_settings_api_transaction(config, tmp_path, monkeypatch):
    async def scenario():
        path = tmp_path / 'config/site.local.json'
        path.parent.mkdir()
        path.write_text(json.dumps(config), encoding='utf-8')
        initial = path.read_bytes()
        app = create_app(config, tmp_path, 'external', 'ingest', config_path=path)
        async with TestClient(TestServer(app)) as client:
            bootstrap = await (await client.get('/api/bootstrap')).json()
            assert bootstrap['settings_editable']
            headers = {'X-Control-Token': bootstrap['control_token']}
            assert (await client.get('/api/settings')).status == 403
            assert (await client.get('/api/settings', headers={**headers, 'Origin': 'https://other.example'})).status == 403
            data = await (await client.get('/api/settings', headers=headers)).json()
            assert 'cloud' not in data['settings']
            settings = editable(config)
            settings['anchors'][0]['position'][0] = .25
            before = await (await client.get('/api/state')).json()
            preview = await client.post('/api/settings/preview', json={'settings': settings}, headers=headers)
            assert preview.status == 200
            assert path.read_bytes() == initial
            assert (await (await client.get('/api/state')).json())['run_id'] == before['run_id']
            body = {'settings': settings, 'expected_revision': data['revision']}
            from ble_inventory import server
            real_persist = server.persist_edit
            def failed(*args): raise OSError('simulated disk full')
            monkeypatch.setattr(server, 'persist_edit', failed)
            assert (await client.post('/api/settings', json=body, headers=headers)).status == 507
            assert path.read_bytes() == initial
            assert (await (await client.get('/api/state')).json())['run_id'] == before['run_id']
            monkeypatch.setattr(server, 'persist_edit', real_persist)
            response = await client.post('/api/settings', json=body, headers=headers)
            assert response.status == 200, await response.text()
            saved = await response.json()
            assert saved['state']['run_id'] != before['run_id']
            assert load_config(path)['devices'][0]['position'][0] == .25
            assert load_config(path)['cloud'] == config['cloud']
            backups = list((tmp_path / 'config/private/settings-backups').glob('*.json'))
            assert len(backups) == 1 and backups[0].read_bytes() == initial
            old = tmp_path / 'data/raw' / before['run_id'] / 'manifest.json'
            assert json.loads(old.read_text(encoding='utf-8'))['site']['devices'][0]['position'][0] == 0
            assert (await client.post('/api/settings', json=body, headers=headers)).status == 409
            assert load_config(path)['devices'][0]['position'][0] == .25
    asyncio.run(scenario())


def test_settings_unavailable_without_explicit_path(config, tmp_path):
    async def scenario():
        async with TestClient(TestServer(create_app(config, tmp_path, 'external'))) as client:
            b = await (await client.get('/api/bootstrap')).json()
            assert not b['settings_editable']
            assert (await client.get('/api/settings', headers={'X-Control-Token': b['control_token']})).status == 404
    asyncio.run(scenario())


@pytest.mark.parametrize('field', ['transform_id', 'source'])
def test_whitespace_georeference_identifiers_rejected(config, field):
    settings = editable(config)
    settings['georeference'] = dict(latitude_deg=25, longitude_deg=121.5, height_m=0, rotation_deg=0, transform_id='site-v1', source='example')
    settings['georeference'][field] = '   '
    with pytest.raises(ValueError, match='識別'):
        prepare_edit(config, settings)


def test_failed_abort_marker_does_not_mask_storage_error(config, tmp_path, monkeypatch):
    async def scenario():
        from pathlib import Path
        from ble_inventory import server
        path = tmp_path / 'config/site.local.json'
        path.parent.mkdir()
        path.write_text(json.dumps(config), encoding='utf-8')
        initial = path.read_bytes()
        async with TestClient(TestServer(create_app(config, tmp_path, 'external', config_path=path))) as client:
            bootstrap = await (await client.get('/api/bootstrap')).json()
            headers = {'X-Control-Token': bootstrap['control_token']}
            data = await (await client.get('/api/settings', headers=headers)).json()
            old_run = (await (await client.get('/api/state')).json())['run_id']
            original_write = Path.write_text
            def fail_marker(self, *args, **kwargs):
                if self.name == 'aborted.txt': raise OSError('disk full during error cleanup')
                return original_write(self, *args, **kwargs)
            def fail_persist(*args): raise OSError('disk full')
            monkeypatch.setattr(Path, 'write_text', fail_marker)
            monkeypatch.setattr(server, 'persist_edit', fail_persist)
            response = await client.post('/api/settings', json={'expected_revision': data['revision'], 'settings': editable(config)}, headers=headers)
            assert response.status == 507
            assert path.read_bytes() == initial
            assert (await (await client.get('/api/state')).json())['run_id'] == old_run
    asyncio.run(scenario())
