"""BLE decoding and explicit synthetic observations; neither sends XY truth to engine."""
import math
import random
import struct
import time

MANUFACTURER_ID = 0xFFFF  # Experimental prototype only, not an assigned company identifier.
PACKET = struct.Struct("<2sBBHbH")


def decode_advertisement(data):
    if len(data) != PACKET.size:
        return None
    magic, version, role, ordinal, reference_rssi, sequence = PACKET.unpack(data)
    if magic != b"BI" or version != 1 or role not in (1, 2) or not 1 <= ordinal <= 999 or not -127 <= reference_rssi <= 0:
        return None
    return {"device_id": f"{'A' if role == 1 else 'T'}{ordinal:02d}", "rssi_at_1m_dbm": reference_rssi}


class SyntheticSource:
    """Standalone mathematical test source. This is NOT Gazebo/SITL."""
    def __init__(self, config, seed=5047, noise_db=0.8):
        self.config = config
        self.random = random.Random(seed)
        self.noise_db = noise_db
        self.sequence = 0
        self.disabled = set()

    def sample(self, timestamp=None):
        now = time.time() if timestamp is None else timestamp
        xmin, ymin, xmax, ymax = self.config["bounds_m"]
        width, height = xmax-xmin, ymax-ymin
        angle = self.sequence*0.18
        scanner = (xmin+width*(0.5+0.35*math.cos(angle)), ymin+height*(0.5+0.33*math.sin(angle)), self.config["scanner_height_m"])
        targets = [d for d in self.config["devices"] if d["role"] == "target"]
        truth = {d["id"]: (xmin+width*(0.25+0.5*i/max(len(targets)-1, 1)), ymin+height*(0.35+0.3*(i%2)), d.get("height_m", scanner[2])) for i, d in enumerate(targets)}
        observations = []
        for device in self.config["devices"]:
            if device["id"] in self.disabled:
                continue
            point = device["position"] if device["role"] == "anchor" else truth[device["id"]]
            distance = max(math.dist(scanner, point), 0.2)
            reference = device.get("rssi_at_1m_dbm", self.config["rssi_at_1m_dbm"])
            rssi = reference-10*device.get("path_loss_exponent", self.config["path_loss_exponent"])*math.log10(distance)+self.random.gauss(0, self.noise_db)
            observations.append({"device_id": device["id"], "rssi_dbm": round(rssi, 3), "rssi_at_1m_dbm": reference})
        batch = {"schema_version": "1.0", "timestamp": now, "source": "simulation", "scanner_id": self.config["scanner_id"],
                 "sequence": self.sequence, "scanner_height_m": scanner[2], "observations": observations}
        self.sequence += 1
        # Returned separately, only for an evaluation file.
        return batch, {"timestamp": now, "scanner": list(scanner), "targets": truth}


class BleSource:
    def __init__(self, config):
        self.config = config
        self.pending = {}
        self.sequence = 0
        self.scanner = None

    def _callback(self, _device, advertisement):
        raw = advertisement.manufacturer_data.get(MANUFACTURER_ID)
        obs = decode_advertisement(raw) if raw else None
        if obs:
            self.pending[obs["device_id"]] = {**obs, "rssi_dbm": advertisement.rssi}

    async def start(self):
        from bleak import BleakScanner
        self.scanner = BleakScanner(detection_callback=self._callback)
        await self.scanner.start()

    async def stop(self):
        if self.scanner:
            await self.scanner.stop()

    def sample(self):
        observations = list(self.pending.values())
        self.pending.clear()
        self.sequence += 1
        return {"schema_version": "1.0", "timestamp": time.time(), "source": "physical", "scanner_id": self.config["scanner_id"],
                "sequence": self.sequence, "observations": observations}
