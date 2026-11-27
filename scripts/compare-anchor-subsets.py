"""Fair offline ablation comparing baseline vs. expanded anchor subsets on identical observations.

Guardrails:
- Pure offline, zero network, zero deployment, read-only on all input files.
- Validates every complete raw observation batch (schema v1.0, single source/scanner,
  strict sequence order, non-decreasing timestamps, no embedded truth) BEFORE filtering.
- Replays baseline and expanded anchor subsets in two cold-start InventoryEngine instances
  using deep-copied identical site configs, removing only anchors outside each subset while
  preserving identical Target observations, timestamps, sequences, source, heights, RSSI
  model parameters, and temporal filter parameters.
- Ground truth is strictly optional offline evaluation input and NEVER enters either engine.
- Deduplicates valid positions strictly by ``position_at`` (counting only ``quality == "valid"``
  with a newly produced ``position_at``).
- Never fabricates formal success rate (always ``null`` when no pre-defined evaluation grid is
  supplied) and never reports RPi scanner error when scanner truth is missing.
- Never includes private config fields (such as ``cloud`` credentials/paths) or host info in output.
"""
from __future__ import annotations

import argparse
import bisect
import copy
import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Any, Sequence

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from ble_inventory import __version__ as PACKAGE_VERSION
from ble_inventory.config import normalize_config
from ble_inventory.contracts import validate_batch
from ble_inventory.engine import InventoryEngine

SCHEMA_VERSION = "1.0"
DEFAULT_BASELINE_ANCHORS = "A01,A02,A03,A04"
DEFAULT_EXPANDED_ANCHORS = "A01,A02,A03,A04,A05,A06"
DEFAULT_MAX_TIME_DELTA_S = 0.25


def _is_finite_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def parse_anchor_list(raw: str | Sequence[str], label: str) -> list[str]:
    """Parse and validate a non-empty list of unique anchor IDs."""
    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            raise ValueError(f"{label} must not be empty")
        tokens = [part.strip() for part in text.split(",")]
    elif isinstance(raw, (list, tuple)):
        if not raw:
            raise ValueError(f"{label} must not be empty")
        tokens = []
        for item in raw:
            if not isinstance(item, str):
                raise ValueError(f"{label} entries must be strings, got {type(item).__name__}")
            tokens.append(item.strip())
    else:
        raise ValueError(f"{label} must be a comma-separated string or sequence of strings")

    if any(not tok for tok in tokens):
        raise ValueError(f"{label} contains an empty anchor ID")
    if len(tokens) != len(set(tokens)):
        seen: set[str] = set()
        dups: list[str] = []
        for tok in tokens:
            if tok in seen and tok not in dups:
                dups.append(tok)
            seen.add(tok)
        raise ValueError(f"Duplicate anchor IDs in {label}: {', '.join(dups)}")
    return tokens


def _validate_raw_batch_strict(batch: Any, batch_index: int) -> dict[str, Any]:
    """Validate one raw observation batch against v1.0 schema, rejecting booleans as numbers."""
    if not isinstance(batch, dict):
        raise ValueError(f"Observation batch #{batch_index} must be a JSON object")
    if isinstance(batch.get("sequence"), bool):
        raise ValueError(f"Observation batch #{batch_index}: sequence must be an integer, not bool")
    if isinstance(batch.get("timestamp"), bool):
        raise ValueError(f"Observation batch #{batch_index}: timestamp must be a number, not bool")
    if isinstance(batch.get("scanner_height_m"), bool):
        raise ValueError(f"Observation batch #{batch_index}: scanner_height_m must be a number, not bool")

    observations = batch.get("observations")
    if isinstance(observations, list):
        for obs_idx, obs in enumerate(observations):
            if isinstance(obs, dict):
                if isinstance(obs.get("rssi_dbm"), bool):
                    raise ValueError(
                        f"Observation batch #{batch_index} item #{obs_idx}: rssi_dbm must be a number, not bool"
                    )
                if isinstance(obs.get("rssi_at_1m_dbm"), bool):
                    raise ValueError(
                        f"Observation batch #{batch_index} item #{obs_idx}: rssi_at_1m_dbm must be a number, not bool"
                    )

    validate_batch(batch)
    return batch


def validate_observation_stream(
    batches: Sequence[dict[str, Any]],
    expected_scanner_id: str,
) -> tuple[str, set[str]]:
    """Validate the complete raw observation stream BEFORE any anchor filtering.

    Rejects empty streams, schema/truth violations, mixed sources, mixed or mismatched
    scanner_id, duplicate sequences, and out-of-order sequences or timestamps.
    """
    if not batches:
        raise ValueError("Observation stream is empty")

    source: str | None = None
    scanner_id: str | None = None
    last_sequence = -1
    last_timestamp: float | None = None
    observed_ids: set[str] = set()

    for idx, batch in enumerate(batches):
        validated = _validate_raw_batch_strict(batch, idx)
        batch_source = validated["source"]
        batch_scanner = validated["scanner_id"]
        batch_seq = validated["sequence"]
        batch_ts = float(validated["timestamp"])

        if source is None:
            source = batch_source
        elif batch_source != source:
            raise ValueError(
                f"Mixed observation sources in raw stream at batch #{idx}: {source!r} vs {batch_source!r}"
            )

        if scanner_id is None:
            scanner_id = batch_scanner
        elif batch_scanner != scanner_id:
            raise ValueError(
                f"Mixed scanner_id in raw stream at batch #{idx}: {scanner_id!r} vs {batch_scanner!r}"
            )

        if batch_scanner != expected_scanner_id:
            raise ValueError(
                f"Observation scanner_id {batch_scanner!r} does not match config scanner_id {expected_scanner_id!r}"
            )

        if batch_seq <= last_sequence:
            raise ValueError(
                f"Duplicate or out-of-order sequence at batch #{idx}: {batch_seq} after {last_sequence}"
            )
        if last_timestamp is not None and batch_ts < last_timestamp:
            raise ValueError(
                f"Out-of-order timestamp at batch #{idx}: {batch_ts} < {last_timestamp}"
            )

        last_sequence = batch_seq
        last_timestamp = batch_ts

        for obs in validated["observations"]:
            observed_ids.add(obs["device_id"])

    assert source is not None
    return source, observed_ids


def load_observations_jsonl(path: Path, expected_scanner_id: str) -> tuple[list[dict[str, Any]], str, str, set[str]]:
    """Load and validate a raw observations JSONL file and return (batches, sha256, source, observed_ids)."""
    raw_bytes = path.read_bytes()
    raw_sha256 = _sha256_bytes(raw_bytes)
    text = raw_bytes.decode("utf-8")
    lines = [line for line in text.splitlines() if line.strip()]
    if not lines:
        raise ValueError(f"Observations file is empty: {path.name}")
    batches = [json.loads(line) for line in lines]
    source, observed_ids = validate_observation_stream(batches, expected_scanner_id)
    return batches, raw_sha256, source, observed_ids


def load_config_json(path: Path) -> tuple[dict[str, Any], str]:
    """Load, hash, and normalize site configuration JSON."""
    raw_bytes = path.read_bytes()
    config_sha256 = _sha256_bytes(raw_bytes)
    raw_payload = json.loads(raw_bytes.decode("utf-8"))
    if not isinstance(raw_payload, dict):
        raise ValueError("Site configuration must be a JSON object")
    normalized = normalize_config(raw_payload)
    return normalized, config_sha256


def _validate_xy_point(value: Any, label: str) -> tuple[float, float]:
    if not isinstance(value, (list, tuple)) or len(value) < 2:
        raise ValueError(f"{label} must be a list of at least [x, y]")
    if not (_is_finite_number(value[0]) and _is_finite_number(value[1])):
        raise ValueError(f"{label} coordinates must be finite numbers")
    return float(value[0]), float(value[1])


def validate_truth_rows(rows: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    """Validate separate offline ground truth rows and sort them by timestamp."""
    if not rows:
        raise ValueError("Truth file is empty")
    validated: list[dict[str, Any]] = []
    for idx, row in enumerate(rows):
        if not isinstance(row, dict):
            raise ValueError(f"Truth row #{idx} must be a JSON object")
        ts = row.get("timestamp")
        if not _is_finite_number(ts) or float(ts) <= 0:
            raise ValueError(f"Truth row #{idx} requires a positive finite timestamp")
        scanner_val = row.get("scanner")
        if scanner_val is not None:
            _validate_xy_point(scanner_val, f"Truth row #{idx} scanner")
        targets_val = row.get("targets")
        if targets_val is not None:
            if not isinstance(targets_val, dict):
                raise ValueError(f"Truth row #{idx} targets must be a JSON object or null")
            for target_id, coords in targets_val.items():
                if not isinstance(target_id, str) or not target_id.strip():
                    raise ValueError(f"Truth row #{idx} contains invalid target ID")
                if coords is not None:
                    _validate_xy_point(coords, f"Truth row #{idx} targets[{target_id}]")
        validated.append(row)
    return sorted(validated, key=lambda r: float(r["timestamp"]))


def load_truth_jsonl(path: Path) -> tuple[list[dict[str, Any]], str]:
    """Load, hash, validate, and sort an optional offline truth JSONL file."""
    raw_bytes = path.read_bytes()
    truth_sha256 = _sha256_bytes(raw_bytes)
    text = raw_bytes.decode("utf-8")
    lines = [line for line in text.splitlines() if line.strip()]
    if not lines:
        raise ValueError(f"Truth file is empty: {path.name}")
    rows = [json.loads(line) for line in lines]
    return validate_truth_rows(rows), truth_sha256


def validate_anchor_subsets(
    base_config: dict[str, Any],
    baseline_anchors: str | Sequence[str],
    expanded_anchors: str | Sequence[str],
    observed_ids: set[str],
) -> tuple[list[str], list[str]]:
    """Verify baseline is a strict anchor subset (>=3) of expanded and all expanded anchors exist and were observed."""
    baseline = parse_anchor_list(baseline_anchors, "baseline_anchors")
    expanded = parse_anchor_list(expanded_anchors, "expanded_anchors")

    if len(baseline) < 3:
        raise ValueError(f"baseline_anchors must contain at least 3 unique anchor IDs, got {len(baseline)}")

    baseline_set = set(baseline)
    expanded_set = set(expanded)
    if not baseline_set.issubset(expanded_set):
        extra = [aid for aid in baseline if aid not in expanded_set]
        raise ValueError(
            f"baseline_anchors must be a subset of expanded_anchors; unexpected in baseline: {', '.join(extra)}"
        )
    if baseline_set == expanded_set:
        raise ValueError("baseline_anchors must be a strict (proper) subset of expanded_anchors")

    device_roles = {d["id"]: d["role"] for d in base_config["devices"]}
    missing_from_config = [aid for aid in expanded if aid not in device_roles]
    if missing_from_config:
        raise ValueError(
            f"Anchor IDs not found in site config: {', '.join(missing_from_config)}"
        )
    non_anchors = [aid for aid in expanded if device_roles[aid] != "anchor"]
    if non_anchors:
        raise ValueError(
            f"Device IDs are not configured as role='anchor': {', '.join(non_anchors)}"
        )

    missing_observed = [aid for aid in expanded if aid not in observed_ids]
    if missing_observed:
        raise ValueError(
            f"Expanded anchor IDs missing from raw observations ({', '.join(missing_observed)}); "
            "cannot evaluate expanded subset without observed data for every expanded anchor"
        )

    return baseline, expanded


def build_subset_config(base_config: dict[str, Any], allowed_anchors: Sequence[str]) -> dict[str, Any]:
    """Return a deep-copied normalized config keeping all targets and only the allowed anchors."""
    allowed_set = set(allowed_anchors)
    cfg = copy.deepcopy(base_config)
    cfg["devices"] = [
        copy.deepcopy(device)
        for device in base_config["devices"]
        if device["role"] != "anchor" or device["id"] in allowed_set
    ]
    return normalize_config(cfg)


def filter_batch_for_anchors(
    raw_batch: dict[str, Any],
    allowed_anchors: set[str],
    config_anchor_ids: set[str],
    config_target_ids: set[str],
) -> dict[str, Any]:
    """Return a deep-copied observation batch removing only anchors outside ``allowed_anchors``.

    Preserves identical Target observations, timestamp, sequence, source, scanner_id,
    schema_version, and scanner_height_m (if present).
    """
    filtered_observations: list[dict[str, Any]] = []
    for obs in raw_batch["observations"]:
        dev_id = obs["device_id"]
        is_anchor_obs = (dev_id in config_anchor_ids) or (dev_id not in config_target_ids and dev_id.startswith("A"))
        if is_anchor_obs and dev_id not in allowed_anchors:
            continue
        filtered_observations.append(copy.deepcopy(obs))

    filtered_batch = {k: copy.deepcopy(v) for k, v in raw_batch.items() if k != "observations"}
    filtered_batch["observations"] = filtered_observations
    return filtered_batch


def replay_subset(
    base_config: dict[str, Any],
    raw_batches: Sequence[dict[str, Any]],
    source: str,
    allowed_anchors: Sequence[str],
    config_anchor_ids: set[str],
    config_target_ids: set[str],
    eval_device_roles: dict[str, str],
) -> dict[str, Any]:
    """Cold-start replay of one anchor subset using snapshot(now=batch['timestamp'])."""
    subset_cfg = build_subset_config(base_config, allowed_anchors)
    allowed_set = set(allowed_anchors)
    engine = InventoryEngine(subset_cfg)
    engine.start(source)

    valid_positions: dict[str, dict[float, tuple[float, float]]] = {dev_id: {} for dev_id in eval_device_roles}
    duplicate_valid_ignored: dict[str, int] = {dev_id: 0 for dev_id in eval_device_roles}

    for raw_batch in raw_batches:
        filtered_batch = filter_batch_for_anchors(
            raw_batch,
            allowed_anchors=allowed_set,
            config_anchor_ids=config_anchor_ids,
            config_target_ids=config_target_ids,
        )
        engine.ingest(filtered_batch)
        snap = engine.snapshot(now=raw_batch["timestamp"])

        entries = [{**snap["scanner"], "role": "scanner"}]
        entries.extend(d for d in snap["devices"] if d.get("role") == "target")

        for entry in entries:
            dev_id = entry.get("id")
            if dev_id not in valid_positions:
                continue
            if entry.get("quality") != "valid":
                continue
            pos = entry.get("position")
            stamp = entry.get("position_at")
            if not isinstance(pos, dict) or not _is_finite_number(stamp):
                continue
            if not (_is_finite_number(pos.get("x_m")) and _is_finite_number(pos.get("y_m"))):
                continue
            stamp_f = float(stamp)
            if stamp_f in valid_positions[dev_id]:
                duplicate_valid_ignored[dev_id] += 1
                continue
            valid_positions[dev_id][stamp_f] = (float(pos["x_m"]), float(pos["y_m"]))

    return {
        "valid_positions": valid_positions,
        "duplicate_valid_ignored": duplicate_valid_ignored,
    }


def _match_truth_error(
    dev_id: str,
    role: str,
    stamp: float,
    xy: tuple[float, float],
    sorted_truth: Sequence[dict[str, Any]],
    truth_times: Sequence[float],
    max_time_delta_s: float,
) -> float | None:
    """Align a single position_at timestamp to nearest truth within tolerance; return horizontal error (m) or None."""
    idx = bisect.bisect_left(truth_times, stamp)
    choices = [i for i in (idx - 1, idx) if 0 <= i < len(truth_times)]
    if not choices:
        return None
    match_idx = min(choices, key=lambda i: abs(truth_times[i] - stamp))
    if abs(truth_times[match_idx] - stamp) > max_time_delta_s:
        return None
    row = sorted_truth[match_idx]
    if role == "scanner":
        expected = row.get("scanner")
    else:
        targets = row.get("targets")
        expected = targets.get(dev_id) if isinstance(targets, dict) else None
    if expected is None:
        return None
    return math.dist((xy[0], xy[1]), (float(expected[0]), float(expected[1])))


def _summarize_error_values(values: Sequence[float]) -> dict[str, Any] | None:
    if not values:
        return None
    arr = np.asarray(values, dtype=float)
    return {
        "samples": len(values),
        "mae_m": float(np.mean(arr)),
        "rmse_m": float(np.sqrt(np.mean(np.square(arr)))),
        "p50_m": float(np.percentile(arr, 50)),
        "p95_m": float(np.percentile(arr, 95)),
    }


def _evaluate_group_against_truth(
    valid_positions: dict[str, dict[float, tuple[float, float]]],
    eval_device_roles: dict[str, str],
    sorted_truth: Sequence[dict[str, Any]],
    truth_times: Sequence[float],
    max_time_delta_s: float,
) -> tuple[dict[str, dict[float, float]], int]:
    """Compute per-device timestamp->horizontal_error mapping and count skipped unmatched valid positions."""
    errors_by_device: dict[str, dict[float, float]] = {dev_id: {} for dev_id in eval_device_roles}
    skipped_unmatched = 0
    for dev_id, role in eval_device_roles.items():
        for stamp, xy in valid_positions[dev_id].items():
            err = _match_truth_error(dev_id, role, stamp, xy, sorted_truth, truth_times, max_time_delta_s)
            if err is None:
                skipped_unmatched += 1
            else:
                errors_by_device[dev_id][stamp] = err
    return errors_by_device, skipped_unmatched


def compare_anchor_subsets_data(
    raw_batches: Sequence[dict[str, Any]],
    base_config: dict[str, Any],
    *,
    baseline_anchors: str | Sequence[str] = DEFAULT_BASELINE_ANCHORS,
    expanded_anchors: str | Sequence[str] = DEFAULT_EXPANDED_ANCHORS,
    truth_rows: Sequence[dict[str, Any]] | None = None,
    max_time_delta_s: float = DEFAULT_MAX_TIME_DELTA_S,
    observations_sha256: str | None = None,
    config_sha256: str | None = None,
    truth_sha256: str | None = None,
    version: str | None = None,
) -> dict[str, Any]:
    """Run fair offline anchor-subset ablation on validated in-memory objects."""
    if not _is_finite_number(max_time_delta_s) or float(max_time_delta_s) < 0:
        raise ValueError(f"max_time_delta_s must be finite and >= 0, got {max_time_delta_s!r}")
    max_delta = float(max_time_delta_s)

    normalized_config = normalize_config(base_config)
    scanner_id = normalized_config["scanner_id"]

    # Validate full raw batch stream BEFORE any filtering.
    source, observed_ids = validate_observation_stream(raw_batches, scanner_id)
    baseline_list, expanded_list = validate_anchor_subsets(
        normalized_config, baseline_anchors, expanded_anchors, observed_ids
    )

    sorted_truth: list[dict[str, Any]] | None = None
    truth_times: list[float] = []
    if truth_rows is not None:
        sorted_truth = validate_truth_rows(truth_rows)
        truth_times = [float(r["timestamp"]) for r in sorted_truth]

    config_anchor_ids = {d["id"] for d in normalized_config["devices"] if d["role"] == "anchor"}
    config_target_ids = {d["id"] for d in normalized_config["devices"] if d["role"] == "target"}
    eval_device_roles: dict[str, str] = {scanner_id: "scanner"}
    for device in normalized_config["devices"]:
        if device["role"] == "target":
            eval_device_roles[device["id"]] = "target"

    # Cold-start replay for both subsets without ever passing truth to InventoryEngine.
    baseline_run = replay_subset(
        normalized_config,
        raw_batches,
        source,
        baseline_list,
        config_anchor_ids,
        config_target_ids,
        eval_device_roles,
    )
    expanded_run = replay_subset(
        normalized_config,
        raw_batches,
        source,
        expanded_list,
        config_anchor_ids,
        config_target_ids,
        eval_device_roles,
    )

    baseline_errors: dict[str, dict[float, float]] | None = None
    expanded_errors: dict[str, dict[float, float]] | None = None
    baseline_skipped: int | None = None
    expanded_skipped: int | None = None
    scanner_truth_available = False

    if sorted_truth is not None:
        scanner_truth_available = any(row.get("scanner") is not None for row in sorted_truth)
        baseline_errors, baseline_skipped = _evaluate_group_against_truth(
            baseline_run["valid_positions"], eval_device_roles, sorted_truth, truth_times, max_delta
        )
        expanded_errors, expanded_skipped = _evaluate_group_against_truth(
            expanded_run["valid_positions"], eval_device_roles, sorted_truth, truth_times, max_delta
        )

    def _build_group_output(
        anchors: list[str],
        run: dict[str, Any],
        errors_map: dict[str, dict[float, float]] | None,
        skipped: int | None,
    ) -> dict[str, Any]:
        devices_out: dict[str, Any] = {}
        for dev_id, role in eval_device_roles.items():
            valid_map = run["valid_positions"][dev_id]
            if errors_map is None:
                metrics = None
            else:
                err_vals = list(errors_map[dev_id].values())
                metrics = _summarize_error_values(err_vals)
            devices_out[dev_id] = {
                "role": role,
                "valid_positions": len(valid_map),
                "duplicate_valid_positions_ignored": run["duplicate_valid_ignored"][dev_id],
                "formal_success_rate": None,
                "error_metrics": metrics,
            }
        return {
            "anchors": anchors,
            "skipped_unmatched_truth": skipped,
            "devices": devices_out,
        }

    common_valid: dict[str, Any] = {}
    for dev_id, role in eval_device_roles.items():
        b_stamps = set(baseline_run["valid_positions"][dev_id].keys())
        e_stamps = set(expanded_run["valid_positions"][dev_id].keys())
        shared_stamps = sorted(b_stamps & e_stamps)

        if baseline_errors is None or expanded_errors is None:
            common_valid[dev_id] = {
                "role": role,
                "common_valid_positions": len(shared_stamps),
                "matched_samples": None,
                "baseline_rmse_m": None,
                "expanded_rmse_m": None,
                "baseline_mae_m": None,
                "expanded_mae_m": None,
                "rmse_delta_m": None,
            }
        else:
            b_common = [
                baseline_errors[dev_id][t]
                for t in shared_stamps
                if t in baseline_errors[dev_id] and t in expanded_errors[dev_id]
            ]
            e_common = [
                expanded_errors[dev_id][t]
                for t in shared_stamps
                if t in baseline_errors[dev_id] and t in expanded_errors[dev_id]
            ]
            if b_common:
                b_arr = np.asarray(b_common, dtype=float)
                e_arr = np.asarray(e_common, dtype=float)
                b_rmse = float(np.sqrt(np.mean(np.square(b_arr))))
                e_rmse = float(np.sqrt(np.mean(np.square(e_arr))))
                b_mae = float(np.mean(b_arr))
                e_mae = float(np.mean(e_arr))
                common_valid[dev_id] = {
                    "role": role,
                    "common_valid_positions": len(shared_stamps),
                    "matched_samples": len(b_common),
                    "baseline_rmse_m": b_rmse,
                    "expanded_rmse_m": e_rmse,
                    "baseline_mae_m": b_mae,
                    "expanded_mae_m": e_mae,
                    "rmse_delta_m": e_rmse - b_rmse,
                }
            else:
                common_valid[dev_id] = {
                    "role": role,
                    "common_valid_positions": len(shared_stamps),
                    "matched_samples": 0,
                    "baseline_rmse_m": None,
                    "expanded_rmse_m": None,
                    "baseline_mae_m": None,
                    "expanded_mae_m": None,
                    "rmse_delta_m": None,
                }

    limitations = [
        "純離線同資料 Anchor 子集合消融比較（ablation），兩組皆採冷啟動、deepcopy 相同設定、同批 Target 觀測與相同模型／濾波參數。",
        "誤差指標皆為條件於有效解之水平誤差（僅 XY，不計 Z），比較時須同時檢視各組有效位置數與共同有效樣本數。",
        "未提供預先定義之評估時點與容許新鮮度，正式定位成功率標為 null，不以原始觀測批數事後充當分母。",
        "單趟巡查的時間序列樣本並非獨立試驗，濾波後樣本具時間相關性，結果不直接外推其他場地、路徑或整體精度。",
    ]
    if source == "simulation":
        limitations.append("觀測來源為 simulation（合成或模擬），不得冒充實體 BLE（physical）量測結果。")
    if sorted_truth is None:
        limitations.append("未提供獨立真值檔，所有誤差指標皆為 null，僅回報各組與共同有效位置數。")
    elif not scanner_truth_available:
        limitations.append("真值檔未提供掃描器（scanner）真值，不回報 RPi 水平誤差（error_metrics 為 null）。")

    added_anchors = [aid for aid in expanded_list if aid not in set(baseline_list)]
    version_out = version.strip() if isinstance(version, str) and version.strip() else PACKAGE_VERSION

    return {
        "schema_version": SCHEMA_VERSION,
        "comparison_kind": "anchor-subset-ablation",
        "version": version_out,
        "source": source,
        "scanner_id": scanner_id,
        "input_batches": len(raw_batches),
        "observations_sha256": observations_sha256,
        "config_sha256": config_sha256,
        "truth_provided": sorted_truth is not None,
        "truth_sha256": truth_sha256,
        "truth_used_by_solver": False,
        "max_time_delta_s": max_delta,
        "metric": "horizontal position error in meters",
        "formal_success_rate": None,
        "formal_success_rate_reason": "未提供預先定義之評估時點與容許新鮮度，正式定位成功率為 null，不以原始批數充當分母",
        "anchor_subsets": {
            "baseline": baseline_list,
            "expanded": expanded_list,
            "added_anchors": added_anchors,
        },
        "groups": {
            "baseline": _build_group_output(baseline_list, baseline_run, baseline_errors, baseline_skipped),
            "expanded": _build_group_output(expanded_list, expanded_run, expanded_errors, expanded_skipped),
        },
        "common_valid": common_valid,
        "limitations": limitations,
    }


def _ensure_output_not_input(output_path: Path, input_paths: Sequence[Path | None]) -> None:
    resolved_out = output_path.resolve()
    for inp in input_paths:
        if inp is not None and (
            resolved_out == inp.resolve()
            or (output_path.exists() and inp.exists() and output_path.samefile(inp))
        ):
            raise ValueError(f"Output path must not overwrite an input file: {output_path.name}")


def compare_anchor_subsets(
    observations_path: Path,
    config_path: Path,
    *,
    baseline_anchors: str | Sequence[str] = DEFAULT_BASELINE_ANCHORS,
    expanded_anchors: str | Sequence[str] = DEFAULT_EXPANDED_ANCHORS,
    truth_path: Path | None = None,
    max_time_delta_s: float = DEFAULT_MAX_TIME_DELTA_S,
    output_path: Path | None = None,
    version: str | None = None,
) -> dict[str, Any]:
    """File-based entry point for fair offline anchor-subset ablation."""
    if output_path is not None:
        _ensure_output_not_input(output_path, (observations_path, config_path, truth_path))

    normalized_config, config_sha256 = load_config_json(config_path)
    raw_batches, observations_sha256, _source, _observed_ids = load_observations_jsonl(
        observations_path, normalized_config["scanner_id"]
    )
    truth_rows: list[dict[str, Any]] | None = None
    truth_sha256: str | None = None
    if truth_path is not None:
        truth_rows, truth_sha256 = load_truth_jsonl(truth_path)

    result = compare_anchor_subsets_data(
        raw_batches,
        normalized_config,
        baseline_anchors=baseline_anchors,
        expanded_anchors=expanded_anchors,
        truth_rows=truth_rows,
        max_time_delta_s=max_time_delta_s,
        observations_sha256=observations_sha256,
        config_sha256=config_sha256,
        truth_sha256=truth_sha256,
        version=version,
    )

    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Fair offline ablation comparing baseline vs. expanded anchor subsets on identical raw observations."
    )
    parser.add_argument("observations", type=Path, help="Raw observations JSONL (schema v1.0)")
    parser.add_argument("config", type=Path, help="Site configuration JSON containing all expanded anchors")
    parser.add_argument(
        "--baseline-anchors",
        default=DEFAULT_BASELINE_ANCHORS,
        help=f"Comma-separated baseline anchor IDs (default: {DEFAULT_BASELINE_ANCHORS})",
    )
    parser.add_argument(
        "--expanded-anchors",
        default=DEFAULT_EXPANDED_ANCHORS,
        help=f"Comma-separated expanded anchor IDs (default: {DEFAULT_EXPANDED_ANCHORS})",
    )
    parser.add_argument(
        "--truth",
        type=Path,
        default=None,
        help="Optional separate offline truth JSONL (timestamp, optional scanner, optional targets)",
    )
    parser.add_argument(
        "--max-time-delta-s",
        type=float,
        default=DEFAULT_MAX_TIME_DELTA_S,
        help=f"Maximum timestamp alignment tolerance in seconds (default: {DEFAULT_MAX_TIME_DELTA_S})",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional path to write comparison JSON (must not overwrite any input file)",
    )
    parser.add_argument(
        "--version",
        type=str,
        default=None,
        help="Optional software version or commit SHA to record in output metadata",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    result = compare_anchor_subsets(
        args.observations,
        args.config,
        baseline_anchors=args.baseline_anchors,
        expanded_anchors=args.expanded_anchors,
        truth_path=args.truth,
        max_time_delta_s=args.max_time_delta_s,
        output_path=args.output,
        version=args.version,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(2)
