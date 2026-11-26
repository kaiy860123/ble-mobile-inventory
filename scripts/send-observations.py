"""Send precomputed observation JSONL to the local external-source API (not a Gazebo model)."""
import argparse
import json
import os
import time
from urllib.request import Request,urlopen
from pathlib import Path

parser=argparse.ArgumentParser()
parser.add_argument("file",type=Path)
parser.add_argument("--url",default="http://127.0.0.1:8080")
args=parser.parse_args()
token=os.environ.get("BLE_INGEST_TOKEN")
if not token:
    parser.error("Set BLE_INGEST_TOKEN in the environment; do not put it in a URL")
for index,line in enumerate(args.file.read_text(encoding="utf-8").splitlines()):
    if not line.strip():continue
    batch=json.loads(line)
    # Live API requires wall-clock UTC. Original timestamps remain in the original file.
    batch["timestamp"]=time.time();batch["sequence"]=index
    request=Request(args.url.rstrip('/')+'/api/observations',data=json.dumps(batch).encode(),headers={"Content-Type":"application/json","Authorization":"Bearer "+token},method="POST")
    with urlopen(request,timeout=10) as response:
        print(f"sequence={index} status={response.status}")
    time.sleep(1)
