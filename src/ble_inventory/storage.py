"""Append-only, per-task raw observations, results and reproducibility metadata."""
import csv
import io
import json
from pathlib import Path
import platform
from . import __version__
from .config import public_config


def compact_snapshot(snapshot):
    # Browser/replay reconstructs a bounded trail from per-frame scanner positions.
    return {**snapshot, "trajectory": snapshot["trajectory"][-1:]}


class RunStore:
    def __init__(self, root, engine, mode):
        self.root = Path(root)
        self.raw = self.root / "data" / "raw" / engine.run_id
        self.processed = self.root / "data" / "processed" / engine.run_id
        self.raw.mkdir(parents=True, exist_ok=False)
        self.processed.mkdir(parents=True, exist_ok=False)
        self.observations = (self.raw / "observations.jsonl").open("x", encoding="utf-8")
        self.states = (self.processed / "states.jsonl").open("x", encoding="utf-8")
        manifest = {"schema_version": "1.0", "run_id": engine.run_id, "source": engine.source, "mode": mode,
                    "application_version": __version__, "python": platform.python_version(), "started_at": engine.started_at,
                    "timezone": "UTC", "site": public_config(engine.config), "truth_used_by_solver": False}
        (self.raw / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    def observation(self, value):
        self.observations.write(json.dumps(value, ensure_ascii=False, allow_nan=False)+"\n")
        self.observations.flush()

    def snapshot(self, value):
        self.states.write(json.dumps(compact_snapshot(value), ensure_ascii=False, allow_nan=False)+"\n")
        self.states.flush()

    def close(self):
        self.observations.close()
        self.states.close()

    def replay(self):
        if not self.states.closed:
            self.states.flush()
        frames = [json.loads(line) for line in (self.processed / "states.jsonl").read_text(encoding="utf-8").splitlines() if line]
        return {"schema_version": "1.0", "kind": "ble-inventory-replay", "frames": frames}

    def csv(self):
        output = io.StringIO(newline="")
        columns = ["run_id", "source", "timestamp", "device_id", "role", "visible", "quality", "last_seen", "position_at", "rssi_dbm", "x_m", "y_m", "latitude_deg", "longitude_deg", "residual_m"]
        writer = csv.DictWriter(output, fieldnames=columns)
        writer.writeheader()
        for frame in self.replay()["frames"]:
            for device in [frame["scanner"] | {"role": "scanner"}, *frame["devices"]]:
                position = device.get("position") or {}
                geo = position.get("wgs84") or {}
                writer.writerow({"run_id": frame["run_id"], "source": frame["source"], "timestamp": frame["timestamp"],
                                 "device_id": device["id"], "role": device["role"], **{k: device.get(k, "") for k in ("visible", "quality", "last_seen", "position_at", "rssi_dbm")},
                                 **{k: position.get(k, "") for k in ("x_m", "y_m", "residual_m")}, **{k: geo.get(k, "") for k in ("latitude_deg", "longitude_deg")}})
        return output.getvalue()
