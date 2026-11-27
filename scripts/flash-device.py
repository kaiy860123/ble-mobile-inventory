"""Build/upload exactly one identified XIAO; never guesses a serial port."""
import argparse
from pathlib import Path
import subprocess
import sys

parser=argparse.ArgumentParser()
parser.add_argument("device",choices=["A01","A02","A03","A04","T01","T02","A05","A06","T03"])
parser.add_argument("--port",required=True,help="Explicit COM port or /dev/serial/by-id/... of the connected board")
args=parser.parse_args()
root=Path(__file__).resolve().parents[1]
subprocess.run([sys.executable,"-m","platformio","run","--project-dir",str(root/"firmware"),"-e",args.device,"--target","upload","--upload-port",args.port],check=True)
