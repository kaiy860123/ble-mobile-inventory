"""Deploy a prepared package via existing SSH authentication; never embeds passwords."""
import argparse
from pathlib import Path
import re
import subprocess

parser=argparse.ArgumentParser()
parser.add_argument("host")
parser.add_argument("--user",required=True)
parser.add_argument("--archive",type=Path,default=Path("deliverables/ble-mobile-inventory.tar.gz"))
parser.add_argument("--install-service",action="store_true")
args=parser.parse_args()
if not re.fullmatch(r"[A-Za-z0-9.-]+",args.host) or not re.fullmatch(r"[a-z_][a-z0-9_-]*",args.user):parser.error("Invalid SSH host/user")
if not args.archive.is_file():parser.error("Build the deployment archive first")
target=f"{args.user}@{args.host}"
subprocess.run(["ssh",target,"mkdir -p ~/ble-mobile-inventory"],check=True)
subprocess.run(["scp",str(args.archive.resolve()),target+":ble-mobile-inventory/deploy.tar.gz"],check=True)
subprocess.run(["ssh",target,"cd ~/ble-mobile-inventory && tar xzf deploy.tar.gz && bash scripts/setup-rpi.sh"],check=True)
if args.install_service:subprocess.run(["ssh","-t",target,"cd ~/ble-mobile-inventory && bash scripts/install-service.sh"],check=True)
