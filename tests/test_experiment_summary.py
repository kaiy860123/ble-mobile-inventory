"""Independent unit tests for scripts/summarize-experiments.py (AG-003).

Covers:
- Hand-calculated evaluation JSON + metadata aggregation.
- Hand-calculated offline state-vs-truth evaluation with duplicate old positions,
  stale/insufficient frames, missing position_at guard, and unmatched timestamps.
- Zero denominators, zero samples, and missing metadata/metrics (未提供 vs 不適用).
- Inventory recall set intersection |S_R ∩ G_R| / |G_R| and anchor exclusion.
- Unmeasured latency guard (never defaulting to 1 s / publish_interval_s).
- Mixed sources (within-run and cross-run), source conflicts, and multiple versions.
- Strict truth separation (rejecting truth_used_by_solver=True and embedded truth keys).
- Read-only verification against repo synthetic fixture and experiments-template.csv.
- CLI execution and CSV formula injection protection.
"""
from __future__ import annotations

import csv
import importlib.util
import io
import json
import math
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "summarize-experiments.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("summarize_experiments", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MOD = _load_module()


def _make_frame(
    *,
    timestamp: float,
    run_id: str = "hand-calc-001",
    source: str = "simulation",
    scanner: dict,
    devices: list[dict],
) -> dict:
    return {
        "schema_version": "1.0",
        "timestamp": timestamp,
        "run_id": run_id,
        "source": source,
        "active": True,
        "scanner": scanner,
        "devices": devices,
        "site": {"publish_interval_s": 1.0},
    }


def test_hand_calculated_evaluation_json_and_metadata(tmp_path):
    """Primary mode: existing evaluate-run.py JSON + explicit metadata with hand-checked math."""
    eval_payload = {
        "schema_version": "1.0",
        "sources": ["simulation"],
        "metric": "horizontal position error in meters",
        "truth_used_by_solver": False,
        "skipped_unmatched": 2,
        "devices": {
            "RPi01": {"samples": 90, "mae_m": 1.043, "rmse_m": 1.106, "p50_m": 1.029, "p95_m": 1.734},
            "T01": {"samples": 85, "mae_m": 0.464, "rmse_m": 0.802, "p50_m": 0.305, "p95_m": 1.809},
            "T02": {"samples": 65, "mae_m": 0.220, "rmse_m": 0.349, "p50_m": 0.116, "p95_m": 1.029},
        },
    }
    eval_file = tmp_path / "eval_syn.json"
    eval_file.write_text(json.dumps(eval_payload), encoding="utf-8")

    summary = MOD.summarize_experiments(
        [
            {
                "experiment_id": "EXP-SYN-5047",
                "source": "synthetic",
                "site": "indoor-demo",
                "route": "90s synthetic loop",
                "version": "9225d6be262071ab8ad31d6fb1f8b76526a5b04e",
                "run_id": "synthetic-example-5047",
                "scanner_id": "RPi01",
                "scheduled_eval_points": {"RPi01": 90, "T01": 90, "T02": 65},
                "expected_targets": ["T01", "T02"],
                "inventoried_targets": ["T01", "T02"],
                "evaluation_path": "eval_syn.json",
                "limitations": "固定種子合成資料，非 Gazebo 或實機",
            }
        ],
        base_dir=tmp_path,
    )

    assert summary["truth_used_by_solver"] is False
    assert summary["comparison_flags"] == {
        "distinct_sources": ["synthetic"],
        "has_mixed_sources": False,
        "distinct_versions": ["9225d6be262071ab8ad31d6fb1f8b76526a5b04e"],
        "has_multiple_versions": False,
        "distinct_run_ids": ["synthetic-example-5047"],
    }
    assert summary["warnings"] == []

    by_dev = {row["device_id"]: row for row in summary["rows"]}
    assert set(by_dev) == {"RPi01", "T01", "T02"}

    assert by_dev["RPi01"]["device_role"] == "scanner"
    assert by_dev["RPi01"]["valid_samples"] == 90
    assert by_dev["RPi01"]["scheduled_eval_points"] == 90
    assert by_dev["RPi01"]["localization_success_rate"] == pytest.approx(1.0)
    assert by_dev["RPi01"]["mae_m"] == pytest.approx(1.043)
    assert by_dev["RPi01"]["rmse_m"] == pytest.approx(1.106)
    assert by_dev["RPi01"]["p50_m"] == pytest.approx(1.029)
    assert by_dev["RPi01"]["p95_m"] == pytest.approx(1.734)
    assert by_dev["RPi01"]["inventory_recall"] == pytest.approx(1.0)
    assert by_dev["RPi01"]["end_to_end_latency_ms"] == MOD.NOT_PROVIDED
    assert by_dev["RPi01"]["skipped_unmatched"] == 2
    assert by_dev["RPi01"]["evaluation_file"] == "eval_syn.json"

    assert by_dev["T01"]["device_role"] == "target"
    assert by_dev["T01"]["localization_success_rate"] == pytest.approx(85.0 / 90.0)
    assert by_dev["T02"]["localization_success_rate"] == pytest.approx(1.0)


def test_hand_calculated_states_and_separate_truth_no_duplicate_positions():
    """Hand-calculated offline evaluation verifying exact deduplication of repeated old positions."""
    truth = [
        {"timestamp": 1000.0, "scanner": [0.0, 0.0, 1.2], "targets": {"T01": [10.0, 0.0, 1.2], "T02": [0.0, 10.0, 1.2]}},
        {"timestamp": 1001.0, "scanner": [1.0, 0.0, 1.2], "targets": {"T01": [10.0, 0.0, 1.2], "T02": [0.0, 10.0, 1.2]}},
        {"timestamp": 1002.0, "scanner": [2.0, 0.0, 1.2], "targets": {"T01": [10.0, 0.0, 1.2], "T02": [0.0, 10.0, 1.2]}},
        {"timestamp": 1003.0, "scanner": [3.0, 0.0, 1.2], "targets": {"T01": [10.0, 0.0, 1.2], "T02": [0.0, 10.0, 1.2]}},
    ]

    states = [
        # Frame 0: RPi01 err=5.0, T01 err=1.0, A01 anchor ignored, T02 unseen
        _make_frame(
            timestamp=1000.0,
            scanner={"id": "RPi01", "quality": "valid", "position": {"x_m": 3.0, "y_m": 4.0}, "position_at": 1000.0},
            devices=[
                {"id": "A01", "role": "anchor", "quality": "fixed", "position": {"x_m": 0.0, "y_m": 0.0}, "position_at": None, "last_seen": 1000.0},
                {"id": "T01", "role": "target", "quality": "valid", "position": {"x_m": 10.0, "y_m": 1.0}, "position_at": 1000.0, "last_seen": 1000.0},
                {"id": "T02", "role": "target", "quality": "unseen", "position": None, "position_at": None},
            ],
        ),
        # Frame 1: Duplicate old position_at=1000.0 for RPi01 and T01 -> MUST NOT be double-counted
        _make_frame(
            timestamp=1000.5,
            scanner={"id": "RPi01", "quality": "valid", "position": {"x_m": 3.0, "y_m": 4.0}, "position_at": 1000.0},
            devices=[
                {"id": "T01", "role": "target", "quality": "valid", "position": {"x_m": 10.0, "y_m": 1.0}, "position_at": 1000.0, "last_seen": 1000.0},
                {"id": "T02", "role": "target", "quality": "unseen", "position": None, "position_at": None},
            ],
        ),
        # Frame 2: RPi01 err=1.0, T01 err=5.0, T02 observed (enters S_R) but insufficient position
        _make_frame(
            timestamp=1001.0,
            scanner={"id": "RPi01", "quality": "valid", "position": {"x_m": 1.0, "y_m": 1.0}, "position_at": 1001.0},
            devices=[
                {"id": "T01", "role": "target", "quality": "valid", "position": {"x_m": 13.0, "y_m": 4.0}, "position_at": 1001.0, "last_seen": 1001.0},
                {"id": "T02", "role": "target", "quality": "insufficient", "position": None, "position_at": None, "last_seen": 1001.0},
            ],
        ),
        # Frame 3: RPi01 err=3.0, T01 stale holding old position (ignored), T02 stale (still in S_R)
        _make_frame(
            timestamp=1002.0,
            scanner={"id": "RPi01", "quality": "valid", "position": {"x_m": 2.0, "y_m": 3.0}, "position_at": 1002.0},
            devices=[
                {"id": "T01", "role": "target", "quality": "stale", "position": {"x_m": 13.0, "y_m": 4.0}, "position_at": 1001.0, "last_seen": 1001.0},
                {"id": "T02", "role": "target", "quality": "stale", "position": None, "position_at": None, "last_seen": 1001.0},
            ],
        ),
        # Frame 4: RPi01 err=7.0, T01 err=3.0, T02 valid with position_at=None (defensive skip, no crash)
        _make_frame(
            timestamp=1003.0,
            scanner={"id": "RPi01", "quality": "valid", "position": {"x_m": 3.0, "y_m": 7.0}, "position_at": 1003.0},
            devices=[
                {"id": "T01", "role": "target", "quality": "valid", "position": {"x_m": 10.0, "y_m": 3.0}, "position_at": 1003.0, "last_seen": 1003.0},
                {"id": "T02", "role": "target", "quality": "valid", "position": {"x_m": 0.0, "y_m": 10.0}, "position_at": None, "last_seen": 1003.0},
            ],
        ),
        # Frame 5: Unmatched timestamp (> 0.25 s away from truth)
        _make_frame(
            timestamp=1010.0,
            scanner={"id": "RPi01", "quality": "valid", "position": {"x_m": 99.0, "y_m": 99.0}, "position_at": 1010.0},
            devices=[],
        ),
    ]

    eval_out = MOD.evaluate_states_against_truth(states, truth, max_time_delta_s=0.25)
    assert eval_out["truth_used_by_solver"] is False
    assert eval_out["duplicate_positions_ignored"] == 2
    assert eval_out["invalid_position_at_skipped"] == 1
    assert eval_out["skipped_unmatched"] == 1

    # Hand-checked RPi01 errors: [1.0, 3.0, 5.0, 7.0]
    rpi = eval_out["devices"]["RPi01"]
    assert rpi["samples"] == 4
    assert rpi["mae_m"] == pytest.approx(4.0)
    assert rpi["rmse_m"] == pytest.approx(math.sqrt(21.0))
    assert rpi["p50_m"] == pytest.approx(4.0)
    assert rpi["p95_m"] == pytest.approx(6.7)

    # Hand-checked T01 errors: [1.0, 3.0, 5.0]
    t01 = eval_out["devices"]["T01"]
    assert t01["samples"] == 3
    assert t01["mae_m"] == pytest.approx(3.0)
    assert t01["rmse_m"] == pytest.approx(math.sqrt(35.0 / 3.0))
    assert t01["p50_m"] == pytest.approx(3.0)
    assert t01["p95_m"] == pytest.approx(4.8)

    # Anchor A01 and invalid-timestamp T02 must not appear in evaluated devices.
    assert "A01" not in eval_out["devices"]
    assert "T02" not in eval_out["devices"]

    # Summarize end-to-end with states + separate truth, extracting S_R automatically.
    summary = MOD.summarize_experiments(
        [
            {
                "experiment_id": "EXP-HAND-001",
                "source": "synthetic",
                "site": "lab-grid",
                "route": "4-step line",
                "version": "abc1234",
                "scheduled_eval_points": {"RPi01": 5, "T01": 4, "T02": 4},
                "expected_targets": ["T01", "T02", "T03"],
                "states": states,
                "truth": truth,
            }
        ]
    )
    rows = {r["device_id"]: r for r in summary["rows"]}
    assert set(rows) == {"RPi01", "T01", "T02"}
    assert rows["RPi01"]["run_id"] == "hand-calc-001"
    assert rows["RPi01"]["localization_success_rate"] == pytest.approx(4.0 / 5.0)
    assert rows["T01"]["localization_success_rate"] == pytest.approx(3.0 / 4.0)
    assert rows["T02"]["valid_samples"] == 0
    assert rows["T02"]["localization_success_rate"] == pytest.approx(0.0)
    assert rows["T02"]["mae_m"] == MOD.NOT_APPLICABLE
    assert rows["T02"]["rmse_m"] == MOD.NOT_APPLICABLE
    assert rows["T02"]["p50_m"] == MOD.NOT_APPLICABLE
    assert rows["T02"]["p95_m"] == MOD.NOT_APPLICABLE
    # S_R = {T01, T02} (A01 excluded), G_R = {T01, T02, T03} -> recall = 2/3
    assert rows["RPi01"]["inventoried_targets"] == "T01;T02"
    assert rows["RPi01"]["inventory_recall"] == pytest.approx(2.0 / 3.0)
    # publish_interval_s=1.0 in states must NEVER be turned into latency
    assert rows["RPi01"]["end_to_end_latency_ms"] == MOD.NOT_PROVIDED


def test_cross_check_detects_double_counted_evaluation_against_states():
    """If an external eval JSON over-counts repeated old positions relative to states, flag it."""
    states = [
        _make_frame(
            timestamp=1000.0,
            run_id="dup-check-run",
            scanner={"id": "RPi01", "quality": "valid", "position": {"x_m": 1.0, "y_m": 2.0}, "position_at": 1000.0},
            devices=[],
        ),
        _make_frame(
            timestamp=1001.0,
            run_id="dup-check-run",
            scanner={"id": "RPi01", "quality": "valid", "position": {"x_m": 1.0, "y_m": 2.0}, "position_at": 1000.0},
            devices=[],
        ),
        _make_frame(
            timestamp=1002.0,
            run_id="dup-check-run",
            scanner={"id": "RPi01", "quality": "valid", "position": {"x_m": 2.0, "y_m": 2.0}, "position_at": 1002.0},
            devices=[],
        ),
    ]
    bad_eval = {
        "schema_version": "1.0",
        "sources": ["simulation"],
        "truth_used_by_solver": False,
        "skipped_unmatched": 0,
        "devices": {
            "RPi01": {"samples": 3, "mae_m": 0.5, "rmse_m": 0.5, "p50_m": 0.5, "p95_m": 0.5},
        },
    }
    summary = MOD.summarize_experiments(
        [
            {
                "experiment_id": "EXP-DUP-CHECK",
                "source": "synthetic",
                "version": "v1",
                "run_id": "dup-check-run",
                "scheduled_eval_points": 3,
                "evaluation": bad_eval,
                "states": states,
            }
        ]
    )
    assert any("重複計分舊位置" in w for w in summary["warnings"])
    assert "重複計分舊位置" in summary["rows"][0]["limitations"]


def test_zero_denominators_zero_samples_and_overflow_denominator():
    """Zero denominators and zero samples must yield 不適用, never 0 or ZeroDivisionError."""
    summary = MOD.summarize_experiments(
        [
            {
                "experiment_id": "EXP-ZERO-DENOM",
                "source": "physical",
                "version": "291f0d1",
                "run_id": "phy-zero-001",
                "scheduled_eval_points": 0,
                "expected_targets": [],
                "inventoried_targets": [],
                "evaluation": {
                    "schema_version": "1.0",
                    "sources": ["physical"],
                    "truth_used_by_solver": False,
                    "skipped_unmatched": 0,
                    "devices": {},
                },
            },
            {
                "experiment_id": "EXP-ZERO-SAMPLES-EXPLICIT-DEVICE",
                "source": "physical",
                "version": "291f0d1",
                "run_id": "phy-zero-002",
                "scheduled_eval_points": {"RPi01": 10},
                "expected_targets": ["T01", "T02"],
                "inventoried_targets": [],
                "evaluation": {
                    "schema_version": "1.0",
                    "sources": ["physical"],
                    "truth_used_by_solver": False,
                    "skipped_unmatched": 0,
                    "devices": {
                        "RPi01": {"samples": 0, "mae_m": 0.0, "rmse_m": 0.0, "p50_m": 0.0, "p95_m": 0.0}
                    },
                },
            },
            {
                "experiment_id": "EXP-OVERFLOW-DENOM",
                "source": "physical",
                "version": "291f0d1",
                "run_id": "phy-overflow-003",
                "scheduled_eval_points": {"RPi01": 5},
                "expected_targets": ["T01"],
                "inventoried_targets": ["T01"],
                "evaluation": {
                    "schema_version": "1.0",
                    "sources": ["physical"],
                    "truth_used_by_solver": False,
                    "skipped_unmatched": 0,
                    "devices": {
                        "RPi01": {"samples": 8, "mae_m": 1.0, "rmse_m": 1.0, "p50_m": 1.0, "p95_m": 1.0}
                    },
                },
            },
        ]
    )
    by_exp = {row["experiment_id"]: row for row in summary["rows"]}

    z0 = by_exp["EXP-ZERO-DENOM"]
    assert z0["valid_samples"] == 0
    assert z0["scheduled_eval_points"] == 0
    assert z0["localization_success_rate"] == MOD.NOT_APPLICABLE
    assert z0["inventory_recall"] == MOD.NOT_APPLICABLE
    assert z0["mae_m"] == MOD.NOT_APPLICABLE
    assert z0["rmse_m"] == MOD.NOT_APPLICABLE
    assert z0["p50_m"] == MOD.NOT_APPLICABLE
    assert z0["p95_m"] == MOD.NOT_APPLICABLE

    z1 = by_exp["EXP-ZERO-SAMPLES-EXPLICIT-DEVICE"]
    assert z1["valid_samples"] == 0
    assert z1["localization_success_rate"] == pytest.approx(0.0)
    assert z1["inventory_recall"] == pytest.approx(0.0)
    assert z1["mae_m"] == MOD.NOT_APPLICABLE
    assert z1["rmse_m"] == MOD.NOT_APPLICABLE

    ov = by_exp["EXP-OVERFLOW-DENOM"]
    assert ov["localization_success_rate"] == MOD.NOT_APPLICABLE
    assert "有效樣本數（8）大於預定評估時點數（5）" in ov["limitations"]


def test_missing_metadata_missing_metrics_and_unmeasured_latency():
    """Missing denominators, sets, metrics, and unmeasured latency must stay 未提供 without guessing."""
    summary = MOD.summarize_experiments(
        [
            {
                "experiment_id": "EXP-MISSING-001",
                "publish_interval_s": 1.0,
                "end_to_end_latency_ms": 1000.0,
                "latency_measured": False,
                "evaluation": {
                    "schema_version": "1.0",
                    "sources": ["simulation"],
                    "truth_used_by_solver": False,
                    "devices": {
                        "RPi01": {"samples": 12, "mae_m": 0.9, "rmse_m": 1.1, "p95_m": None}
                    },
                },
            },
            {
                "experiment_id": "EXP-MEASURED-LATENCY",
                "source": "aws_e2e",
                "version": "291f0d1",
                "run_id": "aws-run-01",
                "end_to_end_latency_ms": 245.5,
                "latency_measured": True,
                "missing_reason": "僅量測雲端轉發延遲，無定位真值",
            },
        ]
    )
    by_exp = {row["experiment_id"]: row for row in summary["rows"]}

    m = by_exp["EXP-MISSING-001"]
    assert m["source"] == MOD.NOT_PROVIDED
    assert m["source_status"] == "unspecified"
    assert m["version"] == MOD.NOT_PROVIDED
    assert m["run_id"] == MOD.NOT_PROVIDED
    assert m["scheduled_eval_points"] == MOD.NOT_PROVIDED
    assert m["localization_success_rate"] == MOD.NOT_PROVIDED
    assert m["expected_targets"] == MOD.NOT_PROVIDED
    assert m["inventoried_targets"] == MOD.NOT_PROVIDED
    assert m["inventory_recall"] == MOD.NOT_PROVIDED
    assert m["p50_m"] == MOD.NOT_PROVIDED
    assert m["p95_m"] == MOD.NOT_PROVIDED
    assert m["end_to_end_latency_ms"] == MOD.NOT_PROVIDED
    assert m["mae_m"] == pytest.approx(0.9)
    assert m["rmse_m"] == pytest.approx(1.1)

    lat = by_exp["EXP-MEASURED-LATENCY"]
    assert lat["end_to_end_latency_ms"] == pytest.approx(245.5)
    assert lat["valid_samples"] == MOD.NOT_PROVIDED
    assert lat["mae_m"] == MOD.NOT_PROVIDED


def test_inventory_recall_uses_intersection_and_deduplicates():
    """Recall must compute |S_R ∩ G_R| / |G_R|, ignoring unexpected extra targets."""
    summary = MOD.summarize_experiments(
        [
            {
                "experiment_id": "EXP-RECALL-INTERSECT",
                "source": "physical",
                "version": "291f0d1",
                "run_id": "phy-recall-01",
                "expected_targets": ["T01", "T02", "T02"],
                "inventoried_targets": ["T01", "T01", "T03"],
                "evaluation": {
                    "schema_version": "1.0",
                    "sources": ["physical"],
                    "truth_used_by_solver": False,
                    "skipped_unmatched": 0,
                    "devices": {
                        "RPi01": {"samples": 5, "mae_m": 1.0, "rmse_m": 1.2, "p50_m": 1.0, "p95_m": 1.5}
                    },
                },
            }
        ]
    )
    row = summary["rows"][0]
    assert row["expected_targets"] == "T01;T02"
    assert row["inventoried_targets"] == "T01;T03"
    assert row["inventory_recall"] == pytest.approx(0.5)


def test_mixed_sources_conflict_and_different_versions_flagged():
    """Single-run mixed/conflicting sources and multi-run mixed sources/versions must be clearly flagged."""
    summary = MOD.summarize_experiments(
        [
            {
                "experiment_id": "EXP-MIXED-INTERNAL",
                "source": "synthetic",
                "version": "9225d6b",
                "run_id": "run-mixed-1",
                "evaluation": {
                    "schema_version": "1.0",
                    "sources": ["physical", "simulation"],
                    "truth_used_by_solver": False,
                    "skipped_unmatched": 0,
                    "devices": {"RPi01": {"samples": 4, "mae_m": 1.0, "rmse_m": 1.0, "p50_m": 1.0, "p95_m": 1.0}},
                },
            },
            {
                "experiment_id": "EXP-CONFLICT-SOURCE",
                "source": "physical",
                "version": "291f0d1",
                "run_id": "run-conflict-2",
                "evaluation": {
                    "schema_version": "1.0",
                    "sources": ["simulation"],
                    "truth_used_by_solver": False,
                    "skipped_unmatched": 0,
                    "devices": {"RPi01": {"samples": 4, "mae_m": 2.0, "rmse_m": 2.0, "p50_m": 2.0, "p95_m": 2.0}},
                },
            },
            {
                "experiment_id": "EXP-GAZEBO-CLEAN",
                "source": "gazebo",
                "version": "291f0d1",
                "run_id": "run-gazebo-3",
                "evaluation": {
                    "schema_version": "1.0",
                    "sources": ["simulation"],
                    "truth_used_by_solver": False,
                    "skipped_unmatched": 0,
                    "devices": {"RPi01": {"samples": 4, "mae_m": 1.5, "rmse_m": 1.6, "p50_m": 1.5, "p95_m": 1.9}},
                },
            },
        ]
    )

    flags = summary["comparison_flags"]
    assert flags["has_mixed_sources"] is True
    assert flags["distinct_sources"] == ["gazebo", "physical", "synthetic"]
    assert flags["has_multiple_versions"] is True
    assert flags["distinct_versions"] == ["291f0d1", "9225d6b"]

    by_exp = {r["experiment_id"]: r for r in summary["rows"]}
    assert by_exp["EXP-MIXED-INTERNAL"]["source_status"] == "mixed"
    assert by_exp["EXP-CONFLICT-SOURCE"]["source_status"] == "conflict"
    assert by_exp["EXP-GAZEBO-CLEAN"]["source_status"] == "ok"

    md = MOD.render_markdown(summary)
    assert "混合來源" in md
    assert "多版本比較" in md
    assert "不得合併平均" in md


def test_truth_separation_rejects_solver_truth_and_embedded_truth():
    """Solver-used truth or truth fields embedded in state snapshots must be rejected."""
    with pytest.raises(ValueError, match="truth_used_by_solver"):
        MOD.summarize_experiments(
            [
                {
                    "experiment_id": "EXP-BAD-TRUTH",
                    "source": "synthetic",
                    "version": "v1",
                    "run_id": "bad-1",
                    "evaluation": {
                        "schema_version": "1.0",
                        "sources": ["simulation"],
                        "truth_used_by_solver": True,
                        "devices": {},
                    },
                }
            ]
        )

    bad_state = _make_frame(
        timestamp=1000.0,
        scanner={"id": "RPi01", "quality": "valid", "position": {"x_m": 1.0, "y_m": 2.0}, "position_at": 1000.0},
        devices=[],
    )
    bad_state["ground_truth"] = {"scanner": [1.0, 2.0, 1.2]}
    with pytest.raises(ValueError, match="forbidden truth"):
        MOD.inspect_states([bad_state])

    # Missing truth_used_by_solver flag does not pass silently: emits 未提供 + warning.
    summary = MOD.summarize_experiments(
        [
            {
                "experiment_id": "EXP-NO-TRUTH-FLAG",
                "source": "synthetic",
                "version": "v1",
                "run_id": "run-no-flag",
                "evaluation": {
                    "schema_version": "1.0",
                    "sources": ["simulation"],
                    "devices": {"RPi01": {"samples": 1, "mae_m": 0.2, "rmse_m": 0.2, "p50_m": 0.2, "p95_m": 0.2}},
                },
            }
        ]
    )
    assert summary["rows"][0]["truth_used_by_solver"] == MOD.NOT_PROVIDED
    assert any("truth_used_by_solver" in w for w in summary["warnings"])


@pytest.mark.parametrize(
    "bad_entry",
    [
        {"experiment_id": "BAD-NEG-SCHED", "source": "synthetic", "scheduled_eval_points": -1},
        {"experiment_id": "BAD-BOOL-SCHED", "source": "synthetic", "scheduled_eval_points": True},
        {"experiment_id": "BAD-SOURCE", "source": "drone_guess"},
        {"experiment_id": "BAD-NEG-LATENCY", "source": "aws_e2e", "end_to_end_latency_ms": -5.0},
        {
            "experiment_id": "BAD-NAN-MAE",
            "source": "synthetic",
            "evaluation": {
                "sources": ["simulation"],
                "truth_used_by_solver": False,
                "devices": {"RPi01": {"samples": 2, "mae_m": float("nan"), "rmse_m": 1.0, "p50_m": 1.0, "p95_m": 1.0}},
            },
        },
        {
            "experiment_id": "BAD-NEG-RMSE",
            "source": "synthetic",
            "evaluation": {
                "sources": ["simulation"],
                "truth_used_by_solver": False,
                "devices": {"RPi01": {"samples": 2, "mae_m": 1.0, "rmse_m": -0.1, "p50_m": 1.0, "p95_m": 1.0}},
            },
        },
    ],
)
def test_invalid_numeric_or_source_inputs_rejected(bad_entry):
    with pytest.raises(ValueError):
        MOD.summarize_experiments([bad_entry])


def test_repo_synthetic_fixture_matches_methods_section_11_readonly():
    """Read-only check on web/public/demo.json + tests/fixtures/truth.jsonl reproduces methods.md §11."""
    demo_path = REPO_ROOT / "web" / "public" / "demo.json"
    truth_path = REPO_ROOT / "tests" / "fixtures" / "truth.jsonl"

    summary = MOD.summarize_experiments(
        [
            {
                "experiment_id": "TEST-005-SYN",
                "source": "synthetic",
                "site": "indoor-demo",
                "route": "90s synthetic loop (T02 off after 65s)",
                "version": "9225d6be262071ab8ad31d6fb1f8b76526a5b04e",
                "scheduled_eval_points": {"RPi01": 90, "T01": 90, "T02": 65},
                "expected_targets": ["T01", "T02"],
                "states_path": str(demo_path),
                "truth_path": str(truth_path),
            }
        ]
    )
    by_dev = {row["device_id"]: row for row in summary["rows"]}
    assert set(by_dev) == {"RPi01", "T01", "T02"}

    assert by_dev["RPi01"]["run_id"] == "synthetic-example-5047"
    assert by_dev["RPi01"]["valid_samples"] == 90
    assert by_dev["RPi01"]["mae_m"] == pytest.approx(1.043, abs=1e-3)
    assert by_dev["RPi01"]["rmse_m"] == pytest.approx(1.106, abs=1e-3)
    assert by_dev["RPi01"]["p50_m"] == pytest.approx(1.029, abs=1e-3)
    assert by_dev["RPi01"]["p95_m"] == pytest.approx(1.734, abs=1e-3)
    assert by_dev["RPi01"]["localization_success_rate"] == pytest.approx(1.0)
    assert by_dev["RPi01"]["inventory_recall"] == pytest.approx(1.0)
    assert by_dev["RPi01"]["end_to_end_latency_ms"] == MOD.NOT_PROVIDED

    assert by_dev["T01"]["valid_samples"] == 85
    assert by_dev["T01"]["mae_m"] == pytest.approx(0.464, abs=1e-3)
    assert by_dev["T01"]["rmse_m"] == pytest.approx(0.802, abs=1e-3)
    assert by_dev["T01"]["p50_m"] == pytest.approx(0.305, abs=1e-3)
    assert by_dev["T01"]["p95_m"] == pytest.approx(1.809, abs=1e-3)
    assert by_dev["T01"]["localization_success_rate"] == pytest.approx(85.0 / 90.0)

    assert by_dev["T02"]["valid_samples"] == 65
    assert by_dev["T02"]["mae_m"] == pytest.approx(0.220, abs=1e-3)
    assert by_dev["T02"]["rmse_m"] == pytest.approx(0.349, abs=1e-3)
    assert by_dev["T02"]["p50_m"] == pytest.approx(0.116, abs=1e-3)
    assert by_dev["T02"]["p95_m"] == pytest.approx(1.029, abs=1e-3)
    assert by_dev["T02"]["localization_success_rate"] == pytest.approx(1.0)


def test_experiments_template_csv_schema_and_no_fabricated_numbers():
    """docs/report/experiments-template.csv must match CSV_COLUMNS and keep pending metrics 未提供."""
    template_path = REPO_ROOT / "docs" / "report" / "experiments-template.csv"
    with template_path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        header = next(reader)
        data_rows = list(reader)

    assert header == MOD.CSV_COLUMNS
    assert len(data_rows) == 4
    assert all(len(r) == len(MOD.CSV_COLUMNS) for r in data_rows)

    entries = MOD.load_manifest(template_path)
    summary = MOD.summarize_experiments(entries, base_dir=template_path.parent)
    assert summary["comparison_flags"]["has_mixed_sources"] is True
    assert summary["comparison_flags"]["distinct_sources"] == ["aws_e2e", "gazebo", "physical", "synthetic"]

    for row in summary["rows"]:
        for col in (
            "valid_samples",
            "scheduled_eval_points",
            "localization_success_rate",
            "mae_m",
            "rmse_m",
            "p50_m",
            "p95_m",
            "inventory_recall",
            "end_to_end_latency_ms",
        ):
            assert row[col] == MOD.NOT_PROVIDED


def test_cli_manifest_outputs_and_csv_formula_protection(tmp_path):
    """CLI writes JSON/CSV/Markdown cleanly and guards spreadsheet formula injection."""
    eval_file = tmp_path / "eval.json"
    eval_file.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "sources": ["physical"],
                "truth_used_by_solver": False,
                "skipped_unmatched": 0,
                "devices": {
                    "RPi01": {"samples": 10, "mae_m": 0.5, "rmse_m": 0.6, "p50_m": 0.45, "p95_m": 0.95}
                },
            }
        ),
        encoding="utf-8",
    )
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "experiments": [
                    {
                        "experiment_id": "EXP-CLI-001",
                        "source": "physical",
                        "site": "room-A",
                        "route": "=SUM(A1:A2)",
                        "version": "291f0d1",
                        "run_id": "phy-cli-001",
                        "scheduled_eval_points": 20,
                        "expected_targets": ["T01", "T02"],
                        "inventoried_targets": ["T01"],
                        "evaluation_path": "eval.json",
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    csv_out = tmp_path / "out.csv"
    md_out = tmp_path / "out.md"
    json_out = tmp_path / "out.json"

    rc = MOD.main(
        [
            "--manifest",
            str(manifest),
            "--csv-out",
            str(csv_out),
            "--md-out",
            str(md_out),
            "--json-out",
            str(json_out),
            "--format",
            "json",
        ]
    )
    assert rc == 0

    parsed_json = json.loads(json_out.read_text(encoding="utf-8"))
    assert parsed_json["rows"][0]["localization_success_rate"] == pytest.approx(0.5)
    assert parsed_json["rows"][0]["inventory_recall"] == pytest.approx(0.5)

    parsed_csv = list(csv.DictReader(io.StringIO(csv_out.read_text(encoding="utf-8"))))
    assert len(parsed_csv) == 1
    assert parsed_csv[0]["route"] == "'=SUM(A1:A2)"
    assert parsed_csv[0]["localization_success_rate"] == "0.5000"
    assert parsed_csv[0]["inventory_recall"] == "0.5000"
    assert parsed_csv[0]["end_to_end_latency_ms"] == MOD.NOT_PROVIDED

    md_text = md_out.read_text(encoding="utf-8")
    assert "EXP-CLI-001" in md_text
    assert "0.5000" in md_text


def test_unknown_truth_separation_stays_unknown_in_summary_and_markdown():
    summary = MOD.summarize_experiments([{
        "source": "synthetic", "version": "v1", "run_id": "run-1",
        "evaluation": {"devices": {}},
    }])
    assert summary["truth_used_by_solver"] == MOD.NOT_PROVIDED
    assert "truth_used_by_solver = false" not in MOD.render_markdown(summary)


@pytest.mark.parametrize("metadata_run", [None, "run-other"])
def test_reject_mixed_or_mismatched_run_ids(metadata_run):
    run_ids = ["run-1", "run-2"] if metadata_run is None else ["run-1"]
    states = [_make_frame(timestamp=1000, run_id=rid, scanner={
        "id": "RPi01", "quality": "valid", "position_at": 1000,
        "position": {"x_m": 1, "y_m": 0},
    }, devices=[]) for rid in run_ids]
    with pytest.raises(ValueError, match="run_id"):
        MOD.summarize_experiments([{
            "source": "synthetic", "version": "v1", "run_id": metadata_run,
            "states": states, "truth": [{"timestamp": 1000, "scanner": [0, 0]}],
        }])


def test_csv_preserves_explicit_unmeasured_latency(tmp_path):
    manifest = tmp_path / "input.csv"
    manifest.write_text(
        "experiment_id,source,version,run_id,end_to_end_latency_ms,latency_measured\n"
        "latency,physical,v1,run-1,1000,false\n", encoding="utf-8")
    summary = MOD.summarize_experiments(MOD.load_manifest(manifest))
    assert summary["rows"][0]["end_to_end_latency_ms"] == MOD.NOT_PROVIDED
