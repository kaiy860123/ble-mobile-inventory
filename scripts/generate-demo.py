"""Generate standalone, explicitly synthetic observation/replay fixtures (not Gazebo)."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from ble_inventory.config import load_config
from ble_inventory.engine import InventoryEngine
from ble_inventory.inputs import SyntheticSource
from ble_inventory.storage import compact_snapshot


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config/site.example.json")
    parser.add_argument("--frames", type=int, default=90)
    parser.add_argument("--output", default="web/public/demo.json")
    parser.add_argument("--georeference-example", action="store_true")
    args = parser.parse_args()
    config = load_config(args.config)
    if args.georeference_example:
        config["georeference"] = {"latitude_deg":25.01734,"longitude_deg":121.53975,"height_m":0,"rotation_deg":25,"transform_id":"fictional-demo-v1","source":"example"}
    engine = InventoryEngine(config)
    engine.run_id = "synthetic-example-5047"
    engine.started_at = 1795651200.0
    source = SyntheticSource(config)
    frames, observations, truth = [], [], []
    for i in range(args.frames):
        if i == 55:
            source.disabled.add("T02")
        if i == 75:
            source.disabled.discard("T02")
        batch, expected = source.sample(engine.started_at+i)
        engine.ingest(batch)
        frames.append({**compact_snapshot(engine.snapshot(batch["timestamp"])), "input_mode":"demo"})
        observations.append(batch)
        truth.append(expected)
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({"schema_version":"1.0","kind":"ble-inventory-replay","description":"Synthetic mathematical fixture, NOT a Gazebo/SITL or hardware validation","frames":frames},ensure_ascii=False,separators=(",",":")),encoding="utf-8")
    fixture_dir = Path("tests/fixtures")
    fixture_dir.mkdir(exist_ok=True)
    (fixture_dir / "observations.jsonl").write_text("\n".join(json.dumps(row) for row in observations)+"\n",encoding="utf-8")
    (fixture_dir / "truth.jsonl").write_text("\n".join(json.dumps(row) for row in truth)+"\n",encoding="utf-8")
    print(f"Generated {len(frames)} synthetic frames; observations and evaluation truth are separate.")


if __name__ == "__main__":
    main()
