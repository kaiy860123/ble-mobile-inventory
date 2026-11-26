"""Summarize BLE localization & inventory evaluation outputs with explicit metadata.

Reads existing evaluation JSON outputs from ``scripts/evaluate-run.py`` (plus optional
replay/state logs and separate offline truth JSONL) together with explicit experiment
metadata, and produces comparable JSON, CSV, and Markdown experiment tables.

Guardrails:
- Ground truth is strictly offline evaluation input and must never enter the solver.
- Unknown denominators, missing expected/inventoried target sets, and unmeasured
  end-to-end latency are emitted as ``未提供`` without guessing.
- Zero denominators and zero valid samples are emitted as ``不適用`` rather than ``0``.
- Mixed sources and multiple software versions are explicitly flagged and never pooled.
"""
from __future__ import annotations

import argparse
import bisect
import csv
import io
import json
import math
from pathlib import Path
from typing import Any

import numpy as np

SCHEMA_VERSION = "1.0"
NOT_PROVIDED = "未提供"
NOT_APPLICABLE = "不適用"

ALLOWED_METADATA_SOURCES = (
    "synthetic",
    "gazebo",
    "physical",
    "simulation",
    "aws_e2e",
)

SOURCE_COMPATIBILITY: dict[str, set[str]] = {
    "synthetic": {"simulation", "synthetic"},
    "gazebo": {"simulation", "gazebo"},
    "simulation": {"simulation"},
    "physical": {"physical"},
    "aws_e2e": {"physical", "simulation", "aws_e2e"},
}

FORBIDDEN_TRUTH_KEYS = frozenset(
    {
        "truth",
        "ground_truth",
        "true_position",
        "scanner_truth",
        "target_truth",
        "scanner_position",
        "target_positions",
    }
)

MISSING_SENTINELS = frozenset(
    {"", "未提供", "待測", "待取得", "n/a", "na", "none", "null"}
)

EMPTY_SET_SENTINELS = frozenset({"[]", "∅", "empty", "EMPTY"})

CSV_COLUMNS = [
    "experiment_id",
    "source",
    "source_status",
    "site",
    "route",
    "version",
    "run_id",
    "device_id",
    "device_role",
    "valid_samples",
    "scheduled_eval_points",
    "localization_success_rate",
    "mae_m",
    "rmse_m",
    "p50_m",
    "p95_m",
    "expected_targets",
    "inventoried_targets",
    "inventory_recall",
    "end_to_end_latency_ms",
    "skipped_unmatched",
    "truth_used_by_solver",
    "evaluation_file",
    "states_file",
    "missing_reason",
    "limitations",
]


def _is_missing_text(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip().lower() in MISSING_SENTINELS
    return False


def _clean_optional_str(value: Any) -> str | None:
    if _is_missing_text(value):
        return None
    if isinstance(value, bool):
        raise ValueError("Boolean is not valid where text is expected")
    text = str(value).strip()
    return text if text else None


def _parse_bool_optional(value: Any, field_name: str) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        text = value.strip().lower()
        if text in MISSING_SENTINELS:
            return None
        if text == "true":
            return True
        if text == "false":
            return False
    raise ValueError(f"Invalid boolean for {field_name}: {value!r}")


def _parse_nonneg_int(value: Any, field_name: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{field_name} must be a non-negative integer, got bool")
    if isinstance(value, int):
        if value < 0:
            raise ValueError(f"{field_name} must be >= 0, got {value}")
        return value
    if isinstance(value, str):
        text = value.strip()
        try:
            parsed = int(text)
        except ValueError as exc:
            raise ValueError(f"{field_name} must be a non-negative integer, got {value!r}") from exc
        if parsed < 0:
            raise ValueError(f"{field_name} must be >= 0, got {parsed}")
        return parsed
    raise ValueError(f"{field_name} must be a non-negative integer, got {value!r}")


def _parse_nonneg_float(value: Any, field_name: str) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{field_name} must be a finite non-negative number, got bool")
    if isinstance(value, (int, float)):
        num = float(value)
    elif isinstance(value, str):
        try:
            num = float(value.strip())
        except ValueError as exc:
            raise ValueError(f"{field_name} must be a finite non-negative number, got {value!r}") from exc
    else:
        raise ValueError(f"{field_name} must be a finite non-negative number, got {value!r}")
    if not math.isfinite(num) or num < 0:
        raise ValueError(f"{field_name} must be finite and >= 0, got {value!r}")
    return num


def _is_finite_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


def _parse_target_set(value: Any, field_name: str) -> list[str] | None:
    """Parse a target ID collection into a deduplicated sorted list.

    Returns ``None`` when omitted/missing, or ``[]`` when explicitly empty.
    """
    if value is None:
        return None
    if isinstance(value, (list, tuple, set, frozenset)):
        cleaned: set[str] = set()
        for item in value:
            if not isinstance(item, str) or not item.strip():
                raise ValueError(f"{field_name} entries must be non-empty strings, got {item!r}")
            cleaned.add(item.strip())
        return sorted(cleaned)
    if isinstance(value, str):
        text = value.strip()
        if text in EMPTY_SET_SENTINELS or text.lower() == "empty":
            return []
        if text.lower() in MISSING_SENTINELS:
            return None
        sep = ";" if ";" in text else ","
        tokens = [part.strip() for part in text.split(sep)]
        if any(not tok for tok in tokens):
            raise ValueError(f"{field_name} contains blank ID in {value!r}")
        return sorted(set(tokens))
    raise ValueError(f"{field_name} must be a list or delimited string, got {type(value).__name__}")


def _parse_scheduled_eval_points(value: Any) -> int | dict[str, int | None] | None:
    """Parse scheduled evaluation denominator: int, per-device mapping, or None."""
    if value is None:
        return None
    if isinstance(value, dict):
        result: dict[str, int | None] = {}
        for dev_id, count in value.items():
            key = str(dev_id).strip()
            if not key:
                raise ValueError("scheduled_eval_points mapping contains empty device ID")
            if _is_missing_text(count):
                result[key] = None
            else:
                result[key] = _parse_nonneg_int(count, f"scheduled_eval_points[{key}]")
        return result
    if isinstance(value, int) and not isinstance(value, bool):
        return _parse_nonneg_int(value, "scheduled_eval_points")
    if isinstance(value, str):
        text = value.strip()
        if text.lower() in MISSING_SENTINELS:
            return None
        if text.startswith("{"):
            parsed = json.loads(text)
            if not isinstance(parsed, dict):
                raise ValueError("scheduled_eval_points JSON string must decode to an object")
            return _parse_scheduled_eval_points(parsed)
        if "=" in text:
            mapping: dict[str, int | None] = {}
            sep = ";" if ";" in text else ","
            for item in text.split(sep):
                part = item.strip()
                if not part:
                    continue
                if "=" not in part:
                    raise ValueError(f"Invalid scheduled_eval_points entry: {part!r}")
                dev_id, raw_count = part.split("=", 1)
                dev_key = dev_id.strip()
                if not dev_key:
                    raise ValueError(f"Empty device ID in scheduled_eval_points: {part!r}")
                mapping[dev_key] = (
                    None
                    if _is_missing_text(raw_count)
                    else _parse_nonneg_int(raw_count, f"scheduled_eval_points[{dev_key}]")
                )
            return mapping
        return _parse_nonneg_int(text, "scheduled_eval_points")
    raise ValueError(f"Invalid scheduled_eval_points: {value!r}")


def _parse_source(value: Any) -> str | None:
    text = _clean_optional_str(value)
    if text is None:
        return None
    normalized = text.lower()
    if normalized not in ALLOWED_METADATA_SOURCES:
        raise ValueError(
            f"Unsupported metadata source {value!r}; allowed: {', '.join(ALLOWED_METADATA_SOURCES)}"
        )
    return normalized


def _resolve_path(path_value: str | Path, base_dir: Path | None) -> Path:
    path = Path(path_value)
    if not path.is_absolute() and base_dir is not None:
        return base_dir / path
    return path


def _check_no_embedded_truth(frame: dict[str, Any], frame_index: int) -> None:
    if not isinstance(frame, dict):
        raise ValueError(f"State frame #{frame_index} must be an object")
    bad_top = sorted(set(frame.keys()) & FORBIDDEN_TRUTH_KEYS)
    if bad_top:
        raise ValueError(
            f"State frame #{frame_index} embeds forbidden truth fields ({', '.join(bad_top)}); "
            "ground truth must stay in a separate evaluation file"
        )
    scanner = frame.get("scanner")
    if isinstance(scanner, dict):
        bad_scanner = sorted(set(scanner.keys()) & FORBIDDEN_TRUTH_KEYS)
        if bad_scanner:
            raise ValueError(
                f"State frame #{frame_index} scanner embeds forbidden truth fields ({', '.join(bad_scanner)})"
            )
    devices = frame.get("devices", [])
    if isinstance(devices, list):
        for dev in devices:
            if isinstance(dev, dict):
                bad_dev = sorted(set(dev.keys()) & FORBIDDEN_TRUTH_KEYS)
                if bad_dev:
                    raise ValueError(
                        f"State frame #{frame_index} device embeds forbidden truth fields ({', '.join(bad_dev)})"
                    )


def load_states(path: Path) -> list[dict[str, Any]]:
    """Load replay JSON or states.jsonl while rejecting embedded truth fields."""
    raw_text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        payload = json.loads(raw_text)
        if isinstance(payload, dict) and isinstance(payload.get("frames"), list):
            frames = payload["frames"]
        elif isinstance(payload, list):
            frames = payload
        else:
            raise ValueError(f"Unsupported replay JSON structure in {path}")
    else:
        frames = [json.loads(line) for line in raw_text.splitlines() if line.strip()]
    for idx, frame in enumerate(frames):
        _check_no_embedded_truth(frame, idx)
    return frames


def load_truth(path: Path) -> list[dict[str, Any]]:
    """Load separate offline ground truth JSONL sorted by timestamp."""
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not rows:
        raise ValueError("No evaluation truth")
    for idx, row in enumerate(rows):
        if not isinstance(row, dict) or not _is_finite_number(row.get("timestamp")):
            raise ValueError(f"Invalid truth row #{idx}: finite numeric timestamp required")
    return sorted(rows, key=lambda r: float(r["timestamp"]))


def _iter_state_devices(frame: dict[str, Any]) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    scanner = frame.get("scanner")
    if isinstance(scanner, dict) and scanner.get("id"):
        entries.append({**scanner, "role": "scanner"})
    for dev in frame.get("devices", []):
        if isinstance(dev, dict) and dev.get("id"):
            entries.append(dev)
    return entries


def inspect_states(states: list[dict[str, Any]]) -> dict[str, Any]:
    """Extract deduplicated valid position counts, S_R, run IDs, and sources from states."""
    run_ids: set[str] = set()
    sources: set[str] = set()
    device_roles: dict[str, str] = {}
    inventoried_targets: set[str] = set()
    seen_valid_keys: set[tuple[Any, str, float]] = set()
    unique_valid_counts: dict[str, int] = {}
    duplicate_valid_ignored = 0
    invalid_position_at_skipped = 0

    for idx, frame in enumerate(states):
        _check_no_embedded_truth(frame, idx)
        run_id = frame.get("run_id")
        if isinstance(run_id, str) and run_id.strip():
            run_ids.add(run_id.strip())
        src = frame.get("source")
        if isinstance(src, str) and src.strip():
            sources.add(src.strip())
        for dev in _iter_state_devices(frame):
            dev_id = str(dev["id"])
            role = dev.get("role")
            if isinstance(role, str) and role.strip():
                device_roles[dev_id] = role.strip()
            if role == "target" and dev.get("last_seen") is not None:
                inventoried_targets.add(dev_id)
            if role == "anchor" or dev.get("quality") != "valid" or not isinstance(dev.get("position"), dict):
                continue
            position = dev["position"]
            stamp = dev.get("position_at")
            if not _is_finite_number(stamp) or not (
                _is_finite_number(position.get("x_m")) and _is_finite_number(position.get("y_m"))
            ):
                invalid_position_at_skipped += 1
                continue
            key = (run_id, dev_id, float(stamp))
            if key in seen_valid_keys:
                duplicate_valid_ignored += 1
                continue
            seen_valid_keys.add(key)
            unique_valid_counts[dev_id] = unique_valid_counts.get(dev_id, 0) + 1

    return {
        "run_ids": sorted(run_ids),
        "sources": sorted(sources),
        "device_roles": device_roles,
        "inventoried_targets": sorted(inventoried_targets),
        "unique_valid_position_counts": unique_valid_counts,
        "duplicate_valid_positions_ignored": duplicate_valid_ignored,
        "invalid_position_at_skipped": invalid_position_at_skipped,
    }


def evaluate_states_against_truth(
    states: list[dict[str, Any]],
    truth: list[dict[str, Any]],
    max_time_delta_s: float = 0.25,
) -> dict[str, Any]:
    """Evaluate recorded state snapshots against a separate truth sequence offline.

    Follows ``docs/report/methods.md`` section 10 and ``scripts/evaluate-run.py``:
    - Never feeds truth to any solver (``truth_used_by_solver`` is always ``False``).
    - Only evaluates ``quality == "valid"`` non-anchor devices with finite position and ``position_at``.
    - Deduplicates by ``(run_id, device_id, position_at)`` so repeated old positions are never double-counted.
    """
    if not _is_finite_number(max_time_delta_s) or float(max_time_delta_s) < 0:
        raise ValueError(f"max_time_delta_s must be finite and >= 0, got {max_time_delta_s!r}")
    if not truth:
        raise ValueError("No evaluation truth")
    sorted_truth = sorted(truth, key=lambda row: float(row["timestamp"]))
    times = [float(row["timestamp"]) for row in sorted_truth]

    errors: dict[str, list[float]] = {}
    seen: set[tuple[Any, str, float]] = set()
    sources_seen: set[str] = set()
    skipped_unmatched = 0
    duplicate_positions_ignored = 0
    invalid_position_at_skipped = 0

    for idx, state in enumerate(states):
        _check_no_embedded_truth(state, idx)
        src = state.get("source")
        if isinstance(src, str) and src.strip():
            sources_seen.add(src.strip())
        run_id = state.get("run_id")
        for device in _iter_state_devices(state):
            if device.get("role") == "anchor" or device.get("quality") != "valid" or not isinstance(device.get("position"), dict):
                continue
            stamp = device.get("position_at")
            position = device["position"]
            if not _is_finite_number(stamp) or not (
                _is_finite_number(position.get("x_m")) and _is_finite_number(position.get("y_m"))
            ):
                invalid_position_at_skipped += 1
                continue
            stamp_f = float(stamp)
            dev_id = str(device["id"])
            key = (run_id, dev_id, stamp_f)
            if key in seen:
                duplicate_positions_ignored += 1
                continue
            seen.add(key)
            pos_idx = bisect.bisect_left(times, stamp_f)
            choices = [i for i in (pos_idx - 1, pos_idx) if 0 <= i < len(times)]
            match = min(choices, key=lambda i: abs(times[i] - stamp_f))
            if abs(times[match] - stamp_f) > float(max_time_delta_s):
                skipped_unmatched += 1
                continue
            expected = (
                sorted_truth[match].get("scanner")
                if device.get("role") == "scanner"
                else sorted_truth[match].get("targets", {}).get(dev_id)
            )
            if expected is None or len(expected) < 2:
                skipped_unmatched += 1
                continue
            err = math.dist((float(position["x_m"]), float(position["y_m"])), (float(expected[0]), float(expected[1])))
            errors.setdefault(dev_id, []).append(err)

    devices_summary: dict[str, dict[str, Any]] = {}
    for dev_id, values in errors.items():
        arr = np.asarray(values, dtype=float)
        devices_summary[dev_id] = {
            "samples": len(values),
            "mae_m": float(np.mean(arr)),
            "rmse_m": float(np.sqrt(np.mean(np.square(arr)))),
            "p50_m": float(np.percentile(arr, 50)),
            "p95_m": float(np.percentile(arr, 95)),
        }

    return {
        "schema_version": SCHEMA_VERSION,
        "sources": sorted(sources_seen),
        "metric": "horizontal position error in meters",
        "truth_used_by_solver": False,
        "skipped_unmatched": skipped_unmatched,
        "duplicate_positions_ignored": duplicate_positions_ignored,
        "invalid_position_at_skipped": invalid_position_at_skipped,
        "devices": devices_summary,
    }


def _format_targets(targets: list[str] | None) -> str:
    if targets is None:
        return NOT_PROVIDED
    if len(targets) == 0:
        return "[]"
    return ";".join(targets)


def _compute_inventory_recall(
    expected_targets: list[str] | None,
    inventoried_targets: list[str] | None,
    run_notes: list[str],
) -> tuple[str, str, float | str]:
    expected_str = _format_targets(expected_targets)
    inventoried_str = _format_targets(inventoried_targets)
    if expected_targets is None:
        run_notes.append("未提供應盤點集合 G_R，盤點召回率標為未提供")
        return expected_str, inventoried_str, NOT_PROVIDED
    if len(expected_targets) == 0:
        run_notes.append("應盤點集合為空（|G_R|=0），盤點召回率不適用")
        return expected_str, inventoried_str, NOT_APPLICABLE
    if inventoried_targets is None:
        run_notes.append("未提供實際已盤點集合 S_R，盤點召回率標為未提供")
        return expected_str, inventoried_str, NOT_PROVIDED
    matched = set(expected_targets) & set(inventoried_targets)
    recall = float(len(matched)) / float(len(expected_targets))
    return expected_str, inventoried_str, recall


def _compute_success_rate(
    valid_samples: int | str,
    scheduled_points: int | None,
    row_notes: list[str],
) -> tuple[int | str, float | str]:
    if valid_samples == NOT_PROVIDED:
        if scheduled_points is None:
            return NOT_PROVIDED, NOT_PROVIDED
        if scheduled_points == 0:
            row_notes.append("預定評估時點數為 0，定位成功率不適用")
            return 0, NOT_APPLICABLE
        return scheduled_points, NOT_PROVIDED

    assert isinstance(valid_samples, int)
    if scheduled_points is None:
        row_notes.append("未提供預定評估時點數，定位成功率標為未提供")
        return NOT_PROVIDED, NOT_PROVIDED
    if scheduled_points == 0:
        row_notes.append("預定評估時點數為 0，定位成功率不適用")
        return 0, NOT_APPLICABLE
    if valid_samples > scheduled_points:
        row_notes.append(
            f"異常：有效樣本數（{valid_samples}）大於預定評估時點數（{scheduled_points}），請確認分母定義或是否重複計分"
        )
        return scheduled_points, NOT_APPLICABLE
    return scheduled_points, float(valid_samples) / float(scheduled_points)


def _extract_error_metrics(
    device_stats: dict[str, Any],
    valid_samples: int,
    row_notes: list[str],
) -> dict[str, float | str]:
    metric_keys = ("mae_m", "rmse_m", "p50_m", "p95_m")
    if valid_samples == 0:
        if any(device_stats.get(k) is not None for k in metric_keys):
            row_notes.append("樣本數為 0，誤差指標標為不適用（不以 0 冒充誤差）")
        return {k: NOT_APPLICABLE for k in metric_keys}

    out: dict[str, float | str] = {}
    missing_metrics: list[str] = []
    for key in metric_keys:
        raw = device_stats.get(key)
        if raw is None or _is_missing_text(raw):
            out[key] = NOT_PROVIDED
            missing_metrics.append(key)
        else:
            out[key] = _parse_nonneg_float(raw, key)
    if missing_metrics:
        row_notes.append(f"部分誤差指標缺值（{', '.join(missing_metrics)}）")
    return out


def _join_unique(parts: list[str]) -> str:
    cleaned = [p.strip() for p in parts if isinstance(p, str) and p.strip()]
    if not cleaned:
        return NOT_PROVIDED
    return "；".join(dict.fromkeys(cleaned))


def summarize_experiment(
    entry: dict[str, Any],
    base_dir: Path | None = None,
) -> tuple[list[dict[str, Any]], list[str], bool]:
    """Summarize one experiment metadata entry into normalized comparison rows.

    Returns ``(rows, run_warnings, run_has_mixed_source)``.
    """
    if not isinstance(entry, dict):
        raise ValueError("Each experiment entry must be an object")

    run_warnings: list[str] = []
    run_notes: list[str] = []
    run_has_mixed_source = False

    experiment_id = _clean_optional_str(entry.get("experiment_id")) or NOT_PROVIDED
    meta_source = _parse_source(entry.get("source"))
    site = _clean_optional_str(entry.get("site")) or NOT_PROVIDED
    route = _clean_optional_str(entry.get("route")) or NOT_PROVIDED
    version = _clean_optional_str(entry.get("version"))
    meta_run_id = _clean_optional_str(entry.get("run_id"))
    user_missing_reason = _clean_optional_str(entry.get("missing_reason")) or ""
    user_limitations = _clean_optional_str(entry.get("limitations"))
    if user_limitations:
        run_notes.append(user_limitations)

    if version is None:
        version_out = NOT_PROVIDED
        run_warnings.append(f"[{experiment_id}] 缺少程式版本／commit SHA，無法完整追溯")
        run_notes.append("缺少程式版本／commit SHA")
    else:
        version_out = version

    eval_path_raw = _clean_optional_str(entry.get("evaluation_path") or entry.get("evaluation_file"))
    states_path_raw = _clean_optional_str(entry.get("states_path") or entry.get("states_file"))
    truth_path_raw = _clean_optional_str(entry.get("truth_path") or entry.get("truth_file"))

    states: list[dict[str, Any]] | None = None
    if entry.get("states") is not None:
        states = list(entry["states"])
    elif states_path_raw is not None:
        states = load_states(_resolve_path(states_path_raw, base_dir))

    state_facts = inspect_states(states) if states is not None else None
    if state_facts is not None:
        run_ids = state_facts["run_ids"]
        if len(run_ids) > 1:
            raise ValueError("Multiple run_id values: split states into one experiment per run_id")
        if meta_run_id is not None and run_ids and run_ids[0] != meta_run_id:
            raise ValueError("Metadata run_id does not match state run_id")

    truth: list[dict[str, Any]] | None = None
    if entry.get("truth") is not None:
        truth = list(entry["truth"])
    elif truth_path_raw is not None:
        truth = load_truth(_resolve_path(truth_path_raw, base_dir))

    evaluation: dict[str, Any] | None = None
    if entry.get("evaluation") is not None:
        evaluation = entry["evaluation"]
        if not isinstance(evaluation, dict):
            raise ValueError("Inline evaluation must be an object")
    elif eval_path_raw is not None:
        evaluation = json.loads(_resolve_path(eval_path_raw, base_dir).read_text(encoding="utf-8"))
        if not isinstance(evaluation, dict):
            raise ValueError(f"Evaluation JSON in {eval_path_raw} must be an object")
    elif states is not None and truth is not None:
        max_delta = _parse_nonneg_float(entry.get("max_time_delta_s", 0.25), "max_time_delta_s")
        evaluation = evaluate_states_against_truth(states, truth, max_time_delta_s=max_delta)

    # Check truth_used_by_solver strictly.
    meta_truth_flag = _parse_bool_optional(entry.get("truth_used_by_solver"), "truth_used_by_solver")
    if meta_truth_flag is True:
        raise ValueError("truth_used_by_solver must be False; ground truth must never enter the solver")

    if evaluation is not None:
        eval_truth_flag = evaluation.get("truth_used_by_solver")
        if eval_truth_flag is True:
            raise ValueError("Evaluation reports truth_used_by_solver=True; ground truth must never enter the solver")
        if eval_truth_flag is False:
            truth_flag: bool | str = False
        elif eval_truth_flag is None:
            truth_flag = NOT_PROVIDED
            msg = "評估檔缺少 truth_used_by_solver 標記，請確認真值未進入求解器"
            run_warnings.append(f"[{experiment_id}] {msg}")
            run_notes.append(msg)
        else:
            raise ValueError(f"Invalid truth_used_by_solver value in evaluation: {eval_truth_flag!r}")
    else:
        truth_flag = False if meta_truth_flag is False else NOT_PROVIDED

    # Run ID resolution and cross-check.
    if state_facts is not None and len(state_facts["run_ids"]) > 1:
        msg = f"狀態檔包含多個 run_id（{', '.join(state_facts['run_ids'])}），可能混入不同任務"
        run_warnings.append(f"[{experiment_id}] {msg}")
        run_notes.append(msg)

    if meta_run_id is not None:
        run_id_out = meta_run_id
        if state_facts is not None and len(state_facts["run_ids"]) == 1 and state_facts["run_ids"][0] != meta_run_id:
            msg = f"run_id 不一致：metadata 為 {meta_run_id}，狀態檔為 {state_facts['run_ids'][0]}"
            run_warnings.append(f"[{experiment_id}] {msg}")
            run_notes.append(msg)
    elif state_facts is not None and len(state_facts["run_ids"]) == 1:
        run_id_out = state_facts["run_ids"][0]
    else:
        run_id_out = NOT_PROVIDED
        msg = "缺少 run_id，無法追溯原始紀錄目錄"
        run_warnings.append(f"[{experiment_id}] {msg}")
        run_notes.append(msg)

    # Source validation and mixed-source detection.
    eval_sources_raw = evaluation.get("sources") if evaluation is not None else None
    eval_sources: list[str] = []
    if isinstance(eval_sources_raw, list):
        eval_sources = sorted({str(s).strip().lower() for s in eval_sources_raw if str(s).strip()})

    state_sources = [s.lower() for s in state_facts["sources"]] if state_facts is not None else []
    source_out = meta_source if meta_source is not None else NOT_PROVIDED
    source_status = "ok" if meta_source is not None else "unspecified"

    if meta_source is None:
        msg = "metadata 未提供資料來源（synthetic／gazebo／physical）"
        run_warnings.append(f"[{experiment_id}] {msg}")
        run_notes.append(msg)
    elif meta_source == "simulation":
        run_notes.append("來源僅標註 simulation，建議明確區分 synthetic 或 gazebo")

    if len(eval_sources) > 1:
        source_status = "mixed"
        run_has_mixed_source = True
        msg = f"評估檔包含混合來源（{', '.join(eval_sources)}），不可視為單一來源結果"
        run_warnings.append(f"[{experiment_id}] {msg}")
        run_notes.append(msg)
    elif len(eval_sources) == 1 and meta_source is not None:
        if eval_sources[0] not in SOURCE_COMPATIBILITY[meta_source]:
            source_status = "conflict"
            run_has_mixed_source = True
            msg = f"來源衝突：metadata 標示 {meta_source}，但評估檔來源為 {eval_sources[0]}"
            run_warnings.append(f"[{experiment_id}] {msg}")
            run_notes.append(msg)

    if len(state_sources) > 1:
        source_status = "mixed"
        run_has_mixed_source = True
        msg = f"狀態檔包含混合來源（{', '.join(state_sources)}）"
        run_warnings.append(f"[{experiment_id}] {msg}")
        run_notes.append(msg)
    elif len(state_sources) == 1 and meta_source is not None:
        if state_sources[0] not in SOURCE_COMPATIBILITY[meta_source]:
            if source_status != "mixed":
                source_status = "conflict"
            run_has_mixed_source = True
            msg = f"來源衝突：metadata 標示 {meta_source}，但狀態檔來源為 {state_sources[0]}"
            run_warnings.append(f"[{experiment_id}] {msg}")
            run_notes.append(msg)

    # Inventory sets (G_R and S_R).
    expected_targets = _parse_target_set(entry.get("expected_targets"), "expected_targets")
    meta_inventoried = _parse_target_set(entry.get("inventoried_targets"), "inventoried_targets")
    if meta_inventoried is not None:
        inventoried_targets: list[str] | None = meta_inventoried
        if state_facts is not None and set(meta_inventoried) != set(state_facts["inventoried_targets"]):
            msg = (
                f"metadata 已盤點集合（{','.join(meta_inventoried) or '[]'}）"
                f"與狀態檔紀錄（{','.join(state_facts['inventoried_targets']) or '[]'}）不一致"
            )
            run_warnings.append(f"[{experiment_id}] {msg}")
            run_notes.append(msg)
    elif state_facts is not None:
        inventoried_targets = state_facts["inventoried_targets"]
    else:
        inventoried_targets = None

    expected_str, inventoried_str, inventory_recall = _compute_inventory_recall(
        expected_targets, inventoried_targets, run_notes
    )

    # Measured end-to-end latency (never inferred from publish_interval_s).
    latency_measured = _parse_bool_optional(entry.get("latency_measured"), "latency_measured")
    raw_latency = entry.get("end_to_end_latency_ms")
    if raw_latency is None:
        raw_latency = entry.get("measured_latency_ms")
    if latency_measured is False:
        latency_out: float | str = NOT_PROVIDED
        run_notes.append("端到端延遲未實測，標為未提供（不以更新間隔 1 s 取代）")
    elif _is_missing_text(raw_latency):
        latency_out = NOT_PROVIDED
    else:
        latency_out = _parse_nonneg_float(raw_latency, "end_to_end_latency_ms")

    # Scheduled evaluation points (int or per-device dict).
    scheduled_spec = _parse_scheduled_eval_points(entry.get("scheduled_eval_points"))

    def scheduled_for(dev_id: str) -> int | None:
        if scheduled_spec is None:
            return None
        if isinstance(scheduled_spec, int):
            return scheduled_spec
        return scheduled_spec.get(dev_id)

    explicit_roles = entry.get("device_roles") if isinstance(entry.get("device_roles"), dict) else {}
    scanner_id = _clean_optional_str(entry.get("scanner_id"))
    expected_set = set(expected_targets or [])
    inventoried_set = set(inventoried_targets or [])

    def role_for(dev_id: str) -> str:
        if dev_id in explicit_roles and _clean_optional_str(explicit_roles[dev_id]):
            return str(explicit_roles[dev_id]).strip()
        if state_facts is not None and dev_id in state_facts["device_roles"]:
            return state_facts["device_roles"][dev_id]
        if scanner_id is not None and dev_id == scanner_id:
            return "scanner"
        if dev_id in expected_set or dev_id in inventoried_set:
            return "target"
        return NOT_PROVIDED

    eval_file_out = eval_path_raw or NOT_PROVIDED
    states_file_out = states_path_raw or NOT_PROVIDED

    # Pending / unexecuted experiment (no evaluation data).
    if evaluation is None:
        pending_devices = _parse_target_set(entry.get("devices"), "devices")
        device_id_out = pending_devices[0] if pending_devices and len(pending_devices) == 1 else NOT_PROVIDED
        row_notes = list(run_notes)
        sched_val = scheduled_spec if isinstance(scheduled_spec, int) else (
            scheduled_spec.get(device_id_out) if isinstance(scheduled_spec, dict) else None
        )
        sched_out, success_rate = _compute_success_rate(NOT_PROVIDED, sched_val, row_notes)
        missing_reason_out = user_missing_reason or "尚未提供評估檔"
        row = {
            "experiment_id": experiment_id,
            "source": source_out,
            "source_status": source_status,
            "site": site,
            "route": route,
            "version": version_out,
            "run_id": run_id_out,
            "device_id": device_id_out,
            "device_role": role_for(device_id_out) if device_id_out != NOT_PROVIDED else NOT_PROVIDED,
            "valid_samples": NOT_PROVIDED,
            "scheduled_eval_points": sched_out,
            "localization_success_rate": success_rate,
            "mae_m": NOT_PROVIDED,
            "rmse_m": NOT_PROVIDED,
            "p50_m": NOT_PROVIDED,
            "p95_m": NOT_PROVIDED,
            "expected_targets": expected_str,
            "inventoried_targets": inventoried_str,
            "inventory_recall": inventory_recall,
            "end_to_end_latency_ms": latency_out,
            "skipped_unmatched": NOT_PROVIDED,
            "truth_used_by_solver": truth_flag,
            "evaluation_file": eval_file_out,
            "states_file": states_file_out,
            "missing_reason": missing_reason_out,
            "limitations": _join_unique(row_notes),
        }
        return [row], run_warnings, run_has_mixed_source

    # Evaluated experiment.
    eval_devices = evaluation.get("devices")
    if eval_devices is None:
        eval_devices = {}
    if not isinstance(eval_devices, dict):
        raise ValueError("evaluation.devices must be an object")

    raw_skipped = evaluation.get("skipped_unmatched")
    skipped_unmatched: int | str = (
        NOT_PROVIDED if _is_missing_text(raw_skipped) else _parse_nonneg_int(raw_skipped, "skipped_unmatched")
    )

    device_order: list[str] = list(eval_devices.keys())
    explicit_devices = entry.get("devices")
    if isinstance(explicit_devices, (list, tuple)):
        for d in explicit_devices:
            d_clean = _clean_optional_str(d)
            if d_clean and d_clean not in device_order:
                device_order.append(d_clean)
    if isinstance(scheduled_spec, dict):
        for d in scheduled_spec.keys():
            if d not in device_order:
                device_order.append(d)

    if not device_order:
        row_notes = list(run_notes)
        row_notes.append("本次評估無任何有效定位解（valid_samples=0）")
        sched_val = scheduled_spec if isinstance(scheduled_spec, int) else None
        sched_out, success_rate = _compute_success_rate(0, sched_val, row_notes)
        row = {
            "experiment_id": experiment_id,
            "source": source_out,
            "source_status": source_status,
            "site": site,
            "route": route,
            "version": version_out,
            "run_id": run_id_out,
            "device_id": "無有效解",
            "device_role": NOT_PROVIDED,
            "valid_samples": 0,
            "scheduled_eval_points": sched_out,
            "localization_success_rate": success_rate,
            "mae_m": NOT_APPLICABLE,
            "rmse_m": NOT_APPLICABLE,
            "p50_m": NOT_APPLICABLE,
            "p95_m": NOT_APPLICABLE,
            "expected_targets": expected_str,
            "inventoried_targets": inventoried_str,
            "inventory_recall": inventory_recall,
            "end_to_end_latency_ms": latency_out,
            "skipped_unmatched": skipped_unmatched,
            "truth_used_by_solver": truth_flag,
            "evaluation_file": eval_file_out,
            "states_file": states_file_out,
            "missing_reason": user_missing_reason,
            "limitations": _join_unique(row_notes),
        }
        return [row], run_warnings, run_has_mixed_source

    rows: list[dict[str, Any]] = []
    for dev_id in device_order:
        row_notes = list(run_notes)
        stats = eval_devices.get(dev_id)
        if stats is None:
            valid_samples = 0
            metrics = {k: NOT_APPLICABLE for k in ("mae_m", "rmse_m", "p50_m", "p95_m")}
            row_notes.append("此設備無有效定位樣本（valid_samples=0），誤差指標不適用")
        else:
            if not isinstance(stats, dict):
                raise ValueError(f"evaluation.devices[{dev_id!r}] must be an object")
            if stats.get("samples") is None:
                raise ValueError(f"evaluation.devices[{dev_id!r}] missing 'samples'")
            valid_samples = _parse_nonneg_int(stats["samples"], f"devices[{dev_id}].samples")
            metrics = _extract_error_metrics(stats, valid_samples, row_notes)

        if state_facts is not None:
            unique_in_states = state_facts["unique_valid_position_counts"].get(dev_id, 0)
            if valid_samples > unique_in_states:
                msg = (
                    f"警告：{dev_id} 評估樣本數（{valid_samples}）大於狀態檔去重後有效位置數（{unique_in_states}），"
                    "可能存在重複計分舊位置"
                )
                run_warnings.append(f"[{experiment_id}] {msg}")
                row_notes.append(msg)

        sched_out, success_rate = _compute_success_rate(valid_samples, scheduled_for(dev_id), row_notes)
        rows.append(
            {
                "experiment_id": experiment_id,
                "source": source_out,
                "source_status": source_status,
                "site": site,
                "route": route,
                "version": version_out,
                "run_id": run_id_out,
                "device_id": dev_id,
                "device_role": role_for(dev_id),
                "valid_samples": valid_samples,
                "scheduled_eval_points": sched_out,
                "localization_success_rate": success_rate,
                "mae_m": metrics["mae_m"],
                "rmse_m": metrics["rmse_m"],
                "p50_m": metrics["p50_m"],
                "p95_m": metrics["p95_m"],
                "expected_targets": expected_str,
                "inventoried_targets": inventoried_str,
                "inventory_recall": inventory_recall,
                "end_to_end_latency_ms": latency_out,
                "skipped_unmatched": skipped_unmatched,
                "truth_used_by_solver": truth_flag,
                "evaluation_file": eval_file_out,
                "states_file": states_file_out,
                "missing_reason": user_missing_reason,
                "limitations": _join_unique(row_notes),
            }
        )

    return rows, run_warnings, run_has_mixed_source


def summarize_experiments(
    entries: list[dict[str, Any]],
    base_dir: Path | None = None,
) -> dict[str, Any]:
    """Summarize multiple experiments and compute cross-run comparison flags."""
    if not isinstance(entries, list):
        raise ValueError("entries must be a list of experiment metadata objects")

    all_rows: list[dict[str, Any]] = []
    warnings: list[str] = []
    any_run_mixed = False

    for entry in entries:
        rows, run_warnings, run_mixed = summarize_experiment(entry, base_dir=base_dir)
        all_rows.extend(rows)
        warnings.extend(run_warnings)
        any_run_mixed = any_run_mixed or run_mixed

    distinct_sources = sorted({row["source"] for row in all_rows if row["source"] != NOT_PROVIDED})
    distinct_versions = sorted({row["version"] for row in all_rows if row["version"] != NOT_PROVIDED})
    distinct_run_ids = sorted({row["run_id"] for row in all_rows if row["run_id"] != NOT_PROVIDED})

    has_mixed_sources = any_run_mixed or len(distinct_sources) > 1
    has_multiple_versions = len(distinct_versions) > 1

    top_warnings: list[str] = []
    if has_mixed_sources:
        label = ", ".join(distinct_sources) if distinct_sources else "多來源／來源衝突"
        top_warnings.append(
            f"彙整結果包含混合來源（{label}），合成／Gazebo／實體數據須分開解讀，不得合併平均或冒充實機精度。"
        )
    if has_multiple_versions:
        top_warnings.append(
            f"彙整結果包含多個程式版本（{', '.join(distinct_versions)}），跨版本比較應確認設定與演算法差異。"
        )
    top_warnings.extend(warnings)

    return {
        "schema_version": SCHEMA_VERSION,
        "truth_used_by_solver": (
            False if all_rows and all(row["truth_used_by_solver"] is False for row in all_rows)
            else NOT_PROVIDED
        ),
        "comparison_flags": {
            "distinct_sources": distinct_sources,
            "has_mixed_sources": has_mixed_sources,
            "distinct_versions": distinct_versions,
            "has_multiple_versions": has_multiple_versions,
            "distinct_run_ids": distinct_run_ids,
        },
        "warnings": list(dict.fromkeys(top_warnings)),
        "rows": all_rows,
    }


def load_manifest(path: Path) -> list[dict[str, Any]]:
    """Load an experiment manifest from JSON or CSV."""
    suffix = path.suffix.lower()
    if suffix == ".json":
        payload = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(payload, dict) and isinstance(payload.get("experiments"), list):
            return payload["experiments"]
        if isinstance(payload, list):
            return payload
        raise ValueError(f"Manifest JSON in {path} must be a list or contain an 'experiments' list")
    if suffix == ".csv":
        entries: list[dict[str, Any]] = []
        with path.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if not reader.fieldnames:
                raise ValueError(f"Empty CSV manifest: {path}")
            for row in reader:
                if not any((v or "").strip() for v in row.values()):
                    continue
                entry: dict[str, Any] = {
                    "experiment_id": row.get("experiment_id"),
                    "source": row.get("source"),
                    "site": row.get("site"),
                    "route": row.get("route"),
                    "version": row.get("version"),
                    "run_id": row.get("run_id"),
                    "scheduled_eval_points": row.get("scheduled_eval_points"),
                    "expected_targets": row.get("expected_targets"),
                    "inventoried_targets": row.get("inventoried_targets"),
                    "end_to_end_latency_ms": row.get("end_to_end_latency_ms"),
                    "latency_measured": row.get("latency_measured"),
                    "truth_used_by_solver": row.get("truth_used_by_solver"),
                    "evaluation_path": row.get("evaluation_file") or row.get("evaluation_path"),
                    "states_path": row.get("states_file") or row.get("states_path"),
                    "truth_path": row.get("truth_file") or row.get("truth_path"),
                    "missing_reason": row.get("missing_reason"),
                    "limitations": row.get("limitations"),
                }
                dev_id = _clean_optional_str(row.get("device_id"))
                if dev_id is not None:
                    entry["devices"] = [dev_id]
                entries.append(entry)
        return entries
    raise ValueError(f"Unsupported manifest format: {path.suffix} (expected .json or .csv)")


def _csv_guard(text: str) -> str:
    if not text:
        return text
    if text[0] in ("=", "+", "@", "\t", "\r"):
        return "'" + text
    if text[0] == "-":
        try:
            float(text)
        except ValueError:
            return "'" + text
    return text


def _format_cell(column: str, value: Any, *, csv_safe: bool = False) -> str:
    if value is None:
        return ""
    if value in (NOT_PROVIDED, NOT_APPLICABLE):
        return str(value)
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if column in ("localization_success_rate", "inventory_recall"):
            return f"{value:.4f}"
        if column in ("mae_m", "rmse_m", "p50_m", "p95_m"):
            return f"{value:.3f}"
        if column == "end_to_end_latency_ms":
            return f"{value:.2f}"
        return f"{value:.6g}"
    text = str(value)
    return _csv_guard(text) if csv_safe else text


def render_csv(summary: dict[str, Any]) -> str:
    """Render summary rows as UTF-8 CSV using ``CSV_COLUMNS`` with formula protection."""
    buf = io.StringIO(newline="")
    writer = csv.DictWriter(buf, fieldnames=CSV_COLUMNS, lineterminator="\n")
    writer.writeheader()
    for row in summary["rows"]:
        writer.writerow({col: _format_cell(col, row.get(col), csv_safe=True) for col in CSV_COLUMNS})
    return buf.getvalue()


def _md_escape(text: str) -> str:
    return text.replace("|", "\\|").replace("\r\n", " ").replace("\n", " ")


def render_markdown(summary: dict[str, Any]) -> str:
    """Render summary as a comparable GitHub-flavored Markdown report section."""
    flags = summary["comparison_flags"]
    lines: list[str] = [
        "# 實驗彙整比較表",
        "",
        f"- 彙整列數：{len(summary['rows'])}",
        f"- 資料來源：{', '.join(flags['distinct_sources']) if flags['distinct_sources'] else NOT_PROVIDED}"
        + ("（**混合來源**）" if flags["has_mixed_sources"] else ""),
        f"- 程式版本：{', '.join(flags['distinct_versions']) if flags['distinct_versions'] else NOT_PROVIDED}"
        + ("（**多版本比較**）" if flags["has_multiple_versions"] else ""),
        ("- 真值分離：各輸入宣告 `truth_used_by_solver = false`（彙整器未獨立驗證求解器資料流）"
         if summary["truth_used_by_solver"] is False else "- 真值分離：未提供完整標記，無法確認所有輸入"),
        "",
    ]
    if summary["warnings"]:
        lines.append("## 警示與比較前提")
        lines.append("")
        for warn in summary["warnings"]:
            lines.append(f"- {warn}")
        lines.append("")

    headers = [
        ("experiment_id", "實驗編號"),
        ("source", "來源"),
        ("source_status", "來源檢核"),
        ("site", "場地"),
        ("route", "路徑"),
        ("version", "版本"),
        ("run_id", "run_id"),
        ("device_id", "設備"),
        ("valid_samples", "有效樣本"),
        ("scheduled_eval_points", "預定時點"),
        ("localization_success_rate", "定位成功率"),
        ("mae_m", "MAE (m)"),
        ("rmse_m", "RMSE (m)"),
        ("p50_m", "P50 (m)"),
        ("p95_m", "P95 (m)"),
        ("inventory_recall", "盤點召回率"),
        ("end_to_end_latency_ms", "實測延遲 (ms)"),
        ("missing_reason", "缺測原因"),
        ("limitations", "限制"),
    ]
    lines.append("| " + " | ".join(title for _, title in headers) + " |")
    lines.append("| " + " | ".join("---" for _ in headers) + " |")
    for row in summary["rows"]:
        cells = [_md_escape(_format_cell(col, row.get(col), csv_safe=False)) for col, _ in headers]
        lines.append("| " + " | ".join(cells) + " |")
    lines.append("")
    return "\n".join(lines)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Summarize BLE evaluation JSON and explicit experiment metadata into comparable tables."
    )
    parser.add_argument("--manifest", type=Path, help="JSON or CSV manifest listing one or more experiments")
    parser.add_argument("--evaluation", type=Path, help="Single-run evaluation JSON from scripts/evaluate-run.py")
    parser.add_argument("--states", type=Path, help="Optional single-run replay JSON or states.jsonl")
    parser.add_argument("--truth", type=Path, help="Optional separate offline truth JSONL (used if --evaluation omitted)")
    parser.add_argument("--experiment-id", help="Experiment ID label for single-run mode")
    parser.add_argument("--source", choices=ALLOWED_METADATA_SOURCES, help="Explicit data source")
    parser.add_argument("--site", help="Site ID or description")
    parser.add_argument("--route", help="Route or scenario description")
    parser.add_argument("--version", help="Code version or Git commit SHA")
    parser.add_argument("--run-id", help="Run ID matching data/raw/<run_id>")
    parser.add_argument(
        "--scheduled-eval-points",
        help="Scheduled evaluation count (int, JSON map, or dev=count;dev=count)",
    )
    parser.add_argument("--expected-targets", help="Expected target set G_R (semicolon-separated or EMPTY)")
    parser.add_argument("--inventoried-targets", help="Inventoried target set S_R (semicolon-separated or EMPTY)")
    parser.add_argument("--latency-ms", help="Explicitly measured end-to-end latency in ms (omit if unmeasured)")
    parser.add_argument("--devices", help="Optional semicolon-separated device IDs to include even at 0 samples")
    parser.add_argument("--scanner-id", help="Scanner device ID")
    parser.add_argument("--missing-reason", help="Reason for missing/pending measurements")
    parser.add_argument("--limitations", help="Experiment limitations and caveats")
    parser.add_argument("--max-time-delta-s", type=float, default=0.25, help="Max alignment delta for offline truth eval")
    parser.add_argument("--csv-out", type=Path, help="Write CSV table to this path")
    parser.add_argument("--md-out", type=Path, help="Write Markdown table to this path")
    parser.add_argument("--json-out", type=Path, help="Write structured JSON summary to this path")
    parser.add_argument(
        "--format",
        choices=("markdown", "csv", "json"),
        default="markdown",
        help="Format printed to stdout (default: markdown)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.manifest is not None:
        entries = load_manifest(args.manifest)
        base_dir = args.manifest.resolve().parent
    elif any(
        getattr(args, attr) is not None
        for attr in ("evaluation", "states", "experiment_id", "source", "run_id")
    ):
        entry: dict[str, Any] = {
            "experiment_id": args.experiment_id,
            "source": args.source,
            "site": args.site,
            "route": args.route,
            "version": args.version,
            "run_id": args.run_id,
            "evaluation_path": str(args.evaluation) if args.evaluation is not None else None,
            "states_path": str(args.states) if args.states is not None else None,
            "truth_path": str(args.truth) if args.truth is not None else None,
            "scheduled_eval_points": args.scheduled_eval_points,
            "expected_targets": args.expected_targets,
            "inventoried_targets": args.inventoried_targets,
            "end_to_end_latency_ms": args.latency_ms,
            "devices": _parse_target_set(args.devices, "devices") if args.devices is not None else None,
            "scanner_id": args.scanner_id,
            "missing_reason": args.missing_reason,
            "limitations": args.limitations,
            "max_time_delta_s": args.max_time_delta_s,
        }
        entries = [entry]
        base_dir = None
    else:
        parser.error("Provide --manifest or at least one single-run input (--evaluation/--states/--source/--run-id)")

    summary = summarize_experiments(entries, base_dir=base_dir)

    csv_text = render_csv(summary)
    md_text = render_markdown(summary)
    json_text = json.dumps(summary, ensure_ascii=False, indent=2)

    if args.csv_out is not None:
        args.csv_out.parent.mkdir(parents=True, exist_ok=True)
        args.csv_out.write_text(csv_text, encoding="utf-8")
    if args.md_out is not None:
        args.md_out.parent.mkdir(parents=True, exist_ok=True)
        args.md_out.write_text(md_text, encoding="utf-8")
    if args.json_out is not None:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json_text, encoding="utf-8")

    if args.format == "csv":
        print(csv_text, end="")
    elif args.format == "json":
        print(json_text)
    else:
        print(md_text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
