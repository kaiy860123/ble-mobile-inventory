import json
import pytest
from ble_inventory.config import load_config
from ble_inventory.coordinates import GeoReference


def test_wgs84_anchor_input_converted_and_conflict_rejected(config,tmp_path):
    reference=GeoReference(25,121,rotation_deg=30)
    config['georeference']={'latitude_deg':25,'longitude_deg':121,'rotation_deg':30}
    device=config['devices'][0]
    device.pop('position')
    geo=reference.to_wgs84(4,5,1.2)
    device['position_wgs84']={k:geo[k] for k in ('latitude_deg','longitude_deg','height_m')}
    path=tmp_path/'site.json';path.write_text(json.dumps(config),encoding='utf-8')
    loaded=load_config(path)
    assert loaded['devices'][0]['position']==pytest.approx([4,5,1.2],abs=1e-6)
    device['position']=[100,100,1.2]
    path.write_text(json.dumps(config),encoding='utf-8')
    with pytest.raises(ValueError,match='disagree'):load_config(path)
