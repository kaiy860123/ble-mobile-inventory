"""Strict observation validation: scanner truth must never enter the solver."""
import math
import re

BATCH_KEYS = {"schema_version", "timestamp", "source", "scanner_id", "sequence", "scanner_height_m", "observations"}
OBS_KEYS = {"device_id", "rssi_dbm", "rssi_at_1m_dbm"}


def validate_batch(batch):
    if not isinstance(batch, dict):
        raise ValueError("Observation batch must be an object")
    if set(batch)-BATCH_KEYS:
        raise ValueError("Unexpected batch fields; truth/positions are not localization input")
    if batch.get("schema_version") != "1.0" or batch.get("source") not in ("physical", "simulation"):
        raise ValueError("Unsupported observation schema or source")
    timestamp = batch.get("timestamp")
    if not isinstance(timestamp, (int, float)) or not math.isfinite(timestamp) or timestamp <= 0:
        raise ValueError("timestamp must be finite Unix UTC seconds")
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", batch.get("scanner_id", "")):
        raise ValueError("Invalid scanner_id")
    if not isinstance(batch.get("sequence"), int) or batch["sequence"] < 0:
        raise ValueError("sequence must be nonnegative integer")
    height = batch.get("scanner_height_m")
    if height is not None and (not isinstance(height, (int, float)) or not math.isfinite(height)):
        raise ValueError("Invalid scanner height")
    observations = batch.get("observations")
    if not isinstance(observations, list) or len(observations) > 256:
        raise ValueError("observations must be a list with at most 256 entries")
    seen = set()
    for obs in observations:
        if not isinstance(obs, dict):
            raise ValueError("Observation must be an object")
        if set(obs)-OBS_KEYS or not re.fullmatch(r"[AT][0-9]{2,3}", obs.get("device_id", "")):
            raise ValueError("Invalid observation fields or ID")
        if obs["device_id"] in seen:
            raise ValueError("Duplicate device in observation batch")
        seen.add(obs["device_id"])
        for key in ("rssi_dbm", "rssi_at_1m_dbm"):
            value = obs.get(key)
            if value is None and key != "rssi_dbm":
                continue
            if not isinstance(value, (int, float)) or not math.isfinite(value) or not -127 <= value <= 20:
                raise ValueError(f"Invalid {key}")
    return batch
