"""Restricted, revisioned site edits; private deployment settings stay server-side."""
import copy
import hashlib
import json
import math
import os
from pathlib import Path
import re
import tempfile
import uuid
import numpy as np
from .config import normalize_config
from .coordinates import GeoReference

FIELDS = {"frame_id", "bounds_m", "scanner_height_m", "georeference", "configuration_status", "anchors", "targets"}


class RevisionConflict(ValueError):
    pass


def read_document(path):
    raw = Path(path).read_bytes()
    return json.loads(raw), hashlib.sha256(raw).hexdigest()


def editable_view(config):
    reference = GeoReference(**config["georeference"]) if config.get("georeference") else None
    anchors = []
    for d in config["devices"]:
        if d["role"] != "anchor":
            continue
        row = {"id": d["id"], "position": d["position"]}
        if d.get("position_wgs84"):
            row["position_wgs84"] = d["position_wgs84"]
        if reference:
            row["computed_wgs84"] = reference.to_wgs84(*d["position"])
        anchors.append(row)
    return {**{k: config.get(k) for k in FIELDS - {"anchors", "targets"}}, "anchors": anchors,
            "targets": [{"id": d["id"], "height_m": d.get("height_m", 0)} for d in config["devices"] if d["role"] == "target"]}


def number(v, limit=1e6):
    if isinstance(v, bool) or not isinstance(v, (float, int)) or not math.isfinite(v) or abs(v) > limit:
        raise ValueError("座標／高度必須為有限數值，且在允許範圍內")
    return v


def prepare_edit(original, settings):
    if not isinstance(settings, dict) or set(settings) != FIELDS:
        raise ValueError("設定欄位不完整或含未授權欄位")
    if not isinstance(settings["frame_id"], str) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,64}", settings["frame_id"]):
        raise ValueError("frame_id 限 1–64 個英數字、底線、點或連字號")
    if settings["configuration_status"] not in ("example", "measured"):
        raise ValueError("無效的量測狀態")
    bounds = settings["bounds_m"]
    if not isinstance(bounds, list) or len(bounds) != 4:
        raise ValueError("場域範圍需要四個數值")
    for v in bounds:
        number(v)
    number(settings["scanner_height_m"], 10000)
    geo = settings["georeference"]
    if geo is not None:
        if not isinstance(geo, dict) or set(geo) - {"latitude_deg", "longitude_deg", "height_m", "rotation_deg", "transform_id", "source"}:
            raise ValueError("無效的地理原點欄位")
        for k in ("latitude_deg", "longitude_deg", "height_m", "rotation_deg"):
            number(geo.get(k, 0), 10000)
        for k in ("transform_id", "source"):
            if k in geo and (not isinstance(geo[k], str) or not 1 <= len(geo[k]) <= 64):
                raise ValueError("地理原點識別欄位無效")
        GeoReference(**geo)
    candidate = copy.deepcopy(original)
    for k in FIELDS - {"anchors", "targets"}:
        candidate[k] = copy.deepcopy(settings[k])
    for field, role in (("anchors", "anchor"), ("targets", "target")):
        devices = {d["id"]: d for d in candidate["devices"] if d["role"] == role}
        rows = settings[field]
        if not isinstance(rows, list) or any(not isinstance(r, dict) for r in rows) or len(rows) != len(devices) or {r.get("id") for r in rows} != set(devices):
            raise ValueError("設備 ID／角色不可變更或重複")
        for row in rows:
            d = devices[row["id"]]
            if role == "target":
                if set(row) != {"id", "height_m"}:
                    raise ValueError("Target 僅可設定高度；平面位置由定位計算")
                d["height_m"] = number(row["height_m"], 10000)
                continue
            if set(row) == {"id", "position"}:
                xyz = row["position"]
                if not isinstance(xyz, list) or len(xyz) != 3:
                    raise ValueError("Anchor 需要 x、y、z")
                d["position"] = [number(v) for v in xyz]
                d.pop("position_wgs84", None)
            elif set(row) == {"id", "position_wgs84"} and geo:
                g = row["position_wgs84"]
                if not isinstance(g, dict) or set(g) != {"latitude_deg", "longitude_deg", "height_m"}:
                    raise ValueError("WGS84 需要緯度、經度及橢球高")
                for v in g.values():
                    number(v, 10000)
                if not -90 <= g["latitude_deg"] <= 90 or not -180 <= g["longitude_deg"] <= 180:
                    raise ValueError("WGS84 經緯度越界")
                d["position_wgs84"] = copy.deepcopy(g)
                d.pop("position", None)
            else:
                raise ValueError("Anchor 必須選擇 Local 或 WGS84；WGS84 需要地理原點")
    candidate = normalize_config(candidate)
    xy = np.array([d["position"][:2] for d in candidate["devices"] if d["role"] == "anchor"])
    if len(xy) < 3:
        raise ValueError("至少需要三個 Anchor")
    singular = np.linalg.svd(xy - xy.mean(axis=0), compute_uv=False)
    if singular[-1] < 1e-5 or singular[0] / singular[-1] > 100:
        raise ValueError("Anchor 共線或幾何條件不良")
    warnings = []
    if candidate["configuration_status"] != "measured":
        warnings.append("目前仍為示例座標，請完成場地量測後再標記為已量測")
    for d in candidate["devices"]:
        if d["role"] == "anchor" and not (bounds[0] <= d["position"][0] <= bounds[2] and bounds[1] <= d["position"][1] <= bounds[3]):
            warnings.append(f'{d["id"]} 位於顯示範圍外')
    return candidate, warnings


def persist_edit(path, candidate, revision, backup_dir):
    path = Path(path)
    _, actual = read_document(path)
    if revision != actual:
        raise RevisionConflict("設定已被其他頁面修改，請重新載入後再編輯")
    backup_dir = Path(backup_dir)
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup = backup_dir / f"{uuid.uuid4().hex}.json"
    backup.write_bytes(path.read_bytes())
    backup.chmod(0o600)
    payload = json.dumps(candidate, ensure_ascii=False, indent=2, allow_nan=False).encode("utf-8")
    fd, name = tempfile.mkstemp(prefix=".site-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(payload)
            f.flush()
            os.fsync(f.fileno())
        os.chmod(name, path.stat().st_mode)
        if read_document(path)[1] != revision:
            raise RevisionConflict("設定檔在保存前已變更")
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)
    return hashlib.sha256(payload).hexdigest()
