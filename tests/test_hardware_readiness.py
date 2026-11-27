import importlib.util
from pathlib import Path
import time
import pytest

spec=importlib.util.spec_from_file_location('hardware_readiness',Path(__file__).parents[1]/'scripts/check-physical-readiness.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)

def state(**changes):
    return dict(source='physical',input_mode='ble',active=True,devices=[],**changes)

def test_requires_new_sightings_not_old_cached_positions():
    now=time.time()
    sample=state()
    sample['devices']=[{'id':'A01','last_seen':now-20,'position':{'x_m':1}}, {'id':'T01','last_seen':now}, {'id':'UNKNOWN','last_seen':now}]
    assert module.inspect_state(sample,now-1)=={'T01'}

def test_all_expected_ids_seen_after_start():
    now=time.time();sample=state()
    sample['devices']=[{'id':key,'last_seen':now} for key in module.EXPECTED]
    assert module.inspect_state(sample,now-1)==module.EXPECTED

@pytest.mark.parametrize('changes',[{'source':'simulation'},{'input_mode':'demo'},{'active':False},{'input_error':'Bluetooth unavailable'}])
def test_nonphysical_inactive_or_failed_input_is_not_hardware_evidence(changes):
    sample=state();sample.update(changes)
    with pytest.raises(ValueError):module.inspect_state(sample,time.time())
