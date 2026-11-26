"""Stateful two-stage localization. No simulated truth is accepted here."""
from collections import deque
import copy
import math
import time
import uuid
from .config import public_config
from .contracts import validate_batch
from .coordinates import GeoReference
from .positioning import RssiFilter, rssi_to_distance, horizontal_distance, multilaterate


class InventoryEngine:
    def __init__(self, config):
        self.config = config
        self.roster = {d["id"]: d for d in config["devices"]}
        self.geo = GeoReference(**config["georeference"]) if config.get("georeference") else None
        self.start("simulation")

    def start(self, source):
        if source not in ("physical", "simulation"):
            raise ValueError("Invalid source")
        self.run_id = time.strftime("%Y%m%dT%H%M%S", time.gmtime())+"Z_"+source+"_"+uuid.uuid4().hex[:6]
        self.source = source
        self.active = True
        self.started_at = time.time()
        self.last_batch_at = None
        self.last_sequence = -1
        self.devices = {}
        self.filters = {}
        self.scanner = {"position": None, "position_at": None, "quality": "insufficient", "reason": "等待 Anchor 觀測"}
        self.target_samples = {key: deque(maxlen=240) for key, d in self.roster.items() if d["role"] == "target"}
        self.trajectory = deque(maxlen=600)
        self.seen = set()
        self.rejected_batches = 0

    def ingest(self, batch):
        validate_batch(batch)
        if not self.active:
            return False
        if batch["source"] != self.source or batch["scanner_id"] != self.config["scanner_id"]:
            raise ValueError("Observation source or scanner_id does not match active task")
        if batch["sequence"] <= self.last_sequence or (self.last_batch_at is not None and batch["timestamp"] < self.last_batch_at):
            raise ValueError("Duplicate or out-of-order observation")
        self.last_sequence = batch["sequence"]
        now = batch["timestamp"]
        self.last_batch_at = now
        current_targets = []
        for obs in batch["observations"]:
            key = obs["device_id"]
            if key not in self.roster:
                continue
            state = self.devices.setdefault(key, {"position": None, "position_at": None, "quality": "insufficient", "reason": "尚無足夠觀測"})
            # Reset temporal filter on a long gap rather than blending an old task segment.
            if key not in self.filters or now-state.get("last_seen", now) > self.config["stale_after_s"]:
                self.filters[key] = RssiFilter(self.config["filter_alpha"], self.config.get("median_window", 5))
            state.update(last_seen=now, rssi_dbm=obs["rssi_dbm"], filtered_rssi_dbm=self.filters[key].add(obs["rssi_dbm"]))
            device = self.roster[key]
            ref = next(v for v in (device.get("rssi_at_1m_dbm"), obs.get("rssi_at_1m_dbm"), self.config["rssi_at_1m_dbm"]) if v is not None)
            state["distance_m"] = rssi_to_distance(state["filtered_rssi_dbm"], ref, device.get("path_loss_exponent", self.config["path_loss_exponent"]))
            if device["role"] == "target":
                self.seen.add(key)
                current_targets.append(key)
        height = batch.get("scanner_height_m")
        if height is None:
            height = self.config["scanner_height_m"]
        points, ranges = [], []
        for key, device in self.roster.items():
            state = self.devices.get(key)
            if device["role"] != "anchor" or not state or now-state["last_seen"] > self.config["anchor_ttl_s"]:
                continue
            try:
                distance = horizontal_distance(state["distance_m"], height-device["position"][2])
            except ValueError:
                continue
            points.append(device["position"][:2])
            ranges.append(distance)
        try:
            position = multilaterate(points, ranges)
            if position["residual_m"] > self.config["max_residual_m"]:
                raise ValueError("Anchor RSSI 殘差過大")
            position["z_m"] = height
            self.scanner.update(position=self._position(position), position_at=now, quality="valid", reason="")
            self.trajectory.append({"timestamp": now, **self.scanner["position"]})
            for key in current_targets:
                state = self.devices[key]
                device = self.roster[key]
                try:
                    distance = horizontal_distance(state["distance_m"], height-device.get("height_m", height))
                except ValueError:
                    state.update(quality="insufficient", reason="RSSI 測距與高度不一致")
                    continue
                samples = self.target_samples[key]
                if not samples or math.hypot(position["x_m"]-samples[-1][1], position["y_m"]-samples[-1][2]) >= 0.15:
                    samples.append((now, position["x_m"], position["y_m"], distance))
                while samples and now-samples[0][0] > self.config["target_window_s"]:
                    samples.popleft()
                self._solve_target(key, now)
        except ValueError as error:
            self.scanner.update(quality="insufficient", reason=str(error))
            for key in current_targets:
                self.devices[key].update(quality="insufficient", reason="掃描器位置無效，暫停更新目標定位")
        return True

    def _solve_target(self, key, now):
        samples = self.target_samples[key]
        state = self.devices[key]
        if len(samples) < self.config["target_min_samples"]:
            state.update(quality="insufficient", reason=f"移動觀測不足 ({len(samples)}/{self.config['target_min_samples']})")
            return
        try:
            result = multilaterate([(s[1], s[2]) for s in samples], [s[3] for s in samples], self.config["target_min_baseline_m"])
            if result["residual_m"] > self.config["max_residual_m"]:
                raise ValueError("Target RSSI 殘差過大")
            result["z_m"] = self.roster[key].get("height_m", self.config["scanner_height_m"])
            state.update(position=self._position(result), position_at=now, quality="valid", reason="")
        except ValueError as error:
            state.update(quality="insufficient", reason=str(error))

    def _position(self, result):
        position = {**result, "frame_id": self.config["frame_id"]}
        position["wgs84"] = self.geo.to_wgs84(result["x_m"], result["y_m"], result.get("z_m", 0)) if self.geo else None
        return position

    def snapshot(self, now=None):
        now = time.time() if now is None else now
        rows = []
        visible = 0
        for key, device in self.roster.items():
            state = copy.deepcopy(self.devices.get(key, {}))
            age = now-state["last_seen"] if "last_seen" in state else None
            is_visible = age is not None and 0 <= age <= self.config["stale_after_s"]
            if device["role"] == "target" and is_visible:
                visible += 1
            if device["role"] == "anchor":
                fixed = dict(zip(("x_m", "y_m", "z_m"), device["position"]))
                state.update(position=self._position(fixed), quality="fixed", reason="已知參考點")
            elif not is_visible:
                state.update(quality="stale" if age is not None else "unseen", reason="暫未收到，保留最後有效位置" if age is not None else "本次尚未偵測")
            rows.append({"id": key, "role": device["role"], **state, "visible": is_visible, "age_s": age})
        scanner = copy.deepcopy(self.scanner)
        if self.last_batch_at is None or now-self.last_batch_at > self.config["anchor_ttl_s"]:
            scanner.update(quality="stale" if scanner["position"] else "insufficient", reason="近期無有效觀測")
        return {"schema_version": "1.0", "timestamp": now, "run_id": self.run_id, "source": self.source,
                "active": self.active, "started_at": self.started_at, "last_observation_at": self.last_batch_at,
                "counts": {"inventoried": len(self.seen), "visible": visible, "expected": len(self.target_samples)},
                "scanner": {"id": self.config["scanner_id"], **scanner}, "devices": rows,
                "trajectory": list(self.trajectory), "site": public_config(self.config)}
