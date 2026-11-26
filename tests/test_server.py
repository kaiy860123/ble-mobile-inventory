import asyncio
import time
from aiohttp.test_utils import TestClient, TestServer
from ble_inventory.server import create_app
from ble_inventory.inputs import SyntheticSource


def test_external_ingestion_controls_and_export(config,tmp_path):
    async def scenario():
        app=create_app(config,tmp_path,"external",ingest_token="test-token")
        async with TestClient(TestServer(app)) as client:
            response=await client.get('/api/bootstrap');bootstrap=await response.json()
            assert bootstrap['local'] is True
            assert (await client.post('/api/control',json={'action':'stop'})).status==403
            headers={'X-Control-Token':bootstrap['control_token']}
            assert (await client.post('/api/control',json={'action':'stop'},headers={**headers,'Origin':'https://attacker.example'})).status==403
            source=SyntheticSource(config)
            batch,_=source.sample()
            assert (await client.post('/api/observations',json=batch)).status==401
            response=await client.post('/api/observations',json=batch,headers={'Authorization':'Bearer test-token'})
            assert response.status==200 and (await response.json())['accepted']
            assert (await client.post('/api/observations',json=batch,headers={'Authorization':'Bearer test-token'})).status==400
            state=await (await client.get('/api/state')).json()
            assert state['counts']['inventoried']==2
            await asyncio.sleep(1.05)
            replay=await (await client.get('/api/export')).json()
            assert replay['kind']=='ble-inventory-replay' and replay['frames']
            csv=await (await client.get('/api/export?format=csv')).text()
            assert 'rssi_dbm' in csv
            assert (await client.post('/api/control',json={'action':'stop'},headers=headers)).status==200
            batch,_=source.sample()
            response=await client.post('/api/observations',json=batch,headers={'Authorization':'Bearer test-token'})
            assert (await response.json())['accepted'] is False
            old_run=state['run_id']
            state=await (await client.post('/api/control',json={'action':'start'},headers=headers)).json()
            assert state['run_id']!=old_run and state['counts']['inventoried']==0
    asyncio.run(scenario())
