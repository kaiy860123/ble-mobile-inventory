"""Evaluate saved estimates against a separate truth file; never feeds truth to the solver."""
import argparse
import bisect
import json
import math
from pathlib import Path
import numpy as np

parser=argparse.ArgumentParser()
parser.add_argument("states",type=Path,help="Replay JSON or states.jsonl")
parser.add_argument("truth",type=Path,help="JSONL with timestamp, scanner:[x,y,z], targets:{T01:[x,y,z]}")
parser.add_argument("--max-time-delta-s",type=float,default=0.25)
parser.add_argument("--output",type=Path,default=Path("artifacts/evaluation.json"))
args=parser.parse_args()
contents=args.states.read_text(encoding="utf-8")
states=json.loads(contents)["frames"] if args.states.suffix==".json" else [json.loads(line) for line in contents.splitlines() if line]
truth=sorted([json.loads(line) for line in args.truth.read_text(encoding="utf-8").splitlines() if line],key=lambda r:r["timestamp"])
if not truth:raise SystemExit("No evaluation truth")
times=[row["timestamp"] for row in truth]
errors={};seen=set();skipped=0
for state in states:
    for device in [{**state["scanner"],"role":"scanner"},*state["devices"]]:
        if device.get("role")=="anchor" or device.get("quality")!="valid" or not device.get("position"):continue
        stamp=device.get("position_at")
        key=(state["run_id"],device["id"],stamp)
        if key in seen:continue
        seen.add(key)
        index=bisect.bisect_left(times,stamp)
        choices=[i for i in (index-1,index) if 0<=i<len(times)]
        match=min(choices,key=lambda i:abs(times[i]-stamp))
        if abs(times[match]-stamp)>args.max_time_delta_s:skipped+=1;continue
        expected=truth[match].get("scanner") if device.get("role")=="scanner" else truth[match].get("targets",{}).get(device["id"])
        if expected is None:skipped+=1;continue
        position=device["position"]
        error=math.dist((position["x_m"],position["y_m"]),expected[:2])
        errors.setdefault(device["id"],[]).append(error)
result={"schema_version":"1.0","sources":sorted({row["source"] for row in states}),"metric":"horizontal position error in meters","truth_used_by_solver":False,"skipped_unmatched":skipped,"devices":{key:{"samples":len(values),"mae_m":float(np.mean(values)),"rmse_m":float(np.sqrt(np.mean(np.square(values)))),"p50_m":float(np.percentile(values,50)),"p95_m":float(np.percentile(values,95))} for key,values in errors.items()}}
args.output.parent.mkdir(parents=True,exist_ok=True)
args.output.write_text(json.dumps(result,indent=2),encoding="utf-8")
print(json.dumps(result,indent=2))
