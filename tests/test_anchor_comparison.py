"""Independent synthetic unit tests for scripts/compare-anchor-subsets.py (AG-005).

All fixtures generated here are purely synthetic mathematical geometry data
(``source == "simulation"``) and MUST NEVER be presented as physical BLE or
Gazebo measurements.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import math
from pathlib import Path
from typing import Any

import pytest

from ble_inventory.contracts import BATCH_KEYS
from ble_inventory.engine import InventoryEngine

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "compare-anchor-subsets.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("compare_anchor_subsets", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MOD = _load_module()


def test_output_hardlink_alias_cannot_overwrite_input(tmp_path):
    source = tmp_path / 'raw.jsonl'
    source.write_text('original measurements\n', encoding='utf-8')
    alias = tmp_path / 'comparison.json'
    alias.hardlink_to(source)
    with pytest.raises(ValueError, match='overwrite'):
        MOD._ensure_output_not_input(alias, (source,))
    assert source.read_text(encoding='utf-8') == 'original measurements\n'

# Independent synthetic 6-anchor room geometry (6 m x 6 m, z = 1.0 m).
SYNTHETIC_ANCHORS: dict[str, list[float]] = {
    "A01": [0.0, 0.0, 1.0],
    "A02": [6.0, 0.0, 1.0],
    "A03": [6.0, 6.0, 1.0],
    "A04": [0.0, 6.0, 1.0],
    "A05": [3.0, 0.0, 1.0],
    "A06": [3.0, 6.0, 1.0],
}

SYNTHETIC_TARGETS: dict[str, list[float]] = {
    "T01": [2.5, 3.2, 1.0],
    "T02": [3.8, 2.6, 1.0],
}

# 12 well-spaced curved synthetic waypoints (consecutive step >= 1.1 m;
# first 6 points span 4.0 m x 3.2 m with condition number ~2.6).
SYNTHETIC_WAYPOINTS: list[tuple[float, float]] = [
    (1.0, 1.0),
    (2.2, 1.0),
    (3.4, 1.2),
    (4.6, 1.8),
    (5.0, 3.0),
    (4.6, 4.2),
    (3.4, 4.8),
    (2.2, 4.8),
    (1.2, 4.2),
    (1.0, 3.0),
    (1.4, 2.0),
    (2.6, 1.8),
]


def _independent_rssi(distance_m: float, rssi_at_1m_dbm: float = -59.0, path_loss_exponent: float = 2.0) -> float:
    """Pure log-distance forward model (independent of ble_inventory.positioning)."""
    return rssi_at_1m_dbm - 10.0 * path_loss_exponent * math.log10(distance_m)


def _make_six_anchor_config(
    *,
    filter_alpha: float = 1.0,
    median_window: int = 1,
    anchor_ttl_s: float = 3.0,
    stale_after_s: float = 10.0,
    max_residual_m: float = 2.5,
    include_private_cloud: bool = False,
) -> dict[str, Any]:
    cfg: dict[str, Any] = {
        "schema_version": "1.0",
        "site_id": "synthetic-six-anchor-unit",
        "label": "Synthetic 6-anchor test site (not physical)",
        "configuration_status": "synthetic-test",
        "frame_id": "room-local",
        "bounds_m": [0.0, 0.0, 6.0, 6.0],
        "scanner_id": "RPi01",
        "scanner_height_m": 1.0,
        "path_loss_exponent": 2.0,
        "rssi_at_1m_dbm": -59.0,
        "filter_alpha": filter_alpha,
        "median_window": median_window,
        "anchor_ttl_s": anchor_ttl_s,
        "stale_after_s": stale_after_s,
        "publish_interval_s": 1.0,
        "target_window_s": 120.0,
        "target_min_samples": 6,
        "target_min_baseline_m": 1.5,
        "max_residual_m": max_residual_m,
        "georeference": None,
        "devices": [
            {"id": aid, "role": "anchor", "position": list(pos)}
            for aid, pos in SYNTHETIC_ANCHORS.items()
        ]
        + [
            {"id": tid, "role": "target", "height_m": pos[2]}
            for tid, pos in SYNTHETIC_TARGETS.items()
        ],
    }
    if include_private_cloud:
        cfg["cloud"] = {
            "enabled": True,
            "endpoint": "secret-iot-endpoint.example.invalid",
            "region": "ap-southeast-2",
            "topic": "ble-inventory/private/state",
            "client_id": "rpi-secret-client",
            "cert_path": "/etc/ble-inventory/certs/device.pem.crt",
            "key_path": "/etc/ble-inventory/certs/private.pem.key",
            "ca_path": "/etc/ble-inventory/certs/AmazonRootCA1.pem",
        }
    return cfg


def _build_synthetic_batch(
    *,
    timestamp: float,
    sequence: int,
    scanner_xyz: tuple[float, float, float],
    anchor_ids: tuple[str, ...] = ("A01", "A02", "A03", "A04", "A05", "A06"),
    target_ids: tuple[str, ...] = ("T01", "T02"),
    range_overrides: dict[str, float] | None = None,
    source: str = "simulation",
    scanner_id: str = "RPi01",
) -> dict[str, Any]:
    overrides = range_overrides or {}
    observations: list[dict[str, Any]] = []
    for aid in anchor_ids:
        dist = overrides.get(aid, math.dist(scanner_xyz, SYNTHETIC_ANCHORS[aid]))
        observations.append(
            {
                "device_id": aid,
                "rssi_dbm": _independent_rssi(dist),
                "rssi_at_1m_dbm": -59.0,
            }
        )
    for tid in target_ids:
        dist = overrides.get(tid, math.dist(scanner_xyz, SYNTHETIC_TARGETS[tid]))
        observations.append(
            {
                "device_id": tid,
                "rssi_dbm": _independent_rssi(dist),
                "rssi_at_1m_dbm": -59.0,
            }
        )
    return {
        "schema_version": "1.0",
        "timestamp": timestamp,
        "source": source,
        "scanner_id": scanner_id,
        "sequence": sequence,
        "scanner_height_m": scanner_xyz[2],
        "observations": observations,
    }


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")


def test_synthetic_independent_geometry_and_hand_calculated_errors(tmp_path):
    """Independent synthetic geometry recovers exact positions and matches hand-calculated horizontal errors."""
    cfg = _make_six_anchor_config()
    cfg_path = tmp_path / "site.json"
    cfg_path.write_text(json.dumps(cfg), encoding="utf-8")

    # Part 1: 12-batch exact noise-free synthetic trajectory.
    batches: list[dict[str, Any]] = []
    truth_rows: list[dict[str, Any]] = []
    for idx, (x, y) in enumerate(SYNTHETIC_WAYPOINTS):
        ts = 1700000000.0 + idx
        batches.append(_build_synthetic_batch(timestamp=ts, sequence=idx, scanner_xyz=(x, y, 1.0)))
        truth_rows.append(
            {
                "timestamp": ts,
                "scanner": [x, y, 1.0],
                "targets": {tid: list(pos) for tid, pos in SYNTHETIC_TARGETS.items()},
            }
        )
    obs_path = tmp_path / "obs_exact.jsonl"
    truth_path = tmp_path / "truth_exact.jsonl"
    _write_jsonl(obs_path, batches)
    _write_jsonl(truth_path, truth_rows)

    result = MOD.compare_anchor_subsets(obs_path, cfg_path, truth_path=truth_path)

    assert result["schema_version"] == "1.0"
    assert result["source"] == "simulation"
    assert result["input_batches"] == 12
    assert result["truth_provided"] is True
    assert result["truth_used_by_solver"] is False
    assert result["formal_success_rate"] is None
    assert result["observations_sha256"] == hashlib.sha256(obs_path.read_bytes()).hexdigest()
    assert result["config_sha256"] == hashlib.sha256(cfg_path.read_bytes()).hexdigest()
    assert result["truth_sha256"] == hashlib.sha256(truth_path.read_bytes()).hexdigest()
    assert result["anchor_subsets"] == {
        "baseline": ["A01", "A02", "A03", "A04"],
        "expanded": ["A01", "A02", "A03", "A04", "A05", "A06"],
        "added_anchors": ["A05", "A06"],
    }
    assert any("simulation" in note and "physical" in note for note in result["limitations"])

    for group_name in ("baseline", "expanded"):
        group = result["groups"][group_name]
        assert group["skipped_unmatched_truth"] == 0
        assert group["devices"]["RPi01"]["valid_positions"] == 12
        assert group["devices"]["RPi01"]["formal_success_rate"] is None
        assert group["devices"]["RPi01"]["error_metrics"]["samples"] == 12
        assert group["devices"]["RPi01"]["error_metrics"]["rmse_m"] == pytest.approx(0.0, abs=1e-4)
        for tid in ("T01", "T02"):
            assert group["devices"][tid]["valid_positions"] == 7
            assert group["devices"][tid]["error_metrics"]["samples"] == 7
            assert group["devices"][tid]["error_metrics"]["rmse_m"] == pytest.approx(0.0, abs=1e-3)

    # Part 2: Hand-calculated known horizontal errors [1.0, 3.0, 5.0, 7.0] with large Z offset ignored.
    known_batches: list[dict[str, Any]] = []
    known_truth: list[dict[str, Any]] = []
    # Exact horizontal offsets with norms 1.0, 3.0, 5.0 (3-4-5 triangle), and 7.0; huge Z offset (+50.0 m).
    offsets = [(1.0, 0.0), (0.0, 3.0), (3.0, 4.0), (0.0, 7.0)]
    for idx, (dx, dy) in enumerate(offsets):
        ts = 1700001000.0 + idx
        sx, sy = SYNTHETIC_WAYPOINTS[idx]
        known_batches.append(_build_synthetic_batch(timestamp=ts, sequence=idx, scanner_xyz=(sx, sy, 1.0)))
        known_truth.append(
            {
                "timestamp": ts,
                "scanner": [sx + dx, sy + dy, 51.0],
                "targets": {},
            }
        )

    hand = MOD.compare_anchor_subsets_data(known_batches, cfg, truth_rows=known_truth)
    for group_name in ("baseline", "expanded"):
        metrics = hand["groups"][group_name]["devices"]["RPi01"]["error_metrics"]
        assert metrics["samples"] == 4
        assert metrics["mae_m"] == pytest.approx(4.0, abs=1e-4)
        assert metrics["rmse_m"] == pytest.approx(math.sqrt(21.0), abs=1e-4)
        assert metrics["p50_m"] == pytest.approx(4.0, abs=1e-4)
        assert metrics["p95_m"] == pytest.approx(6.7, abs=1e-4)

    common_rpi = hand["common_valid"]["RPi01"]
    assert common_rpi["common_valid_positions"] == 4
    assert common_rpi["matched_samples"] == 4
    assert common_rpi["baseline_rmse_m"] == pytest.approx(math.sqrt(21.0), abs=1e-4)
    assert common_rpi["expanded_rmse_m"] == pytest.approx(math.sqrt(21.0), abs=1e-4)


def test_baseline_and_expanded_use_different_anchors_but_identical_targets(monkeypatch):
    """Both engines use deep-copied configs with distinct anchor subsets and identical Target/batch inputs."""
    recorded_runs: list[dict[str, Any]] = []

    class RecordingEngine(InventoryEngine):
        def __init__(self, config):
            self._record = {"config": config, "batches": []}
            recorded_runs.append(self._record)
            super().__init__(config)

        def ingest(self, batch):
            self._record["batches"].append(batch)
            return super().ingest(batch)

    monkeypatch.setattr(MOD, "InventoryEngine", RecordingEngine)

    cfg = _make_six_anchor_config(filter_alpha=0.65, median_window=3)
    batches = [
        _build_synthetic_batch(timestamp=1700002000.0 + i, sequence=i, scanner_xyz=(x, y, 1.0))
        for i, (x, y) in enumerate(SYNTHETIC_WAYPOINTS[:8])
    ]

    MOD.compare_anchor_subsets_data(batches, cfg)

    assert len(recorded_runs) == 2
    baseline_rec, expanded_rec = recorded_runs

    # Independent deep-copied configs (not sharing dict references).
    assert baseline_rec["config"] is not expanded_rec["config"]
    assert baseline_rec["config"] is not cfg
    assert expanded_rec["config"] is not cfg

    b_anchors = [d["id"] for d in baseline_rec["config"]["devices"] if d["role"] == "anchor"]
    e_anchors = [d["id"] for d in expanded_rec["config"]["devices"] if d["role"] == "anchor"]
    assert b_anchors == ["A01", "A02", "A03", "A04"]
    assert e_anchors == ["A01", "A02", "A03", "A04", "A05", "A06"]

    b_targets = [d for d in baseline_rec["config"]["devices"] if d["role"] == "target"]
    e_targets = [d for d in expanded_rec["config"]["devices"] if d["role"] == "target"]
    assert b_targets == e_targets

    # Identical model, height, filter, and threshold parameters.
    for key in (
        "scanner_id",
        "scanner_height_m",
        "path_loss_exponent",
        "rssi_at_1m_dbm",
        "filter_alpha",
        "median_window",
        "anchor_ttl_s",
        "stale_after_s",
        "target_window_s",
        "target_min_samples",
        "target_min_baseline_m",
        "max_residual_m",
        "bounds_m",
    ):
        assert baseline_rec["config"][key] == expanded_rec["config"][key]

    # Verify per-batch anchor filtering and identical target observations/metadata.
    assert len(baseline_rec["batches"]) == len(expanded_rec["batches"]) == len(batches)
    for b_batch, e_batch in zip(baseline_rec["batches"], expanded_rec["batches"]):
        for meta_key in ("schema_version", "timestamp", "source", "scanner_id", "sequence", "scanner_height_m"):
            assert b_batch[meta_key] == e_batch[meta_key]

        b_anchor_obs = {o["device_id"] for o in b_batch["observations"] if o["device_id"].startswith("A")}
        e_anchor_obs = {o["device_id"] for o in e_batch["observations"] if o["device_id"].startswith("A")}
        assert b_anchor_obs == {"A01", "A02", "A03", "A04"}
        assert e_anchor_obs == {"A01", "A02", "A03", "A04", "A05", "A06"}

        b_target_obs = [o for o in b_batch["observations"] if o["device_id"].startswith("T")]
        e_target_obs = [o for o in e_batch["observations"] if o["device_id"].startswith("T")]
        assert b_target_obs == e_target_obs
        assert {o["device_id"] for o in b_target_obs} == {"T01", "T02"}


def test_cold_start_reproducibility_and_no_private_config_leak(tmp_path):
    """Repeated runs produce bit-identical results and never leak private cloud config or paths."""
    cfg = _make_six_anchor_config(filter_alpha=0.65, median_window=3, include_private_cloud=True)
    cfg_path = tmp_path / "site_private.json"
    cfg_path.write_text(json.dumps(cfg), encoding="utf-8")

    batches = [
        _build_synthetic_batch(timestamp=1700003000.0 + i, sequence=i, scanner_xyz=(x, y, 1.0))
        for i, (x, y) in enumerate(SYNTHETIC_WAYPOINTS)
    ]
    truth = [
        {
            "timestamp": 1700003000.0 + i,
            "scanner": [x, y, 1.0],
            "targets": {tid: list(pos) for tid, pos in SYNTHETIC_TARGETS.items()},
        }
        for i, (x, y) in enumerate(SYNTHETIC_WAYPOINTS)
    ]
    obs_path = tmp_path / "obs.jsonl"
    truth_path = tmp_path / "truth.jsonl"
    _write_jsonl(obs_path, batches)
    _write_jsonl(truth_path, truth)

    run_one = MOD.compare_anchor_subsets(obs_path, cfg_path, truth_path=truth_path)
    run_two = MOD.compare_anchor_subsets(obs_path, cfg_path, truth_path=truth_path)
    assert run_one == run_two

    serialized = json.dumps(run_one, ensure_ascii=False)
    for forbidden in (
        "secret-iot-endpoint.example.invalid",
        "device.pem.crt",
        "private.pem.key",
        "AmazonRootCA1.pem",
        "rpi-secret-client",
        "cert_path",
        "key_path",
        "ca_path",
        str(tmp_path),
    ):
        assert forbidden not in serialized


def test_cached_position_deduplication_counts_only_new_valid_position_at():
    """Cached valid positions retained while a target is absent must never be double-counted."""
    cfg = _make_six_anchor_config(filter_alpha=1.0, median_window=1, stale_after_s=10.0)
    batches: list[dict[str, Any]] = []
    truth: list[dict[str, Any]] = []

    for idx, (x, y) in enumerate(SYNTHETIC_WAYPOINTS[:10]):
        ts = 1700004000.0 + idx
        # Batches 0..7 observe both T01 and T02 (valid at idx 5, 6, 7 -> 3 unique position_at).
        # Batches 8..9 omit T01 while still within stale_after_s=10 s, so snapshot keeps T01
        # quality="valid" with cached position_at=1700004007.0 for 2 extra snapshots.
        targets = ("T01", "T02") if idx <= 7 else ("T02",)
        batches.append(
            _build_synthetic_batch(timestamp=ts, sequence=idx, scanner_xyz=(x, y, 1.0), target_ids=targets)
        )
        truth.append(
            {
                "timestamp": ts,
                "scanner": [x, y, 1.0],
                "targets": {tid: list(pos) for tid, pos in SYNTHETIC_TARGETS.items()},
            }
        )

    result = MOD.compare_anchor_subsets_data(batches, cfg, truth_rows=truth)
    for group_name in ("baseline", "expanded"):
        devices = result["groups"][group_name]["devices"]
        assert devices["RPi01"]["valid_positions"] == 10
        assert devices["RPi01"]["duplicate_valid_positions_ignored"] == 0

        assert devices["T01"]["valid_positions"] == 3
        assert devices["T01"]["duplicate_valid_positions_ignored"] == 2
        assert devices["T01"]["error_metrics"]["samples"] == 3

        assert devices["T02"]["valid_positions"] == 5
        assert devices["T02"]["duplicate_valid_positions_ignored"] == 0
        assert devices["T02"]["error_metrics"]["samples"] == 5


def test_common_valid_vs_own_valid_samples_and_anchor_difference():
    """Separately reports each group's own valid samples vs. shared valid timestamps and RMSEs."""
    # anchor_ttl_s=0.5 with 1.0 s batch spacing isolates each batch's anchor observations cleanly.
    cfg = _make_six_anchor_config(filter_alpha=1.0, median_window=1, anchor_ttl_s=0.5, max_residual_m=2.5)
    center = (3.0, 3.0, 1.0)
    a01_true_dist = math.dist(center, SYNTHETIC_ANCHORS["A01"])

    batches = [
        # t=1000: Only A01, A02, A05, A06 observed -> baseline has 2 anchors (invalid), expanded has 4 (valid).
        _build_synthetic_batch(
            timestamp=1700005000.0,
            sequence=0,
            scanner_xyz=center,
            anchor_ids=("A01", "A02", "A05", "A06"),
        ),
        # t=1001: All 6 exact -> both valid with ~0 error.
        _build_synthetic_batch(
            timestamp=1700005001.0,
            sequence=1,
            scanner_xyz=center,
        ),
        # t=1002: All 6 with +1.0 m range perturbation on A01 -> both valid, expanded error < baseline error.
        _build_synthetic_batch(
            timestamp=1700005002.0,
            sequence=2,
            scanner_xyz=center,
            range_overrides={"A01": a01_true_dist + 1.0},
        ),
        # t=1003: All 6 with 25.0 m outlier on A05 -> baseline valid (ignores A05), expanded rejected (> max_residual_m).
        _build_synthetic_batch(
            timestamp=1700005003.0,
            sequence=3,
            scanner_xyz=center,
            range_overrides={"A05": 25.0},
        ),
    ]
    truth = [
        # Truth offset 2.0 m at t=1000 (only in expanded own set).
        {"timestamp": 1700005000.0, "scanner": [5.0, 3.0, 1.0], "targets": {}},
        # Exact truth at common timestamps t=1001, t=1002.
        {"timestamp": 1700005001.0, "scanner": [3.0, 3.0, 1.0], "targets": {}},
        {"timestamp": 1700005002.0, "scanner": [3.0, 3.0, 1.0], "targets": {}},
        # Truth offset 3.0 m at t=1003 (only in baseline own set).
        {"timestamp": 1700005003.0, "scanner": [3.0, 6.0, 1.0], "targets": {}},
    ]

    result = MOD.compare_anchor_subsets_data(batches, cfg, truth_rows=truth)

    b_rpi = result["groups"]["baseline"]["devices"]["RPi01"]
    e_rpi = result["groups"]["expanded"]["devices"]["RPi01"]
    c_rpi = result["common_valid"]["RPi01"]

    # Own valid sets: baseline={1001,1002,1003}, expanded={1000,1001,1002}; common={1001,1002}.
    assert b_rpi["valid_positions"] == 3
    assert b_rpi["error_metrics"]["samples"] == 3
    assert e_rpi["valid_positions"] == 3
    assert e_rpi["error_metrics"]["samples"] == 3
    assert c_rpi["common_valid_positions"] == 2
    assert c_rpi["matched_samples"] == 2

    # Own RMSE includes the non-overlapping timestamps (3.0 m / 2.0 m offsets), so own RMSE > common RMSE.
    assert b_rpi["error_metrics"]["rmse_m"] > c_rpi["baseline_rmse_m"] + 1.0
    assert e_rpi["error_metrics"]["rmse_m"] > c_rpi["expanded_rmse_m"] + 0.5

    # On shared valid timestamps {1001, 1002}, 6-anchor resists A01 perturbation better than 4-anchor.
    assert c_rpi["expanded_rmse_m"] < c_rpi["baseline_rmse_m"]
    assert c_rpi["rmse_delta_m"] == pytest.approx(c_rpi["expanded_rmse_m"] - c_rpi["baseline_rmse_m"])
    assert c_rpi["rmse_delta_m"] < 0


def test_without_truth_and_target_only_truth():
    """Handles missing truth (all error metrics null) and target-only truth (no RPi error)."""
    cfg = _make_six_anchor_config()
    batches = [
        _build_synthetic_batch(timestamp=1700006000.0 + i, sequence=i, scanner_xyz=(x, y, 1.0))
        for i, (x, y) in enumerate(SYNTHETIC_WAYPOINTS)
    ]

    # Case 1: No truth provided at all.
    no_truth = MOD.compare_anchor_subsets_data(batches, cfg, truth_rows=None)
    assert no_truth["truth_provided"] is False
    assert no_truth["truth_sha256"] is None
    assert no_truth["formal_success_rate"] is None
    for group_name in ("baseline", "expanded"):
        assert no_truth["groups"][group_name]["skipped_unmatched_truth"] is None
        for dev_id, expected_valid in (("RPi01", 12), ("T01", 7), ("T02", 7)):
            dev = no_truth["groups"][group_name]["devices"][dev_id]
            assert dev["valid_positions"] == expected_valid
            assert dev["error_metrics"] is None
            assert dev["formal_success_rate"] is None
    for dev_id, expected_common in (("RPi01", 12), ("T01", 7), ("T02", 7)):
        c = no_truth["common_valid"][dev_id]
        assert c["common_valid_positions"] == expected_common
        assert c["matched_samples"] is None
        assert c["baseline_rmse_m"] is None
        assert c["expanded_rmse_m"] is None

    # Case 2: Target-only truth (scanner truth absent / null, like moving patrol without RPi trajectory truth).
    target_only_truth = [
        {
            "timestamp": 1700006000.0 + i,
            "scanner": None,
            "targets": {tid: list(pos) for tid, pos in SYNTHETIC_TARGETS.items()},
        }
        for i in range(len(SYNTHETIC_WAYPOINTS))
    ]
    target_only = MOD.compare_anchor_subsets_data(batches, cfg, truth_rows=target_only_truth)
    assert target_only["truth_provided"] is True
    for group_name in ("baseline", "expanded"):
        devs = target_only["groups"][group_name]["devices"]
        assert devs["RPi01"]["valid_positions"] == 12
        assert devs["RPi01"]["error_metrics"] is None
        assert devs["T01"]["error_metrics"]["samples"] == 7
        assert devs["T02"]["error_metrics"]["samples"] == 7
    assert target_only["common_valid"]["RPi01"]["common_valid_positions"] == 12
    assert target_only["common_valid"]["RPi01"]["matched_samples"] == 0
    assert target_only["common_valid"]["RPi01"]["baseline_rmse_m"] is None
    assert target_only["common_valid"]["RPi01"]["expanded_rmse_m"] is None
    assert target_only["common_valid"]["T01"]["matched_samples"] == 7
    assert target_only["common_valid"]["T02"]["matched_samples"] == 7

    # Case 3: Truth timestamp tolerance respected (0.5 s shift unmatched at 0.25 s, matched at 0.6 s).
    shifted_truth = [
        {"timestamp": 1700006000.5 + i, "scanner": [x, y, 1.0], "targets": {}}
        for i, (x, y) in enumerate(SYNTHETIC_WAYPOINTS)
    ]
    strict_tol = MOD.compare_anchor_subsets_data(batches, cfg, truth_rows=shifted_truth, max_time_delta_s=0.25)
    assert strict_tol["groups"]["baseline"]["devices"]["RPi01"]["error_metrics"] is None
    assert strict_tol["groups"]["baseline"]["skipped_unmatched_truth"] > 0

    loose_tol = MOD.compare_anchor_subsets_data(batches, cfg, truth_rows=shifted_truth, max_time_delta_s=0.6)
    assert loose_tol["groups"]["baseline"]["devices"]["RPi01"]["error_metrics"]["samples"] == 12


def test_rejects_missing_expanded_anchors_and_invalid_subsets():
    """Explicitly rejects 4-anchor-only data labeled as 6-anchor, and rejects invalid subset definitions."""
    cfg = _make_six_anchor_config()

    # Raw data containing ONLY A01-A04 (no A05/A06).
    four_anchor_batches = [
        _build_synthetic_batch(
            timestamp=1700007000.0 + i,
            sequence=i,
            scanner_xyz=(x, y, 1.0),
            anchor_ids=("A01", "A02", "A03", "A04"),
        )
        for i, (x, y) in enumerate(SYNTHETIC_WAYPOINTS[:4])
    ]
    with pytest.raises(ValueError, match="A05.*A06"):
        MOD.compare_anchor_subsets_data(four_anchor_batches, cfg)

    # Raw data missing only A06.
    five_anchor_batches = [
        _build_synthetic_batch(
            timestamp=1700007100.0 + i,
            sequence=i,
            scanner_xyz=(x, y, 1.0),
            anchor_ids=("A01", "A02", "A03", "A04", "A05"),
        )
        for i, (x, y) in enumerate(SYNTHETIC_WAYPOINTS[:4])
    ]
    with pytest.raises(ValueError, match="A06"):
        MOD.compare_anchor_subsets_data(five_anchor_batches, cfg)

    full_batches = [
        _build_synthetic_batch(timestamp=1700007200.0 + i, sequence=i, scanner_xyz=(x, y, 1.0))
        for i, (x, y) in enumerate(SYNTHETIC_WAYPOINTS[:4])
    ]

    # Baseline fewer than 3 anchors.
    with pytest.raises(ValueError, match="at least 3"):
        MOD.compare_anchor_subsets_data(full_batches, cfg, baseline_anchors="A01,A02")

    # Baseline equal to expanded (not a strict subset).
    with pytest.raises(ValueError, match="strict"):
        MOD.compare_anchor_subsets_data(
            full_batches,
            cfg,
            baseline_anchors="A01,A02,A03,A04",
            expanded_anchors="A01,A02,A03,A04",
        )

    # Baseline not a subset of expanded.
    with pytest.raises(ValueError, match="subset"):
        MOD.compare_anchor_subsets_data(
            full_batches,
            cfg,
            baseline_anchors="A01,A02,A03,A06",
            expanded_anchors="A01,A02,A03,A04,A05",
        )

    # Duplicate anchor IDs.
    with pytest.raises(ValueError, match="Duplicate"):
        MOD.compare_anchor_subsets_data(full_batches, cfg, baseline_anchors="A01,A01,A02,A03")

    # Target ID passed as anchor.
    with pytest.raises(ValueError, match="role='anchor'"):
        MOD.compare_anchor_subsets_data(
            full_batches,
            cfg,
            baseline_anchors="A01,A02,A03",
            expanded_anchors="A01,A02,A03,T01",
        )

    # Anchor ID absent from config.
    with pytest.raises(ValueError, match="not found in site config"):
        MOD.compare_anchor_subsets_data(
            full_batches,
            cfg,
            baseline_anchors="A01,A02,A03,A04",
            expanded_anchors="A01,A02,A03,A04,A05,A09",
        )


def test_rejects_empty_mixed_duplicate_out_of_order_and_invalid_raw_before_filtering(tmp_path):
    """Validates complete raw batches BEFORE filtering and rejects empty/mixed/duplicate/out-of-order streams."""
    cfg = _make_six_anchor_config()
    cfg_path = tmp_path / "site.json"
    cfg_path.write_text(json.dumps(cfg), encoding="utf-8")

    # Empty observations file.
    empty_obs = tmp_path / "empty.jsonl"
    empty_obs.write_text("\n   \n", encoding="utf-8")
    with pytest.raises(ValueError, match="empty"):
        MOD.compare_anchor_subsets(empty_obs, cfg_path)

    b0 = _build_synthetic_batch(timestamp=1700008000.0, sequence=0, scanner_xyz=(2.0, 2.0, 1.0))
    b1 = _build_synthetic_batch(timestamp=1700008001.0, sequence=1, scanner_xyz=(3.0, 2.0, 1.0))

    # Mixed source.
    b1_phys = {**b1, "source": "physical"}
    with pytest.raises(ValueError, match="Mixed observation sources"):
        MOD.compare_anchor_subsets_data([b0, b1_phys], cfg)

    # Mixed scanner_id.
    b1_other_scanner = {**b1, "scanner_id": "RPi02"}
    with pytest.raises(ValueError, match="Mixed scanner_id"):
        MOD.compare_anchor_subsets_data([b0, b1_other_scanner], cfg)

    # Scanner_id mismatch with config.
    b0_wrong_scanner = {**b0, "scanner_id": "RPi99"}
    with pytest.raises(ValueError, match="does not match config scanner_id"):
        MOD.compare_anchor_subsets_data([b0_wrong_scanner], cfg)

    # Duplicate sequence.
    b1_dup_seq = {**b1, "sequence": 0}
    with pytest.raises(ValueError, match="Duplicate or out-of-order sequence"):
        MOD.compare_anchor_subsets_data([b0, b1_dup_seq], cfg)

    # Out-of-order sequence.
    b0_seq2 = {**b0, "sequence": 2}
    with pytest.raises(ValueError, match="Duplicate or out-of-order sequence"):
        MOD.compare_anchor_subsets_data([b0_seq2, b1], cfg)

    # Out-of-order timestamp.
    b1_back_ts = {**b1, "timestamp": 1700007999.0}
    with pytest.raises(ValueError, match="Out-of-order timestamp"):
        MOD.compare_anchor_subsets_data([b0, b1_back_ts], cfg)

    # Corrupt observation on A05 (which baseline would filter out) MUST still be rejected before filtering.
    corrupt_obs = [dict(o) for o in b0["observations"]]
    for item in corrupt_obs:
        if item["device_id"] == "A05":
            item["rssi_dbm"] = 999.0
    b0_corrupt_a05 = {**b0, "observations": corrupt_obs}
    with pytest.raises(ValueError, match="Invalid rssi_dbm"):
        MOD.compare_anchor_subsets_data([b0_corrupt_a05, b1], cfg)

    # Duplicate device_id on A06 in raw batch MUST be rejected before filtering.
    dup_a06_obs = list(b0["observations"]) + [{"device_id": "A06", "rssi_dbm": -70.0}]
    b0_dup_a06 = {**b0, "observations": dup_a06_obs}
    with pytest.raises(ValueError, match="Duplicate device"):
        MOD.compare_anchor_subsets_data([b0_dup_a06, b1], cfg)

    # Invalid max_time_delta_s.
    with pytest.raises(ValueError, match="max_time_delta_s"):
        MOD.compare_anchor_subsets_data([b0, b1], cfg, max_time_delta_s=-0.1)


def test_truth_never_enters_solver_and_embedded_truth_rejected(monkeypatch):
    """Embedded truth in observation batches is rejected, and offline truth never reaches InventoryEngine."""
    cfg = _make_six_anchor_config()
    batches = [
        _build_synthetic_batch(timestamp=1700009000.0 + i, sequence=i, scanner_xyz=(x, y, 1.0))
        for i, (x, y) in enumerate(SYNTHETIC_WAYPOINTS[:8])
    ]

    # Embedded truth in raw batch is strictly rejected.
    bad_batch = {**batches[0], "scanner_position": [1.0, 2.0]}
    with pytest.raises(ValueError, match="truth"):
        MOD.compare_anchor_subsets_data([bad_batch, *batches[1:]], cfg)

    ingested_batches: list[dict[str, Any]] = []

    class GuardEngine(InventoryEngine):
        def ingest(self, batch):
            assert set(batch.keys()) <= BATCH_KEYS
            assert "truth" not in batch and "scanner" not in batch and "targets" not in batch
            ingested_batches.append(batch)
            return super().ingest(batch)

    monkeypatch.setattr(MOD, "InventoryEngine", GuardEngine)

    truth_rows = [
        {
            "timestamp": 1700009000.0 + i,
            "scanner": [x + 5.0, y + 5.0, 1.0],
            "targets": {tid: [pos[0] + 10.0, pos[1] + 10.0, 1.0] for tid, pos in SYNTHETIC_TARGETS.items()},
        }
        for i, (x, y) in enumerate(SYNTHETIC_WAYPOINTS[:8])
    ]

    res_no_truth = MOD.compare_anchor_subsets_data(batches, cfg, truth_rows=None)
    count_without_truth = len(ingested_batches)
    res_with_truth = MOD.compare_anchor_subsets_data(batches, cfg, truth_rows=truth_rows)

    assert count_without_truth == 2 * len(batches)
    assert len(ingested_batches) == 4 * len(batches)
    assert res_with_truth["truth_used_by_solver"] is False

    # Valid position counts must be identical whether truth is supplied or omitted.
    for group_name in ("baseline", "expanded"):
        for dev_id in ("RPi01", "T01", "T02"):
            assert (
                res_no_truth["groups"][group_name]["devices"][dev_id]["valid_positions"]
                == res_with_truth["groups"][group_name]["devices"][dev_id]["valid_positions"]
            )


def test_cli_end_to_end_and_input_overwrite_guard(tmp_path, capsys):
    """CLI parses arguments, writes JSON output without modifying inputs, and blocks input overwrites."""
    cfg = _make_six_anchor_config()
    cfg_path = tmp_path / "site.json"
    obs_path = tmp_path / "obs.jsonl"
    truth_path = tmp_path / "truth.jsonl"
    out_path = tmp_path / "comparison.json"

    cfg_path.write_text(json.dumps(cfg), encoding="utf-8")
    batches = [
        _build_synthetic_batch(timestamp=1700010000.0 + i, sequence=i, scanner_xyz=(x, y, 1.0))
        for i, (x, y) in enumerate(SYNTHETIC_WAYPOINTS[:8])
    ]
    truth = [
        {
            "timestamp": 1700010000.0 + i,
            "scanner": [x, y, 1.0],
            "targets": {tid: list(pos) for tid, pos in SYNTHETIC_TARGETS.items()},
        }
        for i, (x, y) in enumerate(SYNTHETIC_WAYPOINTS[:8])
    ]
    _write_jsonl(obs_path, batches)
    _write_jsonl(truth_path, truth)

    obs_before = obs_path.read_bytes()
    cfg_before = cfg_path.read_bytes()
    truth_before = truth_path.read_bytes()

    rc = MOD.main(
        [
            str(obs_path),
            str(cfg_path),
            "--baseline-anchors",
            "A01,A02,A03,A04",
            "--expanded-anchors",
            "A01,A02,A03,A04,A05,A06",
            "--truth",
            str(truth_path),
            "--max-time-delta-s",
            "0.25",
            "--output",
            str(out_path),
            "--version",
            "synthetic-unit-sha",
        ]
    )
    assert rc == 0
    stdout_payload = json.loads(capsys.readouterr().out)
    file_payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert stdout_payload == file_payload
    assert file_payload["version"] == "synthetic-unit-sha"
    assert file_payload["formal_success_rate"] is None
    assert obs_path.read_bytes() == obs_before
    assert cfg_path.read_bytes() == cfg_before
    assert truth_path.read_bytes() == truth_before

    # Attempting to overwrite any input file is strictly rejected.
    for target_input in (obs_path, cfg_path, truth_path):
        with pytest.raises(ValueError, match="overwrite"):
            MOD.main([str(obs_path), str(cfg_path), "--truth", str(truth_path), "--output", str(target_input)])
    assert obs_path.read_bytes() == obs_before
    assert cfg_path.read_bytes() == cfg_before
    assert truth_path.read_bytes() == truth_before
