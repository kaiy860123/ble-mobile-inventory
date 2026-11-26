"""Configuration validation. Example coordinates are never presented as measurements."""
import copy
import json
import math
from pathlib import Path


def load_config(path):
    config = json.loads(Path(path).read_text(encoding="utf-8"))
    if config.get("georeference"):
        from .coordinates import GeoReference
        reference = GeoReference(**config["georeference"])
        for device in config.get("devices", []):
            if device["role"] == "anchor" and device.get("position_wgs84"):
                geographic = device["position_wgs84"]
                local = reference.to_local(geographic["latitude_deg"], geographic["longitude_deg"], geographic.get("height_m"))
                derived = [local["x_m"], local["y_m"], local["z_m"] if "height_m" in geographic else device.get("height_m", config["scanner_height_m"])]
                if device.get("position") is not None and math.dist(device["position"], derived) > 0.5:
                    raise ValueError("Anchor Local/WGS84 inputs disagree by more than 0.5m")
                device["position"] = derived
    validate_config(config)
    return config


def validate_config(config):
    if config.get("schema_version") != "1.0":
        raise ValueError("Unsupported site schema_version")
    ids = []
    for device in config.get("devices", []):
        ids.append(device["id"])
        if device["role"] not in ("anchor", "target"):
            raise ValueError("Unknown device role")
        if device["role"] == "anchor":
            xyz = device.get("position", [])
            if len(xyz) != 3 or not all(math.isfinite(float(v)) for v in xyz):
                raise ValueError("Anchor needs finite x, y, z in meters")
    if len(ids) != len(set(ids)) or not ids:
        raise ValueError("Device IDs must be nonempty and unique")
    for key in ("path_loss_exponent", "anchor_ttl_s", "stale_after_s", "publish_interval_s", "target_window_s", "target_min_baseline_m", "max_residual_m"):
        if not math.isfinite(float(config[key])) or config[key] <= 0:
            raise ValueError(f"{key} must be positive")
    if not 0 < config["filter_alpha"] <= 1 or config["target_min_samples"] < 3:
        raise ValueError("Invalid filter or sample count")
    if not 1 <= config.get("median_window", 5) <= 31 or config["target_min_samples"] > 240:
        raise ValueError("Invalid filter window or target sample count")
    bounds = config["bounds_m"]
    if len(bounds) != 4 or not all(math.isfinite(float(v)) for v in bounds) or bounds[0] >= bounds[2] or bounds[1] >= bounds[3]:
        raise ValueError("bounds_m must be [xmin,ymin,xmax,ymax]")
    if config.get("georeference"):
        from .coordinates import GeoReference
        GeoReference(**config["georeference"])


def public_config(config):
    value = copy.deepcopy(config)
    # No certificate filenames, local filesystem paths or cloud connection secrets.
    value.pop("cloud", None)
    return value
