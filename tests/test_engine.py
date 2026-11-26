import math
import struct
import pytest
from ble_inventory.contracts import validate_batch
from ble_inventory.engine import InventoryEngine
from ble_inventory.inputs import SyntheticSource, decode_advertisement
from ble_inventory.positioning import multilaterate, horizontal_distance
from ble_inventory.storage import RunStore


def test_multilateration_independent_geometry():
    points=[(0,0),(10,0),(10,8),(0,8)]
    result=multilaterate(points,[math.dist(p,(3,4)) for p in points])
    assert (result["x_m"],result["y_m"]) == pytest.approx((3,4),abs=1e-7)
    with pytest.raises(ValueError,match="geometry"):
        multilaterate([(0,0),(1,0),(2,0)],[1,2,3])
    with pytest.raises(ValueError):
        horizontal_distance(1,2)


def test_full_two_stage_without_truth(config):
    config.update(filter_alpha=1,median_window=1)
    engine=InventoryEngine(config)
    source=SyntheticSource(config,noise_db=0)
    for i in range(20):
        batch,truth=source.sample(1000+i)
        assert "scanner" not in batch and "targets" not in batch
        engine.ingest(batch)
    state=engine.snapshot(1019)
    assert state["counts"] == {"inventoried":2,"visible":2,"expected":2}
    assert state["scanner"]["quality"] == "valid"
    for target in [d for d in state["devices"] if d["role"]=="target"]:
        assert target["quality"] == "valid"
        assert (target["position"]["x_m"],target["position"]["y_m"]) == pytest.approx(truth["targets"][target["id"]][:2],abs=0.01)
    stale=engine.snapshot(1031)
    assert stale["counts"]["inventoried"]==2 and stale["counts"]["visible"]==0
    assert [d for d in stale["devices"] if d["role"]=="target"][0]["position"] is not None
    engine.start("simulation")
    assert engine.snapshot(1031)["counts"]["inventoried"]==0


def test_truth_duplicate_and_order_rejected(config):
    engine=InventoryEngine(config);source=SyntheticSource(config)
    batch,_=source.sample(1000)
    with pytest.raises(ValueError,match="truth"):
        validate_batch({**batch,"scanner_position":[1,2]})
    engine.ingest(batch)
    with pytest.raises(ValueError,match="out-of-order"):
        engine.ingest(batch)
    bad={**batch,"sequence":10,"observations":[batch["observations"][0]]*2}
    with pytest.raises(ValueError,match="Duplicate"):
        engine.ingest(bad)


def test_missing_anchors_no_fabricated_solution(config):
    engine=InventoryEngine(config);source=SyntheticSource(config)
    source.disabled.update({"A01","A02"})
    batch,_=source.sample(1000);engine.ingest(batch)
    state=engine.snapshot(1000)
    assert state["scanner"]["position"] is None
    assert state["counts"]["inventoried"]==2
    assert all(d["position"] is None for d in state["devices"] if d["role"]=="target")


def test_ble_binary_contract():
    packet=struct.pack("<2sBBHbH",b"BI",1,2,2,-59,0)
    assert decode_advertisement(packet)=={"device_id":"T02","rssi_at_1m_dbm":-59}
    assert decode_advertisement(b"junk") is None


def test_append_only_records_and_csv(config,tmp_path):
    engine=InventoryEngine(config);source=SyntheticSource(config)
    store=RunStore(tmp_path,engine,"demo")
    batch,_=source.sample(1000);engine.ingest(batch);store.observation(batch);store.snapshot(engine.snapshot(1000))
    replay=store.replay()
    assert replay["kind"]=="ble-inventory-replay" and len(replay["frames"])==1
    assert "latitude_deg" in store.csv()
    assert "cert_path" not in (store.raw/"manifest.json").read_text(encoding="utf-8")
    store.close()
