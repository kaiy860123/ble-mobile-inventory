import math
import pytest
from ble_inventory.coordinates import GeoReference, geodetic_to_ecef, ecef_to_geodetic, A, F


def test_independent_wgs84_control_points():
    assert geodetic_to_ecef(0,0) == pytest.approx((6378137,0,0),abs=1e-8)
    assert geodetic_to_ecef(0,90) == pytest.approx((0,6378137,0),abs=1e-8)
    assert geodetic_to_ecef(90,0) == pytest.approx((0,0,6356752.314245),abs=1e-6)
    assert ecef_to_geodetic(0,0,6356752.314245) == pytest.approx((90,0,0),abs=1e-6)


def test_independent_east_and_rotation():
    east = GeoReference(0,0).to_wgs84(100,0)
    assert east["latitude_deg"] == pytest.approx(0,abs=1e-10)
    assert east["longitude_deg"] == pytest.approx(math.degrees(math.atan2(100,6378137)),abs=1e-10)
    north = GeoReference(0,0,rotation_deg=90).to_wgs84(100,0)
    assert north["longitude_deg"] == pytest.approx(0,abs=1e-10)
    assert north["latitude_deg"] > 0


@pytest.mark.parametrize("rotation",[0,25,90,-135,360])
def test_taipei_roundtrip_with_height(rotation):
    reference=GeoReference(25.01734,121.53975,height_m=15,rotation_deg=rotation)
    geo=reference.to_wgs84(12.34,-5.67,1.2)
    local=reference.to_local(geo["latitude_deg"],geo["longitude_deg"],geo["height_m"])
    assert tuple(local.values()) == pytest.approx((12.34,-5.67,1.2),abs=1e-6)


def test_invalid_origin():
    with pytest.raises(ValueError):
        GeoReference(120,0)
