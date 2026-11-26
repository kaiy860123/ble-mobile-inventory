"""Fit RSSI(d)=RSSI_1m - 10*n*log10(d) from measured CSV samples."""
import argparse
import csv
import json
import math
from pathlib import Path
import numpy as np

parser=argparse.ArgumentParser()
parser.add_argument("csv",type=Path,help="Columns: device_id,distance_m,rssi_dbm")
parser.add_argument("--output",type=Path,default=Path("config/calibration.local.json"))
args=parser.parse_args()
groups={}
with args.csv.open(encoding="utf-8-sig",newline="") as handle:
    for row in csv.DictReader(handle):
        distance,rssi=float(row["distance_m"]),float(row["rssi_dbm"])
        if not all(math.isfinite(v) for v in (distance,rssi)) or distance<=0:raise ValueError("Invalid calibration sample")
        groups.setdefault(row["device_id"],[]).append((math.log10(distance),rssi))
result={}
for key,samples in groups.items():
    x=np.array([s[0] for s in samples]);y=np.array([s[1] for s in samples])
    if len(samples)<6 or np.ptp(x)<0.3:raise ValueError(f"{key}: need 6+ samples spanning at least a factor of 2 in distance")
    intercept,slope=np.linalg.lstsq(np.column_stack([np.ones(len(x)),x]),y,rcond=None)[0]
    exponent=-float(slope)/10
    if not 0.5<=exponent<=6:raise ValueError(f"{key}: fitted path-loss exponent implausible; inspect samples")
    result[key]={"rssi_at_1m_dbm":float(intercept),"path_loss_exponent":exponent,"sample_count":len(samples),"rssi_residual_db":float(np.sqrt(np.mean((y-intercept-slope*x)**2)))}
args.output.parent.mkdir(parents=True,exist_ok=True)
args.output.write_text(json.dumps(result,indent=2),encoding="utf-8")
print("Calibration saved. Review and copy each device's model parameters into its site configuration entry.")
