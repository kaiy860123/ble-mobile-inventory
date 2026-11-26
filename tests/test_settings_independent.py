"""Independent acceptance tests for AG-001 (site settings & coordinate transaction)."""
import asyncio
import copy
import hashlib
import json
import math
from pathlib import Path
import re

import pytest
from aiohttp.test_utils import TestClient, TestServer

from ble_inventory.config import load_config
from ble_inventory.inputs import SyntheticSource
from ble_inventory.server import create_app
from ble_inventory.site_settings import FIELDS, RevisionConflict, editable_view, prepare_edit


# --- Independent WGS84 / ENU / Local reference math (not importing coordinates.py) ---

_WGS84_A = 6378137.0
_WGS84_F = 1.0 / 298.257223563
_WGS84_E2 = _WGS84_F * (2.0 - _WGS84_F)


def _indep_llh_to_ecef(lat_deg, lon_deg, h_m):
    lat = math.radians(lat_deg)
    lon = math.radians(lon_deg)
    sin_lat, cos_lat = math.sin(lat), math.cos(lat)
    sin_lon, cos_lon = math.sin(lon), math.cos(lon)
    nu = _WGS84_A / math.sqrt(1.0 - _WGS84_E2 * sin_lat * sin_lat)
    return (
        (nu + h_m) * cos_lat * cos_lon,
        (nu + h_m) * cos_lat * sin_lon,
        (nu * (1.0 - _WGS84_E2) + h_m) * sin_lat,
    )


def _indep_ecef_to_llh(x, y, z):
    p = math.hypot(x, y)
    lon = math.atan2(y, x)
    lat = math.atan2(z, p * (1.0 - _WGS84_E2))
    for _ in range(20):
        sin_lat = math.sin(lat)
        nu = _WGS84_A / math.sqrt(1.0 - _WGS84_E2 * sin_lat * sin_lat)
        nxt = math.atan2(z + _WGS84_E2 * nu * sin_lat, p)
        if abs(nxt - lat) < 1e-15:
            lat = nxt
            break
        lat = nxt
    sin_lat = math.sin(lat)
    nu = _WGS84_A / math.sqrt(1.0 - _WGS84_E2 * sin_lat * sin_lat)
    h = p / math.cos(lat) - nu
    return math.degrees(lat), math.degrees(lon), h


def _indep_local_to_wgs84(origin_lat, origin_lon, origin_h, rot_deg, x_m, y_m, z_m):
    """Reference transform: rotation_deg is Local +X counter-clockwise from East."""
    theta = math.radians(rot_deg)
    east = math.cos(theta) * x_m - math.sin(theta) * y_m
    north = math.sin(theta) * x_m + math.cos(theta) * y_m
    up = z_m

    lat0 = math.radians(origin_lat)
    lon0 = math.radians(origin_lon)
    sin_lat, cos_lat = math.sin(lat0), math.cos(lat0)
    sin_lon, cos_lon = math.sin(lon0), math.cos(lon0)

    ox, oy, oz = _indep_llh_to_ecef(origin_lat, origin_lon, origin_h)
    dx = -sin_lon * east - sin_lat * cos_lon * north + cos_lat * cos_lon * up
    dy = cos_lon * east - sin_lat * sin_lon * north + cos_lat * sin_lon * up
    dz = cos_lat * north + sin_lat * up
    lat, lon, h = _indep_ecef_to_llh(ox + dx, oy + dy, oz + dz)
    return {"latitude_deg": lat, "longitude_deg": lon, "height_m": h}


def _to_editable_payload(view):
    payload = copy.deepcopy(view)
    for row in payload["anchors"]:
        row.pop("computed_wgs84", None)
        if "position_wgs84" in row:
            row.pop("position", None)
    return payload


def _make_config_with_private_cloud(base_config):
    cfg = copy.deepcopy(base_config)
    cfg["path_loss_exponent"] = 2.35
    cfg["rssi_at_1m_dbm"] = -61.5
    cfg["filter_alpha"] = 0.55
    cfg["median_window"] = 5
    cfg["cloud"] = {
        "enabled": False,
        "endpoint": "example-private.iot.ap-northeast-1.amazonaws.com",
        "region": "ap-northeast-1",
        "topic": "ble-inventory/private-site/state",
        "client_id": "rpi-private-01",
        "cert_path": "/etc/ble-inventory/certs/device.pem.crt",
        "key_path": "/etc/ble-inventory/certs/private.pem.key",
        "ca_path": "/etc/ble-inventory/certs/AmazonRootCA1.pem",
    }
    return cfg


def _write_site(tmp_path, cfg):
    path = tmp_path / "config" / "site.local.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def _snapshot_tree(root):
    result = {}
    for p in sorted(Path(root).rglob("*")):
        rel = p.relative_to(root).as_posix()
        result[rel] = p.read_bytes() if p.is_file() else None
    return result


# --- 1. Local save, reload, restart, private preservation, old-run isolation ---


def test_local_save_reload_restart_preserves_private_and_old_run(config, tmp_path):
    async def scenario():
        cfg = _make_config_with_private_cloud(config)
        path = _write_site(tmp_path, cfg)
        initial_bytes = path.read_bytes()
        initial_sha = hashlib.sha256(initial_bytes).hexdigest()

        app = create_app(cfg, tmp_path, mode="external", ingest_token="ingest-tok", config_path=path)
        async with TestClient(TestServer(app)) as client:
            boot = await (await client.get("/api/bootstrap")).json()
            assert boot["local"] is True
            assert boot["settings_editable"] is True
            headers = {"X-Control-Token": boot["control_token"]}

            # GET /api/settings exposes only whitelisted editable fields, never cloud or RF model internals.
            resp = await client.get("/api/settings", headers=headers)
            assert resp.status == 200
            assert resp.headers.get("Cache-Control") == "no-store"
            got = await resp.json()
            assert got["revision"] == initial_sha
            assert set(got["settings"]) == FIELDS
            raw_text = json.dumps(got)
            for secret_marker in ("cloud", "private.pem.key", "device.pem.crt", "path_loss_exponent"):
                assert secret_marker not in raw_text

            # Record one observation in old run before editing settings.
            source = SyntheticSource(cfg, seed=101, noise_db=0.1)
            batch, _ = source.sample()
            ingest_resp = await client.post(
                "/api/observations",
                json=batch,
                headers={"Authorization": "Bearer ingest-tok"},
            )
            assert ingest_resp.status == 200 and (await ingest_resp.json())["accepted"] is True
            old_state = await (await client.get("/api/state")).json()
            old_run_id = old_state["run_id"]
            assert old_state["counts"]["inventoried"] == 2

            # Apply Local edits across all whitelisted fields.
            edited = _to_editable_payload(got["settings"])
            edited["frame_id"] = "lab-floor-2.v1"
            edited["bounds_m"] = [-2.5, -1.0, 15.5, 11.0]
            edited["scanner_height_m"] = 1.45
            edited["configuration_status"] = "measured"
            edited["anchors"] = [
                {"id": "A01", "position": [-1.0, 0.5, 1.8]},
                {"id": "A02", "position": [13.5, 0.25, 1.85]},
                {"id": "A03", "position": [14.0, 9.75, 1.9]},
                {"id": "A04", "position": [-0.5, 10.0, 1.75]},
            ]
            edited["targets"] = [
                {"id": "T01", "height_m": 0.85},
                {"id": "T02", "height_m": 1.65},
            ]

            save_resp = await client.post(
                "/api/settings",
                json={"expected_revision": got["revision"], "settings": edited},
                headers=headers,
            )
            assert save_resp.status == 200, await save_resp.text()
            saved = await save_resp.json()
            assert saved["saved"] is True
            assert saved["warnings"] == []
            assert saved["revision"] == hashlib.sha256(path.read_bytes()).hexdigest()
            assert saved["revision"] != initial_sha

            new_state = saved["state"]
            new_run_id = new_state["run_id"]
            assert new_run_id != old_run_id
            assert new_state["counts"]["inventoried"] == 0
            assert new_state["site"]["frame_id"] == "lab-floor-2.v1"
            assert new_state["site"]["bounds_m"] == [-2.5, -1.0, 15.5, 11.0]
            assert new_state["site"]["scanner_height_m"] == 1.45
            assert new_state["site"]["configuration_status"] == "measured"
            assert "cloud" not in new_state["site"]

            # Reload from GET /api/settings reflects saved edits immediately.
            reloaded = await (await client.get("/api/settings", headers=headers)).json()
            assert reloaded["revision"] == saved["revision"]
            assert reloaded["settings"]["frame_id"] == "lab-floor-2.v1"
            assert reloaded["settings"]["anchors"] == edited["anchors"]
            assert reloaded["settings"]["targets"] == edited["targets"]

            # Disk document retains private cloud & untouched RF model parameters.
            disk_doc = load_config(path)
            assert disk_doc["cloud"] == cfg["cloud"]
            assert disk_doc["path_loss_exponent"] == 2.35
            assert disk_doc["rssi_at_1m_dbm"] == -61.5
            assert disk_doc["filter_alpha"] == 0.55
            assert disk_doc["median_window"] == 5
            assert disk_doc["site_id"] == cfg["site_id"]
            assert disk_doc["scanner_id"] == cfg["scanner_id"]

            # Backup preserves exact pre-edit bytes.
            backups = list((tmp_path / "config" / "private" / "settings-backups").glob("*.json"))
            assert len(backups) == 1
            assert backups[0].read_bytes() == initial_bytes

            # Old run manifest & observations remain untouched; new run manifest has new site.
            old_manifest = json.loads((tmp_path / "data" / "raw" / old_run_id / "manifest.json").read_text(encoding="utf-8"))
            new_manifest = json.loads((tmp_path / "data" / "raw" / new_run_id / "manifest.json").read_text(encoding="utf-8"))
            assert old_manifest["site"]["frame_id"] == cfg["frame_id"]
            assert old_manifest["site"]["devices"][0]["position"] == [0, 0, 1.2]
            assert "cloud" not in old_manifest["site"]
            old_obs_lines = (tmp_path / "data" / "raw" / old_run_id / "observations.jsonl").read_text(encoding="utf-8").splitlines()
            assert len(old_obs_lines) == 1
            assert new_manifest["site"]["frame_id"] == "lab-floor-2.v1"
            assert new_manifest["site"]["devices"][0]["position"] == [-1.0, 0.5, 1.8]

        # Simulate server restart from persisted disk file.
        restarted_cfg = load_config(path)
        restarted_app = create_app(restarted_cfg, tmp_path, mode="external", ingest_token="ingest-tok", config_path=path)
        async with TestClient(TestServer(restarted_app)) as client2:
            boot2 = await (await client2.get("/api/bootstrap")).json()
            headers2 = {"X-Control-Token": boot2["control_token"]}
            after_restart = await (await client2.get("/api/settings", headers=headers2)).json()
            assert after_restart["revision"] == saved["revision"]
            assert after_restart["settings"]["frame_id"] == "lab-floor-2.v1"
            assert after_restart["settings"]["anchors"] == edited["anchors"]
            assert after_restart["settings"]["targets"] == edited["targets"]
            state2 = await (await client2.get("/api/state")).json()
            assert state2["site"]["frame_id"] == "lab-floor-2.v1"
            assert state2["site"]["devices"][0]["position"] == [-1.0, 0.5, 1.8]

    asyncio.run(scenario())


def test_out_of_bounds_anchor_and_example_status_produce_warnings_without_rejecting(config):
    settings = _to_editable_payload(editable_view(config))
    settings["configuration_status"] = "example"
    settings["anchors"][1]["position"] = [25.0, 0.0, 1.2]  # Outside bounds_m [0, 0, 12, 9]
    _, warnings = prepare_edit(config, settings)
    assert any("示例座標" in w for w in warnings)
    assert any("A02" in w and "範圍外" in w for w in warnings)


def test_disable_georeference_and_switch_back_to_local_does_not_fabricate_wgs84(config, tmp_path):
    async def scenario():
        cfg = copy.deepcopy(config)
        origin = {"latitude_deg": 25.01734, "longitude_deg": 121.53975, "height_m": 15.0, "rotation_deg": 25.0, "transform_id": "site-v1", "source": "measured"}
        cfg["georeference"] = origin
        cfg["devices"][0]["position_wgs84"] = _indep_local_to_wgs84(25.01734, 121.53975, 15.0, 25.0, 0.0, 0.0, 1.2)
        path = _write_site(tmp_path, cfg)

        app = create_app(load_config(path), tmp_path, mode="external", ingest_token="tok", config_path=path)
        async with TestClient(TestServer(app)) as client:
            boot = await (await client.get("/api/bootstrap")).json()
            headers = {"X-Control-Token": boot["control_token"]}
            got = await (await client.get("/api/settings", headers=headers)).json()
            assert got["settings"]["anchors"][0].get("computed_wgs84") is not None

            edited = _to_editable_payload(got["settings"])
            edited["georeference"] = None
            edited["anchors"] = [
                {"id": "A01", "position": [0.0, 0.0, 1.2]},
                {"id": "A02", "position": [12.0, 0.0, 1.2]},
                {"id": "A03", "position": [12.0, 9.0, 1.2]},
                {"id": "A04", "position": [0.0, 9.0, 1.2]},
            ]
            resp = await client.post("/api/settings", json={"expected_revision": got["revision"], "settings": edited}, headers=headers)
            assert resp.status == 200, await resp.text()
            body = await resp.json()
            assert body["state"]["site"]["georeference"] is None
            for dev in body["state"]["devices"]:
                if dev["role"] == "anchor":
                    assert dev["position"]["wgs84"] is None

            reloaded = await (await client.get("/api/settings", headers=headers)).json()
            assert reloaded["settings"]["georeference"] is None
            for row in reloaded["settings"]["anchors"]:
                assert "position_wgs84" not in row
                assert "computed_wgs84" not in row

            disk = json.loads(path.read_text(encoding="utf-8"))
            assert disk["georeference"] is None
            for dev in disk["devices"]:
                assert "position_wgs84" not in dev

    asyncio.run(scenario())


# --- 2. WGS84 with rotation (independent math reference) ---


@pytest.mark.parametrize("rotation_deg", [0.0, 25.0, 37.0, 90.0, -90.0, -135.0, 180.0])
def test_wgs84_anchors_with_rotation_match_independent_math(config, tmp_path, rotation_deg):
    async def scenario():
        path = _write_site(tmp_path, config)
        origin_lat, origin_lon, origin_h = 25.01734, 121.53975, 18.5
        expected_local = {
            "A01": [0.0, 0.0, 1.2],
            "A02": [12.5, 1.0, 1.5],
            "A03": [11.0, 9.5, 2.1],
            "A04": [-0.5, 8.0, 1.0],
        }
        wgs_inputs = {
            aid: _indep_local_to_wgs84(origin_lat, origin_lon, origin_h, rotation_deg, *xyz)
            for aid, xyz in expected_local.items()
        }

        app = create_app(config, tmp_path, mode="external", ingest_token="tok", config_path=path)
        async with TestClient(TestServer(app)) as client:
            boot = await (await client.get("/api/bootstrap")).json()
            headers = {"X-Control-Token": boot["control_token"]}
            got = await (await client.get("/api/settings", headers=headers)).json()
            edited = _to_editable_payload(got["settings"])
            edited["georeference"] = {
                "latitude_deg": origin_lat,
                "longitude_deg": origin_lon,
                "height_m": origin_h,
                "rotation_deg": rotation_deg,
                "transform_id": f"taipei-rot-{int(rotation_deg)}",
                "source": "measured",
            }
            edited["anchors"] = [{"id": aid, "position_wgs84": wgs_inputs[aid]} for aid in ("A01", "A02", "A03", "A04")]

            # Preview first and verify independent conversion without writing.
            prev_resp = await client.post("/api/settings/preview", json={"settings": edited}, headers=headers)
            assert prev_resp.status == 200, await prev_resp.text()
            prev = await prev_resp.json()
            for row in prev["settings"]["anchors"]:
                assert row["position"] == pytest.approx(expected_local[row["id"]], abs=1e-5)
                assert row["computed_wgs84"]["latitude_deg"] == pytest.approx(wgs_inputs[row["id"]]["latitude_deg"], abs=1e-9)
                assert row["computed_wgs84"]["longitude_deg"] == pytest.approx(wgs_inputs[row["id"]]["longitude_deg"], abs=1e-9)
                assert row["computed_wgs84"]["height_m"] == pytest.approx(wgs_inputs[row["id"]]["height_m"], abs=1e-4)

            # Save and verify persisted reload & live state.
            save_resp = await client.post(
                "/api/settings",
                json={"expected_revision": got["revision"], "settings": edited},
                headers=headers,
            )
            assert save_resp.status == 200, await save_resp.text()
            saved = await save_resp.json()
            assert saved["state"]["site"]["georeference"]["rotation_deg"] == rotation_deg
            for dev in saved["state"]["devices"]:
                if dev["role"] == "anchor":
                    aid = dev["id"]
                    assert [dev["position"]["x_m"], dev["position"]["y_m"], dev["position"]["z_m"]] == pytest.approx(expected_local[aid], abs=1e-5)
                    assert dev["position"]["wgs84"]["latitude_deg"] == pytest.approx(wgs_inputs[aid]["latitude_deg"], abs=1e-9)
                    assert dev["position"]["wgs84"]["longitude_deg"] == pytest.approx(wgs_inputs[aid]["longitude_deg"], abs=1e-9)

            reloaded_disk = load_config(path)
            for dev in reloaded_disk["devices"]:
                if dev["role"] == "anchor":
                    assert dev["position"] == pytest.approx(expected_local[dev["id"]], abs=1e-5)

    asyncio.run(scenario())


def test_wgs84_rotation_90_deg_direction_north_is_plus_x_west_is_plus_y(config):
    """Explicitly check rotation sign convention: +90 deg maps East->-Y, North->+X, West->+Y."""
    origin_lat, origin_lon, origin_h = 25.0, 121.5, 10.0
    # 10 m due North and 10 m due West from origin via independent 0-deg ENU helper:
    # At rot=0: x=E, y=N. So due North = (E=0, N=10), due West = (E=-10, N=0), due East = (E=10, N=0).
    p_origin = _indep_local_to_wgs84(origin_lat, origin_lon, origin_h, 0.0, 0.0, 0.0, 1.2)
    p_north = _indep_local_to_wgs84(origin_lat, origin_lon, origin_h, 0.0, 0.0, 10.0, 1.2)
    p_west = _indep_local_to_wgs84(origin_lat, origin_lon, origin_h, 0.0, -10.0, 0.0, 1.2)
    p_nw = _indep_local_to_wgs84(origin_lat, origin_lon, origin_h, 0.0, -10.0, 10.0, 1.2)

    settings = _to_editable_payload(editable_view(config))
    settings["georeference"] = {
        "latitude_deg": origin_lat,
        "longitude_deg": origin_lon,
        "height_m": origin_h,
        "rotation_deg": 90.0,
        "transform_id": "rot90-check",
        "source": "measured",
    }
    settings["anchors"] = [
        {"id": "A01", "position_wgs84": p_origin},
        {"id": "A02", "position_wgs84": p_north},
        {"id": "A03", "position_wgs84": p_nw},
        {"id": "A04", "position_wgs84": p_west},
    ]
    candidate, _ = prepare_edit(config, settings)
    by_id = {d["id"]: d["position"] for d in candidate["devices"] if d["role"] == "anchor"}
    assert by_id["A01"] == pytest.approx([0.0, 0.0, 1.2], abs=1e-5)
    assert by_id["A02"] == pytest.approx([10.0, 0.0, 1.2], abs=1e-5)  # North -> +X
    assert by_id["A04"] == pytest.approx([0.0, 10.0, 1.2], abs=1e-5)  # West -> +Y
    assert by_id["A03"] == pytest.approx([10.0, 10.0, 1.2], abs=1e-5)


def test_mixed_local_and_wgs84_anchors_save_and_reload(config, tmp_path):
    origin_lat, origin_lon, origin_h, rot = 25.01734, 121.53975, 20.0, 25.0
    settings = _to_editable_payload(editable_view(config))
    settings["georeference"] = {
        "latitude_deg": origin_lat,
        "longitude_deg": origin_lon,
        "height_m": origin_h,
        "rotation_deg": rot,
        "transform_id": "mixed-v1",
        "source": "measured",
    }
    wgs_a01 = _indep_local_to_wgs84(origin_lat, origin_lon, origin_h, rot, 0.0, 0.0, 1.2)
    wgs_a02 = _indep_local_to_wgs84(origin_lat, origin_lon, origin_h, rot, 12.0, 0.0, 1.4)
    expected_wgs_a03 = _indep_local_to_wgs84(origin_lat, origin_lon, origin_h, rot, 12.0, 9.0, 1.6)
    settings["anchors"] = [
        {"id": "A01", "position_wgs84": wgs_a01},
        {"id": "A02", "position_wgs84": wgs_a02},
        {"id": "A03", "position": [12.0, 9.0, 1.6]},
        {"id": "A04", "position": [0.0, 9.0, 1.2]},
    ]
    candidate, _ = prepare_edit(config, settings)
    path = _write_site(tmp_path, candidate)
    loaded = load_config(path)
    view = editable_view(loaded)
    by_id = {a["id"]: a for a in view["anchors"]}
    assert by_id["A01"]["position"] == pytest.approx([0.0, 0.0, 1.2], abs=1e-5)
    assert by_id["A02"]["position"] == pytest.approx([12.0, 0.0, 1.4], abs=1e-5)
    assert "position_wgs84" in by_id["A01"] and "position_wgs84" not in by_id["A03"]
    assert by_id["A03"]["computed_wgs84"]["latitude_deg"] == pytest.approx(expected_wgs_a03["latitude_deg"], abs=1e-9)
    assert by_id["A03"]["computed_wgs84"]["longitude_deg"] == pytest.approx(expected_wgs_a03["longitude_deg"], abs=1e-9)


# --- 3. Empty / NaN / Infinity / out-of-range / unauthorized inputs ---


def _mutate_invalid(settings, case):
    s = copy.deepcopy(settings)
    if case == "frame_id_empty":
        s["frame_id"] = ""
    elif case == "frame_id_spaces":
        s["frame_id"] = "   "
    elif case == "frame_id_illegal_char":
        s["frame_id"] = "../etc/passwd"
    elif case == "frame_id_too_long":
        s["frame_id"] = "x" * 65
    elif case == "status_empty":
        s["configuration_status"] = ""
    elif case == "status_invalid":
        s["configuration_status"] = "verified"
    elif case == "bounds_empty_str":
        s["bounds_m"][0] = ""
    elif case == "bounds_none":
        s["bounds_m"][2] = None
    elif case == "bounds_bool":
        s["bounds_m"][2] = True
    elif case == "bounds_nan":
        s["bounds_m"][1] = float("nan")
    elif case == "bounds_inf":
        s["bounds_m"][2] = float("inf")
    elif case == "bounds_neg_inf":
        s["bounds_m"][0] = float("-inf")
    elif case == "bounds_wrong_len":
        s["bounds_m"] = [0, 0, 12]
    elif case == "bounds_inverted_x":
        s["bounds_m"] = [12, 0, 0, 9]
    elif case == "bounds_inverted_y":
        s["bounds_m"] = [0, 9, 12, 0]
    elif case == "bounds_zero_height":
        s["bounds_m"] = [0, 5, 12, 5]
    elif case == "bounds_over_limit":
        s["bounds_m"] = [0, 0, 1_000_000.1, 9]
    elif case == "bounds_under_limit":
        s["bounds_m"] = [-1_000_000.1, 0, 12, 9]
    elif case == "scanner_height_empty":
        s["scanner_height_m"] = ""
    elif case == "scanner_height_nan":
        s["scanner_height_m"] = float("nan")
    elif case == "scanner_height_inf":
        s["scanner_height_m"] = float("inf")
    elif case == "scanner_height_bool":
        s["scanner_height_m"] = False
    elif case == "scanner_height_over_limit":
        s["scanner_height_m"] = 10000.1
    elif case == "scanner_height_under_limit":
        s["scanner_height_m"] = -10000.1
    elif case == "anchor_x_empty":
        s["anchors"][0]["position"][0] = ""
    elif case == "anchor_y_none":
        s["anchors"][0]["position"][1] = None
    elif case == "anchor_z_inf":
        s["anchors"][0]["position"][2] = float("inf")
    elif case == "anchor_x_over_limit":
        s["anchors"][0]["position"][0] = 1_000_001.0
    elif case == "anchor_pos_len_2":
        s["anchors"][0]["position"] = [0, 0]
    elif case == "anchor_both_local_and_wgs":
        s["georeference"] = {"latitude_deg": 25.0, "longitude_deg": 121.5, "height_m": 0.0, "rotation_deg": 0.0}
        s["anchors"][0]["position_wgs84"] = {"latitude_deg": 25.0, "longitude_deg": 121.5, "height_m": 1.2}
    elif case == "anchor_wgs_without_geo":
        s["georeference"] = None
        s["anchors"][0] = {"id": "A01", "position_wgs84": {"latitude_deg": 25.0, "longitude_deg": 121.5, "height_m": 1.2}}
    elif case == "anchor_wgs_lat_gt_90":
        s["georeference"] = {"latitude_deg": 25.0, "longitude_deg": 121.5, "height_m": 0.0, "rotation_deg": 0.0}
        s["anchors"][0] = {"id": "A01", "position_wgs84": {"latitude_deg": 90.001, "longitude_deg": 121.5, "height_m": 1.2}}
    elif case == "anchor_wgs_lat_lt_neg90":
        s["georeference"] = {"latitude_deg": 25.0, "longitude_deg": 121.5, "height_m": 0.0, "rotation_deg": 0.0}
        s["anchors"][0] = {"id": "A01", "position_wgs84": {"latitude_deg": -90.001, "longitude_deg": 121.5, "height_m": 1.2}}
    elif case == "anchor_wgs_lon_gt_180":
        s["georeference"] = {"latitude_deg": 25.0, "longitude_deg": 121.5, "height_m": 0.0, "rotation_deg": 0.0}
        s["anchors"][0] = {"id": "A01", "position_wgs84": {"latitude_deg": 25.0, "longitude_deg": 180.001, "height_m": 1.2}}
    elif case == "anchor_wgs_height_over_limit":
        s["georeference"] = {"latitude_deg": 25.0, "longitude_deg": 121.5, "height_m": 0.0, "rotation_deg": 0.0}
        s["anchors"][0] = {"id": "A01", "position_wgs84": {"latitude_deg": 25.0, "longitude_deg": 121.5, "height_m": 10001.0}}
    elif case == "anchor_wgs_nan":
        s["georeference"] = {"latitude_deg": 25.0, "longitude_deg": 121.5, "height_m": 0.0, "rotation_deg": 0.0}
        s["anchors"][0] = {"id": "A01", "position_wgs84": {"latitude_deg": float("nan"), "longitude_deg": 121.5, "height_m": 1.2}}
    elif case == "geo_lat_out_of_range":
        s["georeference"] = {"latitude_deg": 91.0, "longitude_deg": 121.5, "height_m": 0.0, "rotation_deg": 0.0}
    elif case == "geo_lon_out_of_range":
        s["georeference"] = {"latitude_deg": 25.0, "longitude_deg": -181.0, "height_m": 0.0, "rotation_deg": 0.0}
    elif case == "geo_rot_nan":
        s["georeference"] = {"latitude_deg": 25.0, "longitude_deg": 121.5, "height_m": 0.0, "rotation_deg": float("nan")}
    elif case == "geo_rot_over_limit":
        s["georeference"] = {"latitude_deg": 25.0, "longitude_deg": 121.5, "height_m": 0.0, "rotation_deg": 10000.1}
    elif case == "geo_height_over_limit":
        s["georeference"] = {"latitude_deg": 25.0, "longitude_deg": 121.5, "height_m": -10000.1, "rotation_deg": 0.0}
    elif case == "geo_missing_lat_lon":
        s["georeference"] = {}
    elif case == "geo_extra_field":
        s["georeference"] = {"latitude_deg": 25.0, "longitude_deg": 121.5, "evil": 1}
    elif case == "geo_empty_transform_id":
        s["georeference"] = {"latitude_deg": 25.0, "longitude_deg": 121.5, "transform_id": ""}
    elif case == "target_height_empty":
        s["targets"][0]["height_m"] = ""
    elif case == "target_height_nan":
        s["targets"][0]["height_m"] = float("nan")
    elif case == "target_height_over_limit":
        s["targets"][0]["height_m"] = 10001.0
    elif case == "target_extra_truth_field":
        s["targets"][0]["x_m"] = 3.0
    elif case == "anchor_duplicate_id":
        s["anchors"][1]["id"] = "A01"
    elif case == "anchor_missing_one":
        s["anchors"] = s["anchors"][:3]
    elif case == "anchor_extra_one":
        s["anchors"].append({"id": "A05", "position": [6.0, 4.5, 1.2]})
    elif case == "missing_whitelisted_field":
        s.pop("bounds_m")
    elif case == "extra_path_field":
        s["config_path"] = "/etc/passwd"
    else:
        raise AssertionError(f"Unhandled case: {case}")
    return s


INVALID_CASES = [
    "frame_id_empty",
    "frame_id_spaces",
    "frame_id_illegal_char",
    "frame_id_too_long",
    "status_empty",
    "status_invalid",
    "bounds_empty_str",
    "bounds_none",
    "bounds_bool",
    "bounds_nan",
    "bounds_inf",
    "bounds_neg_inf",
    "bounds_wrong_len",
    "bounds_inverted_x",
    "bounds_inverted_y",
    "bounds_zero_height",
    "bounds_over_limit",
    "bounds_under_limit",
    "scanner_height_empty",
    "scanner_height_nan",
    "scanner_height_inf",
    "scanner_height_bool",
    "scanner_height_over_limit",
    "scanner_height_under_limit",
    "anchor_x_empty",
    "anchor_y_none",
    "anchor_z_inf",
    "anchor_x_over_limit",
    "anchor_pos_len_2",
    "anchor_both_local_and_wgs",
    "anchor_wgs_without_geo",
    "anchor_wgs_lat_gt_90",
    "anchor_wgs_lat_lt_neg90",
    "anchor_wgs_lon_gt_180",
    "anchor_wgs_height_over_limit",
    "anchor_wgs_nan",
    "geo_lat_out_of_range",
    "geo_lon_out_of_range",
    "geo_rot_nan",
    "geo_rot_over_limit",
    "geo_height_over_limit",
    "geo_missing_lat_lon",
    "geo_extra_field",
    "geo_empty_transform_id",
    "target_height_empty",
    "target_height_nan",
    "target_height_over_limit",
    "target_extra_truth_field",
    "anchor_duplicate_id",
    "anchor_missing_one",
    "anchor_extra_one",
    "missing_whitelisted_field",
    "extra_path_field",
]


@pytest.mark.parametrize("case", INVALID_CASES)
def test_invalid_inputs_rejected_by_prepare_edit(config, case):
    base = _to_editable_payload(editable_view(config))
    mutated = _mutate_invalid(base, case)
    with pytest.raises((ValueError, TypeError)):
        prepare_edit(config, mutated)


def test_http_raw_nan_infinity_and_malformed_json_rejected_without_write(config, tmp_path):
    async def scenario():
        path = _write_site(tmp_path, config)
        initial = path.read_bytes()
        app = create_app(config, tmp_path, mode="external", ingest_token="tok", config_path=path)
        async with TestClient(TestServer(app)) as client:
            boot = await (await client.get("/api/bootstrap")).json()
            headers = {"X-Control-Token": boot["control_token"], "Content-Type": "application/json"}
            got = await (await client.get("/api/settings", headers=headers)).json()
            before_run = (await (await client.get("/api/state")).json())["run_id"]
            base = _to_editable_payload(got["settings"])

            # Literal NaN and Infinity in raw HTTP body (non-standard JSON that Python json.loads accepts).
            for token in ("NaN", "Infinity", "-Infinity"):
                raw_payload = json.dumps({"expected_revision": got["revision"], "settings": base}).replace('"scanner_height_m": 1.2', f'"scanner_height_m": {token}')
                assert token in raw_payload
                r_save = await client.post("/api/settings", data=raw_payload, headers=headers)
                assert r_save.status == 400
                raw_prev = json.dumps({"settings": base}).replace('"scanner_height_m": 1.2', f'"scanner_height_m": {token}')
                r_prev = await client.post("/api/settings/preview", data=raw_prev, headers=headers)
                assert r_prev.status == 400

            # Malformed JSON & wrong top-level envelopes.
            assert (await client.post("/api/settings", data="{broken", headers=headers)).status == 400
            assert (await client.post("/api/settings", json={"settings": base}, headers=headers)).status == 400
            assert (await client.post("/api/settings", json={"settings": base, "expected_revision": got["revision"], "extra": 1}, headers=headers)).status == 400
            assert (await client.post("/api/settings/preview", json={"settings": base, "expected_revision": got["revision"]}, headers=headers)).status == 400

            assert path.read_bytes() == initial
            assert (await (await client.get("/api/state")).json())["run_id"] == before_run
            assert not (tmp_path / "config" / "private" / "settings-backups").exists()

    asyncio.run(scenario())


# --- 4. Collinear & ill-conditioned Anchor geometry ---


@pytest.mark.parametrize(
    "label,coords",
    [
        ("horizontal_line", [[0, 0, 1.2], [4, 0, 1.2], [8, 0, 1.2], [12, 0, 1.2]]),
        ("vertical_line", [[3, 0, 1.2], [3, 3, 1.2], [3, 6, 1.2], [3, 9, 1.2]]),
        ("diagonal_line", [[0, 0, 1.2], [3, 3, 1.2], [6, 6, 1.2], [9, 9, 1.2]]),
        ("coincident_points", [[5, 5, 1.2], [5, 5, 1.2], [5, 5, 1.2], [5, 5, 1.2]]),
        ("ill_conditioned_ratio_200", [[0, 0, 1.2], [100, 0, 1.2], [100, 0.5, 1.2], [0, 0.5, 1.2]]),
    ],
)
def test_collinear_and_ill_conditioned_local_anchors_rejected(config, label, coords):
    settings = _to_editable_payload(editable_view(config))
    for row, pos in zip(settings["anchors"], coords):
        row["position"] = pos
    with pytest.raises(ValueError, match="共線或幾何條件不良"):
        prepare_edit(config, settings)


def test_collinear_wgs84_anchors_rejected_and_valid_thin_rectangle_accepted(config):
    origin_lat, origin_lon, origin_h, rot = 25.01734, 121.53975, 15.0, 37.0
    settings = _to_editable_payload(editable_view(config))
    settings["georeference"] = {
        "latitude_deg": origin_lat,
        "longitude_deg": origin_lon,
        "height_m": origin_h,
        "rotation_deg": rot,
        "transform_id": "collinear-wgs",
        "source": "measured",
    }
    # 4 points along a single diagonal line in Local -> collinear in WGS84 as well.
    settings["anchors"] = [
        {"id": f"A0{i+1}", "position_wgs84": _indep_local_to_wgs84(origin_lat, origin_lon, origin_h, rot, i * 4.0, i * 2.0, 1.2)}
        for i in range(4)
    ]
    with pytest.raises(ValueError, match="共線或幾何條件不良"):
        prepare_edit(config, settings)

    # Valid non-collinear thin rectangle (aspect ratio 10 < 100) should succeed.
    good = _to_editable_payload(editable_view(config))
    for row, pos in zip(good["anchors"], [[0, 0, 1.2], [10, 0, 1.2], [10, 1, 1.2], [0, 1, 1.2]]):
        row["position"] = pos
    candidate, _ = prepare_edit(config, good)
    assert candidate["devices"][2]["position"] == [10, 1, 1.2]


# --- 5. Stale revision & two-page conflict (sequential, concurrent, external) ---


def test_stale_revision_and_two_page_sequential_conflict(config, tmp_path):
    async def scenario():
        path = _write_site(tmp_path, config)
        initial = path.read_bytes()
        app = create_app(config, tmp_path, mode="external", ingest_token="tok", config_path=path)
        async with TestClient(TestServer(app)) as client:
            boot = await (await client.get("/api/bootstrap")).json()
            headers = {"X-Control-Token": boot["control_token"]}

            # Stale/fake revision rejected before writing or creating backup/run.
            page_a = await (await client.get("/api/settings", headers=headers)).json()
            page_b = await (await client.get("/api/settings", headers=headers)).json()
            assert page_a["revision"] == page_b["revision"]
            run_0 = (await (await client.get("/api/state")).json())["run_id"]

            for bad_rev in ("0" * 64, "", None):
                r_bad = await client.post(
                    "/api/settings",
                    json={"expected_revision": bad_rev, "settings": _to_editable_payload(page_a["settings"])},
                    headers=headers,
                )
                assert r_bad.status == 409
            assert path.read_bytes() == initial
            assert (await (await client.get("/api/state")).json())["run_id"] == run_0
            assert not (tmp_path / "config" / "private" / "settings-backups").exists()

            # Page A edits A01 and saves successfully.
            edit_a = _to_editable_payload(page_a["settings"])
            edit_a["anchors"][0]["position"] = [1.5, 0.25, 1.2]
            resp_a = await client.post(
                "/api/settings",
                json={"expected_revision": page_a["revision"], "settings": edit_a},
                headers=headers,
            )
            assert resp_a.status == 200
            saved_a = await resp_a.json()
            run_1 = saved_a["state"]["run_id"]
            assert run_1 != run_0
            bytes_after_a = path.read_bytes()

            # Page B edits A02 using stale revision_0 -> preview succeeds (read-only), save returns 409!
            edit_b = _to_editable_payload(page_b["settings"])
            edit_b["anchors"][1]["position"] = [10.5, 0.0, 1.2]
            assert (await client.post("/api/settings/preview", json={"settings": edit_b}, headers=headers)).status == 200
            resp_b = await client.post(
                "/api/settings",
                json={"expected_revision": page_b["revision"], "settings": edit_b},
                headers=headers,
            )
            assert resp_b.status == 409
            assert path.read_bytes() == bytes_after_a
            assert (await (await client.get("/api/state")).json())["run_id"] == run_1
            assert len(list((tmp_path / "config" / "private" / "settings-backups").glob("*.json"))) == 1

            # Page B reloads fresh revision, merges A02 change, and saves cleanly.
            page_b_reloaded = await (await client.get("/api/settings", headers=headers)).json()
            assert page_b_reloaded["revision"] == saved_a["revision"]
            assert page_b_reloaded["settings"]["anchors"][0]["position"] == [1.5, 0.25, 1.2]
            merged = _to_editable_payload(page_b_reloaded["settings"])
            merged["anchors"][1]["position"] = [10.5, 0.0, 1.2]
            resp_b2 = await client.post(
                "/api/settings",
                json={"expected_revision": page_b_reloaded["revision"], "settings": merged},
                headers=headers,
            )
            assert resp_b2.status == 200
            final_cfg = load_config(path)
            assert final_cfg["devices"][0]["position"] == [1.5, 0.25, 1.2]
            assert final_cfg["devices"][1]["position"] == [10.5, 0.0, 1.2]

    asyncio.run(scenario())


def test_two_page_simultaneous_concurrent_save_race(config, tmp_path):
    async def scenario():
        path = _write_site(tmp_path, config)
        app = create_app(config, tmp_path, mode="external", ingest_token="tok", config_path=path)
        async with TestClient(TestServer(app)) as client:
            boot = await (await client.get("/api/bootstrap")).json()
            headers = {"X-Control-Token": boot["control_token"]}
            initial = await (await client.get("/api/settings", headers=headers)).json()

            edit_a = _to_editable_payload(initial["settings"])
            edit_a["anchors"][0]["position"][0] = 2.0
            edit_b = _to_editable_payload(initial["settings"])
            edit_b["anchors"][0]["position"][0] = 3.0

            res_a, res_b = await asyncio.gather(
                client.post("/api/settings", json={"expected_revision": initial["revision"], "settings": edit_a}, headers=headers),
                client.post("/api/settings", json={"expected_revision": initial["revision"], "settings": edit_b}, headers=headers),
            )
            statuses = sorted([res_a.status, res_b.status])
            assert statuses == [200, 409]
            winner_x = 2.0 if res_a.status == 200 else 3.0
            assert load_config(path)["devices"][0]["position"][0] == winner_x
            assert len(list((tmp_path / "config" / "private" / "settings-backups").glob("*.json"))) == 1

    asyncio.run(scenario())


def test_external_disk_edit_and_roster_change_return_409(config, tmp_path):
    async def scenario():
        path = _write_site(tmp_path, config)
        app = create_app(config, tmp_path, mode="external", ingest_token="tok", config_path=path)
        async with TestClient(TestServer(app)) as client:
            boot = await (await client.get("/api/bootstrap")).json()
            headers = {"X-Control-Token": boot["control_token"]}
            got = await (await client.get("/api/settings", headers=headers)).json()
            run_0 = (await (await client.get("/api/state")).json())["run_id"]

            # Case 1: External edit mutates file content (different revision).
            ext = copy.deepcopy(config)
            ext["frame_id"] = "edited-externally"
            path.write_text(json.dumps(ext), encoding="utf-8")
            r1 = await client.post(
                "/api/settings",
                json={"expected_revision": got["revision"], "settings": _to_editable_payload(got["settings"])},
                headers=headers,
            )
            assert r1.status == 409

            # Case 2: External edit changes device roster even if client fetches the new revision.
            ext_roster = copy.deepcopy(config)
            ext_roster["devices"][0]["id"] = "A99"
            path.write_text(json.dumps(ext_roster), encoding="utf-8")
            rev_roster = hashlib.sha256(path.read_bytes()).hexdigest()
            r2 = await client.post(
                "/api/settings",
                json={"expected_revision": rev_roster, "settings": _to_editable_payload(got["settings"])},
                headers=headers,
            )
            assert r2.status == 409
            assert "重新啟動服務" in await r2.text()
            assert (await (await client.get("/api/state")).json())["run_id"] == run_0

    asyncio.run(scenario())


# --- 6. Cancel & preview never write files or create runs ---


def test_preview_and_read_only_open_never_modify_filesystem_or_run(config, tmp_path):
    async def scenario():
        path = _write_site(tmp_path, config)
        app = create_app(config, tmp_path, mode="external", ingest_token="tok", config_path=path)
        async with TestClient(TestServer(app)) as client:
            boot = await (await client.get("/api/bootstrap")).json()
            headers = {"X-Control-Token": boot["control_token"]}
            before_state = await (await client.get("/api/state")).json()
            before_tree = _snapshot_tree(tmp_path / "config")
            before_raw_runs = sorted(p.name for p in (tmp_path / "data" / "raw").iterdir())
            before_proc_runs = sorted(p.name for p in (tmp_path / "data" / "processed").iterdir())

            # Simulate open + cancel (GET only) + valid Local preview + valid WGS84 preview + invalid preview.
            got = await (await client.get("/api/settings", headers=headers)).json()

            valid_local = _to_editable_payload(got["settings"])
            valid_local["frame_id"] = "preview-only-frame"
            valid_local["anchors"][0]["position"] = [1.0, 1.0, 1.5]
            assert (await client.post("/api/settings/preview", json={"settings": valid_local}, headers=headers)).status == 200

            valid_wgs = _to_editable_payload(got["settings"])
            valid_wgs["georeference"] = {"latitude_deg": 25.0, "longitude_deg": 121.5, "height_m": 10.0, "rotation_deg": 45.0, "transform_id": "p1", "source": "measured"}
            valid_wgs["anchors"][0] = {"id": "A01", "position_wgs84": _indep_local_to_wgs84(25.0, 121.5, 10.0, 45.0, 1.0, 2.0, 1.2)}
            assert (await client.post("/api/settings/preview", json={"settings": valid_wgs}, headers=headers)).status == 200

            invalid_collinear = _to_editable_payload(got["settings"])
            for i, row in enumerate(invalid_collinear["anchors"]):
                row["position"] = [i * 2.0, 0.0, 1.2]
            assert (await client.post("/api/settings/preview", json={"settings": invalid_collinear}, headers=headers)).status == 400

            assert _snapshot_tree(tmp_path / "config") == before_tree
            assert sorted(p.name for p in (tmp_path / "data" / "raw").iterdir()) == before_raw_runs
            assert sorted(p.name for p in (tmp_path / "data" / "processed").iterdir()) == before_proc_runs
            after_state = await (await client.get("/api/state")).json()
            assert after_state["run_id"] == before_state["run_id"]
            assert after_state["site"]["frame_id"] == config["frame_id"]

    asyncio.run(scenario())


# --- 7. Save failure does not switch active task or corrupt config ---


def test_save_failure_mid_atomic_replace_preserves_old_run_and_cleans_tempfiles(config, tmp_path, monkeypatch):
    async def scenario():
        path = _write_site(tmp_path, config)
        initial_bytes = path.read_bytes()
        app = create_app(config, tmp_path, mode="external", ingest_token="tok", config_path=path)
        async with TestClient(TestServer(app)) as client:
            boot = await (await client.get("/api/bootstrap")).json()
            headers = {"X-Control-Token": boot["control_token"]}

            # Ingest an observation in the active run so we can prove continuity after failed save.
            source = SyntheticSource(config, seed=77, noise_db=0.1)
            batch1, _ = source.sample()
            assert (await client.post("/api/observations", json=batch1, headers={"Authorization": "Bearer tok"})).status == 200
            before = await (await client.get("/api/state")).json()
            assert before["counts"]["inventoried"] == 2

            got = await (await client.get("/api/settings", headers=headers)).json()
            edited = _to_editable_payload(got["settings"])
            edited["frame_id"] = "should-not-apply"
            edited["anchors"][0]["position"] = [2.25, 0.5, 1.2]

            # Fail specifically at os.replace inside persist_edit to test temp-file cleanup & rollback.
            from ble_inventory import site_settings

            def fail_replace(src, dst):
                raise OSError("simulated atomic replace failure")

            monkeypatch.setattr(site_settings.os, "replace", fail_replace)

            resp = await client.post(
                "/api/settings",
                json={"expected_revision": got["revision"], "settings": edited},
                headers=headers,
            )
            assert resp.status == 507
            assert "原設定繼續使用" in await resp.text()

            # Disk config untouched & no leftover .site-* temp files.
            assert path.read_bytes() == initial_bytes
            assert list((tmp_path / "config").glob(".site-*")) == []

            # Active run & coordinates did NOT switch; aborted prepared run is marked with aborted.txt.
            after = await (await client.get("/api/state")).json()
            assert after["run_id"] == before["run_id"]
            assert after["counts"]["inventoried"] == 2
            assert after["site"]["frame_id"] == config["frame_id"]
            assert after["site"]["devices"][0]["position"] == [0, 0, 1.2]

            aborted_markers = list((tmp_path / "data" / "raw").glob("*/aborted.txt"))
            assert len(aborted_markers) == 1
            assert aborted_markers[0].parent.name != before["run_id"]

            # Original run continues accepting new observations normally.
            batch2, _ = source.sample()
            r_obs2 = await client.post("/api/observations", json=batch2, headers={"Authorization": "Bearer tok"})
            assert r_obs2.status == 200 and (await r_obs2.json())["accepted"] is True

    asyncio.run(scenario())


def test_save_validation_failure_does_not_switch_run_or_create_backup(config, tmp_path):
    async def scenario():
        path = _write_site(tmp_path, config)
        initial_bytes = path.read_bytes()
        app = create_app(config, tmp_path, mode="external", ingest_token="tok", config_path=path)
        async with TestClient(TestServer(app)) as client:
            boot = await (await client.get("/api/bootstrap")).json()
            headers = {"X-Control-Token": boot["control_token"]}
            before_run = (await (await client.get("/api/state")).json())["run_id"]
            got = await (await client.get("/api/settings", headers=headers)).json()

            bad = _to_editable_payload(got["settings"])
            for i, row in enumerate(bad["anchors"]):
                row["position"] = [float(i), 0.0, 1.2]  # collinear

            resp = await client.post(
                "/api/settings",
                json={"expected_revision": got["revision"], "settings": bad},
                headers=headers,
            )
            assert resp.status == 400
            assert path.read_bytes() == initial_bytes
            assert (await (await client.get("/api/state")).json())["run_id"] == before_run
            assert list((tmp_path / "data" / "raw").iterdir()) == [tmp_path / "data" / "raw" / before_run]
            assert not (tmp_path / "config" / "private" / "settings-backups").exists()

    asyncio.run(scenario())


# --- 8. Public read-only, auth/Origin, and path boundary checks ---


def test_settings_endpoints_enforce_token_origin_and_config_path_boundary(config, tmp_path):
    # Config file outside root/config must be rejected at app creation.
    outside = tmp_path / "outside.json"
    outside.write_text(json.dumps(config), encoding="utf-8")
    with pytest.raises(ValueError, match="root/config"):
        create_app(config, tmp_path, mode="external", config_path=outside)

    async def scenario():
        path = _write_site(tmp_path, config)
        app = create_app(config, tmp_path, mode="external", ingest_token="tok", config_path=path)
        async with TestClient(TestServer(app)) as client:
            boot = await (await client.get("/api/bootstrap")).json()
            token = boot["control_token"]
            same_origin = f"http://{client.host}:{client.port}"
            good_headers = {"X-Control-Token": token, "Origin": same_origin}

            got = await (await client.get("/api/settings", headers=good_headers)).json()
            payload = _to_editable_payload(got["settings"])

            # Missing token, wrong token, and cross-origin rejected on ALL 3 settings endpoints.
            bad_header_sets = [
                {},
                {"X-Control-Token": "wrong-token"},
                {"X-Control-Token": token, "Origin": "https://kaiy860123.github.io"},
                {"X-Control-Token": token, "Origin": "http://127.0.0.1:9999"},
            ]
            for bad_headers in bad_header_sets:
                assert (await client.get("/api/settings", headers=bad_headers)).status == 403
                assert (await client.post("/api/settings/preview", json={"settings": payload}, headers=bad_headers)).status == 403
                assert (
                    await client.post(
                        "/api/settings",
                        json={"expected_revision": got["revision"], "settings": payload},
                        headers=bad_headers,
                    )
                ).status == 403

            # Same-origin with valid token works.
            assert (await client.post("/api/settings/preview", json={"settings": payload}, headers=good_headers)).status == 200

        # Without config_path, all 3 settings endpoints return 404 and bootstrap marks settings_editable=False.
        readonly_app = create_app(config, tmp_path, mode="external", ingest_token="tok", config_path=None)
        async with TestClient(TestServer(readonly_app)) as client_ro:
            boot_ro = await (await client_ro.get("/api/bootstrap")).json()
            assert boot_ro["settings_editable"] is False
            h_ro = {"X-Control-Token": boot_ro["control_token"]}
            assert (await client_ro.get("/api/settings", headers=h_ro)).status == 404
            assert (await client_ro.post("/api/settings/preview", json={"settings": payload}, headers=h_ro)).status == 404
            assert (
                await client_ro.post("/api/settings", json={"expected_revision": "x", "settings": payload}, headers=h_ro)
            ).status == 404

    asyncio.run(scenario())


def test_public_static_html_starts_settings_disabled_and_aws_template_has_no_write_policy():
    repo_root = Path(__file__).resolve().parents[1]
    html = (repo_root / "web" / "index.html").read_text(encoding="utf-8")
    assert re.search(r'<button[^>]*id="settings-button"[^>]*disabled', html)

    js = (repo_root / "web" / "site-settings.js").read_text(encoding="utf-8")
    assert "mode!=='local'||!bootstrap?.settings_editable" in js

    aws_tpl = json.loads((repo_root / "infra" / "aws" / "template.json").read_text(encoding="utf-8"))
    viewer_policy = json.dumps(aws_tpl["Resources"]["ViewerIoTPolicy"])
    assert "iot:Publish" not in viewer_policy
    assert "iot:UpdateThingShadow" not in viewer_policy
